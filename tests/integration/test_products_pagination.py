import pytest
from datetime import datetime, timezone
from db import get_connection, get_products_paginated, insert_product

@pytest.fixture
def clean_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()

def test_products_pagination_cases_a_to_j(clean_db):
    """
    Validación de paginación y búsqueda server-side para el catálogo de productos.
    """
    cur = clean_db.cursor()
    
    # 1. Crear productos de prueba controlados
    sku_prefix = f"TEST-PAG-{int(datetime.now().timestamp())}"
    for i in range(1, 35):
        insert_product({
            "sku": f"{sku_prefix}-{i:02d}",
            "name": f"Producto Paginado {i}",
            "category": "Cat Alpha" if i <= 15 else "Cat Beta",
            "product_type": "Insumo" if i % 2 == 0 else "Final",
            "cost": 100.0 * i,
            "created_at": datetime.now(timezone.utc).isoformat(timespec='seconds')
        })

    # CASO A: El tamaño está fijado en servidor y no se puede ampliar por query.
    page1 = get_products_paginated(page=1, per_page=100000, conn=clean_db)
    assert len(page1["items"]) == 30
    assert page1["page"] == 1
    assert page1["per_page"] == 30
    assert page1["total"] >= 34
    assert page1["total_pages"] >= 2

    # CASO B: Página 2 devuelve los siguientes registros sin duplicados
    page2 = get_products_paginated(page=2, per_page=30, conn=clean_db)
    assert len(page2["items"]) >= 1
    assert page2["page"] == 2
    ids_p1 = {p["id"] for p in page1["items"]}
    ids_p2 = {p["id"] for p in page2["items"]}
    assert ids_p1.isdisjoint(ids_p2)

    # CASO C: Orden estrictamente determinístico por id DESC
    assert page1["items"][0]["id"] > page1["items"][1]["id"]

    # CASO D: Fallback para per_page inválido o abusivo (p.ej. 100000).
    page_invalid = get_products_paginated(page=1, per_page=999, conn=clean_db)
    assert page_invalid["per_page"] == 30

    # CASO F: Búsqueda server-side por SKU específico
    search_sku = get_products_paginated(search=f"{sku_prefix}-05", conn=clean_db)
    assert search_sku["total"] == 1
    assert search_sku["items"][0]["sku"] == f"{sku_prefix}-05"

    # CASO G: Búsqueda server-side por Nombre
    search_name = get_products_paginated(search="Producto Paginado 12", conn=clean_db)
    assert search_name["total"] >= 1
    assert any("Producto Paginado 12" in p["name"] for p in search_name["items"])

    # CASO H: Filtro server-side por Categoría
    cat_alpha = get_products_paginated(search=sku_prefix, category="Cat Alpha", conn=clean_db)
    assert cat_alpha["total"] == 15
    assert all(p["category"] == "Cat Alpha" for p in cat_alpha["items"])

    # CASO I: Filtro server-side por Tipo de Producto
    insumos = get_products_paginated(search=sku_prefix, product_type="Insumo", conn=clean_db)
    assert insumos["total"] == 17
    assert all(p["product_type"] == "Insumo" for p in insumos["items"])

    # CASO J: Búsqueda combinada con categoría
    combo = get_products_paginated(search=f"{sku_prefix}-02", category="Cat Alpha", conn=clean_db)
    assert combo["total"] == 1
    assert combo["items"][0]["sku"] == f"{sku_prefix}-02"

    from app import app
    client=app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=1,username='admin_tester',role_name='Administrativo',permissions={'inventario':True})
    response=client.get('/productos?page=abc&per_page=100000')
    assert response.status_code == 200
    html=response.get_data(as_text=True)
    assert '30 productos por página' in html
    assert html.count('<tr') <= 32
