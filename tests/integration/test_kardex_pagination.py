import pytest
from datetime import datetime, timedelta
from db import (
    get_connection,
    get_product_kardex_history,
    get_all_products_kardex_paginated,
)

@pytest.fixture
def clean_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()

def test_kardex_pagination_cases_a_to_u(clean_db):
    """
    Batería integral de pruebas para Kardex Server-Side Pagination:
    Casos A a U.
    """
    cur = clean_db.cursor()
    
    # 1. Crear producto de prueba con movimientos controlados
    now_str = datetime.now().isoformat()
    cur.execute("""
        INSERT INTO products (sku, name, category, product_type, cost, min_stock, unit_of_measure, created_at)
        VALUES ('TEST-KARDEX-PAG', 'Producto Test Paginacion', 'Miel', 'TERMINADO', 500, 0, 'UN', %s)
        RETURNING id;
    """, (now_str,))
    p_id = cur.fetchone()['id']
    
    # Insertar 60 movimientos cronológicos para probar paginación de 25 en 25 (3 páginas: 25, 25, 10)
    base_time = datetime.now() - timedelta(days=60)
    for i in range(1, 61):
        m_time = (base_time + timedelta(hours=i)).isoformat()
        if i % 3 == 1:
            m_type = 'PURCHASE'
            qty = 10.0
            unit_cost = 1000.0 + (i * 10)
        elif i % 3 == 2:
            m_type = 'SALE'
            qty = 4.0
            unit_cost = 0.0
        else:
            m_type = 'PRODUCTION_OUTPUT'
            qty = 5.0
            unit_cost = 1200.0
            
        cur.execute("""
            INSERT INTO inventory_movements (product_id, movement_type, quantity, unit_cost, created_at, reference_type, reference_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (p_id, m_type, qty, unit_cost, m_time, 'TEST_REF', i))
    
    # Caso F, G, H: Obtener kardex completo sin paginación para verificar baseline matemático
    full_kardex = get_product_kardex_history(p_id, page=None, per_page=None, conn=clean_db)
    assert len(full_kardex["rows"]) == 60
    final_stock = full_kardex["current_stock"]
    final_ppp = full_kardex["current_ppp"]
    final_val = full_kardex["current_inventory_value"]
    assert final_stock > 0
    assert final_ppp > 0
    assert final_val > 0
    
    # CASO A: Kardex producto página 1 retorna máximo 25 movimientos
    pag_1 = get_product_kardex_history(p_id, page=1, per_page=25, conn=clean_db)
    assert len(pag_1["rows"]) == 25
    assert pag_1["total_movements"] == 60
    assert pag_1["filtered_movements"] == 60
    assert pag_1["page"] == 1
    assert pag_1["per_page"] == 25
    assert pag_1["total_pages"] == 3
    
    # CASO B: Página 2 retorna los siguientes 25 movimientos sin duplicados
    pag_2 = get_product_kardex_history(p_id, page=2, per_page=25, conn=clean_db)
    assert len(pag_2["rows"]) == 25
    assert pag_2["page"] == 2
    ids_page_1 = {r["id"] for r in pag_1["rows"]}
    ids_page_2 = {r["id"] for r in pag_2["rows"]}
    assert ids_page_1.isdisjoint(ids_page_2)
    
    # CASO C: Orden por defecto más reciente primero (DESC)
    assert pag_1["rows"][0]["id"] > pag_1["rows"][1]["id"]
    assert pag_1["rows"][0]["created_at"] >= pag_1["rows"][1]["created_at"]
    
    # CASO D: per_page configurable a 25 / 50 / 100
    pag_50 = get_product_kardex_history(p_id, page=1, per_page=50, conn=clean_db)
    assert len(pag_50["rows"]) == 50
    assert pag_50["per_page"] == 50
    assert pag_50["total_pages"] == 2
    
    pag_100 = get_product_kardex_history(p_id, page=1, per_page=100, conn=clean_db)
    assert len(pag_100["rows"]) == 60  # total disponibles
    assert pag_100["per_page"] == 100
    assert pag_100["total_pages"] == 1
    
    # CASO E: per_page inválido (p.ej. 999999 o 'abc') hace fallback a 25
    pag_invalid = get_product_kardex_history(p_id, page=1, per_page=999999, conn=clean_db)
    assert len(pag_invalid["rows"]) == 25
    assert pag_invalid["per_page"] == 25
    
    # CASO F, G, H: Preservación matemática estricta en páginas
    for p in [pag_1, pag_2, pag_50, pag_100]:
        assert p["current_stock"] == final_stock
        assert p["current_ppp"] == final_ppp
        assert p["current_inventory_value"] == final_val
        
    # CASO I & J: Primer movimiento visible conserva exactamente su saldo histórico y audit Antes/Mov/Después
    row_top_p2 = pag_2["rows"][0]
    expected_top_p2 = full_kardex["rows"][25]
    assert row_top_p2["id"] == expected_top_p2["id"]
    assert row_top_p2["balance_qty"] == expected_top_p2["balance_qty"]
    assert row_top_p2["balance_amount"] == expected_top_p2["balance_amount"]
    assert row_top_p2["ppp"] == expected_top_p2["ppp"]
    assert row_top_p2["audit"] == expected_top_p2["audit"]
    
    # CASO K: Filtro por fecha server-side
    date_mid = (base_time + timedelta(hours=30)).strftime('%Y-%m-%d')
    kardex_filtered_date = get_product_kardex_history(p_id, start_date=date_mid, page=1, per_page=25, conn=clean_db)
    assert kardex_filtered_date["filtered_movements"] < 60
    assert all(r["date"] >= date_mid for r in kardex_filtered_date["rows"])
    
    # CASO L: Filtro por tipo de movimiento server-side
    kardex_sales = get_product_kardex_history(p_id, movement_type_filter='SALE', page=1, per_page=25, conn=clean_db)
    assert kardex_sales["filtered_movements"] == 20
    assert all(r["movement_type"] == 'SALE' for r in kardex_sales["rows"])
    # Pero el stock actual del producto sigue siendo el stock global del producto
    assert kardex_sales["current_stock"] == final_stock
    
    # CASO M: Filtros + paginación combinados
    kardex_combined = get_product_kardex_history(p_id, movement_type_filter='PURCHASE', page=1, per_page=25, conn=clean_db)
    assert kardex_combined["filtered_movements"] == 20
    assert len(kardex_combined["rows"]) == 20
    
    # CASO N: Vista general de productos devuelve 25 productos por defecto
    catalog = get_all_products_kardex_paginated(page=1, per_page=25, conn=clean_db)
    assert len(catalog["products"]) <= 25
    assert catalog["per_page"] == 25
    assert catalog["total_products_count"] >= 1
    
    # CASO O & P: Búsqueda SKU y Nombre server-side
    search_sku = get_all_products_kardex_paginated(page=1, per_page=25, search='TEST-KARDEX-PAG', conn=clean_db)
    assert search_sku["total_filtered"] >= 1
    assert any(p["sku"] == 'TEST-KARDEX-PAG' for p in search_sku["products"])
    
    search_name = get_all_products_kardex_paginated(page=1, per_page=25, search='Producto Test Paginacion', conn=clean_db)
    assert search_name["total_filtered"] >= 1
    assert any(p["sku"] == 'TEST-KARDEX-PAG' for p in search_name["products"])
    
    # CASO Q & R: Tarjetas globales de valor y unidades consideran el catálogo completo (no solo la página)
    assert catalog["total_inventory_value"] >= final_val
    assert catalog["total_units_stock"] >= final_stock
    assert catalog["total_products_count"] >= catalog["total_filtered"]
    
    # CASO S, T, U: Verificación sin regresión de tipos de movimiento y motor PPP
    cur.execute("""
        INSERT INTO inventory_movements (product_id, movement_type, quantity, unit_cost, created_at, reference_type, reference_id)
        VALUES (%s, 'SALE_REVERSAL', 4.0, %s, %s, 'test', 1)
    """, (p_id, final_ppp, (datetime.now() + timedelta(minutes=1)).isoformat()))
    
    updated_kardex = get_product_kardex_history(p_id, page=1, per_page=25, conn=clean_db)
    assert updated_kardex["rows"][0]["movement_type"] == 'SALE_REVERSAL'
    assert updated_kardex["rows"][0]["audit"]["movement"]["unit_cost"] == round(final_ppp, 2)
