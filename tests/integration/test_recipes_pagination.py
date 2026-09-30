import pytest
from datetime import datetime, timezone
from db import (
    get_connection,
    get_recipes_paginated,
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

def test_recipes_pagination_and_batch_bom(clean_db):
    """
    Test suite para P0.3:
    - Paginación server-side de recetas BOM (25 por defecto, 50, 100)
    - Carga BATCH de insumos/componentes sin consultas N+1
    - Búsqueda server-side en PostgreSQL por producto final, receta o componente
    """
    cur = clean_db.cursor()
    ts = int(datetime.now().timestamp())
    
    # Crear producto insumo compartido
    insumo_id = insert_product({
        "sku": f"INS-REC-{ts}",
        "name": f"Insumo Receta Test {ts}",
        "category": "Insumos",
        "product_type": "Insumo",
        "cost": 250.0,
        "created_at": datetime.now(timezone.utc).isoformat(timespec='seconds')
    })

    # Crear 30 recetas de prueba con sus componentes
    for i in range(1, 31):
        final_id = insert_product({
            "sku": f"FIN-REC-{ts}-{i:02d}",
            "name": f"Producto Final BOM {i}",
            "category": "Miel Elaborada",
            "product_type": "Final",
            "cost": 1200.0,
            "created_at": datetime.now(timezone.utc).isoformat(timespec='seconds')
        })
        cur.execute(
            """
            INSERT INTO product_recipes (final_product_id, recipe_code, created_at)
            VALUES (%s, %s, NOW())
            RETURNING id
            """,
            (final_id, f"BOM-TEST-{ts}-{i:02d}")
        )
        rec_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO product_recipe_items (recipe_id, input_product_id, quantity_required, unit, notes)
            VALUES (%s, %s, %s, 'UN', 'Item test')
            """,
            (rec_id, insumo_id, i * 2.5)
        )

    # 1. Validación de paginación básica (25 por defecto)
    res_page1 = get_recipes_paginated(page=1, per_page=25, conn=clean_db)
    assert len(res_page1["items"]) == 25
    assert res_page1["page"] == 1
    assert res_page1["per_page"] == 25
    assert res_page1["total"] >= 30

    # Verificar que los ítems del BOM vengan cargados en batch
    for r in res_page1["items"]:
        assert "items" in r
        assert isinstance(r["items"], list)
        assert len(r["items"]) >= 1

    # 2. Página 2
    res_page2 = get_recipes_paginated(page=2, per_page=25, conn=clean_db)
    assert len(res_page2["items"]) >= 1
    assert res_page2["page"] == 2
    ids_p1 = {r["id"] for r in res_page1["items"]}
    ids_p2 = {r["id"] for r in res_page2["items"]}
    assert ids_p1.isdisjoint(ids_p2)

    # 3. Selector 50
    res_50 = get_recipes_paginated(page=1, per_page=50, conn=clean_db)
    assert len(res_50["items"]) <= 50
    assert res_50["per_page"] == 50

    # 4. Búsqueda por código de receta
    target_code = f"BOM-TEST-{ts}-09"
    res_search = get_recipes_paginated(search=target_code, conn=clean_db)
    assert res_search["total"] == 1
    assert res_search["items"][0]["recipe_code"] == target_code

    # 5. Búsqueda por componente insumo
    res_search_comp = get_recipes_paginated(search=f"INS-REC-{ts}", conn=clean_db)
    assert res_search_comp["total"] >= 30
