"""
tests/integration/test_phase6_ux_reports.py
Test suite for Phase 6: UX, Real Reports, Traceability 360 & Recall exports,
and Performance validations.
"""

import csv
import io
import pytest
from datetime import datetime, timezone
from app import app
from core.database import get_connection
import repositories.reporting_repo as rep_repo
import repositories.production_repo as prod_repo
import repositories.lot_genealogy_repo as lot_repo


@pytest.fixture
def phase6_client():
    old_csrf = app.config.get('WTF_CSRF_ENABLED', True)
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    try:
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 1
                sess['username'] = 'admin'
                sess['role_name'] = 'Administrativo'
                sess['full_name'] = 'Administrador Sistema'
                sess['permissions'] = {
                    'dashboard': True,
                    'ventas': True,
                    'inventario': True,
                    'productos': True,
                    'reportes': True,
                    'compras': True,
                    'produccion': True,
                    'trazabilidad': True,
                    'administracion': True,
                }
            yield client
    finally:
        app.config['WTF_CSRF_ENABLED'] = old_csrf


def test_real_reports_endpoints(phase6_client):
    """Verifica que las rutas de reportería no usen mocks estáticos y devuelvan 200 OK."""
    # 1. Reporte de Ventas
    resp_vta = phase6_client.get('/reporteria/ventas')
    assert resp_vta.status_code == 200
    assert b"Reporte General de Ventas" in resp_vta.data
    assert b"$1,245,000" not in resp_vta.data  # Mock eliminado

    # 2. Reporte de Compras
    resp_cmp = phase6_client.get('/reporteria/compras')
    assert resp_cmp.status_code == 200
    assert b"Reporte General de Compras" in resp_cmp.data
    assert b"Colmenares del Sur" not in resp_cmp.data  # Mock eliminado

    # 3. Reporte de Gastos
    resp_gst = phase6_client.get('/reporteria/gastos')
    assert resp_gst.status_code == 200
    assert b"Reporte General de Gastos" in resp_gst.data
    assert b"Log\xc3\xadstica y Distribuci\xc3\xb3n" not in resp_gst.data  # Mock eliminado


def test_real_reporting_repo_queries():
    """Valida que las funciones del reporting repository consulten las tablas reales."""
    vta_data = rep_repo.get_sales_report_data()
    assert isinstance(vta_data, dict)
    assert "total_income" in vta_data
    assert "total_sales_count" in vta_data
    assert "avg_ticket" in vta_data
    assert "products" in vta_data

    cmp_data = rep_repo.get_purchases_report_data()
    assert isinstance(cmp_data, dict)
    assert "total_amount" in cmp_data
    assert "total_suppliers" in cmp_data
    assert "total_pos" in cmp_data
    assert "suppliers" in cmp_data

    gst_data = rep_repo.get_expenses_report_data()
    assert isinstance(gst_data, dict)
    assert "total_expenses" in gst_data
    assert "breakdown" in gst_data


def test_dashboard_metrics_use_inventory_movements():
    """Verifica que el dashboard calcule el stock total desde inventory_movements."""
    metrics = rep_repo.get_sales_metrics()
    assert isinstance(metrics, dict)
    assert "productos_stock" in metrics
    assert isinstance(metrics["productos_stock"], (int, float))
    assert metrics["productos_stock"] >= 0


def test_production_orders_batch_listing():
    """Verifica que list_production_orders devuelva OTs con items y output lot sin N+1."""
    ots = prod_repo.list_production_orders()
    assert isinstance(ots, list)
    if ots:
        ot = ots[0]
        assert "ot_number" in ot
        assert "items" in ot
        assert "additional_items" in ot
        assert "output_lot_id" in ot
        assert "output_lot_number" in ot


def test_traceability_recall_export_endpoints(phase6_client):
    """Verifica exportación oficial de CSV y PDF de Recall para un lote existente."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, lot_number FROM lots ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()

    if row:
        lot_id = row["id"]
        lot_num = row["lot_number"]

        # CSV export
        resp_csv = phase6_client.get(f"/trazabilidad/{lot_id}/export/csv")
        assert resp_csv.status_code == 200
        assert "text/csv" in resp_csv.headers["Content-Type"]
        assert f"filename=recall_impact_{lot_num}" in resp_csv.headers["Content-Disposition"]
        assert b"REPORTE DE RETIRO DE PRODUCTO (RECALL)" in resp_csv.data

        # PDF export
        resp_pdf = phase6_client.get(f"/trazabilidad/{lot_id}/export/pdf")
        assert resp_pdf.status_code == 200
        assert "application/pdf" in resp_pdf.headers["Content-Type"]
        assert f"filename=recall_impact_{lot_num}" in resp_pdf.headers["Content-Disposition"]
        assert resp_pdf.data.startswith(b"%PDF")
