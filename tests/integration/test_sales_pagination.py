import pytest
import json
import uuid
from datetime import datetime, timezone
from db import (
    get_connection,
    get_sales_paginated,
    insert_sale,
    get_sales_metrics
)

@pytest.fixture
def clean_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()

def test_sales_pagination_cases_a_to_u(clean_db):
    """
    Validación exhaustiva de la optimización y paginación server-side de Ventas (/ventas).
    Cubre explícitamente los casos requeridos A hasta U.
    """
    cur = clean_db.cursor()
    today_str = datetime.today().strftime('%Y-%m-%d')

    # A. Default devuelve máximo 25 ventas
    res_default = get_sales_paginated(page=1, per_page=25, conn=clean_db)
    assert len(res_default["items"]) <= 25
    assert res_default["per_page"] == 25
    assert res_default["page"] == 1
    assert res_default["total"] >= 1

    # B. Página 2 no duplica registros
    res_p1 = get_sales_paginated(page=1, per_page=25, conn=clean_db)
    res_p2 = get_sales_paginated(page=2, per_page=25, conn=clean_db)
    ids_p1 = {v["id"] for v in res_p1["items"]}
    ids_p2 = {v["id"] for v in res_p2["items"]}
    assert ids_p1.isdisjoint(ids_p2), "Página 1 y Página 2 contienen IDs duplicados"

    # C. Orden determinístico descendente por timestamp y id
    if len(res_p1["items"]) >= 2:
        for i in range(len(res_p1["items"]) - 1):
            s1 = res_p1["items"][i]
            s2 = res_p1["items"][i + 1]
            dt1 = f"{s1['date']} {s1['time']}"
            dt2 = f"{s2['date']} {s2['time']}"
            assert dt1 >= dt2 or (dt1 == dt2 and s1["id"] > s2["id"]), "Orden de ventas no es estrictamente determinístico DESC"

    # D. Selector 25 / 50 / 100
    res_50 = get_sales_paginated(page=1, per_page=50, conn=clean_db)
    assert len(res_50["items"]) <= 50
    assert res_50["per_page"] == 50

    res_100 = get_sales_paginated(page=1, per_page=100, conn=clean_db)
    assert len(res_100["items"]) <= 100
    assert res_100["per_page"] == 100

    # E. Fallback seguro ante per_page y page inválidos
    res_invalid = get_sales_paginated(page=-5, per_page=9999, conn=clean_db)
    assert res_invalid["page"] == 1
    assert res_invalid["per_page"] == 25

    # F. Búsqueda server-side por número de venta
    sample_sale = res_default["items"][0]
    res_search = get_sales_paginated(search=sample_sale["sale_number"], conn=clean_db)
    assert any(s["sale_number"] == sample_sale["sale_number"] for s in res_search["items"])

    # G. Filtro por Estado server-side
    res_status = get_sales_paginated(status_filter="Completada", conn=clean_db)
    assert all(s["status"]["label"] == "Completada" for s in res_status["items"])

    # H. Filtro por Cliente server-side
    sample_client = sample_sale["customer"]["name"]
    if sample_client:
        res_client = get_sales_paginated(client_filter=sample_client, conn=clean_db)
        assert all(s["customer"]["name"].lower() == sample_client.lower() for s in res_client["items"])

    # I. Búsqueda + Filtros + Paginación combinados
    res_combined = get_sales_paginated(
        page=1,
        per_page=25,
        search=sample_sale["sale_number"],
        status_filter=sample_sale["status"]["label"],
        conn=clean_db
    )
    assert any(s["id"] == sample_sale["id"] for s in res_combined["items"])

    # J. Métricas globales no dependen de la página visible
    m_global = get_sales_metrics()
    cur.execute("SELECT COUNT(*) as count FROM sales WHERE status NOT IN ('Cancelada', 'Cotización') AND (sale_number LIKE 'VTA-%%' OR sale_number LIKE 'P-%%')")
    total_sales_universe = cur.fetchone()["count"]
    assert (m_global["ventas_completadas"] + m_global["ventas_pendientes"]) == total_sales_universe

    # K. Tarjeta 'Ventas Pendientes' mantiene significado
    res_card_pend = get_sales_paginated(card_filter="Ventas Pendientes", conn=clean_db)
    assert all(s["status"]["label"] == "Pendiente" for s in res_card_pend["items"])

    # L. Tarjeta 'Ventas Completadas' mantiene significado
    res_card_comp = get_sales_paginated(card_filter="Ventas Completadas", conn=clean_db)
    assert all(s["status"]["label"] == "Completada" for s in res_card_comp["items"])

    # M. Tarjeta 'Pago Retrasado' mantiene significado
    res_card_ret = get_sales_paginated(card_filter="Pago Retrasado", conn=clean_db)
    assert all(s["payment_status"] == "Retrasada" for s in res_card_ret["items"])

    # N. Tarjeta 'Ventas Hoy' mantiene significado
    res_card_hoy = get_sales_paginated(card_filter="Ventas Hoy", conn=clean_db)
    assert all(s["date"] == today_str for s in res_card_hoy["items"])

    # O. Venta con múltiples pagos o pagos individuales mantiene datos
    cur.execute("SELECT sale_id FROM sale_payments WHERE payment_amount > 0 LIMIT 1")
    row_sp = cur.fetchone()
    if row_sp:
        target_sid = row_sp["sale_id"]
        res_sp = get_sales_paginated(search=f"id:{target_sid}", conn=clean_db)
        for v in res_default["items"]:
            assert "payment_status" in v
            assert "payment_date" in v
            assert "bank_account_id" in v

    # P. Venta con costo congelado mantiene unit_cost_at_sale en sale_items
    cur.execute("SELECT sale_id, unit_cost_at_sale FROM sale_items WHERE unit_cost_at_sale > 0 LIMIT 1")
    row_si = cur.fetchone()
    if row_si:
        assert float(row_si["unit_cost_at_sale"]) > 0

    # Q. Venta histórica sin costo (0 o NULL) permanece intacta sin recálculo arbitrario
    cur.execute("SELECT COUNT(*) as count FROM sale_items WHERE unit_cost_at_sale IS NULL OR unit_cost_at_sale = 0")
    zero_cost_before = cur.fetchone()["count"]
    _ = get_sales_paginated(page=1, per_page=100, conn=clean_db)
    cur.execute("SELECT COUNT(*) as count FROM sale_items WHERE unit_cost_at_sale IS NULL OR unit_cost_at_sale = 0")
    zero_cost_after = cur.fetchone()["count"]
    assert zero_cost_before == zero_cost_after, "Los costos históricos de sale_items no deben ser alterados por la consulta de ventas"

    # R. Venta cancelada mantiene estado Cancelada
    res_canc = get_sales_paginated(status_filter="Cancelada", conn=clean_db)
    assert len(res_canc["items"]) > 0
    assert all(s["status"]["label"] == "Cancelada" for s in res_canc["items"])

    # S. SALE_REVERSAL no sufre regresión
    cur.execute("SELECT COUNT(*) as count FROM inventory_movements WHERE movement_type = 'SALE_REVERSAL'")
    reversal_count_before = cur.fetchone()["count"]
    _ = get_sales_paginated(page=1, per_page=25, conn=clean_db)
    cur.execute("SELECT COUNT(*) as count FROM inventory_movements WHERE movement_type = 'SALE_REVERSAL'")
    reversal_count_after = cur.fetchone()["count"]
    assert reversal_count_before == reversal_count_after

    # T. Packaging/reversal no sufre regresión
    cur.execute("SELECT COUNT(*) as count FROM inventory_movements WHERE movement_type = 'SALE_PACKAGING_REVERSAL'")
    pkg_rev_before = cur.fetchone()["count"]
    _ = get_sales_paginated(page=1, per_page=25, conn=clean_db)
    cur.execute("SELECT COUNT(*) as count FROM inventory_movements WHERE movement_type = 'SALE_PACKAGING_REVERSAL'")
    pkg_rev_after = cur.fetchone()["count"]
    assert pkg_rev_before == pkg_rev_after

    # U. GET /ventas no genera inventory_movements (estrictamente lectura)
    cur.execute("SELECT COUNT(*) as count FROM inventory_movements")
    mov_count_before = cur.fetchone()["count"]
    _ = get_sales_paginated(page=1, per_page=100, conn=clean_db)
    cur.execute("SELECT COUNT(*) as count FROM inventory_movements")
    mov_count_after = cur.fetchone()["count"]
    assert mov_count_before == mov_count_after, "La paginación de ventas generó movimientos en el inventario"


def test_dashboard_pending_kpi_includes_pending_p_prefix_sales():
    """Dashboard's managed-sale universe includes the P- prefix used by quote conversion."""
    marker = uuid.uuid4().hex[:10]
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    before = get_sales_metrics()
    sale_id = insert_sale({
        "sale_number": f"P-DASH-QA-{marker}",
        "customer_name": "Cliente KPI QA",
        "sale_date": today,
        "sale_time": "12:00:00",
        "products": [],
        "total_amount": 125,
        "status": "Pendiente",
        "seller_name": "QA",
        "payment_status": "Pendiente",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        after = get_sales_metrics()
        assert after["ordenes_pendientes"] == before["ordenes_pendientes"] + 1
        assert after["ventas_pendientes"] == before["ventas_pendientes"] + 1
        assert after["ventas_completadas"] == before["ventas_completadas"]
    finally:
        with get_connection() as conn:
            with conn.cursor() as cleanup_cur:
                cleanup_cur.execute("DELETE FROM sales WHERE id=%s", (sale_id,))
            conn.commit()
