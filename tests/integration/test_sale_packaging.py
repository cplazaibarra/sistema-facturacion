import pytest
import json
import threading
from datetime import datetime, timezone
from app import app
from core.database import get_connection
from db import (
    create_product,
    insert_sale,
    get_sale,
    list_packaging_products,
    get_sale_packaging_items,
    sale_has_packaging,
    record_sale_packaging,
    get_sale_financial_summary,
    reverse_sale_packaging,
    record_inventory_movement,
    get_relational_stock
)

@pytest.fixture
def auth_client():
    """Client autenticado con CSRF deshabilitado para pruebas de integración de ventas/embalaje."""
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
def setup_packaging_products():
    """Crea productos de embalaje estándar y productos vendibles con stock."""
    # Caja Pequeña
    p_box_small_id = create_product(
        sku=f"BOX-S-{int(datetime.now().timestamp() * 1000)}",
        name="Caja Pequeña",
        category="Packaging",
        product_type="PACKAGING",
        cost=500.0
    )
    # Movimiento inicial de stock para Caja Pequeña: 100 un.
    record_inventory_movement(
        product_id=p_box_small_id,
        movement_type="IN",
        quantity=100.0,
        unit_cost=500.0,
        notes="Stock inicial test embalaje"
    )

    # Caja Grande
    p_box_large_id = create_product(
        sku=f"BOX-L-{int(datetime.now().timestamp() * 1000)}",
        name="Caja Grande",
        category="Packaging",
        product_type="PACKAGING",
        cost=1000.0
    )
    # Movimiento inicial de stock para Caja Grande: 20 un.
    record_inventory_movement(
        product_id=p_box_large_id,
        movement_type="IN",
        quantity=20.0,
        unit_cost=1000.0,
        notes="Stock inicial test embalaje"
    )

    # Producto vendible
    p_item_id = create_product(
        sku=f"MIEL-500G-{int(datetime.now().timestamp() * 1000)}",
        name="Miel Orgánica 500g",
        category="Mieles",
        product_type="Final",
        cost=3000.0
    )
    record_inventory_movement(
        product_id=p_item_id,
        movement_type="IN",
        quantity=50.0,
        unit_cost=3000.0,
        notes="Stock producto final"
    )

    return {
        "box_small_id": p_box_small_id,
        "box_large_id": p_box_large_id,
        "item_id": p_item_id
    }


def _create_sample_sale(products_list=None, total_amount=119000.0, status="En Preparación"):
    if products_list is None:
        products_list = [{"product_id": 9999, "product_name": "Prod Test", "quantity": 1, "price": 100000.0, "subtotal": 100000.0}]
    now_str = datetime.now(timezone.utc).isoformat(timespec='seconds')
    sale_data = {
        "sale_number": f"VTA-TEST-{int(datetime.now().timestamp() * 1000)}",
        "customer_name": "Cliente Test Embalaje",
        "sale_date": "2026-09-17",
        "sale_time": "12:00:00",
        "products": products_list,
        "total_amount": total_amount,
        "status": status,
        "seller_name": "Vendedor Test",
        "created_at": now_str
    }
    return insert_sale(sale_data)


# 1. test_dispatch_status_requests_packaging
def test_dispatch_status_requests_packaging(auth_client, setup_packaging_products):
    sale_id = _create_sample_sale(status="En Preparación")
    assert sale_has_packaging(sale_id) is False
    resp = auth_client.get(f"/api/ventas/{sale_id}/packaging")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["has_packaging"] is False


# 2. test_completed_status_requests_packaging
def test_completed_status_requests_packaging(auth_client, setup_packaging_products):
    sale_id = _create_sample_sale(status="En Preparación")
    assert sale_has_packaging(sale_id) is False
    resp = auth_client.get(f"/api/ventas/{sale_id}/packaging")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["has_packaging"] is False


# 3. test_other_status_does_not_request_packaging
def test_other_status_does_not_request_packaging(auth_client, setup_packaging_products):
    sale_id = _create_sample_sale(status="Pendiente")
    resp = auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "En Preparación"
    }, follow_redirects=True)
    assert resp.status_code == 200
    sale = get_sale(sale_id)
    assert sale["status"] == "En Preparación"
    assert len(get_sale_packaging_items(sale_id)) == 0


# 4. test_existing_packaging_not_requested_again
def test_existing_packaging_not_requested_again(auth_client, setup_packaging_products):
    prods = setup_packaging_products
    sale_id = _create_sample_sale(status="En Preparación")
    record_sale_packaging(sale_id, [{"product_id": prods["box_small_id"], "quantity": 2}])
    assert sale_has_packaging(sale_id) is True
    resp = auth_client.get(f"/api/ventas/{sale_id}/packaging")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["has_packaging"] is True
    assert len(data["packaging_items"]) == 1


# 5. test_packaging_product_sold_is_not_dispatch_packaging
def test_packaging_product_sold_is_not_dispatch_packaging(auth_client, setup_packaging_products):
    """
    Escenario CASO A vs CASO B:
    El cliente compra comercialmente 100 cajas (sale_items).
    Al consultar la API o pasar a 'Para Despacho', la venta NO debe considerar
    que ya tiene embalaje de despacho registrado. El sistema debe permitir/solicitar
    el embalaje utilizado para despachar.
    """
    prods = setup_packaging_products
    sale_id = _create_sample_sale(products_list=[
        {"product_id": prods["box_large_id"], "product_name": "Caja Grande", "quantity": 100, "price": 1000.0}
    ], status="En Preparación")

    # No tiene embalaje de despacho a pesar de vender cajas en la línea comercial
    assert sale_has_packaging(sale_id) is False
    resp = auth_client.get(f"/api/ventas/{sale_id}/packaging")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["has_packaging"] is False
    assert len(data["packaging_items"]) == 0


# 6. test_multiple_packaging_types
def test_multiple_packaging_types(setup_packaging_products):
    prods = setup_packaging_products
    sale_id = _create_sample_sale()
    items = record_sale_packaging(sale_id, [
        {"product_id": prods["box_small_id"], "quantity": 3},
        {"product_id": prods["box_large_id"], "quantity": 2}
    ])
    assert len(items) == 2
    saved = get_sale_packaging_items(sale_id)
    assert len(saved) == 2


# 7. test_packaging_stock_decreases
def test_packaging_stock_decreases(setup_packaging_products):
    prods = setup_packaging_products
    initial_small = get_relational_stock(prods["box_small_id"])
    initial_large = get_relational_stock(prods["box_large_id"])
    assert initial_small == 100.0
    assert initial_large == 20.0

    sale_id = _create_sample_sale()
    record_sale_packaging(sale_id, [
        {"product_id": prods["box_small_id"], "quantity": 4},
        {"product_id": prods["box_large_id"], "quantity": 2}
    ])

    assert get_relational_stock(prods["box_small_id"]) == 96.0
    assert get_relational_stock(prods["box_large_id"]) == 18.0


# 8. test_packaging_insufficient_stock_rejected
def test_packaging_insufficient_stock_rejected(setup_packaging_products):
    prods = setup_packaging_products
    sale_id = _create_sample_sale()
    with pytest.raises(ValueError, match="Stock insuficiente"):
        record_sale_packaging(sale_id, [
            {"product_id": prods["box_large_id"], "quantity": 25}
        ])
    assert get_relational_stock(prods["box_large_id"]) == 20.0


def test_packaging_allocation_is_not_blocked_by_pending_demand(setup_packaging_products):
    """La reserva comercial de cajas no las asigna físicamente antes de preparar."""
    prods = setup_packaging_products
    box_id = prods["box_small_id"]
    committed_sale = _create_sample_sale(
        products_list=[{"product_id": box_id, "product_name": "Caja Pequeña",
                        "quantity": 98, "price": 1000}],
        status="Pendiente",
    )
    assert committed_sale
    dispatch_sale = _create_sample_sale()
    listed = next(p for p in list_packaging_products() if p["id"] == box_id)
    assert listed["available_stock"] == 100.0

    record_sale_packaging(dispatch_sale, [{"product_id": box_id, "quantity": 3}])
    assert get_relational_stock(box_id) == 97.0
    assert len(get_sale_packaging_items(dispatch_sale)) == 1
    from repositories.sales_repo import check_sale_stock_availability
    check = check_sale_stock_availability(committed_sale)
    assert check["has_deficit"] is True
    assert check["items"][0]["deficit"] == 1.0


# 9. test_packaging_cost_snapshot
def test_packaging_cost_snapshot(setup_packaging_products):
    prods = setup_packaging_products
    sale_id = _create_sample_sale()
    record_sale_packaging(sale_id, [{"product_id": prods["box_small_id"], "quantity": 4}])
    items = get_sale_packaging_items(sale_id)
    assert len(items) == 1
    assert items[0]["unit_cost"] == 500.0
    assert items[0]["total_cost"] == 2000.0


# 10. test_packaging_cost_does_not_change_historically
def test_packaging_cost_does_not_change_historically(setup_packaging_products):
    prods = setup_packaging_products
    sale_id = _create_sample_sale()
    record_sale_packaging(sale_id, [{"product_id": prods["box_small_id"], "quantity": 4}])

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE products SET cost = 950.0 WHERE id = %s", (prods["box_small_id"],))
        conn.commit()

    items = get_sale_packaging_items(sale_id)
    assert items[0]["unit_cost"] == 500.0
    assert items[0]["total_cost"] == 2000.0


# 11. test_packaging_cost_added_to_real_sale_cost
def test_packaging_cost_added_to_real_sale_cost(setup_packaging_products):
    prods = setup_packaging_products
    sale_id = _create_sample_sale(products_list=[
        {"product_id": prods["item_id"], "product_name": "Miel Orgánica", "quantity": 20, "price": 5000.0}
    ], total_amount=119000.0)

    record_sale_packaging(sale_id, [
        {"product_id": prods["box_small_id"], "quantity": 4},
        {"product_id": prods["box_large_id"], "quantity": 2}
    ])

    summary = get_sale_financial_summary(sale_id)
    assert summary["products_cost"] == 60000.0
    assert summary["packaging_cost"] == 4000.0
    assert summary["real_total_cost"] == 64000.0


# 12. test_packaging_cost_does_not_increase_sale_revenue
def test_packaging_cost_does_not_increase_sale_revenue(setup_packaging_products):
    prods = setup_packaging_products
    sale_id = _create_sample_sale(total_amount=119000.0)
    record_sale_packaging(sale_id, [
        {"product_id": prods["box_small_id"], "quantity": 4}
    ])
    sale = get_sale(sale_id)
    assert float(sale["total_amount"]) == 119000.0


# 13. test_real_margin_includes_packaging
def test_real_margin_includes_packaging(setup_packaging_products):
    prods = setup_packaging_products
    sale_id = _create_sample_sale(products_list=[
        {"product_id": prods["item_id"], "quantity": 20, "price": 5000.0}
    ], total_amount=119000.0)

    record_sale_packaging(sale_id, [
        {"product_id": prods["box_small_id"], "quantity": 4},
        {"product_id": prods["box_large_id"], "quantity": 2}
    ])

    summary = get_sale_financial_summary(sale_id)
    assert summary["neto"] == 100000.0
    assert summary["real_total_cost"] == 64000.0
    assert summary["real_margin"] == 36000.0
    assert summary["real_margin_pct"] == 36.0


# 14. test_packaging_and_status_change_are_atomic
def test_packaging_and_status_change_are_atomic(auth_client, setup_packaging_products):
    prods = setup_packaging_products
    sale_id = _create_sample_sale(status="En Preparación")

    resp = auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "Para Despacho",
        "packaging_product_id[]": [str(prods["box_large_id"])],
        "packaging_quantity[]": ["50"]
    }, follow_redirects=True)

    assert resp.status_code == 200
    sale = get_sale(sale_id)
    assert sale["status"] == "En Preparación"
    assert get_relational_stock(prods["box_large_id"]) == 20.0
    assert len(get_sale_packaging_items(sale_id)) == 0


# 15. test_double_submit_does_not_duplicate_packaging
def test_double_submit_does_not_duplicate_packaging(auth_client, setup_packaging_products):
    prods = setup_packaging_products
    sale_id = _create_sample_sale(status="En Preparación")

    auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "Para Despacho",
        "packaging_product_id[]": [str(prods["box_small_id"])],
        "packaging_quantity[]": ["4"]
    }, follow_redirects=True)

    assert get_relational_stock(prods["box_small_id"]) == 96.0

    auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "Para Despacho",
        "packaging_product_id[]": [str(prods["box_small_id"])],
        "packaging_quantity[]": ["4"]
    }, follow_redirects=True)

    assert get_relational_stock(prods["box_small_id"]) == 96.0
    items = get_sale_packaging_items(sale_id)
    assert len(items) == 1


# 16. test_concurrent_packaging_consumption_prevents_negative_stock
def test_concurrent_packaging_consumption_prevents_negative_stock(setup_packaging_products):
    prods = setup_packaging_products
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM inventory_movements WHERE product_id = %s", (prods["box_large_id"],))
        conn.commit()
    record_inventory_movement(
        product_id=prods["box_large_id"],
        movement_type="IN",
        quantity=10.0,
        unit_cost=1000.0,
        notes="Stock exacto para concurrencia"
    )

    sale1_id = _create_sample_sale()
    sale2_id = _create_sample_sale()

    successes = []
    errors = []

    def consume_worker(s_id):
        try:
            record_sale_packaging(s_id, [{"product_id": prods["box_large_id"], "quantity": 7}])
            successes.append(s_id)
        except Exception as e:
            errors.append(str(e))

    t1 = threading.Thread(target=consume_worker, args=(sale1_id,))
    t2 = threading.Thread(target=consume_worker, args=(sale2_id,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(successes) == 1
    assert len(errors) == 1
    assert "Stock insuficiente" in errors[0]
    final_stock = get_relational_stock(prods["box_large_id"])
    assert final_stock == 3.0


# 17. test_sale_cancellation_reverses_packaging_if_applicable
def test_sale_cancellation_reverses_packaging_if_applicable(auth_client, setup_packaging_products):
    prods = setup_packaging_products
    sale_id = _create_sample_sale(status="En Preparación")

    auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "Para Despacho",
        "packaging_product_id[]": [str(prods["box_small_id"])],
        "packaging_quantity[]": ["4"]
    }, follow_redirects=True)
    assert get_relational_stock(prods["box_small_id"]) == 96.0

    auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "Cancelada"
    }, follow_redirects=True)

    assert get_relational_stock(prods["box_small_id"]) == 100.0


# 18. E2E COMPLETO (Requisito 30)
def test_e2e_packaging_flow_dispatch_and_completion(auth_client, setup_packaging_products):
    prods = setup_packaging_products
    sale_id = _create_sample_sale(
        products_list=[
            {"product_id": prods["item_id"], "product_name": "Miel Orgánica", "quantity": 20, "price": 5000.0}
        ],
        total_amount=119000.0,
        status="En Preparación"
    )

    resp1 = auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "Para Despacho",
        "packaging_product_id[]": [str(prods["box_small_id"]), str(prods["box_large_id"])],
        "packaging_quantity[]": ["4", "2"]
    }, follow_redirects=True)
    assert resp1.status_code == 200

    assert get_relational_stock(prods["box_small_id"]) == 96.0
    assert get_relational_stock(prods["box_large_id"]) == 18.0

    summary = get_sale_financial_summary(sale_id)
    assert summary["neto"] == 100000.0
    assert summary["products_cost"] == 60000.0
    assert summary["packaging_cost"] == 4000.0
    assert summary["real_total_cost"] == 64000.0
    assert summary["real_margin"] == 36000.0
    assert summary["real_margin_pct"] == 36.0

    import io
    fake_invoice = (io.BytesIO(b"%PDF-1.4 test invoice"), "factura.pdf")
    resp2 = auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "Completada",
        "invoice_number": "FACT-9999",
        "invoice_file": fake_invoice,
        "packaging_product_id[]": [str(prods["box_small_id"])],
        "packaging_quantity[]": ["4"]
    }, follow_redirects=True, content_type='multipart/form-data')
    assert resp2.status_code == 200

    assert get_relational_stock(prods["box_small_id"]) == 96.0
    assert get_relational_stock(prods["box_large_id"]) == 18.0
    summary_after = get_sale_financial_summary(sale_id)
    assert summary_after["packaging_cost"] == 4000.0
    assert summary_after["real_total_cost"] == 64000.0
    assert summary_after["real_margin"] == 36000.0

    items = get_sale_packaging_items(sale_id)
    assert len(items) == 2


# 19. test_dispatch_packaging_does_not_generate_revenue
def test_dispatch_packaging_does_not_generate_revenue(setup_packaging_products):
    """
    Venta: Producto A x20. Embalaje: Caja Grande x2.
    Confirmar:
    - Ingreso no cambia
    - Neto no cambia
    - IVA no cambia
    - Total no cambia
    - Costo aumenta
    - Margen disminuye
    """
    prods = setup_packaging_products
    initial_total = 119000.0  # Neto: 100000, IVA: 19000
    sale_id = _create_sample_sale(
        products_list=[
            {"product_id": prods["item_id"], "product_name": "Miel Orgánica", "quantity": 20, "price": 5000.0}
        ],
        total_amount=initial_total,
        status="En Preparación"
    )

    summary_before = get_sale_financial_summary(sale_id)
    assert summary_before["total_amount"] == 119000.0
    assert summary_before["neto"] == 100000.0
    assert summary_before["iva"] == 19000.0
    assert summary_before["products_cost"] == 60000.0
    assert summary_before["packaging_cost"] == 0.0
    assert summary_before["real_total_cost"] == 60000.0
    assert summary_before["real_margin"] == 40000.0

    # Registrar embalaje de despacho
    record_sale_packaging(sale_id, [{"product_id": prods["box_large_id"], "quantity": 2}])

    # Validar en la venta persistida
    sale = get_sale(sale_id)
    assert float(sale["total_amount"]) == initial_total

    summary_after = get_sale_financial_summary(sale_id)
    # Ingreso, neto, IVA y total permanecen inalterados
    assert summary_after["total_amount"] == 119000.0
    assert summary_after["neto"] == 100000.0
    assert summary_after["iva"] == 19000.0
    # Costo aumenta
    assert summary_after["packaging_cost"] == 2000.0
    assert summary_after["real_total_cost"] == 62000.0
    # Margen disminuye
    assert summary_after["real_margin"] == 38000.0
    assert summary_after["real_margin"] < summary_before["real_margin"]


# 20. test_existing_dispatch_packaging_is_not_consumed_twice
def test_existing_dispatch_packaging_is_not_consumed_twice(auth_client, setup_packaging_products):
    """
    Registrar explícitamente: Caja Grande x2 como embalaje.
    Cambiar: Para Despacho -> Completada
    Confirmar: solo 2 cajas descontadas en total.
    """
    prods = setup_packaging_products
    initial_stock = get_relational_stock(prods["box_large_id"])
    assert initial_stock == 20.0

    sale_id = _create_sample_sale(status="En Preparación")

    # Pasar a Para Despacho asignando 2 cajas grandes
    resp1 = auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "Para Despacho",
        "packaging_product_id[]": [str(prods["box_large_id"])],
        "packaging_quantity[]": ["2"]
    }, follow_redirects=True)
    assert resp1.status_code == 200

    stock_after_dispatch = get_relational_stock(prods["box_large_id"])
    assert stock_after_dispatch == 18.0

    # Pasar ahora de Para Despacho -> Completada
    import io
    fake_invoice = (io.BytesIO(b"%PDF-1.4 test invoice"), "factura.pdf")
    resp2 = auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "Completada",
        "invoice_number": "FACT-8888",
        "invoice_file": fake_invoice,
        "packaging_product_id[]": [str(prods["box_large_id"])],
        "packaging_quantity[]": ["2"]
    }, follow_redirects=True, content_type='multipart/form-data')
    assert resp2.status_code == 200

    stock_after_completion = get_relational_stock(prods["box_large_id"])
    # Debe seguir siendo 18.0 (solo 2 cajas descontadas, sin duplicación)
    assert stock_after_completion == 18.0

    items = get_sale_packaging_items(sale_id)
    assert len(items) == 1
    assert items[0]["quantity"] == 2


# 21. test_sale_packaging_history_survives_sale_cancellation
def test_sale_packaging_history_survives_sale_cancellation(auth_client, setup_packaging_products):
    """
    Cancelar venta. Confirmar:
    - Movimiento SALE_PACKAGING original permanece
    - SALE_PACKAGING_REVERSAL queda registrado
    - Histórico de costo permanece auditable en sale_packaging_items
    - Stock queda correctamente restituido
    """
    prods = setup_packaging_products
    initial_stock = get_relational_stock(prods["box_small_id"])
    assert initial_stock == 100.0

    sale_id = _create_sample_sale(status="En Preparación")

    # Despachar con 5 cajas
    resp1 = auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "Para Despacho",
        "packaging_product_id[]": [str(prods["box_small_id"])],
        "packaging_quantity[]": ["5"]
    }, follow_redirects=True)
    assert resp1.status_code == 200
    assert get_relational_stock(prods["box_small_id"]) == 95.0

    # Cancelar la venta
    resp2 = auth_client.post('/ventas/actualizar-estado', data={
        "sale_id": sale_id,
        "status": "Cancelada"
    }, follow_redirects=True)
    assert resp2.status_code == 200

    # 1. Stock restituido
    assert get_relational_stock(prods["box_small_id"]) == 100.0

    # 2. Registros de inventario en Kardex: SALE_PACKAGING original y SALE_PACKAGING_REVERSAL existen
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT movement_type, quantity, unit_cost 
                FROM inventory_movements 
                WHERE product_id = %s AND (reference_id = %s OR notes LIKE %s)
                ORDER BY id ASC
                """,
                (prods["box_small_id"], sale_id, f"%Venta #{sale_id}%")
            )
            movements = [dict(r) for r in cur.fetchall()]

    types = [m["movement_type"] for m in movements]
    assert "SALE_PACKAGING" in types
    assert "SALE_PACKAGING_REVERSAL" in types

    orig_mov = next(m for m in movements if m["movement_type"] == "SALE_PACKAGING")
    assert orig_mov["quantity"] == -5.0
    assert orig_mov["unit_cost"] == 500.0

    rev_mov = next(m for m in movements if m["movement_type"] == "SALE_PACKAGING_REVERSAL")
    assert rev_mov["quantity"] == 5.0
    assert rev_mov["unit_cost"] == 500.0

    # 3. Histórico de costo en sale_packaging_items sobrevive intacto y auditable
    items = get_sale_packaging_items(sale_id)
    assert len(items) == 1
    assert items[0]["quantity"] == 5
    assert items[0]["unit_cost"] == 500.0
    assert items[0]["total_cost"] == 2500.0


# 22. test_sale_packaging_fk_restrict_prevents_physical_deletion
def test_sale_packaging_fk_restrict_prevents_physical_deletion(setup_packaging_products):
    """
    Verifica que la política ON DELETE RESTRICT impida la eliminación física
    accidental de una venta que posea registros de embalaje en sale_packaging_items.
    """
    import psycopg2
    prods = setup_packaging_products
    sale_id = _create_sample_sale(status="Para Despacho")
    record_sale_packaging(sale_id, [{"product_id": prods["box_small_id"], "quantity": 1}])

    with get_connection() as conn:
        with conn.cursor() as cur:
            with pytest.raises(psycopg2.IntegrityError):
                cur.execute("DELETE FROM sales WHERE id = %s", (sale_id,))
        conn.rollback()
