"""
tests/integration/test_sales_stock_workflow.py

Suite exhaustiva de pruebas de integración para las reglas de negocio de Ventas e Inventario:
1. Permitir crear y guardar ventas sin stock.
2. No generar movimientos negativos de inventario en la creación.
3. Permitir convertir cotizaciones ganadas a ventas sin stock disponible.
4. Bloquear transición a 'En Preparación' si hay déficit de stock.
5. Bloquear transición a 'Para Despacho' si hay déficit de stock.
6. Bloquear transición a 'Completada' si hay déficit de stock.
7. Permitir transiciones entre estados comerciales sin stock.
8. Desbloqueo dinámico en tiempo real tras ingreso de mercadería posterior.
9. Descuento físico formal en Kardex y sale_items al avanzar a estado operacional.
10. Idempotencia: una venta ya descontada no duplica movimientos ni Kardex.
11. Registro de pago total no fuerza 'Completada' si existe déficit de stock.
12. Transiciones operacionales concurrentes seguras ante stock limitado.
13. Endpoint API /api/ventas/<id>/stock-check entrega información precisa.
14. Compatibilidad con tests legados y productos simulados (IDs mock).
15. Validación E2E del ciclo de vida completo.
"""

import pytest
import json
import re
import threading
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
    get_sale_packaging_items,
    get_next_sale_number
)
from routes.ventas import _convert_quotation_to_sale
from services.stock_context import get_product_stock_balance


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
def sample_products():
    """Crea 2 productos aislados para pruebas de stock."""
    ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    p1_id = create_product(
        sku=f"SKU-STOCK-A-{ts}",
        name=f"Producto Test Stock A {ts}",
        category="Pruebas",
        product_type="Final",
        cost=1500.0,
        price=3000.0,
        requires_lot=False
    )
    p2_id = create_product(
        sku=f"SKU-STOCK-B-{ts}",
        name=f"Producto Test Stock B {ts}",
        category="Pruebas",
        product_type="Final",
        cost=2000.0,
        price=4000.0,
        requires_lot=False
    )
    yield {"p1_id": p1_id, "p2_id": p2_id}

    # Cleanup
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sale_lot_movements WHERE product_id IN (%s, %s)", (p1_id, p2_id))
            cur.execute("DELETE FROM sale_items WHERE product_id IN (%s, %s)", (p1_id, p2_id))
            cur.execute("DELETE FROM inventory_movements WHERE product_id IN (%s, %s)", (p1_id, p2_id))
            cur.execute("DELETE FROM lot_stock WHERE product_id IN (%s, %s)", (p1_id, p2_id))
            cur.execute("DELETE FROM products WHERE id IN (%s, %s)", (p1_id, p2_id))
        conn.commit()


# CASO 1: Permitir crear venta sin stock suficiente
def test_case_1_create_sale_without_stock_allowed(sample_products):
    prods = sample_products
    # Ambos productos tienen stock = 0
    assert get_relational_stock(prods["p1_id"]) == 0.0

    sale_data = {
        "sale_number": f"VTA-TEST-001-{prods['p1_id']}",
        "customer_name": "Cliente Sin Stock 1",
        "sale_date": "2026-09-26",
        "sale_time": "12:00:00",
        "products": [
            {"product_id": prods["p1_id"], "product_name": "Producto A", "quantity": 10, "price": 3000.0, "subtotal": 30000.0}
        ],
        "total_amount": 30000.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
        "notes": "Venta creada sin stock",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    sale_id = insert_sale(sale_data)
    assert sale_id is not None

    sale = get_sale(sale_id)
    assert sale["status"] == "Pendiente"

    # Verificar disponibilidad
    check = check_sale_stock_availability(sale_id)
    assert check["has_deficit"] is True
    assert check["total_deficit_lines"] == 1
    assert check["items"][0]["deficit"] == 10.0


# CASO 2: La creación sin stock NO genera movimientos negativos ni afecta Kardex
def test_case_2_no_negative_stock_on_creation(sample_products):
    prods = sample_products
    sale_data = {
        "sale_number": f"VTA-TEST-002-{prods['p1_id']}",
        "customer_name": "Cliente Sin Stock 2",
        "sale_date": "2026-09-26",
        "sale_time": "12:00:00",
        "products": [
            {"product_id": prods["p1_id"], "product_name": "Producto A", "quantity": 5, "price": 3000.0, "subtotal": 15000.0}
        ],
        "total_amount": 15000.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
        "notes": "Venta sin stock",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    sale_id = insert_sale(sale_data)

    # Verificar que NO se crearon movimientos en inventory_movements ni en sale_items
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM inventory_movements WHERE reference_type = 'sale' AND reference_id = %s", (sale_id,))
            assert cur.fetchone()["cnt"] == 0
            cur.execute("SELECT COUNT(*) as cnt FROM sale_items WHERE sale_id = %s", (sale_id,))
            assert cur.fetchone()["cnt"] == 0

    assert get_relational_stock(prods["p1_id"]) == 0.0


# CASO 3: Conversión de Cotización Ganada a Venta permitida sin stock
def test_case_3_cotizacion_to_sale_without_stock_allowed(sample_products):
    prods = sample_products
    # Crear cotización con 15 unidades de producto sin stock
    with get_connection() as conn:
        with conn.cursor() as cur:
            cot_num = f"COT-TEST-{prods['p1_id']}"
            cur.execute(
                """
                INSERT INTO sales (sale_number, customer_name, seller_name, payment_method, sale_date, sale_time, products_json, total_amount, status, quotation_status, notes, created_at)
                VALUES (%s, 'Cliente Cotización Sin Stock', 'Vendedor Test', 'Efectivo', '2026-09-26', '12:00:00', %s, 45000.0, 'Cotización', 'Activa', '', '2026-09-26 12:00:00')
                RETURNING id
                """,
                (cot_num, json.dumps([{"product_id": prods["p1_id"], "product_name": "Producto A", "quantity": 15, "price": 3000.0}]))
            )
            cot_id = cur.fetchone()["id"]
        conn.commit()

    # Convertir a venta (debe tener éxito, retornar folio y NO arrojar error de stock)
    vta_num, err = _convert_quotation_to_sale(cot_id)
    assert err is None
    assert vta_num is not None
    assert vta_num.startswith("P-")

    # La cotización pasa a Ganada
    cot = get_sale(cot_id)
    assert cot["quotation_status"] == "Ganada"
    assert f"Venta Generada: {vta_num}" in cot["notes"]

    # La venta creada está en Pendiente y con déficit detectado en tiempo real
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, status, notes FROM sales WHERE sale_number = %s", (vta_num,))
            new_sale = cur.fetchone()
            assert new_sale["status"] == "Pendiente"
            assert "Stock pendiente de abastecimiento" in new_sale["notes"]
            new_sale_id = new_sale["id"]

    check = check_sale_stock_availability(new_sale_id)
    assert check["has_deficit"] is True
    assert check["is_discounted"] is False


# CASO 4: Bloquear transición a 'En Preparación' si hay déficit
def test_case_4_transition_to_en_preparacion_blocked_without_stock(auth_client, sample_products):
    prods = sample_products
    sale_data = {
        "sale_number": f"VTA-TEST-004-{prods['p1_id']}",
        "customer_name": "Cliente Sin Stock 4",
        "sale_date": "2026-09-26",
        "sale_time": "12:00:00",
        "products": [
            {"product_id": prods["p1_id"], "product_name": "Producto A", "quantity": 10, "price": 3000.0, "subtotal": 30000.0}
        ],
        "total_amount": 30000.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    sale_id = insert_sale(sale_data)

    resp = auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "En Preparación"
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert "stock insuficiente" in resp.data.decode('utf-8').lower()

    # El estado debe seguir en Pendiente
    sale = get_sale(sale_id)
    assert sale["status"] == "Pendiente"


# CASO 5: Bloquear transición a 'Para Despacho' si hay déficit
def test_case_5_transition_to_para_despacho_blocked_without_stock(auth_client, sample_products):
    prods = sample_products
    sale_data = {
        "sale_number": f"VTA-TEST-005-{prods['p1_id']}",
        "customer_name": "Cliente Sin Stock 5",
        "sale_date": "2026-09-26",
        "sale_time": "12:00:00",
        "products": [
            {"product_id": prods["p1_id"], "product_name": "Producto A", "quantity": 8, "price": 3000.0, "subtotal": 24000.0}
        ],
        "total_amount": 24000.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    sale_id = insert_sale(sale_data)

    resp = auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "Para Despacho"
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert "stock insuficiente" in resp.data.decode('utf-8').lower()
    sale = get_sale(sale_id)
    assert sale["status"] == "Pendiente"


# CASO 6: Bloquear transición a 'Completada' si hay déficit
def test_case_6_transition_to_completada_blocked_without_stock(auth_client, sample_products):
    prods = sample_products
    sale_data = {
        "sale_number": f"VTA-TEST-006-{prods['p1_id']}",
        "customer_name": "Cliente Sin Stock 6",
        "sale_date": "2026-09-26",
        "sale_time": "12:00:00",
        "products": [
            {"product_id": prods["p1_id"], "product_name": "Producto A", "quantity": 12, "price": 3000.0, "subtotal": 36000.0}
        ],
        "total_amount": 36000.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    sale_id = insert_sale(sale_data)

    resp = auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "Completada",
        "invoice_number": "FACT-006"
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert "stock insuficiente" in resp.data.decode('utf-8').lower()
    sale = get_sale(sale_id)
    assert sale["status"] == "Pendiente"


# CASO 7: Transiciones entre estados comerciales permitidas sin stock
def test_case_7_commercial_states_allowed_without_stock(auth_client, sample_products):
    prods = sample_products
    sale_data = {
        "sale_number": f"VTA-TEST-007-{prods['p1_id']}",
        "customer_name": "Cliente Sin Stock 7",
        "sale_date": "2026-09-26",
        "sale_time": "12:00:00",
        "products": [
            {"product_id": prods["p1_id"], "product_name": "Producto A", "quantity": 20, "price": 3000.0, "subtotal": 60000.0}
        ],
        "total_amount": 60000.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    sale_id = insert_sale(sale_data)

    # Cancelar venta sin stock -> permitido
    resp = auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "Cancelada"
    }, follow_redirects=True)
    assert resp.status_code == 200
    sale = get_sale(sale_id)
    assert sale["status"] == "Cancelada"

    # Regla funcional 29-09-2026: Cancelada es terminal, incluso sin consumo.
    resp2 = auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "Pendiente"
    }, follow_redirects=True)
    assert resp2.status_code == 200
    sale = get_sale(sale_id)
    assert sale["status"] == "Cancelada"
    assert "Una venta cancelada no se reactiva" in resp2.get_data(as_text=True)
    assert get_relational_stock(prods['p1_id']) == 0


# CASO 8: Desbloqueo dinámico tras ingreso de mercadería posterior
def test_case_8_stock_arrival_unblocks_sale(auth_client, sample_products):
    prods = sample_products
    sale_data = {
        "sale_number": f"VTA-TEST-008-{prods['p1_id']}",
        "customer_name": "Cliente Desbloqueo",
        "sale_date": "2026-09-26",
        "sale_time": "12:00:00",
        "products": [
            {"product_id": prods["p1_id"], "product_name": "Producto A", "quantity": 10, "price": 3000.0, "subtotal": 30000.0}
        ],
        "total_amount": 30000.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    sale_id = insert_sale(sale_data)

    # 1. Intento fallido sin stock
    resp1 = auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "En Preparación"
    }, follow_redirects=True)
    assert "stock insuficiente" in resp1.data.decode('utf-8').lower()
    assert get_sale(sale_id)["status"] == "Pendiente"

    # 2. Llega stock a bodega (ej. recepción de compra / ingreso)
    record_inventory_movement(
        product_id=prods["p1_id"],
        movement_type="PURCHASE_RECEIPT",
        quantity=15.0,
        unit_cost=1500.0,
        notes="Llegada de mercadería proveedor"
    )
    assert get_relational_stock(prods["p1_id"]) == 15.0

    # 3. La venta se desbloquea dinámicamente sin tocar su registro previo
    check = check_sale_stock_availability(sale_id)
    assert check["has_deficit"] is False
    assert check["items"][0]["available"] == 15.0

    # 4. Ahora la transición tiene éxito
    resp2 = auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "En Preparación"
    }, follow_redirects=True)
    assert resp2.status_code == 200
    assert get_sale(sale_id)["status"] == "En Preparación"


# CASO 9: Descuento físico formal en Kardex y sale_items ocurre en transición operacional
def test_case_9_physical_deduction_on_operational_transition(auth_client, sample_products):
    prods = sample_products
    # Ingresar 20 un. de stock
    record_inventory_movement(
        product_id=prods["p1_id"],
        movement_type="PURCHASE_RECEIPT",
        quantity=20.0,
        unit_cost=1500.0,
        notes="Stock inicial"
    )

    sale_data = {
        "sale_number": f"VTA-TEST-009-{prods['p1_id']}",
        "customer_name": "Cliente Descuento Operacional",
        "sale_date": "2026-09-26",
        "sale_time": "12:00:00",
        "products": [
            {"product_id": prods["p1_id"], "product_name": "Producto A", "quantity": 7, "price": 3000.0, "subtotal": 21000.0}
        ],
        "total_amount": 21000.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    sale_id = insert_sale(sale_data)

    # Antes de la transición: no hay registro en sale_items y stock físico es 20
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM sale_items WHERE sale_id = %s", (sale_id,))
            assert cur.fetchone()["cnt"] == 0

    assert get_relational_stock(prods["p1_id"]) == 20.0

    # Pasar a 'En Preparación'
    resp = auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "En Preparación"
    }, follow_redirects=True)
    assert resp.status_code == 200

    # Ahora sí se descontó físicamente en Kardex y sale_items
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt, SUM(quantity) as qty FROM sale_items WHERE sale_id = %s", (sale_id,))
            row = cur.fetchone()
            assert row["cnt"] == 1
            assert float(row["qty"]) == 7.0

    # Stock remanente en Kardex: 20 - 7 = 13
    assert get_relational_stock(prods["p1_id"]) == 13.0


# CASO 10: Idempotencia: una venta ya descontada no duplica movimientos al avanzar entre estados operacionales
def test_case_10_no_duplicate_discount_if_already_deducted(auth_client, sample_products):
    prods = sample_products
    record_inventory_movement(
        product_id=prods["p1_id"],
        movement_type="PURCHASE_RECEIPT",
        quantity=30.0,
        unit_cost=1500.0,
        notes="Stock lote"
    )

    sale_data = {
        "sale_number": f"VTA-TEST-010-{prods['p1_id']}",
        "customer_name": "Cliente Idempotente",
        "sale_date": "2026-09-26",
        "sale_time": "12:00:00",
        "products": [
            {"product_id": prods["p1_id"], "product_name": "Producto A", "quantity": 10, "price": 3000.0, "subtotal": 30000.0}
        ],
        "total_amount": 30000.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    sale_id = insert_sale(sale_data)

    # 1. Pasar de Pendiente a 'En Preparación' (primer descuento)
    auth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "En Preparación"}, follow_redirects=True)
    assert get_relational_stock(prods["p1_id"]) == 20.0

    # 2. Pasar de 'En Preparación' a 'Para Despacho'
    auth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "Para Despacho"}, follow_redirects=True)
    # El stock NO se debe descontar otra vez (sigue en 20.0)
    assert get_relational_stock(prods["p1_id"]) == 20.0

    # 3. Subir comprobante y pasar a Completada
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE sale_payments SET invoice_file = '/uploads/factura_test.pdf' WHERE sale_id = %s", (sale_id,))
        conn.commit()

    auth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "Completada"}, follow_redirects=True)
    assert get_relational_stock(prods["p1_id"]) == 20.0


# CASO 11: Pago completo en venta sin stock no fuerza 'Completada'
def test_case_11_payment_full_does_not_force_completada_if_stock_deficit(auth_client, sample_products):
    prods = sample_products
    assert get_relational_stock(prods["p1_id"]) == 0.0

    sale_data = {
        "sale_number": f"VTA-TEST-011-{prods['p1_id']}",
        "customer_name": "Cliente Pago Sin Stock",
        "sale_date": "2026-09-26",
        "sale_time": "12:00:00",
        "products": [
            {"product_id": prods["p1_id"], "product_name": "Producto A", "quantity": 10, "price": 3000.0, "subtotal": 30000.0}
        ],
        "total_amount": 30000.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    sale_id = insert_sale(sale_data)

    # Registrar el pago del 100% de la venta
    resp = auth_client.post('/ventas/registrar-pago', data={
        "sale_id": str(sale_id),
        "payment_method": "Efectivo",
        "payment_date": "2026-09-26",
        "payment_amount": "30000.0",
        "payment_notes": "Pago total recibido sin stock físico",
        "idempotency_key": f"key-pago-{sale_id}"
    }, follow_redirects=True)
    assert resp.status_code == 200

    sale = get_sale(sale_id)
    # Pago queda como 'Pagado'
    assert sale["payment_status"] == "Pagado"
    # PERO la venta NO puede pasar a 'Completada' debido a falta de stock
    assert sale["status"] == "Pendiente"


def test_full_payment_does_not_choose_a_sale_for_preparation(auth_client, sample_products):
    """Incluso con físico suficiente, pagar no ejecuta el pedido."""
    pid = sample_products["p1_id"]
    record_inventory_movement(
        product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=10,
        unit_cost=1500, notes="Ingreso previo al pago",
    )
    sale_id = insert_sale({
        "sale_number": f"VTA-PAID-NOT-PREPARED-{pid}",
        "customer_name": "Cliente pago previo", "sale_date": "2026-09-26",
        "sale_time": "12:00:00",
        "products": [{"product_id": pid, "product_name": "Producto A", "quantity": 5, "price": 3000}],
        "total_amount": 15000, "status": "Pendiente", "payment_status": "Pendiente",
        "payment_method": "Efectivo", "created_at": datetime.now(timezone.utc).isoformat(),
    })
    paid = auth_client.post('/ventas/registrar-pago', data={
        'sale_id': str(sale_id), 'payment_method': 'Efectivo',
        'payment_date': '2026-09-26', 'payment_amount': '15000',
        'idempotency_key': f'paid-not-prepared-{sale_id}',
    }, follow_redirects=True)
    assert paid.status_code == 200
    sale = get_sale(sale_id)
    assert sale['payment_status'] == 'Pagado'
    assert sale['status'] == 'Pendiente'
    assert get_relational_stock(pid) == 10.0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) AS n FROM sale_items WHERE sale_id=%s', (sale_id,))
            assert cur.fetchone()['n'] == 0

    prepared = auth_client.post('/ventas/actualizar-estado', data={
        'sale_id': sale_id, 'status': 'En Preparación',
    }, follow_redirects=True)
    assert prepared.status_code == 200
    assert get_sale(sale_id)['status'] == 'En Preparación'
    assert get_relational_stock(pid) == 5.0


# CASO 12: Concurrencia segura: dos ventas compiten por stock limitado
def test_case_12_concurrent_operational_transitions_safe(auth_client, sample_products):
    prods = sample_products
    # Dotar exactamente 10 unidades
    record_inventory_movement(
        product_id=prods["p1_id"],
        movement_type="PURCHASE_RECEIPT",
        quantity=10.0,
        unit_cost=1500.0,
        notes="Stock concurrencia"
    )

    # Dos ventas independientes de 8 unidades cada una (demanda = 16 > 10)
    v1_id = insert_sale({
        "sale_number": f"VTA-CONC-1-{prods['p1_id']}",
        "customer_name": "Cliente Concurrente 1",
        "sale_date": "2026-09-26",
        "sale_time": "12:00:00",
        "products": [{"product_id": prods["p1_id"], "product_name": "Producto A", "quantity": 8, "price": 3000.0}],
        "total_amount": 24000.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT sku FROM products WHERE id=%s", (prods["p1_id"],))
            legacy_sku = cur.fetchone()["sku"]

    v2_id = insert_sale({
        "sale_number": f"VTA-CONC-2-{prods['p1_id']}",
        "customer_name": "Cliente Concurrente 2",
        "sale_date": "2026-09-26",
        "sale_time": "12:00:00",
        # La segunda línea usa identidad legacy por SKU: debe bloquear el
        # mismo producto y competir de forma segura con la primera venta.
        "products": [{"sku": legacy_sku, "product_name": "Producto A", "quantity": 8, "price": 3000.0}],
        "total_amount": 24000.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
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

    t1 = threading.Thread(target=transition_sale, args=(v1_id,))
    t2 = threading.Thread(target=transition_sale, args=(v2_id,))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactamente una debe haber triunfado y la otra debe haber sido rechazada
    assert len(success_sales) == 1, f"Debió triunfar exactamente una: success={success_sales}, failed={failed_sales}"
    assert len(failed_sales) == 1, f"Debió fallar exactamente una: success={success_sales}, failed={failed_sales}"

    # Stock final en Kardex = 10 - 8 = 2.0 (nunca negativo)
    assert get_relational_stock(prods["p1_id"]) == 2.0
    states = [get_sale(v1_id)["status"], get_sale(v2_id)["status"]]
    assert sorted(states) == ["En Preparación", "Pendiente"]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM inventory_movements "
                "WHERE product_id=%s AND reference_type='sale' AND reference_id IN (%s,%s)",
                (prods["p1_id"], v1_id, v2_id),
            )
            assert cur.fetchone()["n"] == 1
            cur.execute("SELECT COUNT(*) AS n FROM sale_items WHERE sale_id IN (%s,%s)", (v1_id, v2_id))
            assert cur.fetchone()["n"] == 1


# CASO: Demanda global vs selección del operador (prioridad sin sesgo cronológico)
@pytest.mark.parametrize("selected", ["first", "later"])
def test_operator_selects_which_pending_sale_uses_physical_stock(auth_client, sample_products, selected):
    """La demanda global no asigna físico: el primer pedido preparado lo consume."""
    pid = sample_products["p1_id"]
    record_inventory_movement(
        product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=10,
        unit_cost=1500, notes="Entrada para prioridad de ventas",
    )

    def pending_sale(suffix, qty):
        return insert_sale({
            "sale_number": f"VTA-PRIORITY-{suffix}-{pid}",
            "customer_name": f"Cliente prioridad {suffix}",
            "sale_date": "2026-09-26", "sale_time": "12:00:00",
            "products": [{"product_id": pid, "product_name": "Producto A", "quantity": qty, "price": 3000}],
            "total_amount": qty * 3000, "status": "Pendiente",
            "payment_status": "Pendiente", "payment_method": "Efectivo",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    first_id = pending_sale("FIRST", 8)
    later_id = pending_sale("LATER", 5)
    assert get_relational_stock(pid) == 10.0
    balance = get_product_stock_balance(pid)
    assert balance["physical_stock"] == 10.0
    assert balance["reserved_stock"] == 13.0
    assert balance["physical_reserved_stock"] == 10.0
    assert balance["available_stock"] == 0.0

    assert check_sale_stock_availability(first_id)["items"][0]["available"] == 10.0
    assert check_sale_stock_availability(later_id)["items"][0]["available"] == 10.0

    selected_id, other_id = (first_id, later_id) if selected == "first" else (later_id, first_id)
    selected_qty = 8 if selected == "first" else 5
    advanced = auth_client.post(
        "/ventas/actualizar-estado",
        data={"sale_id": selected_id, "status": "En Preparación"},
        follow_redirects=True,
    )
    assert advanced.status_code == 200
    assert get_sale(selected_id)["status"] == "En Preparación"
    assert get_relational_stock(pid) == 10.0 - selected_qty

    other_check = check_sale_stock_availability(other_id)
    assert other_check["has_deficit"] is True
    assert other_check["items"][0]["deficit"] == 3.0
    blocked = auth_client.post(
        "/ventas/actualizar-estado",
        data={"sale_id": other_id, "status": "En Preparación"},
        follow_redirects=True,
    )
    assert blocked.status_code == 200
    assert get_sale(other_id)["status"] == "Pendiente"

    # Repetir la transición no puede volver a descontar el mismo pedido.
    retried = auth_client.post(
        "/ventas/actualizar-estado",
        data={"sale_id": selected_id, "status": "En Preparación"},
        follow_redirects=True,
    )
    assert retried.status_code == 200
    assert get_relational_stock(pid) == 10.0 - selected_qty
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM sale_items WHERE sale_id=%s", (selected_id,))
            assert cur.fetchone()["n"] == 1
            cur.execute("SELECT COUNT(*) AS n FROM inventory_movements WHERE reference_type='sale' AND reference_id=%s", (selected_id,))
            assert cur.fetchone()["n"] == 1
            cur.execute("SELECT COUNT(*) AS n FROM sale_items WHERE sale_id=%s", (other_id,))
            assert cur.fetchone()["n"] == 0


def test_quotation_conversion_does_not_allocate_stock(sample_products):
    """Convertir una cotización no decide qué venta recibirá el stock."""
    pid = sample_products["p1_id"]
    record_inventory_movement(
        product_id=pid, movement_type="PURCHASE_RECEIPT", quantity=10,
        unit_cost=1500, notes="Entrada para conversión con reserva previa",
    )
    first_id = insert_sale({
        "sale_number": f"VTA-CONVERSION-PRIOR-{pid}",
        "customer_name": "Cliente anterior", "sale_date": "2026-09-26", "sale_time": "12:00:00",
        "products": [{"product_id": pid, "product_name": "Producto A", "quantity": 8, "price": 3000}],
        "total_amount": 24000, "status": "Pendiente", "payment_status": "Pendiente",
        "payment_method": "Efectivo", "created_at": datetime.now(timezone.utc).isoformat(),
    })
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO sales (sale_number, customer_name, seller_name,
                   payment_method, sale_date, sale_time, products_json, total_amount,
                   status, quotation_status, notes, created_at)
                   VALUES (%s, 'Cliente cotización', 'Vendedor', 'Efectivo',
                   '2026-09-26', '12:00:00', %s, 15000, 'Cotización', 'Activa', '',
                   '2026-09-26 12:00:00') RETURNING id""",
                (f"COT-CONVERSION-PRIOR-{pid}", json.dumps([
                    {"product_id": pid, "product_name": "Producto A", "quantity": 5, "price": 3000}
                ])),
            )
            quote_id = cur.fetchone()["id"]
        conn.commit()

    sale_number, error = _convert_quotation_to_sale(quote_id)
    assert error is None
    assert get_sale(quote_id)["quotation_status"] == "Ganada"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, status FROM sales WHERE sale_number=%s", (sale_number,))
            converted = cur.fetchone()
            cur.execute("SELECT COUNT(*) AS n FROM sale_items WHERE sale_id=%s", (converted["id"],))
            assert cur.fetchone()["n"] == 0
    assert first_id < converted["id"]
    assert converted["status"] == "Pendiente"
    assert get_relational_stock(pid) == 10.0
    assert check_sale_stock_availability(converted["id"])["items"][0]["available"] == 10.0
    balance = get_product_stock_balance(pid)
    assert balance["reserved_stock"] == 13.0
    assert balance["available_stock"] == 0.0


def test_case_13_api_stock_check_endpoint(auth_client, sample_products):
    prods = sample_products
    sale_data = {
        "sale_number": f"VTA-TEST-013-{prods['p1_id']}",
        "customer_name": "Cliente API Stock",
        "sale_date": "2026-09-26",
        "sale_time": "12:00:00",
        "products": [
            {"product_id": prods["p1_id"], "product_name": "Prod A", "quantity": 5, "price": 3000.0},
            {"product_id": prods["p2_id"], "product_name": "Prod B", "quantity": 3, "price": 4000.0}
        ],
        "total_amount": 27000.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    sale_id = insert_sale(sale_data)

    resp = auth_client.get(f'/api/ventas/{sale_id}/stock-check')
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["sale_id"] == sale_id
    assert data["has_deficit"] is True
    assert data["total_deficit_lines"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["deficit"] == 5.0
    assert data["items"][1]["deficit"] == 3.0


# CASO 14: Compatibilidad con tests legados y productos simulados (IDs mock)
def test_case_14_mock_products_in_legacy_tests_safe(auth_client):
    """
    Ventas que contienen productos mock que no existen en la BD (como ID 9999 en test_sale_packaging)
    no deben causar fallos de clave foránea ni errores 500 al consultar stock o pasar de estado.
    """
    sale_id = insert_sale({
        "sale_number": f"VTA-MOCK-{int(datetime.now().timestamp() * 1000)}",
        "customer_name": "Cliente Mock",
        "sale_date": "2026-09-26",
        "sale_time": "12:00:00",
        "products": [{"product_id": 99999, "product_name": "Producto No Existente", "quantity": 1, "price": 5000.0}],
        "total_amount": 5000.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    # Consultar API
    check = check_sale_stock_availability(sale_id)
    assert check["has_deficit"] is False

    # Avanzar de estado
    resp = auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "En Preparación"
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert get_sale(sale_id)["status"] == "En Preparación"


# CASO E2E: Ciclo de vida completo
def test_e2e_sales_stock_lifecycle(auth_client, sample_products):
    """
    Flujo E2E completo:
    1. Se crea venta sin stock suficiente (stock = 0).
    2. La venta se guarda en 'Pendiente' con déficit reportado en el badge/modal.
    3. Intento de pasar a 'En Preparación' es rechazado con desglose de faltantes.
    4. Se registra mercadería mediante orden de compra / entrada a bodega.
    5. La venta se desbloquea dinámicamente.
    6. Se pasa exitosamente a 'En Preparación' (existencias descontadas en Kardex).
    7. Se avanza a 'Para Despacho' y luego a 'Completada'.
    8. La venta finaliza en 'Completada' con trazabilidad y Kardex exactos.
    """
    prods = sample_products

    # 1. Crear venta de 10 unidades sin stock
    sale_id = insert_sale({
        "sale_number": f"VTA-E2E-{prods['p1_id']}",
        "customer_name": "Empresa E2E Spa",
        "sale_date": "2026-09-26",
        "sale_time": "12:00:00",
        "products": [{"product_id": prods["p1_id"], "product_name": "Producto Test A", "quantity": 10, "price": 3000.0, "subtotal": 30000.0}],
        "total_amount": 30000.0,
        "status": "Pendiente",
        "payment_status": "Pendiente",
        "payment_method": "Efectivo",
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    # 2. Venta nace en Pendiente con déficit
    check1 = check_sale_stock_availability(sale_id)
    assert check1["has_deficit"] is True
    assert check1["items"][0]["deficit"] == 10.0

    # 3. Transición bloqueada
    resp_block = auth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "En Preparación"}, follow_redirects=True)
    assert "stock insuficiente" in resp_block.data.decode('utf-8').lower()
    assert get_sale(sale_id)["status"] == "Pendiente"

    # 4. Ingreso de 12 unidades a bodega
    record_inventory_movement(
        product_id=prods["p1_id"],
        movement_type="PURCHASE_RECEIPT",
        quantity=12.0,
        unit_cost=1500.0,
        notes="Recepción de compra E2E"
    )
    assert get_relational_stock(prods["p1_id"]) == 12.0

    # 5. Desbloqueo dinámico
    check2 = check_sale_stock_availability(sale_id)
    assert check2["has_deficit"] is False
    assert check2["items"][0]["available"] == 12.0

    # 6. Transición exitosa a 'En Preparación'
    resp_prep = auth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "En Preparación"}, follow_redirects=True)
    assert resp_prep.status_code == 200
    assert get_sale(sale_id)["status"] == "En Preparación"
    # Stock descontado en Kardex: 12 - 10 = 2.0
    assert get_relational_stock(prods["p1_id"]) == 2.0

    # 7. Avanzar a 'Para Despacho'
    resp_disp = auth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "Para Despacho"}, follow_redirects=True)
    assert resp_disp.status_code == 200
    assert get_sale(sale_id)["status"] == "Para Despacho"

    # Adjuntar factura ficticia para permitir Completada
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE sale_payments SET invoice_file = '/uploads/factura_e2e.pdf' WHERE sale_id = %s", (sale_id,))
        conn.commit()

    # 8. Finalizar en 'Completada'
    resp_comp = auth_client.post('/ventas/actualizar-estado', data={"sale_id": sale_id, "status": "Completada"}, follow_redirects=True)
    assert resp_comp.status_code == 200
    final_sale = get_sale(sale_id)
    assert final_sale["status"] == "Completada"
    assert get_relational_stock(prods["p1_id"]) == 2.0
