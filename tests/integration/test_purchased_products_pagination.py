import pytest
from app import app
from repositories.reporting_repo import get_purchased_products_matrix

def test_purchased_products_matrix_pagination():
    """Prueba que la matriz soporte page, per_page y búsqueda conservando totales globales"""
    matrix = get_purchased_products_matrix(year=2026, page=1, per_page=30)
    assert "products" in matrix
    assert "grand_total_qty" in matrix
    assert "grand_total_amount" in matrix
    assert "monthly_totals" in matrix
    assert "total_skus" in matrix
    assert len(matrix["products"]) <= 30
    assert matrix["page"] == 1
    assert matrix["per_page"] == 30

def test_purchased_products_route_200():
    """Prueba que /compras/productos-comprados responda HTTP 200 con paginación server-side"""
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role_name'] = 'Administrador'
            sess['user_name'] = 'Admin Test'

        resp = client.get('/compras/productos-comprados')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Matriz de Productos Comprados por SKU' in html
        assert 'matrix_per_page_select' in html
        assert 'Total:' in html
