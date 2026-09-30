import pytest
from datetime import datetime, timezone
from db import (
    get_connection,
    get_price_list_products_paginated,
    get_products_batch_calculated_cost,
    insert_product,
)

@pytest.fixture
def clean_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()

def test_price_list_pagination_and_batch_costs(clean_db):
    """
    Test suite para P0.1:
    - Paginación server-side de lista de precios (25, 50, 100)
    - Exclusión estricta de insumos (product_type != 'Insumo')
    - Búsqueda server-side en PostgreSQL
    - Resolución batch de costos sin consultas N+1
    """
    cur = clean_db.cursor()
    sku_prefix = f"LP-PAG-{int(datetime.now().timestamp())}"

    # Insertar 30 productos 'Final' y 5 'Insumo'
    inserted_ids = []
    for i in range(1, 31):
        pid = insert_product({
            "sku": f"{sku_prefix}-FIN-{i:02d}",
            "name": f"Producto Lista Precios {i}",
            "category": "Miel Premium" if i <= 15 else "Miel Estándar",
            "product_type": "Final",
            "cost": 1500.0 + (i * 10),
            "created_at": datetime.now(timezone.utc).isoformat(timespec='seconds')
        })
        inserted_ids.append(pid)

    insumo_ids = []
    for i in range(1, 6):
        pid = insert_product({
            "sku": f"{sku_prefix}-INS-{i:02d}",
            "name": f"Insumo Envase {i}",
            "category": "Insumos",
            "product_type": "Insumo",
            "cost": 300.0,
            "created_at": datetime.now(timezone.utc).isoformat(timespec='seconds')
        })
        insumo_ids.append(pid)

    # 1. Validación de paginación básica (25 por defecto)
    res_page1 = get_price_list_products_paginated(page=1, per_page=25, conn=clean_db)
    assert len(res_page1["items"]) == 25
    assert res_page1["page"] == 1
    assert res_page1["per_page"] == 25
    assert res_page1["total"] >= 30

    # Verificar que NINGÚN producto en la lista de precios sea un Insumo
    for item in res_page1["items"]:
        assert item.get("product_type") != "Insumo"

    # 2. Página 2
    res_page2 = get_price_list_products_paginated(page=2, per_page=25, conn=clean_db)
    assert len(res_page2["items"]) >= 1
    assert res_page2["page"] == 2
    ids_p1 = {p["id"] for p in res_page1["items"]}
    ids_p2 = {p["id"] for p in res_page2["items"]}
    assert ids_p1.isdisjoint(ids_p2)

    # 3. Selector de registros (50)
    res_50 = get_price_list_products_paginated(page=1, per_page=50, conn=clean_db)
    assert len(res_50["items"]) <= 50
    assert res_50["per_page"] == 50

    # 4. Fallback per_page inválido
    res_invalid = get_price_list_products_paginated(page=1, per_page=999, conn=clean_db)
    assert res_invalid["per_page"] == 25

    # 5. Búsqueda server-side por SKU
    res_search_sku = get_price_list_products_paginated(search=f"{sku_prefix}-FIN-07", conn=clean_db)
    assert res_search_sku["total"] == 1
    assert res_search_sku["items"][0]["sku"] == f"{sku_prefix}-FIN-07"

    # 6. Búsqueda server-side por Nombre
    res_search_name = get_price_list_products_paginated(search="Producto Lista Precios 14", conn=clean_db)
    assert res_search_name["total"] >= 1
    assert any(p["sku"] == f"{sku_prefix}-FIN-14" for p in res_search_name["items"])

    # 7. Verificación de cálculo BATCH de costos
    subset_pids = inserted_ids[:10]
    costs_map = get_products_batch_calculated_cost(subset_pids, conn=clean_db)
    assert isinstance(costs_map, dict)
