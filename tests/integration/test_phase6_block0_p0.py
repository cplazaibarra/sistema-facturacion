import pytest
import uuid
import time
from services.products_excel_service import store_preview_cache, pop_preview_cache
from db import get_connection

def test_store_and_pop_preview_postgresql_success():
    user_id = 9991
    items = [{"sku": "TEST-01", "name": "Miel Test", "action": "NUEVO"}]
    summary = {"total": 1, "nuevos": 1, "modificados": 0}

    import_id = store_preview_cache(user_id, items, summary)
    assert import_id is not None

    # Verificar que existe en la tabla de PostgreSQL
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, items, summary FROM excel_import_previews WHERE import_id = %s", (import_id,))
            row = cur.fetchone()
            assert row is not None
            assert row["user_id"] == str(user_id)

    # Worker B (otro contexto/llamada) recupera y consume atómicamente el preview
    data = pop_preview_cache(import_id, user_id)
    assert data is not None
    assert data["user_id"] == str(user_id)
    assert len(data["items"]) == 1
    assert data["items"][0]["sku"] == "TEST-01"

    # Single-use: un segundo intento de pop debe retornar None (evita replay attack / doble confirmación)
    data_second = pop_preview_cache(import_id, user_id)
    assert data_second is None

    # Verificar que fue eliminado de la base de datos
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM excel_import_previews WHERE import_id = %s", (import_id,))
            assert cur.fetchone() is None

def test_preview_isolation_between_users():
    user_a = 9992
    user_b = 9993
    items = [{"sku": "SEC-01", "name": "Sec Test"}]
    summary = {"total": 1}

    import_id = store_preview_cache(user_a, items, summary)

    # Usuario B intenta consumir el preview de Usuario A -> debe denegarse (None)
    stolen = pop_preview_cache(import_id, user_b)
    assert stolen is None

    # El preview original no se pierde y sigue intacto para Usuario A
    legit = pop_preview_cache(import_id, user_a)
    assert legit is not None
    assert legit["items"][0]["sku"] == "SEC-01"

def test_preview_expired():
    user_id = 9994
    items = [{"sku": "EXP-01"}]
    summary = {}

    import_id = store_preview_cache(user_id, items, summary)

    # Forzar fecha de expiración al pasado en BD
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE excel_import_previews SET expires_at = CURRENT_TIMESTAMP - INTERVAL '10 seconds' WHERE import_id = %s", (import_id,))
        conn.commit()

    # Consumir preview expirado debe retornar None
    res = pop_preview_cache(import_id, user_id)
    assert res is None

def test_ventas_reportes_redirects_to_official_report(auth_client):
    # La ruta legacy /ventas/reportes que tenía datos inventados ahora redirige a /reporteria/ventas
    res = auth_client.get('/ventas/reportes')
    assert res.status_code == 302
    assert '/reporteria/ventas' in res.headers['Location']

def test_new_sale_number_prefix_is_p():
    from db import get_next_sale_number
    num = get_next_sale_number()
    assert num.startswith("P-"), f"Expected number to start with 'P-', got '{num}'"

def test_cotizacion_displays_seller_name(auth_client):
    res = auth_client.get('/ventas/cotizaciones')
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert 'Vendedor Responsable:' in html
    assert 'modal-cot-seller' in html
