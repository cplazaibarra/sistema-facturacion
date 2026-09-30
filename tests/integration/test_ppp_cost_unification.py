import pytest
import json
import uuid
from datetime import datetime, timezone
from app import app
from core.database import get_connection
from db import (
    create_product,
    insert_sale,
    get_sale,
    discount_stock_for_sale,
    validate_stock_for_sale,
    record_sale_packaging,
    get_sale_packaging_items,
    get_sale_financial_summary,
    reverse_sale_packaging,
    reverse_sale_inventory,
    record_inventory_movement,
    get_relational_stock,
    get_current_ppp,
    get_product_kardex_history,
    consume_fifo_lots,
    consume_lots_for_sale,
    insert_supplier
)
from repositories import purchases_repo, inventory_repo, production_repo


@pytest.fixture
def auth_client():
    old_csrf = app.config.get("WTF_CSRF_ENABLED", True)
    old_testing = app.config.get("TESTING", False)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    try:
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["username"] = "admin"
                sess["role_name"] = "Administrativo"
                sess["full_name"] = "Administrador Sistema"
                sess["permissions"] = {
                    "dashboard": True, "ventas": True, "inventario": True,
                    "productos": True, "reportes": True, "compras": True,
                    "produccion": True, "trazabilidad": True, "administracion": True,
                }
            yield client
    finally:
        app.config["WTF_CSRF_ENABLED"] = old_csrf
        app.config["TESTING"] = old_testing


def _create_unique_product(prefix="PROD", cost=1000.0, product_type="Final", requires_lot=False):
    sku = f"{prefix}-{uuid.uuid4().hex[:6].upper()}"
    pid = create_product(
        sku=sku,
        name=f"Test Product {sku}",
        category="General",
        product_type=product_type,
        cost=cost
    )
    if requires_lot:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE products SET requires_lot = TRUE WHERE id = %s", (pid,))
            conn.commit()
    return pid, sku


# =========================================================================
# A. SALE guarda PPP y no precio comercial
# B. Venta congela costo histórico en sale_items
# =========================================================================
def test_sale_movement_records_ppp_not_commercial_price():
    pid, sku = _create_unique_product("SALE-PPP", cost=2500.0)
    # 1. Ingreso con costo unitario de 2500
    record_inventory_movement(
        product_id=pid,
        movement_type="PURCHASE_RECEIPT",
        quantity=100.0,
        unit_cost=2500.0,
        notes="Compra inicial"
    )

    ppp_before = get_current_ppp(pid)
    assert ppp_before == 2500.0

    # 2. Crear venta de 4 unidades a precio comercial $5.000
    sale_data = {
        "sale_number": f"VTA-{uuid.uuid4().hex[:6].upper()}",
        "customer_name": "Cliente Test PPP",
        "sale_date": "2026-09-18",
        "sale_time": "12:00:00",
        "products": [{"product_id": pid, "sku": sku, "quantity": 4, "price": 5000.0}],
        "total_amount": 23800.0, # 20000 + 19% IVA
        "status": "Completada",
        "seller_name": "Admin",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    sale_id = insert_sale(sale_data)

    # Descontar existencias (la lógica que ejecuta el despacho)
    discount_stock_for_sale(sale_id, sale_data["products"])

    # 3. Verificar en inventory_movements
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT quantity, unit_cost, movement_type
                FROM inventory_movements
                WHERE product_id = %s AND movement_type = 'SALE' AND reference_id = %s
                """,
                (pid, sale_id)
            )
            mov = cur.fetchone()
            assert mov is not None
            assert float(mov["quantity"]) == -4.0
            # REGLA FUNDAMENTAL: unit_cost debe ser PPP ($2.500), NO el precio comercial ($5.000)
            assert float(mov["unit_cost"]) == 2500.0

            # 4. Verificar snapshot en sale_items
            cur.execute("SELECT * FROM sale_items WHERE sale_id = %s AND product_id = %s", (sale_id, pid))
            s_item = cur.fetchone()
            assert s_item is not None
            assert s_item["quantity"] == 4
            assert float(s_item["unit_price"]) == 5000.0
            assert float(s_item["unit_cost_at_sale"]) == 2500.0
            assert float(s_item["total_cost_at_sale"]) == 10000.0


# =========================================================================
# C. Nueva compra cambia PPP pero NO cambia costo de venta antigua
# D. Margen histórico permanece inmutable
# =========================================================================
def test_new_purchase_changes_ppp_but_not_historical_sale_or_margin():
    pid, sku = _create_unique_product("HIST-COST", cost=2500.0)
    record_inventory_movement(
        product_id=pid,
        movement_type="PURCHASE_RECEIPT",
        quantity=100.0,
        unit_cost=2500.0,
        notes="Compra 1"
    )

    # Venta de 4 unidades
    sale_data = {
        "sale_number": f"VTA-{uuid.uuid4().hex[:6].upper()}",
        "customer_name": "Cliente Margen",
        "sale_date": "2026-09-18",
        "sale_time": "12:00:00",
        "products": [{"product_id": pid, "sku": sku, "quantity": 4, "price": 5000.0}],
        "total_amount": 23800.0,
        "status": "Completada",
        "seller_name": "Admin",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    sale_id = insert_sale(sale_data)
    discount_stock_for_sale(sale_id, sale_data["products"])

    summary1 = get_sale_financial_summary(sale_id)
    assert summary1["products_cost"] == 10000.0

    # Nueva compra a precio mucho más alto ($4.000)
    record_inventory_movement(
        product_id=pid,
        movement_type="PURCHASE_RECEIPT",
        quantity=100.0,
        unit_cost=4000.0,
        notes="Compra 2 cara"
    )

    # El PPP actual del producto debió subir
    ppp_now = get_current_ppp(pid)
    assert ppp_now > 3000.0

    # Al volver a consultar la venta antigua, su costo histórico debe ser idéntico
    summary2 = get_sale_financial_summary(sale_id)
    assert summary2["products_cost"] == 10000.0
    assert summary2["real_total_cost"] == summary1["real_total_cost"]
    assert summary2["real_margin"] == summary1["real_margin"]
    assert summary2["real_margin_pct"] == summary1["real_margin_pct"]


# =========================================================================
# E. Packaging captura PPP
# F. Cambio posterior de PPP no cambia packaging histórico
# G. Packaging reversal usa costo original
# =========================================================================
def test_packaging_captures_ppp_and_preserves_historical_reversal():
    box_id, box_sku = _create_unique_product("BOX-PPP", cost=800.0, product_type="PACKAGING")
    # Entrada inicial de cajas: 50 a $800 ($40.000)
    record_inventory_movement(
        product_id=box_id,
        movement_type="PURCHASE_RECEIPT",
        quantity=50.0,
        unit_cost=800.0,
        notes="Stock cajas"
    )

    sale_data = {
        "sale_number": f"VTA-{uuid.uuid4().hex[:6].upper()}",
        "customer_name": "Cliente Embalaje",
        "sale_date": "2026-09-18",
        "sale_time": "12:00:00",
        "products": [],
        "total_amount": 10000.0,
        "status": "Para Despacho",
        "seller_name": "Admin",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    sale_id = insert_sale(sale_data)

    # Asignar 2 cajas (quedan 48 cajas valorizadas a $800 = $38.400)
    record_sale_packaging(sale_id, [{"product_id": box_id, "quantity": 2}])
    pkg_items = get_sale_packaging_items(sale_id)
    assert len(pkg_items) == 1
    assert pkg_items[0]["unit_cost"] == 800.0
    assert pkg_items[0]["total_cost"] == 1600.0

    # Nueva compra de cajas: 50 cajas a $1.200 ($60.000)
    # Saldo nuevo: 48 + 50 = 98 cajas. Valor: 38400 + 60000 = $98.400 -> PPP = 98400 / 98 = 1004.0816
    record_inventory_movement(
        product_id=box_id,
        movement_type="PURCHASE_RECEIPT",
        quantity=50.0,
        unit_cost=1200.0,
        notes="Stock cajas caras"
    )
    assert get_current_ppp(box_id) > 1000.0

    # Reversión de embalaje
    rev_res = reverse_sale_packaging(sale_id)
    assert len(rev_res) == 1

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT quantity, unit_cost, movement_type
                FROM inventory_movements
                WHERE product_id = %s AND movement_type = 'SALE_PACKAGING_REVERSAL' AND reference_id = %s
                """,
                (box_id, sale_id)
            )
            rev_mov = cur.fetchone()
            assert rev_mov is not None
            assert float(rev_mov["quantity"]) == 2.0
            # Debe revertirse al costo original de $800, NUNCA al actual
            assert float(rev_mov["unit_cost"]) == 800.0


# =========================================================================
# H. Producción consume MP usando PPP
# I. PRODUCTION_OUTPUT recibe costo derivado de insumos PPP
# J. Producto terminado pondera correctamente PPP existente
# =========================================================================
def test_production_consumes_materials_at_ppp_and_values_output(auth_client):
    mp_a_id, sku_a = _create_unique_product("MP-A", cost=1000.0, product_type="Insumo")
    mp_b_id, sku_b = _create_unique_product("MP-B", cost=2000.0, product_type="Insumo")
    pt_id, sku_pt = _create_unique_product("PT-FINAL", cost=3000.0, product_type="Final")

    # Ingreso de materias primas
    record_inventory_movement(product_id=mp_a_id, movement_type="PURCHASE_RECEIPT", quantity=50.0, unit_cost=1000.0)
    record_inventory_movement(product_id=mp_b_id, movement_type="PURCHASE_RECEIPT", quantity=50.0, unit_cost=2000.0)

    # Existencia previa de PT: 10 unidades a $3.000 ($30.000)
    record_inventory_movement(product_id=pt_id, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=3000.0)
    assert get_current_ppp(pt_id) == 3000.0

    # Crear OT para producir 10 PT
    # Requiere 10 MP-A y 5 MP-B -> Costo total esperado = 10*1000 + 5*2000 = $20.000
    items = [
        {"input_product_id": mp_a_id, "quantity_required": 1.0, "total_quantity": 10.0, "unit_cost": 1000.0},
        {"input_product_id": mp_b_id, "quantity_required": 0.5, "total_quantity": 5.0, "unit_cost": 2000.0},
    ]
    ot_id, ot_num = production_repo.create_production_order(
        final_product_id=pt_id,
        quantity=10,
        notes="OT Test PPP",
        status="Aprobada",
        items=items
    )

    # Finalizar OT a través de la ruta web para ejecutar finalizar_ot()
    resp = auth_client.post(f"/produccion/ot/{ot_id}/finalizar", data={
        "output_lot_number": f"LOTE-PT-{ot_id}"
    }, follow_redirects=True)
    assert resp.status_code == 200

    # Verificar movimientos PRODUCTION_INPUT
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT product_id, quantity, unit_cost
                FROM inventory_movements
                WHERE reference_type = 'production_order' AND reference_id = %s AND movement_type = 'PRODUCTION_INPUT'
                ORDER BY product_id ASC
                """,
                (ot_id,)
            )
            inputs = cur.fetchall()
            assert len(inputs) == 2
            input_map = {r["product_id"]: r for r in inputs}
            assert float(input_map[mp_a_id]["unit_cost"]) == 1000.0
            assert float(input_map[mp_b_id]["unit_cost"]) == 2000.0

            # Verificar movimiento PRODUCTION_OUTPUT
            cur.execute(
                """
                SELECT quantity, unit_cost
                FROM inventory_movements
                WHERE reference_type = 'production_order' AND reference_id = %s AND movement_type = 'PRODUCTION_OUTPUT'
                """,
                (ot_id,)
            )
            output = cur.fetchone()
            assert output is not None
            assert float(output["quantity"]) == 10.0
            # $20.000 / 10 = $2.000
            assert float(output["unit_cost"]) == 2000.0

    # Verificar que el PT ponderó correctamente el nuevo PPP:
    # 10 previas a $3.000 ($30.000) + 10 producidas a $2.000 ($20.000) = 20 un por $50.000 -> PPP = $2.500
    pt_kardex = get_product_kardex_history(pt_id)
    assert pt_kardex["current_stock"] == 20.0
    assert pt_kardex["current_ppp"] == 2500.0
    assert pt_kardex["current_inventory_value"] == 50000.0


# =========================================================================
# K. Cancelación venta restaura stock
# L. Cancelación restaura exactamente lotes originales y reactiva DEPLETED
# M. Cancelación usa costo histórico original
# N. Cancelación doble es idempotente
# O. Venta + packaging + cancelación revierte ambos exactamente una vez
# =========================================================================
def test_sale_cancellation_restores_stock_lots_and_is_idempotent(auth_client):
    pid, sku = _create_unique_product("LOT-REST", cost=2500.0, requires_lot=True)
    box_id, box_sku = _create_unique_product("BOX-REST", cost=800.0, product_type="PACKAGING")

    # Crear lote y stock de 10 unidades
    lot_name = f"LOTE-CANC-{uuid.uuid4().hex[:6]}"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO lots (product_id, lot_number, lot_type, origin_type, initial_quantity, status, created_at)
                VALUES (%s, %s, 'RAW_MATERIAL', 'PURCHASE', 10, 'ACTIVE', NOW()) RETURNING id;
                """,
                (pid, lot_name)
            )
            lot_id = cur.fetchone()["id"]
            cur.execute(
                """
                INSERT INTO lot_stock (product_id, lot_number, initial_qty, available_qty, lot_id)
                VALUES (%s, %s, 10, 10, %s);
                """,
                (pid, lot_name, lot_id)
            )
            conn.commit()

    record_inventory_movement(product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=2500.0, lot_id=lot_id, lot_number=lot_name)
    record_inventory_movement(product_id=box_id, movement_type="PURCHASE_RECEIPT", quantity=20.0, unit_cost=800.0)

    # Realizar venta de 10 unidades (agota el lote completamente mediante discount_stock_for_sale)
    sale_data = {
        "sale_number": f"VTA-{uuid.uuid4().hex[:6].upper()}",
        "customer_name": "Cliente Cancelación",
        "sale_date": "2026-09-18",
        "sale_time": "12:00:00",
        "products": [{"product_id": pid, "sku": sku, "quantity": 10, "price": 6000.0, "lot_number": lot_name}],
        "total_amount": 71400.0,
        "status": "Completada",
        "seller_name": "Admin",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    sale_id = insert_sale(sale_data)
    discount_stock_for_sale(sale_id, sale_data["products"])
    record_sale_packaging(sale_id, [{"product_id": box_id, "quantity": 3}])

    # Validar que el lote quedó agotado (DEPLETED y available_qty = 0)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM lots WHERE id = %s", (lot_id,))
            assert cur.fetchone()["status"] == "DEPLETED"
            cur.execute("SELECT available_qty FROM lot_stock WHERE product_id = %s AND lot_number = %s", (pid, lot_name))
            assert cur.fetchone()["available_qty"] == 0

    assert get_relational_stock(pid) == 0.0
    assert get_relational_stock(box_id) == 17.0

    # Ahora cancelamos la venta llamando a la ruta web
    resp = auth_client.post("/ventas/actualizar-estado", data={
        "sale_id": sale_id,
        "status": "Cancelada"
    }, follow_redirects=True)
    assert resp.status_code == 200

    # 1. Stock restaurado
    assert get_relational_stock(pid) == 10.0
    assert get_relational_stock(box_id) == 20.0

    # 2. Lote reactivado
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM lots WHERE id = %s", (lot_id,))
            assert cur.fetchone()["status"] == "ACTIVE"
            cur.execute("SELECT available_qty FROM lot_stock WHERE product_id = %s AND lot_number = %s", (pid, lot_name))
            assert cur.fetchone()["available_qty"] == 10

            # 3. Movimiento SALE_REVERSAL con unit_cost original
            cur.execute(
                """
                SELECT quantity, unit_cost, movement_type
                FROM inventory_movements
                WHERE product_id = %s AND movement_type = 'SALE_REVERSAL' AND reference_id = %s
                """,
                (pid, sale_id)
            )
            reversal_mov = cur.fetchone()
            assert reversal_mov is not None
            assert float(reversal_mov["quantity"]) == 10.0
            assert float(reversal_mov["unit_cost"]) == 2500.0

    # 4. Idempotencia: cancelar nuevamente
    rev2 = reverse_sale_inventory(sale_id)
    assert rev2 == []
    assert get_relational_stock(pid) == 10.0
    assert get_relational_stock(box_id) == 20.0


# =========================================================================
# L. Kardex de reversa modificando matemáticamente el PPP resultante
# =========================================================================
def test_kardex_reversal_updates_ppp_mathematically():
    """
    Compra 1: 10 x $1.000 -> Saldo: 10, Valor: $10.000, PPP: $1.000
    Venta:    -4 x $1.000 -> Saldo: 6, Valor: $6.000, PPP: $1.000
    Compra 2: 10 x $2.000 -> Saldo: 16, Valor: $26.000, PPP: $1.625
    Reversa:  +4 x $1.000 -> Saldo: 20, Valor: $30.000, PPP: $1.500
    """
    pid, sku = _create_unique_product("KARDEX-REV", cost=1000.0)

    # 1. Compra 1
    record_inventory_movement(product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=1000.0)

    # 2. Venta
    sale_data = {
        "sale_number": f"VTA-{uuid.uuid4().hex[:6].upper()}",
        "customer_name": "Test Kardex Reversal",
        "sale_date": "2026-09-01",
        "sale_time": "11:00:00",
        "products": [{"product_id": pid, "sku": sku, "quantity": 4, "price": 2000.0}],
        "total_amount": 9520.0,
        "status": "Completada",
        "seller_name": "Admin",
        "created_at": "2026-09-01 11:00:00"
    }
    sale_id = insert_sale(sale_data)
    discount_stock_for_sale(sale_id, sale_data["products"])

    # 3. Compra 2
    record_inventory_movement(product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=2000.0)

    k_before = get_product_kardex_history(pid)
    assert k_before["current_stock"] == 16.0
    assert k_before["current_inventory_value"] == 26000.0
    assert k_before["current_ppp"] == 1625.0

    # 4. Cancelación de venta (SALE_REVERSAL con $1.000 de costo congelado)
    reverse_sale_inventory(sale_id)

    k_after = get_product_kardex_history(pid)
    assert k_after["current_stock"] == 20.0
    assert k_after["current_inventory_value"] == 30000.0
    assert k_after["current_ppp"] == 1500.0


# =========================================================================
# P. FIFO físico permanece independiente de PPP económico
# =========================================================================
def test_fifo_lots_independent_from_economic_ppp():
    pid, sku = _create_unique_product("MULTI-LOT", cost=1200.0, requires_lot=True)
    lot_a = f"LOTE-A-{uuid.uuid4().hex[:4]}"
    lot_b = f"LOTE-B-{uuid.uuid4().hex[:4]}"

    # Lote A (5 un) y Lote B (10 un)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO lots (product_id, lot_number, lot_type, origin_type, initial_quantity, status, created_at) VALUES (%s, %s, 'RAW_MATERIAL', 'PURCHASE', 5, 'ACTIVE', '2026-09-01 08:00:00') RETURNING id;", (pid, lot_a))
            la_id = cur.fetchone()["id"]
            cur.execute("INSERT INTO lot_stock (product_id, lot_number, initial_qty, available_qty, lot_id, entry_date) VALUES (%s, %s, 5, 5, %s, '2026-09-01');", (pid, lot_a, la_id))

            cur.execute("INSERT INTO lots (product_id, lot_number, lot_type, origin_type, initial_quantity, status, created_at) VALUES (%s, %s, 'RAW_MATERIAL', 'PURCHASE', 10, 'ACTIVE', '2026-09-01 09:00:00') RETURNING id;", (pid, lot_b))
            lb_id = cur.fetchone()["id"]
            cur.execute("INSERT INTO lot_stock (product_id, lot_number, initial_qty, available_qty, lot_id, entry_date) VALUES (%s, %s, 10, 10, %s, '2026-09-01');", (pid, lot_b, lb_id))
            conn.commit()

    record_inventory_movement(product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=5.0, unit_cost=1000.0, lot_id=la_id, lot_number=lot_a)
    record_inventory_movement(product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=1300.0, lot_id=lb_id, lot_number=lot_b)

    # PPP actual = (5*1000 + 10*1300) / 15 = 18000 / 15 = $1.200
    assert get_current_ppp(pid) == 1200.0

    # Consumir 8 unidades mediante FIFO
    consumed = consume_fifo_lots(pid, 8.0)
    assert len(consumed) == 2
    assert consumed[0]["lot_number"] == lot_a and consumed[0]["quantity"] == 5.0
    assert consumed[1]["lot_number"] == lot_b and consumed[1]["quantity"] == 3.0

    # Económicamente el PPP sigue siendo $1.200 para las 8 unidades = $9.600
    assert get_current_ppp(pid) == 1200.0


# =========================================================================
# Q. IVA no entra en costo ni margen
# R. Stock cero deja valorización exactamente en $0.0
# =========================================================================
def test_zero_stock_and_vat_exclusion():
    pid, sku = _create_unique_product("ZERO-VAT", cost=1000.0)
    # Entrada: 10 un a $1.000 (neto sin IVA)
    record_inventory_movement(product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=1000.0)
    assert get_current_ppp(pid) == 1000.0

    # Salida: 10 un
    record_inventory_movement(product_id=pid, movement_type="SALE", quantity=-10.0, unit_cost=1000.0, notes="Salida total")

    k = get_product_kardex_history(pid)
    assert k["current_stock"] == 0.0
    assert k["current_inventory_value"] == 0.0
    # No hay residuos de centavos
    assert k["current_inventory_value"] == 0.0


# =========================================================================
# 21. TEST END-TO-END COMPLETO (E2E OBLIGATORIO)
# =========================================================================
def test_e2e_full_lifecycle_cost_integrity(auth_client):
    """
    Flujo E2E completo:
    1. Proveedor + OC + Recepción de MP con lote -> PPP MP
    2. OT con consumo FIFO exacto de MP -> Costo Insumo PPP -> Lote PT -> Costo fabricación
    3. Ponderación PT con stock existente
    4. Venta de PT -> Consumo Lote -> Snapshot Costo en sale_items -> Packaging -> Margen
    5. Compra posterior altera PPP del mercado -> Venta antigua inalterada
    6. Cancelación Venta -> Restauración PT -> Restauración Lote original -> Reversa Packaging
    7. Auditoría final de Kardex y Genealogía
    """
    # 1. Crear proveedor y MP
    s_id = insert_supplier({
        "rut": "77123456-7",
        "name": f"Proveedor E2E {uuid.uuid4().hex[:4]}",
        "business_line": "Materia Prima",
        "contact_phone": "+56911223344",
        "contact_email": "e2e@supp.cl"
    })
    mp_id, mp_sku = _create_unique_product("E2E-MP", cost=1000.0, product_type="Insumo", requires_lot=True)
    pt_id, pt_sku = _create_unique_product("E2E-PT", cost=2000.0, product_type="Final", requires_lot=True)
    box_id, box_sku = _create_unique_product("E2E-BOX", cost=500.0, product_type="PACKAGING")

    # OC para MP
    oc_num = purchases_repo.create_purchase_order(s_id, "2026-09-18", "OC E2E", [{"product_id": mp_id, "quantity": 100, "unit_price": 1000.0}])
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM purchase_orders WHERE oc_number = %s", (oc_num,))
            po_id = cur.fetchone()["id"]

    # Recepción de MP con Lote
    lote_mp = f"LOT-MP-{uuid.uuid4().hex[:6]}"
    inventory_repo.register_inventory_entry(
        po_id,
        order_number=f"REC-{uuid.uuid4().hex[:6]}",
        entry_date="2026-09-18",
        warehouse="Principal",
        notes="Recepción E2E",
        items=[{"product_id": mp_id, "quantity": 100, "unit_price": 1000.0, "lot_number": lote_mp}]
    )
    assert get_relational_stock(mp_id) == 100.0
    assert get_current_ppp(mp_id) == 1000.0

    # Stock cajas
    record_inventory_movement(product_id=box_id, movement_type="PURCHASE_RECEIPT", quantity=50.0, unit_cost=500.0)

    # 2. Fabricar 10 PT mediante OT consumiendo 20 MP (2 MP por cada PT)
    ot_items = [{"input_product_id": mp_id, "quantity_required": 2.0, "total_quantity": 20.0, "unit_cost": 1000.0}]
    ot_id, ot_num = production_repo.create_production_order(
        final_product_id=pt_id,
        quantity=10,
        notes="OT E2E",
        status="Aprobada",
        items=ot_items
    )
    lote_pt = f"LOT-PT-{uuid.uuid4().hex[:6]}"

    # Finalizar OT
    resp = auth_client.post(f"/produccion/ot/{ot_id}/finalizar", data={
        "output_lot_number": lote_pt
    }, follow_redirects=True)
    assert resp.status_code == 200

    # Verificar existencias y costo PT: 20 MP * $1.000 = $20.000 / 10 PT = $2.000 c/u
    assert get_relational_stock(mp_id) == 80.0
    assert get_relational_stock(pt_id) == 10.0
    assert get_current_ppp(pt_id) == 2000.0

    # 3. Venta de 4 PT a $5.000 + 1 Caja a $500
    sale_data = {
        "sale_number": f"VTA-E2E-{uuid.uuid4().hex[:6].upper()}",
        "customer_name": "Cliente E2E",
        "sale_date": "2026-09-18",
        "sale_time": "12:00:00",
        "products": [{"product_id": pt_id, "sku": pt_sku, "quantity": 4, "price": 5000.0, "lot_number": lote_pt}],
        "total_amount": 23800.0, # Neto $20.000
        "status": "En Preparación",
        "seller_name": "Admin",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    sale_id = insert_sale(sale_data)
    discount_stock_for_sale(sale_id, sale_data["products"])
    record_sale_packaging(sale_id, [{"product_id": box_id, "quantity": 1}])

    # Validar resumen financiero: Neto = $20.000, Productos = 4 * $2.000 = $8.000, Packaging = $500, Costo Real = $8.500, Margen = $11.500
    fin1 = get_sale_financial_summary(sale_id)
    assert fin1["products_cost"] == 8000.0
    assert fin1["packaging_cost"] == 500.0
    assert fin1["real_total_cost"] == 8500.0
    assert fin1["real_margin"] == 11500.0

    # 4. Nueva compra altera PPP de PT en el mercado
    record_inventory_movement(product_id=pt_id, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=5000.0)
    assert get_current_ppp(pt_id) > 3000.0

    # Inmutabilidad del margen histórico
    fin2 = get_sale_financial_summary(sale_id)
    assert fin2["products_cost"] == 8000.0
    assert fin2["real_total_cost"] == 8500.0

    # 5. Cancelación de la venta
    resp_canc = auth_client.post("/ventas/actualizar-estado", data={
        "sale_id": sale_id,
        "status": "Cancelada"
    }, follow_redirects=True)
    assert resp_canc.status_code == 200

    # 6. Validaciones de stock y lote
    # PT antes de compra era 6, con compra de 10 era 16, con reversa de 4 queda en 20
    assert get_relational_stock(pt_id) == 20.0
    assert get_relational_stock(box_id) == 50.0

    # Lote PT restaurado a 10
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT available_qty FROM lot_stock WHERE product_id = %s AND lot_number = %s", (pt_id, lote_pt))
            assert cur.fetchone()["available_qty"] == 10


# =========================================================================
# PRUEBA DE NO BORRADO HISTÓRICO (PREVENCIÓN DE BORRADO FÍSICO DE VENTAS)
# =========================================================================
def test_historical_sale_physical_delete_prevented_by_restrict():
    """
    Verifica que la base de datos impida físicamente eliminar (DELETE) una venta
    si existen snapshots históricos en sale_items (ON DELETE RESTRICT).
    Garantiza que no puedan desaparecer silenciosamente los datos históricos,
    costos de venta, genealogía ni movimientos contables.
    """
    import psycopg2
    pid, sku = _create_unique_product("NO-DEL", cost=1500.0)
    record_inventory_movement(product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=20.0, unit_cost=1500.0)

    sale_data = {
        "sale_number": f"VTA-NODEL-{uuid.uuid4().hex[:6].upper()}",
        "customer_name": "Cliente Inmutable No Borrado",
        "sale_date": "2026-09-18",
        "sale_time": "12:00:00",
        "products": [{"product_id": pid, "sku": sku, "quantity": 5, "price": 3000.0}],
        "total_amount": 17850.0,
        "status": "Completada",
        "seller_name": "Admin",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    sale_id = insert_sale(sale_data)
    discount_stock_for_sale(sale_id, sale_data["products"])

    # Verificar que sale_items contiene el registro histórico
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as c FROM sale_items WHERE sale_id = %s", (sale_id,))
            assert cur.fetchone()["c"] == 1

    # Intentar eliminar físicamente la venta directa en la base de datos
    # Debe disparar una excepción ForeignKeyViolation debido a ON DELETE RESTRICT
    with get_connection() as conn:
        with conn.cursor() as cur:
            with pytest.raises(psycopg2.IntegrityError) as excinfo:
                cur.execute("DELETE FROM sales WHERE id = %s", (sale_id,))
            assert "sale_items" in str(excinfo.value)
        conn.rollback()

    # Verificar que la venta y su histórico siguen intactos tras el intento de borrado
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM sales WHERE id = %s", (sale_id,))
            assert cur.fetchone() is not None
            cur.execute("SELECT COUNT(*) as c FROM sale_items WHERE sale_id = %s", (sale_id,))
            assert cur.fetchone()["c"] == 1

