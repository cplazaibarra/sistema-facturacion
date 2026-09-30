import pytest
from app import app
from db import get_lot_stock_paginated

def test_get_lot_stock_paginated_db():
    """Verifica que el repositorio pagine en base de datos y conserve las métricas globales"""
    res = get_lot_stock_paginated(page=1, per_page=25)
    assert "items" in res
    assert "total" in res
    assert "page" in res
    assert "per_page" in res
    assert "total_pages" in res
    assert "metrics" in res
    assert len(res["items"]) <= 25
    assert res["page"] == 1
    assert res["per_page"] == 25
    
    # Métricas globales
    metrics = res["metrics"]
    assert "total_lotes" in metrics
    assert "lotes_activos" in metrics
    assert "lotes_agotados" in metrics
    assert "unidades_disponibles" in metrics
    assert "valor_total_lotes" in metrics
    assert metrics["total_lotes"] >= res["total"]

def test_inventory_lots_route_200():
    """Verifica que /reporteria/inventario-lotes responda HTTP 200 con paginación server-side"""
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role_name'] = 'Administrador'
            sess['user_name'] = 'Admin Test'

        resp = client.get('/reporteria/inventario-lotes')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Reportes > Inventario por Lotes y Bodega' in html
        assert 'lotes_per_page_select' in html
        assert 'Total:' in html
