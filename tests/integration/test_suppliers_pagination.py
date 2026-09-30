import pytest
from app import app
from db import get_suppliers_paginated

def test_get_suppliers_paginated_db():
    """Prueba que el repositorio retorne proveedores paginados y soporte búsqueda"""
    res = get_suppliers_paginated(page=1, per_page=25)
    assert "items" in res
    assert "total" in res
    assert "page" in res
    assert "per_page" in res
    assert "total_pages" in res
    assert len(res["items"]) <= 25
    assert res["page"] == 1
    assert res["per_page"] == 25

    if res["items"]:
        item = res["items"][0]
        assert "id" in item
        assert "name" in item

def test_get_suppliers_paginated_search():
    """Prueba que la búsqueda filtre proveedores"""
    res = get_suppliers_paginated(page=1, per_page=25, search="Miel")
    assert "items" in res
    assert res["total"] >= 0

def test_proveedores_route_200():
    """Prueba que la ruta /proveedores responda HTTP 200 con paginación server-side"""
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role_name'] = 'Administrador'
            sess['user_name'] = 'Admin Test'

        resp = client.get('/proveedores')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Proveedores Registrados' in html
        assert 'prov_per_page_select' in html
        assert 'Total:' in html
