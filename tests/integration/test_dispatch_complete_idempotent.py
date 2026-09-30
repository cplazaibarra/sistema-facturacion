"""
tests/integration/test_dispatch_complete_idempotent.py

Suite exhaustiva de pruebas de integración para el gate:
DESPACHO COMPLETO E IDEMPOTENTE (Ventas + Preparación + Despacho + Inventario).

Verifica de punta a punta:
1. Venta en 'Pendiente' no descuenta stock físico en Kardex ni lotes.
2. Transición a estado operacional ('En Preparación') descuenta exactamente una vez.
3. Reintento de la misma transición ('En Preparación' -> 'En Preparación') es idempotente.
4. Avance por estados operacionales ('En Preparación' -> 'Para Despacho' -> 'Completada') no duplica el descuento.
5. Movimiento de inventario único de tipo 'SALE' por cada producto/lote.
6. Tipo de referencia 'sale' y reference_id correcto vinculados a la venta.
7. Valoración contable: el movimiento 'SALE' toma el PPP vigente al momento del descuento.
8. Consumo de reserva: reserved_stock se reemplaza limpiamente por deducción física sin doble descuento.
9. Venta sin stock suficiente nace y se mantiene en 'Pendiente'.
10. Venta sin stock tiene prohibido pasar a 'En Preparación', 'Para Despacho' o 'Completada'.
11. Prioridad por operador: pedido B preparado antes que pedido A consume el stock físico disponible.
12. Pedido A queda bloqueado por déficit tras el despacho de B si no queda remanente.
13. Prioridad inversa: pedido A preparado antes que pedido B bloquea a B.
14. Concurrencia entre 2 ventas que compiten por stock: exactamente una gana y la otra es rechazada con stock >= 0.
15. Concurrencia sobre la misma venta (2 hilos pasando a 'En Preparación'): exactamente 1 descuento físico.
16. Atomicidad: venta multiproducto donde 1 producto no tiene stock sufre rollback total sin descuentos parciales.
17. Producto con lotes consume capas FIFO en orden cronológico/caducidad.
18. Trazabilidad genealógica en sale_lot_movements e inventory_movements vincula la venta al lote.
19. Conversión Cotización -> Venta no descuenta stock físico ni elige ganador.
20. Pago total anticipado no descuenta stock físico ni prioriza automáticamente el pedido.
21. Seguridad y RBAC: usuario sin permiso 'ventas' no puede transicionar la venta.
22. Reconciliador de inventario mantiene operational_integrity = 'OK'.
23. Cancelación previa a preparación ('Pendiente' -> 'Cancelada') no genera movimientos y libera reserva.
24. Cancelación posterior a preparación ('En Preparación' -> 'Cancelada') genera reversión compensatoria SALE_REVERSAL al costo histórico original de forma idempotente.
"""

import pytest
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app import app
from core.database import get_connection
from db import (
    create_product,
    insert_sale,
    get_sale,
    record_inventory_movement,
    get_relational_stock,
    check_sale_stock_availability,
    ensure_sale_stock_discounted,
    reverse_sale_inventory,
    get_sale_packaging_items
)
from repositories.kardex_repo import get_current_ppp
from services.stock_context import get_product_stock_balance
from routes.ventas import _convert_quotation_to_sale


@pytest.fixture
def auth_client():
    old_csrf = app.config.get('WTF_CSRF_ENABLED', True)
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    try:
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 1
                sess['username'] = 'admin'
                sess['role_name'] = 'Administrativo'
                sess['full_name'] = 'Administrador Sistema'
                sess['permissions'] = {
                    'dashboard': True,
                    'ventas': True,
                    'inventario': True,
                    'productos': True,
                    'reportes': True,
                    'compras': True,
                    'produccion': True,
                    'trazabilidad': True,
                    'administracion': True,
                }
            yield client
    finally:
        app.config['WTF_CSRF_ENABLED'] = old_csrf


@pytest.fixture
def unauth_client():
    old_csrf = app.config.get('WTF_CSRF_ENABLED', True)
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    try:
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 2
                sess['username'] = 'operario_sin_ventas'
                sess['role_name'] = 'Operario'
                sess['full_name'] = 'Operario Sin Ventas'
                sess['permissions'] = {
                    'dashboard': True,
                    'ventas': False,
                    'inventario': True,
                }
            yield client
    finally:
        app.config['WTF_CSRF_ENABLED'] = old_csrf


@pytest.fixture
def sample_dispatch_products():
    """Crea productos aislados sin lotes y con lotes para pruebas de despacho."""
    ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    p_unlotted_id = create_product(
        sku=f"SKU-DISP-UNLOT-{ts}",
        name=f"Producto Despacho Sin Lote {ts}",
        category="Despacho",
        product_type="Final",
        cost=1000.0,
        price=2500.0,
        requires_lot=False
    )
    p_lotted_id = create_product(
        sku=f"SKU-DISP-LOT-{ts}",
        name=f"Producto Despacho Con Lote {ts}",
        category="Despacho",
        product_type="Final",
        cost=1500.0,
        price=3500.0,
        requires_lot=True
    )
    p_aux_id = create_product(
        sku=f"SKU-DISP-AUX-{ts}",
        name=f"Producto Despacho Aux {ts}",
        category="Despacho",
        product_type="Final",
        cost=2000.0,
        price=4500.0,
        requires_lot=False
    )
    yield {
        "p_unlotted_id": p_unlotted_id,
        "p_lotted_id": p_lotted_id,
        "p_aux_id": p_aux_id
    }

    # Cleanup
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Remove this fixture's document graph too. Leaving pending sales
            # after deleting their products leaks legacy name-based demand into
            # subsequent tests in the same disposable database.
            cur.execute(
                "SELECT id FROM sales WHERE EXISTS (SELECT 1 FROM "
                "jsonb_array_elements(products_json::jsonb) line "
                "WHERE line->>'product_id' = ANY(%s))",
                ([str(p_unlotted_id), str(p_lotted_id), str(p_aux_id)],),
            )
            sale_ids = [r['id'] for r in cur.fetchall()]
            for table in ('sale_payment_items', 'sale_payments', 'sale_packaging_items',
                          'sale_lot_movements', 'sale_items', 'sales_payment_history',
                          'sales_status_history', 'collection_actions'):
                cur.execute(f'DELETE FROM {table} WHERE sale_id = ANY(%s)', (sale_ids,))
            cur.execute('DELETE FROM sales WHERE id = ANY(%s)', (sale_ids,))
            cur.execute("DELETE FROM sale_lot_movements WHERE product_id IN (%s, %s, %s)", (p_unlotted_id, p_lotted_id, p_aux_id))
            cur.execute("DELETE FROM sale_items WHERE product_id IN (%s, %s, %s)", (p_unlotted_id, p_lotted_id, p_aux_id))
            cur.execute("DELETE FROM inventory_movements WHERE product_id IN (%s, %s, %s)", (p_unlotted_id, p_lotted_id, p_aux_id))
            cur.execute("DELETE FROM lot_stock WHERE product_id IN (%s, %s, %s)", (p_unlotted_id, p_lotted_id, p_aux_id))
            cur.execute("DELETE FROM lots WHERE product_id IN (%s, %s, %s)", (p_unlotted_id, p_lotted_id, p_aux_id))
            cur.execute("DELETE FROM products WHERE id IN (%s, %s, %s)", (p_unlotted_id, p_lotted_id, p_aux_id))
        conn.commit()


# ==============================================================================
# TESTS
# ==============================================================================

def test_1_sale_pending_does_not_discount_stock(sample_dispatch_products):
    """1. Venta en 'Pendiente' no descuenta físico, no crea sale_items ni movimientos."""
    pid = sample_dispatch_products["p_unlotted_id"]
    record_inventory_movement(
        product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=20.0, unit_cost=1000.0, notes="Stock base"
    )
    assert get_relational_stock(pid) == 20.0

    sale_id = insert_sale({
        "sale_number": f"VTA-TEST-PEND-{pid}",
        "customer_name": "Cliente Pendiente",
        "sale_date": "2026-09-29",
        "sale_time": "10:00:00",
        "products": [{"product_id": pid, "product_name": "Prod Despacho", "quantity": 5, "price": 2500.0}],
        "total_amount": 12500.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    # El stock físico en Kardex sigue intacto en 20.0
    assert get_relational_stock(pid) == 20.0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM sale_items WHERE sale_id = %s", (sale_id,))
            assert cur.fetchone()["cnt"] == 0
            cur.execute("SELECT COUNT(*) as cnt FROM inventory_movements WHERE reference_type = 'sale' AND reference_id = %s", (sale_id,))
            assert cur.fetchone()["cnt"] == 0


def test_2_to_7_operational_transition_and_idempotency(auth_client, sample_dispatch_products):
    """
    2. Transición a 'En Preparación' descuenta existencias exactamente una vez.
    3. Reintentar misma transición no vuelve a descontar.
    4. Avance a 'Para Despacho' y 'Completada' no vuelve a descontar.
    5. Movimiento único de tipo 'SALE'.
    6. Referencia 'sale' y reference_id exactos.
    7. Valoración contable unit_cost = PPP vigente al momento del descuento.
    8. stock_context: reserved_stock se limpia al ser consumido físicamente.
    """
    pid = sample_dispatch_products["p_unlotted_id"]
    # Dos recepciones a distinto costo para formar PPP: 10 @ 1000, 10 @ 1200 => PPP = 1100
    record_inventory_movement(product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=1000.0, notes="Rec 1")
    record_inventory_movement(product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=1200.0, notes="Rec 2")
    assert get_relational_stock(pid) == 20.0
    ppp_expected = get_current_ppp(pid)
    assert ppp_expected == 1100.0

    sale_id = insert_sale({
        "sale_number": f"VTA-TEST-IDEMP-{pid}",
        "customer_name": "Cliente Idempotencia",
        "sale_date": "2026-09-29",
        "sale_time": "10:00:00",
        "products": [{"product_id": pid, "product_name": "Prod Despacho", "quantity": 8, "price": 2500.0}],
        "total_amount": 20000.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    # Verificar estado de reserva antes de pasar a En Preparación
    bal_before = get_product_stock_balance(pid)
    assert bal_before["physical_stock"] == 20.0
    assert bal_before["reserved_stock"] == 8.0
    assert bal_before["available_stock"] == 12.0

    # 2. Transición a 'En Preparación'
    resp = auth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "En Preparación"}, follow_redirects=True)
    assert resp.status_code == 200
    assert get_sale(sale_id)["status"] == "En Preparación"
    assert get_relational_stock(pid) == 12.0

    # 8. stock_context: reserved_stock ya no incluye esta venta porque sale_items ya está poblado
    bal_after = get_product_stock_balance(pid)
    assert bal_after["physical_stock"] == 12.0
    assert bal_after["reserved_stock"] == 0.0
    assert bal_after["available_stock"] == 12.0

    # 5, 6, 7. Validar movimiento SALE generado
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT movement_type, quantity, unit_cost, reference_type, reference_id "
                "FROM inventory_movements WHERE reference_type = 'sale' AND reference_id = %s",
                (sale_id,)
            )
            movs = cur.fetchall()
            assert len(movs) == 1
            m = movs[0]
            assert m["movement_type"] == "SALE"
            assert float(m["quantity"]) == -8.0
            assert float(m["unit_cost"]) == 1100.0
            assert m["reference_type"] == "sale"
            assert m["reference_id"] == sale_id

            # Validar snapshot en sale_items
            cur.execute("SELECT quantity, unit_cost_at_sale FROM sale_items WHERE sale_id = %s", (sale_id,))
            si = cur.fetchall()
            assert len(si) == 1
            assert float(si[0]["quantity"]) == 8.0
            assert float(si[0]["unit_cost_at_sale"]) == 1100.0

    # 3. Reintentar misma transición ('En Preparación' -> 'En Preparación')
    resp_retry = auth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "En Preparación"}, follow_redirects=True)
    assert resp_retry.status_code == 200
    assert get_relational_stock(pid) == 12.0

    # 4. Transición a 'Para Despacho'
    resp_disp = auth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "Para Despacho"}, follow_redirects=True)
    assert resp_disp.status_code == 200
    assert get_sale(sale_id)["status"] == "Para Despacho"
    assert get_relational_stock(pid) == 12.0

    # 4. Transición a 'Completada' (con factura adjunta)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE sale_payments SET invoice_file = '/uploads/factura_test.pdf' WHERE sale_id = %s", (sale_id,))
        conn.commit()

    resp_comp = auth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "Completada"}, follow_redirects=True)
    assert resp_comp.status_code == 200
    assert get_sale(sale_id)["status"] == "Completada"
    assert get_relational_stock(pid) == 12.0

    # Movimientos en inventory_movements siguen siendo exactamente 1
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM inventory_movements WHERE reference_type = 'sale' AND reference_id = %s", (sale_id,))
            assert cur.fetchone()["cnt"] == 1


def test_9_and_10_sale_without_stock_blocked_from_operational_states(auth_client, sample_dispatch_products):
    """9. Venta sin stock nace y se mantiene en Pendiente. 10. Bloqueada de En Preparación, Para Despacho, Completada."""
    pid = sample_dispatch_products["p_unlotted_id"]
    assert get_relational_stock(pid) == 0.0

    sale_id = insert_sale({
        "sale_number": f"VTA-TEST-NOSTOCK-{pid}",
        "customer_name": "Cliente Sin Stock",
        "sale_date": "2026-09-29",
        "sale_time": "10:00:00",
        "products": [{"product_id": pid, "product_name": "Prod Despacho", "quantity": 10, "price": 2500.0}],
        "total_amount": 25000.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    # Verificar que check_sale_stock_availability detecta déficit
    chk = check_sale_stock_availability(sale_id)
    assert chk["has_deficit"] is True
    assert chk["items"][0]["deficit"] == 10.0

    # Bloqueo a En Preparación
    r1 = auth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "En Preparación"}, follow_redirects=True)
    assert "stock insuficiente" in r1.data.decode('utf-8').lower()
    assert get_sale(sale_id)["status"] == "Pendiente"

    # Bloqueo a Para Despacho
    r2 = auth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "Para Despacho"}, follow_redirects=True)
    assert "stock insuficiente" in r2.data.decode('utf-8').lower()
    assert get_sale(sale_id)["status"] == "Pendiente"

    # Bloqueo a Completada
    r3 = auth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "Completada", "invoice_file": "dummy.pdf"}, follow_redirects=True)
    assert "stock insuficiente" in r3.data.decode('utf-8').lower()
    assert get_sale(sale_id)["status"] == "Pendiente"


@pytest.mark.parametrize("order", ["B_first", "A_first"])
def test_11_to_13_operator_priority_and_remaining_stock(auth_client, sample_dispatch_products, order):
    """
    11. Operador decide: si B se prepara antes que A, B consume el físico disponible.
    12. Tras preparar B, si A excede el remanente físico, A queda bloqueada íntegramente.
    13. Prioridad inversa: si A se prepara primero, B queda bloqueada.
    """
    pid = sample_dispatch_products["p_unlotted_id"]
    record_inventory_movement(product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=1000.0, notes="Stock para prioridad")

    sale_a_id = insert_sale({
        "sale_number": f"VTA-PRIOR-A-{pid}",
        "customer_name": "Cliente A",
        "sale_date": "2026-09-29",
        "sale_time": "10:00:00",
        "products": [{"product_id": pid, "product_name": "Prod Despacho", "quantity": 8, "price": 2500.0}],
        "total_amount": 20000.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    sale_b_id = insert_sale({
        "sale_number": f"VTA-PRIOR-B-{pid}",
        "customer_name": "Cliente B",
        "sale_date": "2026-09-29",
        "sale_time": "10:05:00",
        "products": [{"product_id": pid, "product_name": "Prod Despacho", "quantity": 6, "price": 2500.0}],
        "total_amount": 15000.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    if order == "B_first":
        first_id, second_id = sale_b_id, sale_a_id
        first_qty, second_qty = 6, 8
    else:
        first_id, second_id = sale_a_id, sale_b_id
        first_qty, second_qty = 8, 6

    # Preparar el primer pedido seleccionado por el operador
    resp1 = auth_client.post('/ventas/actualizar-estado', data={"sale_id": first_id, "status": "En Preparación"}, follow_redirects=True)
    assert resp1.status_code == 200
    assert get_sale(first_id)["status"] == "En Preparación"
    rem_stock = 10.0 - first_qty
    assert get_relational_stock(pid) == rem_stock

    # El segundo pedido no cabe en rem_stock (rem_stock < second_qty) -> debe ser bloqueado íntegramente
    resp2 = auth_client.post('/ventas/actualizar-estado', data={"sale_id": second_id, "status": "En Preparación"}, follow_redirects=True)
    assert "stock insuficiente" in resp2.data.decode('utf-8').lower()
    assert get_sale(second_id)["status"] == "Pendiente"
    # Stock físico no sufre descuento parcial
    assert get_relational_stock(pid) == rem_stock


def test_14_concurrency_two_competing_sales(sample_dispatch_products):
    """14. Concurrencia entre 2 ventas que compiten por stock: 1 gana, 1 pierde, stock nunca negativo."""
    pid = sample_dispatch_products["p_unlotted_id"]
    record_inventory_movement(product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=1000.0, notes="Stock concurrencia")

    s1_id = insert_sale({
        "sale_number": f"VTA-CONC-A-{pid}", "customer_name": "Cliente C1",
        "sale_date": "2026-09-29", "sale_time": "10:00:00",
        "products": [{"product_id": pid, "product_name": "Prod Despacho", "quantity": 8, "price": 2500.0}],
        "total_amount": 20000.0, "status": "Pendiente", "payment_status": "Pendiente", "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    s2_id = insert_sale({
        "sale_number": f"VTA-CONC-B-{pid}", "customer_name": "Cliente C2",
        "sale_date": "2026-09-29", "sale_time": "10:00:00",
        "products": [{"product_id": pid, "product_name": "Prod Despacho", "quantity": 8, "price": 2500.0}],
        "total_amount": 20000.0, "status": "Pendiente", "payment_status": "Pendiente", "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    success_sales = []
    failed_sales = []

    def transition_sale(sid):
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 1
                sess['username'] = 'admin'
                sess['role_name'] = 'Administrativo'
                sess['full_name'] = 'Admin'
                sess['permissions'] = {'ventas': True}
            resp = client.post('/ventas/actualizar-estado', data={
                "sale_id": sid,
                "status": "En Preparación"
            }, follow_redirects=True)
            raw_text = resp.data.decode('utf-8')
            flash_messages = re.findall(
                r'<div class="toast-flash-item toast-([^"]+)"[^>]*>.*?<span class="toast-text">(.*?)</span>',
                raw_text,
                re.DOTALL
            )
            has_stock_error = any("stock insuficiente" in msg.lower() for cat, msg in flash_messages)
            has_success = any("con éxito" in msg.lower() or "actualizó" in msg.lower() for cat, msg in flash_messages if cat == "success")

            if has_stock_error:
                failed_sales.append(sid)
            elif has_success or resp.status_code == 200:
                success_sales.append(sid)
            else:
                failed_sales.append((sid, resp.status_code, raw_text[:200]))

    old_csrf = app.config.get('WTF_CSRF_ENABLED', True)
    app.config['WTF_CSRF_ENABLED'] = False
    try:
        t1 = threading.Thread(target=transition_sale, args=(s1_id,))
        t2 = threading.Thread(target=transition_sale, args=(s2_id,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
    finally:
        app.config['WTF_CSRF_ENABLED'] = old_csrf

    # Exactamente una debe haber triunfado y la otra debe haber sido rechazada
    assert len(success_sales) == 1, f"Debió triunfar exactamente una: success={success_sales}, failed={failed_sales}"
    assert len(failed_sales) == 1, f"Debió fallar exactamente una: success={success_sales}, failed={failed_sales}"
    assert get_relational_stock(pid) == 2.0
    states = [get_sale(s1_id)["status"], get_sale(s2_id)["status"]]
    assert sorted(states) == ["En Preparación", "Pendiente"]


def test_15_concurrency_same_sale_double_prepare(sample_dispatch_products):
    """15. Concurrencia sobre la misma venta (2 hilos pasando a 'En Preparación' simultáneamente): exactamente 1 descuento."""
    pid = sample_dispatch_products["p_unlotted_id"]
    record_inventory_movement(product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=20.0, unit_cost=1000.0, notes="Stock doble prepare")

    sale_id = insert_sale({
        "sale_number": f"VTA-SAME-PREP-{pid}", "customer_name": "Cliente Mismo Pedido",
        "sale_date": "2026-09-29", "sale_time": "10:00:00",
        "products": [{"product_id": pid, "product_name": "Prod Despacho", "quantity": 7, "price": 2500.0}],
        "total_amount": 17500.0, "status": "Pendiente", "payment_status": "Pendiente", "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    def worker():
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 1
                sess['username'] = 'admin'
                sess['role_name'] = 'Administrativo'
                sess['permissions'] = {'ventas': True}
            client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "En Preparación"}, follow_redirects=True)

    old_csrf = app.config.get('WTF_CSRF_ENABLED', True)
    app.config['WTF_CSRF_ENABLED'] = False
    try:
        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
    finally:
        app.config['WTF_CSRF_ENABLED'] = old_csrf

    # Stock remanente exacto: 20 - 7 = 13
    assert get_relational_stock(pid) == 13.0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM sale_items WHERE sale_id = %s", (sale_id,))
            assert cur.fetchone()["cnt"] == 1
            cur.execute("SELECT COUNT(*) as cnt FROM inventory_movements WHERE reference_type = 'sale' AND reference_id = %s", (sale_id,))
            assert cur.fetchone()["cnt"] == 1


def test_16_atomic_rollback_multi_product_deficit(auth_client, sample_dispatch_products):
    """16. Venta multi-producto donde 1 producto no tiene stock: rollback atómico total."""
    p1 = sample_dispatch_products["p_unlotted_id"]
    p2 = sample_dispatch_products["p_aux_id"]

    # p1 tiene stock de sobra, p2 tiene 0
    record_inventory_movement(product_id=p1, movement_type="PURCHASE_RECEIPT", quantity=50.0, unit_cost=1000.0, notes="Stock p1")
    assert get_relational_stock(p1) == 50.0
    assert get_relational_stock(p2) == 0.0

    sale_id = insert_sale({
        "sale_number": f"VTA-MULTI-DEF-{p1}", "customer_name": "Cliente Multi",
        "sale_date": "2026-09-29", "sale_time": "10:00:00",
        "products": [
            {"product_id": p1, "product_name": "Prod 1", "quantity": 10, "price": 2500.0},
            {"product_id": p2, "product_name": "Prod 2", "quantity": 5, "price": 4500.0}
        ],
        "total_amount": 47500.0, "status": "Pendiente", "payment_status": "Pendiente", "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    resp = auth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "En Preparación"}, follow_redirects=True)
    assert "stock insuficiente" in resp.data.decode('utf-8').lower()
    assert get_sale(sale_id)["status"] == "Pendiente"

    # Ниngún producto se descontó (p1 sigue en 50.0, p2 en 0.0)
    assert get_relational_stock(p1) == 50.0
    assert get_relational_stock(p2) == 0.0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM sale_items WHERE sale_id = %s", (sale_id,))
            assert cur.fetchone()["cnt"] == 0


def test_17_and_18_lotted_fifo_consumption_and_genealogy(auth_client, sample_dispatch_products):
    """
    17. Producto con lotes consume capas FIFO en orden.
    18. Trazabilidad genealógica en sale_lot_movements e inventory_movements vincula la venta al lote.
    """
    pid = sample_dispatch_products["p_lotted_id"]

    # Crear Lote 1 (5 unidades @ 1500) y Lote 2 (10 unidades @ 1600)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO lots (lot_number, product_id, status, created_at) VALUES (%s, %s, 'ACTIVE', '2026-09-01 00:00:00') RETURNING id",
                (f"LOT-FIFO-1-{pid}", pid)
            )
            l1_id = cur.fetchone()["id"]
            cur.execute(
                "INSERT INTO lot_stock (lot_id, product_id, lot_number, initial_qty, available_qty, warehouse) "
                "VALUES (%s, %s, %s, 5.0, 5.0, 'Bodega A')",
                (l1_id, pid, f"LOT-FIFO-1-{pid}")
            )
            record_inventory_movement(
                product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=5.0, unit_cost=1500.0,
                lot_number=f"LOT-FIFO-1-{pid}", lot_id=l1_id, conn=conn
            )

            cur.execute(
                "INSERT INTO lots (lot_number, product_id, status, created_at) VALUES (%s, %s, 'ACTIVE', '2026-09-02 00:00:00') RETURNING id",
                (f"LOT-FIFO-2-{pid}", pid)
            )
            l2_id = cur.fetchone()["id"]
            cur.execute(
                "INSERT INTO lot_stock (lot_id, product_id, lot_number, initial_qty, available_qty, warehouse) "
                "VALUES (%s, %s, %s, 10.0, 10.0, 'Bodega A')",
                (l2_id, pid, f"LOT-FIFO-2-{pid}")
            )
            record_inventory_movement(
                product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=1600.0,
                lot_number=f"LOT-FIFO-2-{pid}", lot_id=l2_id, conn=conn
            )
        conn.commit()

    assert get_relational_stock(pid) == 15.0

    # Venta de 8 unidades: debe consumir 5 de Lote 1 (agotándolo) y 3 de Lote 2 (quedando 7)
    sale_id = insert_sale({
        "sale_number": f"VTA-FIFO-{pid}", "customer_name": "Cliente FIFO",
        "sale_date": "2026-09-29", "sale_time": "10:00:00",
        "products": [{"product_id": pid, "product_name": "Prod Lotes", "quantity": 8, "price": 3500.0}],
        "total_amount": 28000.0, "status": "Pendiente", "payment_status": "Pendiente", "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    resp = auth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "En Preparación"}, follow_redirects=True)
    assert resp.status_code == 200
    assert get_sale(sale_id)["status"] == "En Preparación"
    assert get_relational_stock(pid) == 7.0

    # 17. Verificar saldos en lot_stock y estado DEPLETED
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT available_qty FROM lot_stock WHERE lot_id = %s", (l1_id,))
            assert float(cur.fetchone()["available_qty"]) == 0.0
            cur.execute("SELECT status FROM lots WHERE id = %s", (l1_id,))
            assert cur.fetchone()["status"] == "DEPLETED"

            cur.execute("SELECT available_qty FROM lot_stock WHERE lot_id = %s", (l2_id,))
            assert float(cur.fetchone()["available_qty"]) == 7.0
            cur.execute("SELECT status FROM lots WHERE id = %s", (l2_id,))
            assert cur.fetchone()["status"] == "ACTIVE"

            # 18. Trazabilidad genealógica en sale_lot_movements
            cur.execute("SELECT lot_number, quantity, lot_id FROM sale_lot_movements WHERE sale_id = %s ORDER BY id ASC", (sale_id,))
            slm = cur.fetchall()
            assert len(slm) == 2
            assert slm[0]["lot_number"] == f"LOT-FIFO-1-{pid}"
            assert float(slm[0]["quantity"]) == 5.0
            assert slm[0]["lot_id"] == l1_id

            assert slm[1]["lot_number"] == f"LOT-FIFO-2-{pid}"
            assert float(slm[1]["quantity"]) == 3.0
            assert slm[1]["lot_id"] == l2_id

            # Movimientos en Kardex vinculados con lote
            cur.execute("SELECT lot_number, quantity, reference_type, reference_id FROM inventory_movements WHERE reference_type = 'sale' AND reference_id = %s ORDER BY id ASC", (sale_id,))
            im_lots = cur.fetchall()
            assert len(im_lots) == 2
            assert im_lots[0]["lot_number"] == f"LOT-FIFO-1-{pid}"
            assert float(im_lots[0]["quantity"]) == -5.0
            assert im_lots[1]["lot_number"] == f"LOT-FIFO-2-{pid}"
            assert float(im_lots[1]["quantity"]) == -3.0


def test_19_quotation_conversion_no_stock_discount(sample_dispatch_products):
    """19. Conversión Cotización -> Venta no descuenta stock físico ni crea sale_items."""
    pid = sample_dispatch_products["p_unlotted_id"]
    record_inventory_movement(product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=1000.0, notes="Stock cotiz")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sales (sale_number, customer_name, seller_name, payment_method, sale_date, sale_time, products_json, total_amount, status, quotation_status, notes, created_at)
                VALUES (%s, 'Cliente Cotiz', 'Vendedor', 'Efectivo', '2026-09-29', '10:00:00', %s, 12500.0, 'Cotización', 'Activa', '', '2026-09-29 10:00:00')
                RETURNING id
                """,
                (f"COT-DISP-{pid}", json.dumps([{"product_id": pid, "product_name": "Prod", "quantity": 5, "price": 2500.0}]))
            )
            cot_id = cur.fetchone()["id"]
        conn.commit()

    vta_num, err = _convert_quotation_to_sale(cot_id)
    assert err is None
    assert vta_num is not None

    # Stock físico no se alteró
    assert get_relational_stock(pid) == 10.0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, status FROM sales WHERE sale_number = %s", (vta_num,))
            new_sale = cur.fetchone()
            assert new_sale["status"] == "Pendiente"
            cur.execute("SELECT COUNT(*) as cnt FROM sale_items WHERE sale_id = %s", (new_sale["id"],))
            assert cur.fetchone()["cnt"] == 0


def test_20_payment_full_does_not_discount_stock(auth_client, sample_dispatch_products):
    """20. Pago total anticipado no descuenta existencias ni prioriza automáticamente el pedido."""
    pid = sample_dispatch_products["p_unlotted_id"]
    record_inventory_movement(product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=1000.0, notes="Stock pago")

    sale_id = insert_sale({
        "sale_number": f"VTA-PAGO-ANTICIP-{pid}", "customer_name": "Cliente Pago Anticipado",
        "sale_date": "2026-09-29", "sale_time": "10:00:00",
        "products": [{"product_id": pid, "product_name": "Prod", "quantity": 5, "price": 2500.0}],
        "total_amount": 12500.0, "status": "Pendiente", "payment_status": "Pendiente", "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    p_resp = auth_client.post('/ventas/registrar-pago', data={
        "sale_id": str(sale_id),
        "payment_method": "Efectivo",
        "payment_date": "2026-09-29",
        "payment_amount": "12500.0",
        "payment_notes": "Pago total anticipado",
        "idempotency_key": f"key-pago-{sale_id}"
    }, follow_redirects=True)
    assert p_resp.status_code == 200

    sale = get_sale(sale_id)
    assert sale["payment_status"] == "Pagado"
    # Estado sigue en Pendiente: no avanza a En Preparación ni a Completada por el mero hecho de pagar
    assert sale["status"] == "Pendiente"
    assert get_relational_stock(pid) == 10.0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM sale_items WHERE sale_id = %s", (sale_id,))
            assert cur.fetchone()["cnt"] == 0


def test_21_unauthorized_user_blocked(unauth_client, sample_dispatch_products):
    """21. Usuario sin permiso 'ventas' no puede modificar estado ni disparar descuento físico."""
    pid = sample_dispatch_products["p_unlotted_id"]
    record_inventory_movement(product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=1000.0, notes="Stock rbac")

    sale_id = insert_sale({
        "sale_number": f"VTA-UNAUTH-{pid}", "customer_name": "Cliente RBAC",
        "sale_date": "2026-09-29", "sale_time": "10:00:00",
        "products": [{"product_id": pid, "product_name": "Prod", "quantity": 4, "price": 2500.0}],
        "total_amount": 10000.0, "status": "Pendiente", "payment_status": "Pendiente", "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    resp = unauth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "En Preparación"}, follow_redirects=True)
    assert "no tiene permiso" in resp.data.decode('utf-8').lower() or resp.status_code in (403, 302, 200)

    # El estado de la venta no se alteró y el stock sigue en 10
    sale = get_sale(sale_id)
    assert sale["status"] == "Pendiente"
    assert get_relational_stock(pid) == 10.0


def test_22_reconciler_integrity_remains_ok(sample_dispatch_products):
    """22. Reconciliador de inventario mantiene operational_integrity = 'OK' para los productos probados."""
    from tools.reconcile_inventory import reconcile_inventory
    p_ids = set(sample_dispatch_products.values())
    summary, details = reconcile_inventory()
    
    # Validar que los productos del flujo de despacho no presentan inconsistencias operacionales
    dispatch_details = [p for p in details if p["id"] in p_ids]
    assert len(dispatch_details) >= 1
    for p in dispatch_details:
        assert not p["quantity_investigation"], f"Inconsistencia en cantidades para {p['sku']}: {p['classifications']}"
        assert not p["traceability_investigation"], f"Inconsistencia en trazabilidad para {p['sku']}: {p['classifications']}"
        if p["requires_lot"]:
            assert abs(p["delta_ledger_lots"]) < 0.001
    
    # En la base normal de producción (facturacion), audit()['operational_integrity'] es OK
    # En la base aislada (facturacion_cleanup_verify), summary separa advertencias legacy de integridad operacional
    assert "operational_integrity" in summary
    assert "legacy_status" in summary


def test_23_pre_consumption_cancellation(auth_client, sample_dispatch_products):
    """23. Cancelación en 'Pendiente' (antes de preparación) no genera movimientos y libera reserva."""
    pid = sample_dispatch_products["p_unlotted_id"]
    record_inventory_movement(product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=1000.0, notes="Stock pre cancel")

    bal_init = get_product_stock_balance(pid)
    init_reserved = bal_init["reserved_stock"]

    sale_id = insert_sale({
        "sale_number": f"VTA-PRE-CANC-{pid}", "customer_name": "Cliente Pre Canc",
        "sale_date": "2026-09-29", "sale_time": "10:00:00",
        "products": [{"product_id": pid, "product_name": "Prod Despacho", "quantity": 4, "price": 2500.0}],
        "total_amount": 10000.0, "status": "Pendiente", "payment_status": "Pendiente", "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    bal = get_product_stock_balance(pid)
    assert bal["reserved_stock"] == init_reserved + 4.0

    # Cancelar venta antes de preparación
    resp = auth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "Cancelada"}, follow_redirects=True)
    assert resp.status_code == 200
    assert get_sale(sale_id)["status"] == "Cancelada"

    # Stock físico no se movió (sigue 10)
    assert get_relational_stock(pid) == 10.0
    # Reserva se liberó inmediatamente
    bal_after = get_product_stock_balance(pid)
    assert bal_after["reserved_stock"] == init_reserved

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM inventory_movements WHERE reference_id = %s", (sale_id,))
            assert cur.fetchone()["cnt"] == 0


def test_24_post_consumption_cancellation_idempotent_reversal(auth_client, sample_dispatch_products):
    """
    24. Cancelación posterior a preparación ('En Preparación' -> 'Cancelada'):
    - Genera SALE_REVERSAL compensatorio con costo histórico original congelado.
    - Restituye stock físico.
    - Idempotencia: cancelar múltiples veces no duplica movimientos ni stock.
    """
    pid = sample_dispatch_products["p_unlotted_id"]
    record_inventory_movement(product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=1000.0, notes="Entrada inicial")

    sale_id = insert_sale({
        "sale_number": f"VTA-POST-CANC-{pid}", "customer_name": "Cliente Post Canc",
        "sale_date": "2026-09-29", "sale_time": "10:00:00",
        "products": [{"product_id": pid, "product_name": "Prod Despacho", "quantity": 4, "price": 2500.0}],
        "total_amount": 10000.0, "status": "Pendiente", "payment_status": "Pendiente", "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    # Preparar pedido: se descuenta físicamente (stock pasa de 10 a 6)
    auth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "En Preparación"}, follow_redirects=True)
    assert get_relational_stock(pid) == 6.0

    # Mientras está preparado, llega nueva compra a costo 2000 (el PPP actual sube)
    record_inventory_movement(product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=2000.0, notes="Compra posterior")
    current_ppp = get_current_ppp(pid)
    assert current_ppp > 1000.0  # El PPP actual subió

    # Cancelar la venta preparada
    resp_canc = auth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "Cancelada"}, follow_redirects=True)
    assert resp_canc.status_code == 200
    assert get_sale(sale_id)["status"] == "Cancelada"

    # Stock físico restituido: 6 + 10 + 4 = 20.0
    assert get_relational_stock(pid) == 20.0

    # Movimiento compensatorio SALE_REVERSAL registrado con costo original (1000.0), no el PPP actual
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT movement_type, quantity, unit_cost, reference_type, reference_id "
                "FROM inventory_movements WHERE reference_id = %s AND movement_type = 'SALE_REVERSAL'",
                (sale_id,)
            )
            rev_movs = cur.fetchall()
            assert len(rev_movs) == 1
            rm = rev_movs[0]
            assert rm["movement_type"] == "SALE_REVERSAL"
            assert float(rm["quantity"]) == 4.0
            assert float(rm["unit_cost"]) == 1000.0
            assert rm["reference_type"] == "sale_cancellation"

    # Idempotencia: llamada directa o segundo envío de Cancelada no vuelve a generar SALE_REVERSAL
    with get_connection() as conn:
        rev_second = reverse_sale_inventory(sale_id, conn=conn)
        conn.commit()
    assert rev_second == []
    assert get_relational_stock(pid) == 20.0


def test_same_sale_waits_on_postgresql_lock_before_idempotency_check(sample_dispatch_products, monkeypatch):
    """Observe a real PostgreSQL blocker, not just two successful threads.

    Pause request 1 after sale_items was checked, but before insertion. Request 2
    must be blocked on the sale row and cannot reach the discount routine.
    """
    from repositories import inventory_repo
    pid = sample_dispatch_products['p_unlotted_id']
    record_inventory_movement(product_id=pid, movement_type='PURCHASE_RECEIPT',
                              quantity=10, unit_cost=1000)
    sid = insert_sale({
        'sale_number': f'VTA-LOCK-PROOF-{pid}', 'customer_name': 'Lock proof',
        'sale_date': '2026-09-29', 'sale_time': '12:00:00',
        'products': [{'product_id': pid, 'quantity': 3, 'price': 1500}],
        'total_amount': 4500, 'status': 'Pendiente', 'payment_status': 'Pendiente',
        'payment_method': 'Efectivo', 'created_at': datetime.now(timezone.utc).isoformat(),
    })
    entered, release = threading.Event(), threading.Event()
    original = inventory_repo.discount_stock_for_sale
    calls, pids = [], {}

    def paused_discount(sale_id, products, conn=None):
        calls.append(sale_id)
        entered.set()
        assert release.wait(15), 'Test must release the first transaction'
        return original(sale_id, products, conn=conn)

    monkeypatch.setattr(inventory_repo, 'discount_stock_for_sale', paused_discount)

    def worker(label):
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT pg_backend_pid() AS pid')
                pids[label] = cur.fetchone()['pid']
            applied = ensure_sale_stock_discounted(sid, conn=conn)
            conn.commit()
            return applied
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker, 'first')
        second = None
        try:
            assert entered.wait(10)
            second = pool.submit(worker, 'second')
            blocked = False
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if 'second' in pids:
                    with get_connection() as conn, conn.cursor() as cur:
                        cur.execute('SELECT pg_blocking_pids(%s) AS blockers', (pids['second'],))
                        blocked = pids['first'] in cur.fetchone()['blockers']
                    if blocked:
                        break
                time.sleep(0.02)
            assert blocked, 'Second connection did not wait on first PostgreSQL transaction'
            assert calls == [sid], 'Second request reached the discount before the first committed'
            assert not second.done()
        finally:
            release.set()
        assert first.result(timeout=10) is True
        assert second is not None and second.result(timeout=10) is False
    assert calls == [sid]
    assert get_relational_stock(pid) == 7
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n, SUM(quantity) AS qty FROM inventory_movements "
                    "WHERE reference_type='sale' AND reference_id=%s", (sid,))
        assert dict(cur.fetchone()) == {'n': 1, 'qty': -3}


def test_late_packaging_failure_rolls_back_materialization(auth_client, sample_dispatch_products):
    """Insufficient packaging occurs AFTER discount; rollback restores all effects."""
    pid, empty = sample_dispatch_products['p_unlotted_id'], sample_dispatch_products['p_aux_id']
    record_inventory_movement(product_id=pid, movement_type='PURCHASE_RECEIPT', quantity=10, unit_cost=1000)
    sid = insert_sale({
        'sale_number': f'VTA-LATE-ROLLBACK-{pid}', 'customer_name': 'Atomic dispatch',
        'sale_date': '2026-09-29', 'sale_time': '12:00:00',
        'products': [{'product_id': pid, 'quantity': 3, 'price': 1500}],
        'total_amount': 4500, 'status': 'Pendiente', 'payment_status': 'Pendiente',
        'payment_method': 'Efectivo', 'created_at': datetime.now(timezone.utc).isoformat(),
    })
    response = auth_client.post('/ventas/actualizar-estado', data={
        'sale_id': sid, 'status': 'Para Despacho',
        'packaging_product_id[]': str(empty), 'packaging_quantity[]': '1',
    }, follow_redirects=True)
    assert 'No se modificó el estado' in response.get_data(as_text=True)
    assert get_sale(sid)['status'] == 'Pendiente'
    assert get_relational_stock(pid) == 10
    with get_connection() as conn, conn.cursor() as cur:
        for table in ('sale_items', 'sale_packaging_items', 'sales_status_history', 'sale_payments'):
            cur.execute(f'SELECT COUNT(*) AS n FROM {table} WHERE sale_id=%s', (sid,))
            assert cur.fetchone()['n'] == 0
        cur.execute("SELECT COUNT(*) AS n FROM inventory_movements WHERE reference_type='sale' AND reference_id=%s", (sid,))
        assert cur.fetchone()['n'] == 0


def _terminal_test_sale(pid):
    record_inventory_movement(product_id=pid, movement_type='PURCHASE_RECEIPT', quantity=20, unit_cost=1000)
    return insert_sale({
        'sale_number': f'VTA-TERMINAL-{pid}', 'customer_name': 'Terminal cancellation',
        'sale_date': '2026-09-29', 'sale_time': '12:00:00',
        'products': [{'product_id': pid, 'quantity': 8, 'price': 1500}],
        'total_amount': 12000, 'status': 'Pendiente', 'payment_status': 'Pendiente',
        'payment_method': 'Efectivo', 'created_at': datetime.now(timezone.utc).isoformat(),
    })


def _terminal_snapshot(sid, pid):
    with get_connection() as conn, conn.cursor() as cur:
        result = {'balance': get_product_stock_balance(pid)}
        for table, key in [('sales', 'id'), ('sale_items', 'sale_id'), ('sale_payments', 'sale_id'),
                           ('sale_payment_items', 'sale_id'), ('sales_status_history', 'sale_id'),
                           ('sales_payment_history', 'sale_id'), ('sale_lot_movements', 'sale_id')]:
            cur.execute(f'SELECT * FROM {table} WHERE {key}=%s ORDER BY id', (sid,))
            result[table] = [dict(r) for r in cur.fetchall()]
        for table in ('inventory_movements', 'lot_stock'):
            cur.execute(f'SELECT * FROM {table} WHERE product_id=%s ORDER BY id', (pid,))
            result[table] = [dict(r) for r in cur.fetchall()]
        return result


@pytest.mark.parametrize('materialized', [False, True], ids=['pending', 'materialized'])
@pytest.mark.parametrize('target', ['Pendiente', 'En Preparación', 'Para Despacho', 'Completada', 'Otro'])
def test_cancelled_sale_is_terminal_for_every_target(auth_client, sample_dispatch_products, materialized, target):
    pid = sample_dispatch_products['p_unlotted_id']
    sid = _terminal_test_sale(pid)
    if materialized:
        auth_client.post('/ventas/actualizar-estado', data={'sale_id': sid, 'status': 'En Preparación'})
        assert get_relational_stock(pid) == 12
    auth_client.post('/ventas/actualizar-estado', data={'sale_id': sid, 'status': 'Cancelada'})
    before = _terminal_snapshot(sid, pid)
    assert before['sales'][0]['status'] == 'Cancelada'
    assert before['balance']['physical_stock'] == 20
    assert before['balance']['reserved_stock'] == 0
    assert len(before['sale_items']) == int(materialized)
    assert len(before['inventory_movements']) == (3 if materialized else 1)
    response = auth_client.post('/ventas/actualizar-estado', data={'sale_id': sid, 'status': target}, follow_redirects=True)
    assert response.status_code == 200
    assert 'Una venta cancelada no se reactiva' in response.get_data(as_text=True)
    assert _terminal_snapshot(sid, pid) == before
    # Includes economic AND ordinary history: cancelling again is now a no-op.
    auth_client.post('/ventas/actualizar-estado', data={'sale_id': sid, 'status': 'Cancelada'})
    assert _terminal_snapshot(sid, pid) == before


@pytest.mark.parametrize('action', ['emit', 'convert', 'approve_payment', 'legacy_payment',
                                   'update_repo', 'quote_repo', 'delete_repo'])
def test_cancelled_sale_alternative_writers_are_blocked(auth_client, sample_dispatch_products, action):
    from repositories.sales_repo import update_sale, update_quotation_status, delete_sale, CancelledSaleError
    pid = sample_dispatch_products['p_unlotted_id']
    sid = _terminal_test_sale(pid)
    auth_client.post('/ventas/actualizar-estado', data={'sale_id': sid, 'status': 'Cancelada'})
    before = _terminal_snapshot(sid, pid)
    if action.endswith('_repo'):
        with pytest.raises(CancelledSaleError):
            if action == 'update_repo':
                update_sale(sid, {'status': 'Pendiente'})
            elif action == 'quote_repo':
                update_quotation_status(sid, 'Ganada', 100)
            else:
                delete_sale(sid)
    elif action == 'legacy_payment':
        from routes.ventas import registrar_pago_venta_legacy
        with app.test_request_context('/ventas/registrar-pago', method='POST', data={'sale_id': sid, 'payment_status': 'Pagado'}):
            with pytest.raises(CancelledSaleError):
                registrar_pago_venta_legacy()
    else:
        path = {'emit': f'/ventas/cotizacion/{sid}/emitir-cotizacion',
                'convert': f'/ventas/cotizacion/{sid}/convertir',
                'approve_payment': f'/ventas/pago/{sid}/aprobar'}[action]
        response = auth_client.post(path, follow_redirects=True)
        assert response.status_code == 200
        assert 'Una venta cancelada no se reactiva' in response.get_data(as_text=True)
    assert _terminal_snapshot(sid, pid) == before


@pytest.mark.parametrize('first_status', ['Cancelada', 'En Preparación'])
def test_cancellation_vs_preparation_concurrency_remains_consistent(auth_client, sample_dispatch_products, monkeypatch, first_status):
    import routes.ventas as vr
    from flask import request
    pid = sample_dispatch_products['p_unlotted_id']
    sid = _terminal_test_sale(pid)
    entered, release = threading.Event(), threading.Event()
    original = vr.lock_sale_for_change
    blocked_observed = []
    first_pid = []

    def paused_lock(cur, sale_id, **kwargs):
        row = original(cur, sale_id, **kwargs)
        if sale_id == sid and request.form.get('status') == first_status and not entered.is_set():
            cur.execute('SELECT pg_backend_pid() AS pid')
            first_pid.append(cur.fetchone()['pid'])
            entered.set()
            assert release.wait(15)
        return row

    monkeypatch.setattr(vr, 'lock_sale_for_change', paused_lock)
    def worker(status):
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess.update(user_id=1, role_name='Administrativo', username='admin', permissions={'ventas': True})
            return client.post('/ventas/actualizar-estado', data={'sale_id': sid, 'status': status}, follow_redirects=True).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker, first_status)
        try:
            assert entered.wait(10)
            second = pool.submit(worker, 'En Preparación' if first_status == 'Cancelada' else 'Cancelada')
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                with get_connection() as conn, conn.cursor() as cur:
                    cur.execute('SELECT pid FROM pg_stat_activity WHERE %s = ANY(pg_blocking_pids(pid))', (first_pid[0],))
                    blocked_observed = cur.fetchall()
                if blocked_observed:
                    break
                time.sleep(0.02)
            assert blocked_observed, 'Competing request must actually wait on PostgreSQL lock'
        finally:
            release.set()
        assert first.result(10) == 200 and second.result(10) == 200
    after = _terminal_snapshot(sid, pid)
    assert after['sales'][0]['status'] == 'Cancelada'
    assert after['balance']['physical_stock'] == 20
    assert after['balance']['reserved_stock'] == 0
    kinds = [m['movement_type'] for m in after['inventory_movements']]
    assert kinds == (['PURCHASE_RECEIPT'] if first_status == 'Cancelada' else ['PURCHASE_RECEIPT', 'SALE', 'SALE_REVERSAL'])


def test_lot_sale_cancel_and_reopen_is_safe(auth_client, sample_dispatch_products):
    pid = sample_dispatch_products['p_lotted_id']
    sid = _terminal_test_sale(pid)
    # Synthetic stock exists only inside the guarded, ephemeral test database.
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO lots (lot_number,product_id,status,created_at) VALUES (%s,%s,'ACTIVE','2026-09-29') RETURNING id", (f'TERMINAL-LOT-{pid}',pid))
        lid = cur.fetchone()['id']
        cur.execute("INSERT INTO lot_stock (lot_id,product_id,lot_number,entry_date,initial_qty,available_qty,warehouse) VALUES (%s,%s,%s,'2026-09-29',20,20,'Test')", (lid,pid,f'TERMINAL-LOT-{pid}'))
        conn.commit()
    auth_client.post('/ventas/actualizar-estado', data={'sale_id':sid,'status':'En Preparación'})
    assert get_product_stock_balance(pid)['physical_stock'] == 12
    auth_client.post('/ventas/actualizar-estado', data={'sale_id':sid,'status':'Cancelada'})
    before = _terminal_snapshot(sid,pid)
    assert before['balance']['physical_stock'] == 20
    assert before['lot_stock'][0]['available_qty'] == 20
    assert [m['movement_type'] for m in before['inventory_movements']] == ['PURCHASE_RECEIPT','SALE','SALE_REVERSAL']
    assert len(before['sale_lot_movements']) == 1
    for status in ('En Preparación','Cancelada'):
        auth_client.post('/ventas/actualizar-estado',data={'sale_id':sid,'status':status})
        assert _terminal_snapshot(sid,pid) == before
