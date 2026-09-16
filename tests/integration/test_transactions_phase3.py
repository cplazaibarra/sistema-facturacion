"""
tests/integration/test_transactions_phase3.py
Suite de validación de transacciones, atomicidad, rollback e idempotencia ante concurrencia (Fase 3).
"""

import pytest
import threading
from datetime import datetime, timezone
from db import (
    get_connection,
    insert_product,
    delete_product,
    register_inventory_entry,
    record_inventory_movement,
    get_relational_stock,
    consume_fifo_lots,
    register_purchase_payment,
    get_next_oc_number,
    get_next_sale_number,
    get_next_ot_number,
)
from routes.ventas import _convert_quotation_to_sale


@pytest.fixture
def test_product():
    """Crea un producto aislado para pruebas de transacciones."""
    sku = f"TX-P3-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    product_data = {
        "sku": sku,
        "name": f"Producto Transaccional {sku}",
        "description": "Producto para pruebas de concurrencia y atomicidad Fase 3",
        "category": "Pruebas",
        "product_type": "Final",
        "cost": 1000.0,
        "price": 2000.0,
        "requires_lot": False,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    }
    prod_id = insert_product(product_data)
    yield {"id": prod_id, "sku": sku, "name": product_data["name"]}

    # Cleanup
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sale_lot_movements WHERE product_id = %s", (prod_id,))
            cur.execute("DELETE FROM inventory_movements WHERE product_id = %s", (prod_id,))
            cur.execute("DELETE FROM inventory_entry_items WHERE product_id = %s", (prod_id,))
            cur.execute("DELETE FROM lot_stock WHERE product_id = %s", (prod_id,))
            cur.execute("DELETE FROM purchase_order_items WHERE product_id = %s", (prod_id,))
            cur.execute("DELETE FROM production_order_items WHERE input_product_id = %s", (prod_id,))
            cur.execute("DELETE FROM products WHERE id = %s", (prod_id,))
        conn.commit()


def test_purchase_atomic_rollback(test_product):
    """
    Verifica que si una recepción de compra falla a la mitad, se ejecuta un ROLLBACK total
    y no queda registro huérfano en inventory_entries, inventory_entry_items ni inventory_movements.
    """
    prod_id = test_product["id"]

    # Crear una OC válida
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO purchase_orders (oc_number, supplier_id, order_date, status, total_amount, created_at)
                VALUES (%s, 1, '2026-03-14', 'Emitida', 50000.0, '2026-03-14 12:00:00')
                RETURNING id
                """,
                (f"OC-TEST-{prod_id}",)
            )
            po_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO purchase_order_items (purchase_order_id, product_id, quantity_ordered, quantity_received, unit_price, total_price)
                VALUES (%s, %s, 10, 0, 5000.0, 50000.0)
                """,
                (po_id, prod_id)
            )
        conn.commit()

    # Intentar ingresar 15 unidades cuando solo se ordenaron 10 (debe fallar y hacer rollback)
    items_to_receive = [
        {"product_id": prod_id, "quantity": 15, "unit_price": 5000.0, "lot_number": f"LOT-FAIL-{prod_id}"}
    ]

    with pytest.raises(ValueError) as excinfo:
        register_inventory_entry(
            po_id=po_id,
            order_number=f"OC-TEST-{prod_id}",
            entry_date="2026-03-14",
            warehouse="Almacén Principal",
            notes="Prueba de rollback forzado",
            items=items_to_receive
        )

    assert "máximo pendiente" in str(excinfo.value) or "No puedes ingresar" in str(excinfo.value)

    # Verificar que NADA se guardó (Atomicidad / Rollback total)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM inventory_entries WHERE purchase_order_id = %s", (po_id,))
            assert cur.fetchone()["count"] == 0

            cur.execute("SELECT COUNT(*) as count FROM inventory_movements WHERE reference_type = 'purchase_order' AND reference_id = %s", (po_id,))
            assert cur.fetchone()["count"] == 0

            cur.execute("SELECT available_qty FROM lot_stock WHERE product_id = %s AND lot_number = %s", (prod_id, f"LOT-FAIL-{prod_id}"))
            assert cur.fetchone() is None

            # La OC debe seguir con 0 recibidos y estado Emitida
            cur.execute("SELECT status FROM purchase_orders WHERE id = %s", (po_id,))
            assert cur.fetchone()["status"] == "Emitida"

            cur.execute("SELECT quantity_received FROM purchase_order_items WHERE purchase_order_id = %s", (po_id,))
            assert cur.fetchone()["quantity_received"] == 0

    # Cleanup de la OC
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM purchase_order_items WHERE purchase_order_id = %s", (po_id,))
            cur.execute("DELETE FROM purchase_orders WHERE id = %s", (po_id,))
        conn.commit()


def test_sale_concurrent_stock_protection(test_product):
    """
    Prueba de Concurrencia y Aislamiento:
    Se disponen 10 unidades de stock. Dos hilos intentan simultáneamente registrar una salida
    de 7 unidades cada uno (demanda total = 14 > 10).
    Con row locks / SELECT FOR UPDATE, exactamente una transacción debe tener éxito y la otra debe fallar.
    El stock final debe ser exactamente 3 (10 - 7), nunca negativo.
    """
    prod_id = test_product["id"]

    # 1. Ingresar stock inicial de 10 unidades
    record_inventory_movement(
        product_id=prod_id,
        movement_type="PURCHASE_RECEIPT",
        quantity=10.0,
        unit_cost=1000.0,
        warehouse="Almacén Principal",
        reference_type="purchase_order",
        reference_id=99999,
        notes="Stock inicial concurrencia"
    )
    assert get_relational_stock(prod_id) == 10.0

    results = []
    errors = []

    def perform_sale(idx):
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    record_inventory_movement(
                        product_id=prod_id,
                        movement_type="SALE",
                        quantity=-7.0,
                        unit_cost=2000.0,
                        warehouse="Almacén Principal",
                        reference_type="sale",
                        reference_id=idx,
                        notes=f"Venta concurrente {idx}",
                        conn=conn
                    )
                conn.commit()
                results.append(idx)
        except Exception as e:
            errors.append((idx, str(e)))

    t1 = threading.Thread(target=perform_sale, args=(1,))
    t2 = threading.Thread(target=perform_sale, args=(2,))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactamente 1 debió tener éxito y 1 debió fallar por INV-001 Stock insuficiente
    assert len(results) == 1, f"Debió ganar solo 1 hilo, pero ganaron {len(results)}"
    assert len(errors) == 1, f"Debió fallar exactamente 1 hilo, errores: {errors}"
    assert "INV-001" in errors[0][1]

    # El stock final remanente debe ser exactamente 3.0
    final_stock = get_relational_stock(prod_id)
    assert final_stock == 3.0


def test_fifo_concurrent_consumption(test_product):
    """
    Prueba de consumo FIFO ante concurrencia con FOR UPDATE en lot_stock.
    Dos lotes: Lote A (5 un) y Lote B (5 un).
    Dos hilos intentan consumir 4 unidades cada uno.
    Ambos deben tener éxito sin sobre-consumir el Lote A y respetando orden FIFO.
    """
    prod_id = test_product["id"]

    # Crear 2 lotes en lot_stock
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO lot_stock (product_id, lot_number, entry_id, entry_date, initial_qty, available_qty, warehouse)
                VALUES 
                (%s, 'LOTE-A', 1, '2026-01-01', 5, 5, 'Principal'),
                (%s, 'LOTE-B', 2, '2026-01-02', 5, 5, 'Principal');
                """,
                (prod_id, prod_id)
            )
        conn.commit()

    consumed_totals = []
    thread_errors = []

    def consume(qty):
        try:
            with get_connection() as conn:
                consumptions = consume_fifo_lots(prod_id, qty, conn=conn)
                conn.commit()
                consumed_totals.append(consumptions)
        except Exception as e:
            thread_errors.append(str(e))

    t1 = threading.Thread(target=consume, args=(4,))
    t2 = threading.Thread(target=consume, args=(4,))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(thread_errors) == 0, f"No debió fallar ningún hilo: {thread_errors}"
    assert len(consumed_totals) == 2

    # Verificar disponibilidad remanente en base de datos
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT lot_number, available_qty FROM lot_stock WHERE product_id = %s ORDER BY entry_date ASC", (prod_id,))
            rows = {r["lot_number"]: float(r["available_qty"]) for r in cur.fetchall()}

    # Lote A (5 inicial) debió quedar en 0
    # Lote B (5 inicial) debió suplir las 3 restantes y quedar en 2
    assert rows["LOTE-A"] == 0.0
    assert rows["LOTE-B"] == 2.0


def test_quotation_conversion_idempotent(test_product):
    """
    Prueba de Idempotencia y Concurrencia en Conversión de Cotización a Venta.
    Dos solicitudes concurrentes convierten la misma cotización.
    Deben retornar exactamente el MISMO número de venta (VTA-XXXXX),
    generar una sola venta en sales y descontar stock UNA sola vez.
    """
    prod_id = test_product["id"]

    # 1. Dotar stock disponible de 20 unidades
    record_inventory_movement(
        product_id=prod_id,
        movement_type="PURCHASE_RECEIPT",
        quantity=20.0,
        unit_cost=1000.0,
        warehouse="Almacén Principal",
        reference_type="purchase_order",
        reference_id=88888,
        notes="Stock para cotización"
    )

    # 2. Crear una cotización
    with get_connection() as conn:
        with conn.cursor() as cur:
            import json
            prods = [{"product_id": prod_id, "product_name": test_product["name"], "quantity": 5, "price": 2500.0}]
            cot_num = f"COT-TEST-{prod_id}"
            cur.execute(
                """
                INSERT INTO sales (sale_number, customer_name, seller_name, payment_method, sale_date, sale_time, products_json, total_amount, status, quotation_status, notes, created_at)
                VALUES (%s, 'Cliente Idempotente', 'Vendedor Test', 'Efectivo', '2026-03-14', '12:00:00', %s, 12500.0, 'Cotización', 'Activa', '', '2026-03-14 12:00:00')
                RETURNING id
                """,
                (cot_num, json.dumps(prods))
            )
            cot_id = cur.fetchone()["id"]
        conn.commit()

    results = []
    errors = []

    def convert():
        vta_num, err = _convert_quotation_to_sale(cot_id)
        if vta_num:
            results.append(vta_num)
        if err:
            errors.append(err)

    t1 = threading.Thread(target=convert)
    t2 = threading.Thread(target=convert)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(errors) == 0, f"Hubo errores en conversión: {errors}"
    assert len(results) == 2
    # Ambos hilos deben devolver exactamente el mismo folio de venta
    assert results[0] == results[1], f"Se generaron dos ventas distintas: {results}"

    # En la base de datos solo debe haber 1 venta generada vinculada a esta cotización
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM sales WHERE sale_number = %s", (results[0],))
            assert cur.fetchone()["cnt"] == 1

            # El stock debe haber disminuido exactamente 5 unidades (20 - 5 = 15), no 10
            cur.execute("SELECT COALESCE(SUM(quantity), 0) as stock FROM inventory_movements WHERE product_id = %s", (prod_id,))
            stock = float(cur.fetchone()["stock"])
            assert stock == 15.0

    # Cleanup cotización y venta
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sale_payments WHERE sale_id IN (SELECT id FROM sales WHERE sale_number = %s)", (results[0],))
            cur.execute("DELETE FROM sales_status_history WHERE sale_id IN (SELECT id FROM sales WHERE sale_number = %s)", (results[0],))
            cur.execute("DELETE FROM sales WHERE sale_number = %s", (results[0],))
            cur.execute("DELETE FROM sales WHERE id = %s", (cot_id,))
        conn.commit()


def test_supplier_payment_atomic_and_idempotent():
    """
    Verifica que el registro de pago a proveedor sea atómico y que un segundo intento
    sobre una factura ya pagada sea rechazado inmediatamente (Idempotencia).
    """
    # 1. Crear factura de prueba pendiente
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO purchase_invoices (invoice_number, supplier_id, invoice_amount, payment_status, due_date, created_at)
                VALUES ('FACT-TEST-TX', 1, 150000.0, 'Pendiente', '2026-04-15', '2026-03-14 12:00:00')
                RETURNING id
                """
            )
            inv_id = cur.fetchone()["id"]
        conn.commit()

    payment_data = {
        "payment_date": "2026-03-14",
        "payment_amount": 150000.0,
        "payment_method": "Transferencia",
        "bank_account_id": None,
        "payment_proof_file": None,
        "payment_notes": "Pago total factura test"
    }

    # Primer pago: debe resultar exitoso
    res1 = register_purchase_payment(inv_id, payment_data)
    assert res1 is True

    # Verificar que quedó Pagada
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT payment_status, payment_amount FROM purchase_invoices WHERE id = %s", (inv_id,))
            row = cur.fetchone()
            assert row["payment_status"] == "Pagada"
            assert float(row["payment_amount"]) == 150000.0

    # Segundo pago sobre la misma factura ya pagada: debe ser rechazado
    res2 = register_purchase_payment(inv_id, payment_data)
    assert res2 is False

    # Cleanup
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM purchase_invoices WHERE id = %s", (inv_id,))
        conn.commit()


def test_concurrent_sequences_generation():
    """
    Prueba que múltiples hilos concurrentes generando correlativos a través de secuencias
    PostgreSQL generen correlativos estrictamente únicos sin colisiones.
    """
    oc_numbers = []
    vta_numbers = []
    ot_numbers = []
    lock = threading.Lock()

    def generate_numbers():
        oc = get_next_oc_number()
        vta = get_next_sale_number("VTA")
        ot = get_next_ot_number()
        with lock:
            oc_numbers.append(oc)
            vta_numbers.append(vta)
            ot_numbers.append(ot)

    threads = [threading.Thread(target=generate_numbers) for _ in range(30)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verificar que se generaron 30 de cada uno y todos son estrictamente únicos
    assert len(oc_numbers) == 30
    assert len(set(oc_numbers)) == 30

    assert len(vta_numbers) == 30
    assert len(set(vta_numbers)) == 30

    assert len(ot_numbers) == 30
    assert len(set(ot_numbers)) == 30


def test_production_atomic_and_idempotent(client, auth_client):
    """
    Verifica que la finalización de OT sea atómica y que ante dos intentos concurrentes
    solo una transacción concrete la finalización (idempotencia y protección por status = 'Aprobada').
    """
    # 1. Crear insumo y producto final
    sku_in = f"IN-OT-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    sku_fin = f"FIN-OT-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    p_in_id = insert_product({
        "sku": sku_in, "name": f"Insumo OT {sku_in}", "product_type": "Insumo", "cost": 500.0, "price": 0.0, "created_at": "2026-03-14"
    })
    p_fin_id = insert_product({
        "sku": sku_fin, "name": f"Producto Final OT {sku_fin}", "product_type": "Final", "cost": 0.0, "price": 5000.0, "created_at": "2026-03-14"
    })

    # Dotar de stock al insumo (10 unidades)
    record_inventory_movement(
        product_id=p_in_id,
        movement_type="PURCHASE_RECEIPT",
        quantity=10.0,
        unit_cost=500.0,
        warehouse="Principal",
        reference_type="purchase_order",
        reference_id=77777,
        notes="Insumo inicial"
    )

    # 2. Crear OT en estado 'Aprobada'
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO production_orders (ot_number, final_product_id, quantity, status, created_at)
                VALUES ('OT-TEST-CONCUR', %s, 2, 'Aprobada', '2026-03-14 12:00:00')
                RETURNING id
                """,
                (p_fin_id,)
            )
            ot_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO production_order_items (production_order_id, input_product_id, quantity_required, unit_cost)
                VALUES (%s, %s, 4, 500.0)
                """,
                (ot_id, p_in_id)
            )
        conn.commit()

    # 3. Disparar finalización concurrente desde 2 hilos llamando a finalizar_ot
    from routes.produccion import finalizar_ot
    from app import app

    results = []
    def finish():
        with app.test_request_context():
            res = finalizar_ot(ot_id)
            results.append(res.status_code)

    t1 = threading.Thread(target=finish)
    t2 = threading.Thread(target=finish)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Ambos deben responder redirect (302)
    assert len(results) == 2

    # Verificar en BD que el estado sea 'Finalizada'
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM production_orders WHERE id = %s", (ot_id,))
            assert cur.fetchone()["status"] == "Finalizada"

            # El insumo solo debió descontarse UNA sola vez (4 unidades, restando 6)
            cur.execute("SELECT COALESCE(SUM(quantity), 0) as stock FROM inventory_movements WHERE product_id = %s", (p_in_id,))
            assert float(cur.fetchone()["stock"]) == 6.0

            # El producto final solo debió generarse UNA sola vez (2 unidades)
            cur.execute("SELECT COALESCE(SUM(quantity), 0) as stock FROM inventory_movements WHERE product_id = %s", (p_fin_id,))
            assert float(cur.fetchone()["stock"]) == 2.0

    # Cleanup
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM inventory_movements WHERE product_id IN (%s, %s)", (p_in_id, p_fin_id))
            cur.execute("DELETE FROM inventory_entry_items WHERE product_id = %s", (p_fin_id,))
            cur.execute("DELETE FROM inventory_entries WHERE order_number = 'OT-TEST-CONCUR'")
            cur.execute("DELETE FROM production_order_items WHERE production_order_id = %s", (ot_id,))
            cur.execute("DELETE FROM production_orders WHERE id = %s", (ot_id,))
            cur.execute("DELETE FROM products WHERE id IN (%s, %s)", (p_in_id, p_fin_id))
            # Limpiar items de prueba de page_data
            cur.execute("SELECT json FROM page_data WHERE key = 'inventory_items'")
            row = cur.fetchone()
            if row and row["json"]:
                import json
                items = json.loads(row["json"])
                filtered = [it for it in items if it.get("code") not in (sku_in, sku_fin) and not str(it.get("code", "")).startswith("FIN-OT-")]
                cur.execute("UPDATE page_data SET json = %s WHERE key = 'inventory_items'", (json.dumps(filtered),))
        conn.commit()
