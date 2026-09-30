import pytest
from app import app
from db import get_purchase_orders_paginated

def test_purchase_orders_paginated_db():
    """Prueba que el repositorio retorne las claves requeridas y respete el límite"""
    res = get_purchase_orders_paginated(page=1, per_page=25)
    assert "items" in res
    assert "total" in res
    assert "page" in res
    assert "per_page" in res
    assert "total_pages" in res
    assert len(res["items"]) <= 25
    assert res["page"] == 1
    assert res["per_page"] == 25

    # Verificar que cada item tenga las claves necesarias para la vista
    if res["items"]:
        item = res["items"][0]
        assert "id" in item
        assert "oc_number" in item
        assert "supplier_name" in item
        assert "invoices" in item
        assert "entries" in item

def test_purchase_orders_paginated_filter_search():
    """Prueba que el filtro de búsqueda por texto opere correctamente"""
    res = get_purchase_orders_paginated(page=1, per_page=25, search="OC-")
    assert "items" in res
    assert res["total"] >= 0

def test_compras_oc_route_200():
    """Prueba que la ruta /compras/oc responda HTTP 200 con paginación server-side"""
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role_name'] = 'Administrador'
            sess['user_name'] = 'Admin Test'

        resp = client.get('/compras/oc')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Listado de Órdenes de Compra (OC)' in html
        assert 'Total:' in html
        assert 'per_page_select' in html
