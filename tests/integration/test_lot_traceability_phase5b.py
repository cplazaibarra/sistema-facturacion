"""
Integration test suite for Phase 5B: Complete Lot Genealogy & Traceability.
Validates:
- Reception with lot creation and immutable origin link
- Production consumption of exact lots (FIFO & multi-lot)
- Production output lot generation and multi-level lineage (MP -> SEMI -> FINAL)
- Sale lot consumption and link from sale to original supplier
- Forward Traceability, Backward Traceability, and Recall Impact
- Depleted lot preservation, inmutability (RESTRICT constraints), requires_lot enforcement
"""

import pytest
import psycopg2
from datetime import datetime, timezone
from core.database import get_connection
import repositories.inventory_repo as inv_repo
import repositories.lot_genealogy_repo as lot_repo
import repositories.products_repo as prod_repo
import repositories.sales_repo as sales_repo
from services.lot_traceability_service import LotTraceabilityService


@pytest.fixture
def genealogy_fixture():
    """Configura el entorno de prueba con proveedor, productos y ordenes para el escenario maestro."""
    ts = int(datetime.now(timezone.utc).timestamp() * 10000)
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Crear Proveedor de Prueba
            cur.execute(
                "INSERT INTO suppliers (name, rut, email, phone, created_at) VALUES (%s, %s, %s, %s, NOW()) RETURNING id",
                (f"Proveedor Miel Sur {ts}", f"76.{ts % 900 + 100}.{ts % 900 + 100}-3", "contacto@mielsur.cl", "+56911223344")
            )
            supplier_id = cur.fetchone()["id"]

            # 2. Crear Productos con requires_lot=True y sin lote
            cur.execute(
                """
                INSERT INTO products (sku, name, category, product_type, requires_lot, cost, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW()) RETURNING id;
                """,
                (f"MP-A-{ts}", "Materia Prima Miel Cruda", "Materia Prima", "Insumo", True, 2500.0)
            )
            mp_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO products (sku, name, category, product_type, requires_lot, cost, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW()) RETURNING id;
                """,
                (f"SEMI-A-{ts}", "Miel Filtrada Intermedia", "Semielaborado", "Insumo", True, 3000.0)
            )
            semi_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO products (sku, name, category, product_type, requires_lot, cost, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW()) RETURNING id;
                """,
                (f"FINAL-A-{ts}", "Miel Envasada 500g Premium", "Terminado", "Producto Terminado", True, 4500.0)
            )
            final_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO products (sku, name, category, product_type, requires_lot, cost, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW()) RETURNING id;
                """,
                (f"NOLOT-{ts}", "Caja Embalaje Simple", "Embalaje", "Insumo", False, 200.0)
            )
            nolot_id = cur.fetchone()["id"]

        conn.commit()

    yield {
        "supplier_id": supplier_id,
        "mp_id": mp_id,
        "semi_id": semi_id,
        "final_id": final_id,
        "nolot_id": nolot_id,
        "ts": ts,
    }

    # Teardown / Cleanup
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                pids = (mp_id, semi_id, final_id, nolot_id)
                cur.execute("DELETE FROM sale_lot_movements WHERE product_id IN %s", (pids,))
                cur.execute("DELETE FROM inventory_movements WHERE product_id IN %s", (pids,))
                cur.execute("DELETE FROM inventory_entry_items WHERE product_id IN %s", (pids,))
                cur.execute("DELETE FROM production_lot_outputs WHERE output_product_id IN %s", (pids,))
                cur.execute("DELETE FROM production_lot_consumptions WHERE input_product_id IN %s", (pids,))
                cur.execute("DELETE FROM lot_stock WHERE product_id IN %s", (pids,))
                cur.execute("DELETE FROM lots WHERE product_id IN %s", (pids,))
                cur.execute("DELETE FROM production_order_items WHERE input_product_id IN %s", (pids,))
                cur.execute("DELETE FROM production_orders WHERE final_product_id IN %s", (pids,))
                cur.execute("DELETE FROM purchase_order_items WHERE product_id IN %s", (pids,))
                cur.execute("DELETE FROM products WHERE id IN %s", (pids,))
                cur.execute("DELETE FROM suppliers WHERE id = %s", (supplier_id,))
                # Limpiar page_data
                cur.execute("SELECT json FROM page_data WHERE key = 'inventory_items'")
                row = cur.fetchone()
                if row and row.get("json"):
                    import json
                    items = json.loads(row["json"])
                    items = [it for it in items if str(ts) not in str(it.get("code", ""))]
                    cur.execute("UPDATE page_data SET json = %s WHERE key = 'inventory_items'", (json.dumps(items),))
            conn.commit()
    except Exception:
        pass


def test_requires_lot_enforced(genealogy_fixture):
    """Verifica que para products.requires_lot = True, el lote sea obligatorio en recepción."""
    mp_id = genealogy_fixture["mp_id"]
    sup_id = genealogy_fixture["supplier_id"]
    ts = genealogy_fixture["ts"]
    oc_num = f"OC-REQ-{ts}"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO purchase_orders (oc_number, supplier_id, order_date, status, total_amount, created_at) VALUES (%s, %s, '2026-09-15', 'Aprobada', 10000, NOW()) RETURNING id",
                (oc_num, sup_id)
            )
            po_id = cur.fetchone()["id"]
            cur.execute(
                "INSERT INTO purchase_order_items (purchase_order_id, product_id, quantity_ordered, quantity_received, unit_price, total_price) VALUES (%s, %s, 10, 0, 1000, 10000)",
                (po_id, mp_id)
            )
        conn.commit()

    # Intentar recibir SIN lote debe fallar con INV-011
    with pytest.raises(ValueError, match="INV-011"):
        inv_repo.register_inventory_entry(
            po_id=po_id,
            order_number=oc_num,
            entry_date="2026-09-15",
            warehouse="Principal",
            notes="Intento sin lote",
            items=[{"product_id": mp_id, "quantity": 10, "unit_price": 1000, "lot_number": ""}]
        )


def test_non_lot_product_still_supported(genealogy_fixture):
    """Verifica que productos con requires_lot = FALSE sigan funcionando sin requerir lote."""
    nolot_id = genealogy_fixture["nolot_id"]
    sup_id = genealogy_fixture["supplier_id"]
    ts = genealogy_fixture["ts"]
    oc_num = f"OC-NOLOT-{ts}"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO purchase_orders (oc_number, supplier_id, order_date, status, total_amount, created_at) VALUES (%s, %s, '2026-09-15', 'Aprobada', 2000, NOW()) RETURNING id",
                (oc_num, sup_id)
            )
            po_id = cur.fetchone()["id"]
            cur.execute(
                "INSERT INTO purchase_order_items (purchase_order_id, product_id, quantity_ordered, quantity_received, unit_price, total_price) VALUES (%s, %s, 10, 0, 200, 2000)",
                (po_id, nolot_id)
            )
        conn.commit()

    # Recepción sin lote para producto regular debe funcionar sin error
    entry_id = inv_repo.register_inventory_entry(
        po_id=po_id,
        order_number=oc_num,
        entry_date="2026-09-15",
        warehouse="Principal",
        notes="Recepción producto sin lote",
        items=[{"product_id": nolot_id, "quantity": 10, "unit_price": 200, "lot_number": ""}]
    )
    assert entry_id > 0


def test_master_traceability_lifecycle_and_recall(genealogy_fixture):
    """
    Escenario Maestro Completo (Pasos 29-35):
    Proveedor -> OC-TEST -> MP-A (Lote MP-001, 100 un)
    OT-TEST-001 consume MP-001 (40 un) -> Produce SEMI-A (Lote SEMI-001, 40 un)
    OT-TEST-002 consume SEMI-001 (20 un) -> Produce FINAL-A (Lote FINAL-001, 20 un)
    Venta 1 consume FINAL-001 (8 un, Cliente X)
    Venta 2 consume FINAL-001 (12 un, Cliente Y)
    Valida: Forward Trace, Backward Trace, Venta->Origen, y Recall de MP-001!
    """
    mp_id = genealogy_fixture["mp_id"]
    semi_id = genealogy_fixture["semi_id"]
    final_id = genealogy_fixture["final_id"]
    sup_id = genealogy_fixture["supplier_id"]
    ts = genealogy_fixture["ts"]
    oc_num = f"OC-M-{ts}"
    ot1_num = f"OT1-{ts}"
    ot2_num = f"OT2-{ts}"
    vta1_num = f"V1-{ts}"
    vta2_num = f"V2-{ts}"

    # 1. RECEPCIÓN DE MATERIA PRIMA (100 un, Lote MP-001)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO purchase_orders (oc_number, supplier_id, order_date, status, total_amount, created_at) VALUES (%s, %s, '2026-09-15', 'Aprobada', 250000, NOW()) RETURNING id",
                (oc_num, sup_id)
            )
            po_id = cur.fetchone()["id"]
            cur.execute(
                "INSERT INTO purchase_order_items (purchase_order_id, product_id, quantity_ordered, quantity_received, unit_price, total_price) VALUES (%s, %s, 100, 0, 2500, 250000)",
                (po_id, mp_id)
            )
        conn.commit()

    entry_id = inv_repo.register_inventory_entry(
        po_id=po_id,
        order_number=oc_num,
        entry_date="2026-09-15",
        warehouse="Principal",
        notes="Recepción Inicial Materia Prima",
        items=[{"product_id": mp_id, "quantity": 100, "unit_price": 2500, "lot_number": "MP-001"}]
    )

    mp_lot = lot_repo.get_lot_by_product_and_number(mp_id, "MP-001")
    assert mp_lot is not None
    assert mp_lot["origin_type"] == "PURCHASE"
    assert mp_lot["supplier_id"] == sup_id
    assert mp_lot["purchase_order_id"] == po_id
    mp_lot_id = mp_lot["id"]

    # 2. PRODUCCIÓN NIVEL 1: OT-TEST-001 (Consume 40 un de MP-001 -> Produce 40 un de SEMI-001)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO production_orders (ot_number, final_product_id, quantity, status, created_at) VALUES (%s, %s, 40, 'Finalizada', NOW()) RETURNING id",
                (ot1_num, semi_id)
            )
            ot1_id = cur.fetchone()["id"]

            # Consumo exacto de MP-001
            cur.execute(
                "UPDATE lot_stock SET available_qty = available_qty - 40 WHERE id = (SELECT id FROM lot_stock WHERE product_id = %s AND lot_number = 'MP-001')",
                (mp_id,)
            )
            lot_repo.record_production_consumption(ot1_id, mp_id, mp_lot_id, 40.0, conn=conn)

            # Generar lote de salida SEMI-001
            semi_lot_id = lot_repo.create_lot(
                product_id=semi_id,
                lot_number="SEMI-001",
                lot_type="SEMI_FINISHED",
                origin_type="PRODUCTION",
                origin_id=ot1_id,
                production_order_id=ot1_id,
                initial_quantity=40.0,
                warehouse="Principal",
                notes=f"Generado por {ot1_num}",
                conn=conn
            )
            lot_repo.record_production_output(ot1_id, semi_id, semi_lot_id, 40.0, conn=conn)

            # Ingresar SEMI-001 a lot_stock
            cur.execute(
                """
                INSERT INTO lot_stock (product_id, lot_number, entry_date, initial_qty, available_qty, warehouse, lot_id)
                VALUES (%s, 'SEMI-001', '2026-09-15', 40, 40, 'Principal', %s)
                """,
                (semi_id, semi_lot_id)
            )
        conn.commit()

    # 3. PRODUCCIÓN NIVEL 2: OT-TEST-002 (Consume 20 un de SEMI-001 -> Produce 20 un de FINAL-001)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO production_orders (ot_number, final_product_id, quantity, status, created_at) VALUES (%s, %s, 20, 'Finalizada', NOW()) RETURNING id",
                (ot2_num, final_id)
            )
            ot2_id = cur.fetchone()["id"]

            # Consumo exacto de SEMI-001
            cur.execute(
                "UPDATE lot_stock SET available_qty = available_qty - 20 WHERE id = (SELECT id FROM lot_stock WHERE product_id = %s AND lot_number = 'SEMI-001')",
                (semi_id,)
            )
            lot_repo.record_production_consumption(ot2_id, semi_id, semi_lot_id, 20.0, conn=conn)

            # Generar lote de salida FINAL-001
            final_lot_id = lot_repo.create_lot(
                product_id=final_id,
                lot_number="FINAL-001",
                lot_type="FINISHED_PRODUCT",
                origin_type="PRODUCTION",
                origin_id=ot2_id,
                production_order_id=ot2_id,
                initial_quantity=20.0,
                warehouse="Principal",
                notes=f"Generado por {ot2_num}",
                conn=conn
            )
            lot_repo.record_production_output(ot2_id, final_id, final_lot_id, 20.0, conn=conn)

            # Ingresar FINAL-001 a lot_stock
            cur.execute(
                """
                INSERT INTO lot_stock (product_id, lot_number, entry_date, initial_qty, available_qty, warehouse, lot_id)
                VALUES (%s, 'FINAL-001', '2026-09-15', 20, 20, 'Principal', %s)
                """,
                (final_id, final_lot_id)
            )
        conn.commit()

    # 4. VENTAS: VTA-TEST-001 (8 un a Cliente X) y VTA-TEST-002 (12 un a Cliente Y)
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Venta 1
            cur.execute(
                """
                INSERT INTO sales (sale_number, customer_name, customer_email, sale_date, sale_time, total_amount, status, seller_name, products_json, created_at)
                VALUES (%s, 'Cliente X', 'clientex@empresa.cl', '2026-09-15', '14:00', 36000, 'Completada', 'Vendedor Test', '[]', NOW())
                RETURNING id;
                """,
                (vta1_num,)
            )
            sale1_id = cur.fetchone()["id"]

            # Venta 2
            cur.execute(
                """
                INSERT INTO sales (sale_number, customer_name, customer_email, sale_date, sale_time, total_amount, status, seller_name, products_json, created_at)
                VALUES (%s, 'Cliente Y', 'clientey@empresa.cl', '2026-09-15', '16:00', 54000, 'Completada', 'Vendedor Test', '[]', NOW())
                RETURNING id;
                """,
                (vta2_num,)
            )
            sale2_id = cur.fetchone()["id"]
        conn.commit()

    # Descontar lote FINAL-001 en Venta 1
    inv_repo.consume_lots_for_sale(sale1_id, [{"product_id": final_id, "lot_number": "FINAL-001", "quantity": 8, "lot_id": final_lot_id}])

    # Descontar lote FINAL-001 en Venta 2
    inv_repo.consume_lots_for_sale(sale2_id, [{"product_id": final_id, "lot_number": "FINAL-001", "quantity": 12, "lot_id": final_lot_id}])

    # =========================================================================
    # 5. VALIDACIÓN FORWARD (Desde MP-001 hacia adelante)
    # =========================================================================
    forward = LotTraceabilityService.trace_lot_forward(mp_lot_id)
    tree_lot_numbers = [l["lot_number"] for l in forward["tree_lots"]]
    assert "MP-001" in tree_lot_numbers
    assert "SEMI-001" in tree_lot_numbers
    assert "FINAL-001" in tree_lot_numbers

    sales_numbers = [s["sale_number"] for s in forward["sales"]]
    assert vta1_num in sales_numbers
    assert vta2_num in sales_numbers

    customers = [s["customer_name"] for s in forward["sales"]]
    assert "Cliente X" in customers
    assert "Cliente Y" in customers

    # =========================================================================
    # 6. VALIDACIÓN BACKWARD (Desde FINAL-001 hacia atrás)
    # =========================================================================
    backward = LotTraceabilityService.trace_lot_backward(final_lot_id)
    ancestor_lot_numbers = [a["lot_number"] for a in backward["ancestors"]]
    assert "FINAL-001" in ancestor_lot_numbers
    assert "SEMI-001" in ancestor_lot_numbers
    assert "MP-001" in ancestor_lot_numbers

    # =========================================================================
    # 7. VALIDACIÓN DESDE VENTA hacia origen
    # =========================================================================
    sale_trace = LotTraceabilityService.trace_sale_to_origin(sale1_id)
    assert len(sale_trace["traces"]) == 1
    t = sale_trace["traces"][0]
    assert t["lot_number"] == "FINAL-001"
    b_trace = t["backward_trace"]
    assert b_trace is not None
    assert any(a["lot_number"] == "MP-001" for a in b_trace["ancestors"])
    assert any("Proveedor Miel Sur" in a.get("supplier_name", "") for a in b_trace["ancestors"])

    # =========================================================================
    # 8. RECALL TEST (Retiro de MP-001)
    # =========================================================================
    recall = LotTraceabilityService.get_lot_recall_impact(mp_lot_id)
    assert recall["affected_lots_count"] == 3  # MP-001, SEMI-001, FINAL-001
    assert recall["affected_sales_count"] == 2  # vta1 y vta2
    assert recall["affected_clients_count"] == 2 # Cliente X y Cliente Y
    assert recall["total_units_sold"] == 20.0  # 8 + 12 = 20 un vendidas


def test_multilot_fifo_genealogy(genealogy_fixture):
    """
    Verifica que si una OT consume múltiples lotes por FIFO:
    MP-A lote A1 = 10, lote A2 = 20. OT requiere 15.
    Consume A1 (10) y A2 (5). La genealogía de la OT registra AMBOS lotes.
    """
    mp_id = genealogy_fixture["mp_id"]
    semi_id = genealogy_fixture["semi_id"]
    ts = genealogy_fixture["ts"]
    ot_num = f"OT-FIFO-{ts}"

    # Crear 2 lotes en lot_stock
    l1_id = lot_repo.create_lot(mp_id, f"LOTE-F1-{ts}", initial_quantity=10.0, warehouse="Principal")
    l2_id = lot_repo.create_lot(mp_id, f"LOTE-F2-{ts}", initial_quantity=20.0, warehouse="Principal")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO lot_stock (product_id, lot_number, entry_date, initial_qty, available_qty, warehouse, lot_id) VALUES (%s, %s, '2026-09-01', 10, 10, 'Principal', %s)",
                (mp_id, f"LOTE-F1-{ts}", l1_id)
            )
            cur.execute(
                "INSERT INTO lot_stock (product_id, lot_number, entry_date, initial_qty, available_qty, warehouse, lot_id) VALUES (%s, %s, '2026-09-02', 20, 20, 'Principal', %s)",
                (mp_id, f"LOTE-F2-{ts}", l2_id)
            )
            cur.execute(
                "INSERT INTO production_orders (ot_number, final_product_id, quantity, status, created_at) VALUES (%s, %s, 15, 'En Proceso', NOW()) RETURNING id",
                (ot_num, semi_id)
            )
            ot_id = cur.fetchone()["id"]
        conn.commit()

    # Consumir 15 unidades por FIFO
    consumed = inv_repo.consume_fifo_lots(mp_id, 15.0, ot_id=ot_id)
    assert len(consumed) == 2
    assert consumed[0]["lot_number"] == f"LOTE-F1-{ts}"
    assert consumed[0]["quantity"] == 10.0
    assert consumed[1]["lot_number"] == f"LOTE-F2-{ts}"
    assert consumed[1]["quantity"] == 5.0

    # Registrar consumos y producto terminado
    with get_connection() as conn:
        for c in consumed:
            lot_repo.record_production_consumption(ot_id, mp_id, c["lot_id"], c["quantity"], conn=conn)

        out_lot_id = lot_repo.create_lot(semi_id, f"SEMI-OUT-{ts}", initial_quantity=15.0, production_order_id=ot_id, conn=conn)
        lot_repo.record_production_output(ot_id, semi_id, out_lot_id, 15.0, conn=conn)
        conn.commit()

    # Verificar que backward de SEMI-MULTILOT-OUT contiene AMBOS lotes de entrada
    backward = LotTraceabilityService.trace_lot_backward(out_lot_id)
    ancestors = [a["lot_number"] for a in backward["ancestors"]]
    assert f"LOTE-F1-{ts}" in ancestors
    assert f"LOTE-F2-{ts}" in ancestors


def test_multiinput_genealogy(genealogy_fixture):
    """
    Verifica que si una OT consume múltiples insumos distintos:
    Insumo 1 (Lote M-01), Insumo 2 (Lote E-01).
    El producto final FINAL-MULTI tiene ambos insumos como ancestros.
    """
    mp_id = genealogy_fixture["mp_id"]
    semi_id = genealogy_fixture["semi_id"]
    final_id = genealogy_fixture["final_id"]
    ts = genealogy_fixture["ts"]
    ot_num = f"OT-INP-{ts}"

    m1_id = lot_repo.create_lot(mp_id, f"MAT-IN-{ts}", initial_quantity=50.0)
    e1_id = lot_repo.create_lot(semi_id, f"SEMI-IN-{ts}", initial_quantity=50.0)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO production_orders (ot_number, final_product_id, quantity, status, created_at) VALUES (%s, %s, 10, 'Finalizada', NOW()) RETURNING id",
                (ot_num, final_id)
            )
            ot_id = cur.fetchone()["id"]

        lot_repo.record_production_consumption(ot_id, mp_id, m1_id, 10.0, conn=conn)
        lot_repo.record_production_consumption(ot_id, semi_id, e1_id, 10.0, conn=conn)

        f_id = lot_repo.create_lot(final_id, f"FINAL-OUT-{ts}", initial_quantity=10.0, production_order_id=ot_id, conn=conn)
        lot_repo.record_production_output(ot_id, final_id, f_id, 10.0, conn=conn)
        conn.commit()

    backward = LotTraceabilityService.trace_lot_backward(f_id)
    ancestors = [a["lot_number"] for a in backward["ancestors"]]
    assert f"MAT-IN-{ts}" in ancestors
    assert f"SEMI-IN-{ts}" in ancestors


def test_depleted_lot_history_preserved(genealogy_fixture):
    """Verifica que cuando un lote se agota (available_qty = 0), no se borra y conserva su historia."""
    mp_id = genealogy_fixture["mp_id"]
    ts = genealogy_fixture["ts"]

    lot_id = lot_repo.create_lot(mp_id, f"LOTE-DEP-{ts}", initial_quantity=5.0)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO lot_stock (product_id, lot_number, entry_date, initial_qty, available_qty, warehouse, lot_id) VALUES (%s, %s, '2026-09-10', 5, 5, 'Principal', %s)",
                (mp_id, f"LOTE-DEP-{ts}", lot_id)
            )
        conn.commit()

    # Consumir todo el lote
    inv_repo.consume_fifo_lots(mp_id, 5.0)

    # El lote en lots sigue existiendo y su status es DEPLETED
    lot = lot_repo.get_lot(lot_id)
    assert lot is not None
    assert lot["status"] == "DEPLETED"

    # En lot_stock la fila permanece con available_qty = 0 (no se borra)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT available_qty FROM lot_stock WHERE lot_id = %s", (lot_id,))
            row = cur.fetchone()
            if row:
                assert row["available_qty"] == 0


def test_lot_history_cannot_be_silently_deleted(genealogy_fixture):
    """Verifica que una entidad lot o movimiento con relaciones no pueda ser eliminada físicamente (RESTRICT)."""
    mp_id = genealogy_fixture["mp_id"]
    ts = genealogy_fixture["ts"]
    ot_num = f"OT-IMM-{ts}"

    lot_id = lot_repo.create_lot(mp_id, f"LOTE-IMM-{ts}", initial_quantity=20.0)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO production_orders (ot_number, final_product_id, quantity, status, created_at) VALUES (%s, %s, 1, 'Finalizada', NOW()) RETURNING id",
                (ot_num, mp_id)
            )
            ot_id = cur.fetchone()["id"]
            cur.execute(
                "INSERT INTO production_lot_consumptions (production_order_id, input_product_id, input_lot_id, quantity_consumed, created_at) VALUES (%s, %s, %s, 5, NOW())",
                (ot_id, mp_id, lot_id)
            )
        conn.commit()

    # Intentar eliminar el lote directamente debe violar la FK RESTRICT
    with get_connection() as conn:
        with conn.cursor() as cur:
            with pytest.raises(psycopg2.IntegrityError):
                cur.execute("DELETE FROM lots WHERE id = %s", (lot_id,))
        conn.rollback()
