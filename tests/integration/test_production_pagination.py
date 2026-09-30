"""
tests/integration/test_production_pagination.py

Suite de pruebas exhaustivas para la paginación y búsqueda server-side
en Fábrica de Productos / Órdenes de Trabajo conforme a los requerimientos A-M.

Casos evaluados:
- Caso A: Página 1 devuelve 25 registros por defecto cuando total >= 25.
- Caso B: Página 2 devuelve los siguientes registros sin duplicación de IDs con página 1.
- Caso C: Ordenamiento canónico estrictamente por po.id DESC.
- Caso D: Búsqueda server-side por número de OT (ot_number).
- Caso E: Búsqueda server-side por nombre de producto final (p.name).
- Caso F: Búsqueda server-side por SKU de producto final (p.sku).
- Caso G: Filtro server-side por estado (Borrador, Solicitada, Aprobada, Finalizada).
- Caso H: Búsqueda combinada con filtro de estado.
- Caso I: Selector per_page (25, 50, 100).
- Caso J: per_page inválido o no permitido hace fallback automático a 25.
- Caso K: Conservación de parámetros en URL / enlaces de paginación.
- Caso L: No regresión en OT Draft (disponibilidad de insumos y activación).
- Caso M: No regresión en el Calendario / Programación Semanal de Producción.
"""

import pytest
from app import app
from db import (
    get_connection,
    get_production_orders_paginated,
    get_material_availability_for_orders,
    list_scheduled_production_orders,
    list_unscheduled_production_orders,
    create_production_order
)


@pytest.fixture
def auth_client():
    """Client autenticado como Administrador para probar rutas de producción."""
    old_csrf = app.config.get("WTF_CSRF_ENABLED", True)
    old_testing = app.config.get("TESTING", False)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    try:
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["username"] = "admin"
                sess["role_name"] = "Administrativo"
                sess["permissions"] = {
                    "dashboard": True,
                    "inventario": True,
                    "productos": True,
                    "produccion": True,
                    "solo_ver": False
                }
            yield client
    finally:
        app.config["WTF_CSRF_ENABLED"] = old_csrf
        app.config["TESTING"] = old_testing


def test_case_a_page_1_default_25():
    """Caso A: Página 1 devuelve 25 registros por defecto."""
    res = get_production_orders_paginated(page=1, per_page=25)
    assert res["total"] >= 25, "Debe haber al menos 25 OTs en la base de datos de pruebas"
    assert len(res["items"]) == 25, f"Se esperaban 25 items, pero se obtuvieron {len(res['items'])}"
    assert res["page"] == 1
    assert res["per_page"] == 25
    assert res["total_pages"] >= 1


def test_case_b_page_2_no_duplicates():
    """Caso B: Página 2 devuelve los siguientes registros sin duplicar IDs con Página 1."""
    res1 = get_production_orders_paginated(page=1, per_page=25)
    res2 = get_production_orders_paginated(page=2, per_page=25)

    ids1 = {ot["id"] for ot in res1["items"]}
    ids2 = {ot["id"] for ot in res2["items"]}

    assert len(ids1) == 25
    assert len(ids2) == 25
    # La intersección debe ser estrictamente vacía
    intersection = ids1.intersection(ids2)
    assert len(intersection) == 0, f"Se encontraron IDs duplicados entre pág 1 y 2: {intersection}"


def test_case_c_order_po_id_desc():
    """Caso C: Ordenamiento canónico estrictamente por po.id DESC."""
    res = get_production_orders_paginated(page=1, per_page=25)
    items = res["items"]
    ids = [ot["id"] for ot in items]
    sorted_ids = sorted(ids, reverse=True)
    assert ids == sorted_ids, f"El orden obtenido {ids} no coincide con po.id DESC {sorted_ids}"


def test_case_d_search_by_ot_number():
    """Caso D: Búsqueda server-side por número de OT (ot_number)."""
    res1 = get_production_orders_paginated(page=1, per_page=1)
    target_ot = res1["items"][0]
    target_number = target_ot["ot_number"]

    res_search = get_production_orders_paginated(search=target_number)
    assert res_search["total"] >= 1
    assert any(ot["ot_number"] == target_number for ot in res_search["items"])


def test_case_e_search_by_product_name():
    """Caso E: Búsqueda server-side por nombre de producto final."""
    res1 = get_production_orders_paginated(page=1, per_page=1)
    target_name = res1["items"][0]["final_product_name"]
    first_word = target_name.split()[0] if target_name else "Miel"

    res_search = get_production_orders_paginated(search=first_word)
    assert res_search["total"] >= 1
    for ot in res_search["items"]:
        match = (
            first_word.lower() in ot["final_product_name"].lower()
            or first_word.lower() in ot["final_product_sku"].lower()
            or first_word.lower() in ot["ot_number"].lower()
        )
        assert match, f"La OT {ot['ot_number']} no contiene el término buscado '{first_word}'"


def test_case_f_search_by_sku():
    """Caso F: Búsqueda server-side por SKU de producto final."""
    res1 = get_production_orders_paginated(page=1, per_page=1)
    target_sku = res1["items"][0]["final_product_sku"]

    res_search = get_production_orders_paginated(search=target_sku)
    assert res_search["total"] >= 1
    assert any(ot["final_product_sku"] == target_sku for ot in res_search["items"])


def test_case_g_filter_by_status():
    """Caso G: Filtro server-side por estado (ej. Borrador, Solicitada)."""
    res_draft = get_production_orders_paginated(status="Borrador", per_page=25)
    assert res_draft["total"] >= 1
    for ot in res_draft["items"]:
        assert ot["status"] == "Borrador"

    res_all = get_production_orders_paginated(status="all", per_page=25)
    assert res_all["total"] >= res_draft["total"]


def test_case_h_search_and_status_combined():
    """Caso H: Búsqueda combinada con filtro de estado."""
    res1 = get_production_orders_paginated(status="Borrador", per_page=1)
    if res1["items"]:
        ot = res1["items"][0]
        term = ot["ot_number"]
        res_comb = get_production_orders_paginated(search=term, status="Borrador")
        assert res_comb["total"] >= 1
        for o in res_comb["items"]:
            assert o["status"] == "Borrador"
            assert term.lower() in o["ot_number"].lower()


def test_case_i_page_sizes_25_50_100():
    """Caso I: Selector per_page (25, 50, 100) retorna los tamaños solicitados."""
    res25 = get_production_orders_paginated(per_page=25)
    res50 = get_production_orders_paginated(per_page=50)
    res100 = get_production_orders_paginated(per_page=100)

    assert len(res25["items"]) == 25
    assert len(res50["items"]) == 50
    assert len(res100["items"]) == 100
    assert res25["per_page"] == 25
    assert res50["per_page"] == 50
    assert res100["per_page"] == 100


def test_case_j_invalid_per_page_fallback():
    """Caso J: per_page inválido o fuera de rango (ej. 999, -1, 'abc') hace fallback a 25."""
    res_invalid_num = get_production_orders_paginated(per_page=999)
    assert res_invalid_num["per_page"] == 25
    assert len(res_invalid_num["items"]) == 25

    res_neg = get_production_orders_paginated(per_page=-5)
    assert res_neg["per_page"] == 25

    res_str = get_production_orders_paginated(per_page="invalido")
    assert res_str["per_page"] == 25


def test_case_k_url_parameter_preservation_in_view(auth_client):
    """Caso K: Conservación de parámetros en URL / vista HTML."""
    resp = auth_client.get('/produccion?status=Borrador&per_page=50&search=OT-')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    assert 'name="search" value="OT-"' in html
    assert 'value="50" selected' in html
    assert 'status=Borrador' in html
    assert 'per_page=50' in html


def test_case_l_no_regression_ot_draft_material_availability():
    """Caso L: Disponibilidad de materiales en BATCH calcula correctamente para OTs en Borrador."""
    res = get_production_orders_paginated(status="Borrador", per_page=10)
    draft_ids = [ot["id"] for ot in res["items"]]
    if draft_ids:
        batch_avail = get_material_availability_for_orders(draft_ids)
        assert len(batch_avail) == len(draft_ids)
        for ot_id in draft_ids:
            assert ot_id in batch_avail
            avail = batch_avail[ot_id]
            assert "is_complete" in avail
            assert "status_label" in avail
            assert "materials" in avail
            assert isinstance(avail["is_complete"], bool)


def test_case_m_no_regression_production_schedule():
    """Caso M: No regresión en el Calendario / Programación Semanal de Producción."""
    sched = list_scheduled_production_orders("2026-01-01", "2026-12-31")
    unsched = list_unscheduled_production_orders()
    assert isinstance(sched, list)
    assert isinstance(unsched, list)
