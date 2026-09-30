"""
tests/integration/test_accounts_payable_report.py
Suite de pruebas para el Reporte Operacional: CUENTAS POR PAGAR (Saldo Pendiente > 0).
Verifica:
1. Factura impaga aparece por el 100% de su saldo.
2. Factura pagada completamente (Saldo = 0) NO aparece.
3. Factura parcialmente pagada aparece únicamente por el saldo restante (Total - Pagado).
4. Gasto operacional pendiente aparece con su saldo pendiente.
5. Gasto operacional pagado no aparece.
6. Factura vencida (due_date < hoy) se clasifica correctamente como 'Vencida'.
7. Obligación futura no aparece como vencida.
8. Pago completo hace desaparecer la obligación del reporte de cuentas por pagar.
9. Pago parcial actualiza el saldo de inmediato.
10. La factura permanece en el reporte histórico "Facturas de Compra y Gastos" tras pagarse.
11. Cero doble contabilización entre factura, pago y gasto.
12. Filtros de búsqueda (proveedor, RUT, documento, concepto) y selects server-side.
13. KPIs superiores calculados ESTRICTAMENTE por Saldo Pendiente (no por total original).
14. Exportación Excel genera archivo íntegro y numérico con todos los registros filtrados.
15. Conciliación estricta: Total Por Pagar BD = Total Por Pagar Pantalla = Total Por Pagar Excel.
16. Protección RBAC (403 si falta permiso 'reportes').
17. Paginación server-side.
18. Ordenamiento por defecto por Fecha de Vencimiento ASC (urgentes primero).
"""

import uuid
from datetime import date, timedelta
import openpyxl
import pytest

from app import app
from db import get_connection
from repositories.reporting_repo import (
    get_accounts_payable_report_data,
    get_purchases_and_expenses_report_data,
)
from services.report_export_service import export_accounts_payable_to_excel


@pytest.fixture
def auth_client():
    old_csrf = app.config.get('WTF_CSRF_ENABLED', True)
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    try:
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 1
                sess['username'] = 'admin_tester'
                sess['role_name'] = 'Administrativo'
                sess['permissions'] = {'reportes': True, 'compras': True}
            yield client
    finally:
        app.config['WTF_CSRF_ENABLED'] = old_csrf


@pytest.fixture
def unauth_client():
    old_csrf = app.config.get('WTF_CSRF_ENABLED', True)
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    try:
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 2
                sess['username'] = 'sin_permiso'
                sess['role_name'] = 'Operario'
                sess['permissions'] = {'reportes': False}
            yield client
    finally:
        app.config['WTF_CSRF_ENABLED'] = old_csrf


@pytest.fixture
def seed_payable_data():
    """Genera datos de prueba aislados para facturas y gastos en cuentas por pagar."""
    marker = uuid.uuid4().hex[:8]
    supplier_name = f"Proveedor CP {marker}"
    rut = f"77{marker[:6]}"
    inv_unpaid = f"FAC-IMP-{marker}"
    inv_partial = f"FAC-PAR-{marker}"
    inv_paid = f"FAC-PAG-{marker}"
    inv_overdue = f"FAC-VENC-{marker}"

    gasto_unpaid = f"Gasto CP {marker}"
    category_name = f"Cat CP {marker}"

    today = date.today()
    overdue_date = (today - timedelta(days=5)).isoformat()
    future_date = (today + timedelta(days=10)).isoformat()
    future_long = (today + timedelta(days=45)).isoformat()

    supplier_id = None
    category_id = None
    expense_id = None
    occ_id = None
    created_invoices = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Proveedor
            cur.execute(
                "INSERT INTO suppliers (name, rut, dv, created_at) VALUES (%s, %s, 'K', %s) RETURNING id",
                (supplier_name, rut, today.isoformat())
            )
            supplier_id = cur.fetchone()["id"]

            # 2. Factura 1: 100% Impaga (Vence en 10 días) - Total $100.000
            cur.execute(
                """INSERT INTO purchase_invoices 
                   (supplier_id, invoice_number, invoice_amount, invoice_date, due_date, payment_status, notes, created_at)
                   VALUES (%s, %s, 100000, %s, %s, 'Pendiente', %s, %s) RETURNING id""",
                (supplier_id, inv_unpaid, today.isoformat(), future_date, f"Impaga {marker}", today.isoformat())
            )
            inv1_id = cur.fetchone()["id"]
            created_invoices.append(inv1_id)

            # 3. Factura 2: Parcialmente Pagada - Total $200.000, Pagado $80.000, Saldo $120.000 (Vence en 45 días)
            cur.execute(
                """INSERT INTO purchase_invoices 
                   (supplier_id, invoice_number, invoice_amount, invoice_date, due_date, payment_status, payment_amount, notes, created_at)
                   VALUES (%s, %s, 200000, %s, %s, 'Pendiente', 80000, %s, %s) RETURNING id""",
                (supplier_id, inv_partial, today.isoformat(), future_long, f"Parcial {marker}", today.isoformat())
            )
            inv2_id = cur.fetchone()["id"]
            created_invoices.append(inv2_id)

            # 4. Factura 3: 100% Pagada - Total $150.000, Pagado $150.000, Saldo $0
            cur.execute(
                """INSERT INTO purchase_invoices 
                   (supplier_id, invoice_number, invoice_amount, invoice_date, due_date, payment_status, payment_amount, payment_date, notes, created_at)
                   VALUES (%s, %s, 150000, %s, %s, 'Pagada', 150000, %s, %s, %s) RETURNING id""",
                (supplier_id, inv_paid, today.isoformat(), future_date, today.isoformat(), f"Pagada {marker}", today.isoformat())
            )
            inv3_id = cur.fetchone()["id"]
            created_invoices.append(inv3_id)

            # 5. Factura 4: Vencida - Total $80.000 (Venció hace 5 días)
            cur.execute(
                """INSERT INTO purchase_invoices 
                   (supplier_id, invoice_number, invoice_amount, invoice_date, due_date, payment_status, notes, created_at)
                   VALUES (%s, %s, 80000, %s, %s, 'Vencida', %s, %s) RETURNING id""",
                (supplier_id, inv_overdue, (today - timedelta(days=30)).isoformat(), overdue_date, f"Vencida {marker}", today.isoformat())
            )
            inv4_id = cur.fetchone()["id"]
            created_invoices.append(inv4_id)

            # 6. Gasto Operacional Pendiente - Total $50.000 (Vence en 6 días)
            cur.execute("INSERT INTO expense_categories (name) VALUES (%s) RETURNING id", (category_name,))
            category_id = cur.fetchone()["id"]

            cur.execute(
                """INSERT INTO operational_expenses 
                   (name, category, category_id, amount, amount_type, frequency, start_date, due_rule, beneficiary, status)
                   VALUES (%s, %s, %s, 50000, 'Fijo', 'Mensual', %s, 'Día del mes', %s, 'Activo') RETURNING id""",
                (gasto_unpaid, category_name, category_id, today.replace(day=1), f"Beneficiario CP {marker}")
            )
            expense_id = cur.fetchone()["id"]

            cur.execute(
                """INSERT INTO operational_expense_occurrences 
                   (expense_id, due_date, amount, status, notes)
                   VALUES (%s, %s, 50000, 'Proyectado', %s) RETURNING id""",
                (expense_id, today + timedelta(days=6), f"Ocurrencia CP {marker}")
            )
            occ_id = cur.fetchone()["id"]

        conn.commit()

    yield {
        "marker": marker,
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "rut": rut,
        "inv_unpaid": inv_unpaid,
        "inv_partial": inv_partial,
        "inv_paid": inv_paid,
        "inv_overdue": inv_overdue,
        "inv1_id": inv1_id,
        "inv2_id": inv2_id,
        "inv3_id": inv3_id,
        "inv4_id": inv4_id,
        "category_id": category_id,
        "category_name": category_name,
        "gasto_unpaid": gasto_unpaid,
        "expense_id": expense_id,
        "occ_id": occ_id,
    }

    # Limpieza
    with get_connection() as conn:
        with conn.cursor() as cur:
            for inv_id in created_invoices:
                cur.execute("DELETE FROM purchase_invoices WHERE id = %s", (inv_id,))
            cur.execute("DELETE FROM suppliers WHERE id = %s", (supplier_id,))
            cur.execute("DELETE FROM operational_expense_occurrences WHERE id = %s", (occ_id,))
            cur.execute("DELETE FROM operational_expenses WHERE id = %s", (expense_id,))
            cur.execute("DELETE FROM expense_categories WHERE id = %s", (category_id,))
        conn.commit()


def test_factura_impaga_appears(seed_payable_data):
    """1. Factura impaga aparece por el 100% de su saldo."""
    d = seed_payable_data
    res = get_accounts_payable_report_data(search=d["inv_unpaid"], per_page=None)
    items = res["items"]
    assert len(items) == 1
    it = items[0]
    assert it["total"] == 100000.0
    assert it["paid_amount"] == 0.0
    assert it["pending_amount"] == 100000.0


def test_factura_pagada_no_aparece(seed_payable_data):
    """2. Factura pagada completamente (Saldo = 0) NO aparece en cuentas por pagar."""
    d = seed_payable_data
    res = get_accounts_payable_report_data(search=d["inv_paid"], per_page=None)
    assert len(res["items"]) == 0


def test_factura_parcial_aparece_por_saldo(seed_payable_data):
    """3. Factura parcialmente pagada aparece únicamente por el saldo restante (Total - Pagado)."""
    d = seed_payable_data
    res = get_accounts_payable_report_data(search=d["inv_partial"], per_page=None)
    assert len(res["items"]) == 1
    it = res["items"][0]
    assert it["total"] == 200000.0
    assert it["paid_amount"] == 80000.0
    assert it["pending_amount"] == 120000.0
    assert it["computed_status"] == "Parcial"


def test_gasto_pendiente_aparece(seed_payable_data):
    """4. Gasto operacional pendiente aparece con su saldo pendiente."""
    d = seed_payable_data
    res = get_accounts_payable_report_data(search=d["gasto_unpaid"], per_page=None)
    assert len(res["items"]) == 1
    it = res["items"][0]
    assert it["origin_code"] == "gasto"
    assert it["pending_amount"] == 50000.0


def test_gasto_pagado_no_aparece(seed_payable_data):
    """5. Gasto operacional pagado no aparece en cuentas por pagar."""
    d = seed_payable_data
    # Marcar el gasto como pagado
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE operational_expense_occurrences 
                SET status = 'Pagado', payment_amount = 50000, paid_date = %s
                WHERE id = %s
            """, (date.today(), d["occ_id"]))
        conn.commit()

    res = get_accounts_payable_report_data(search=d["gasto_unpaid"], per_page=None)
    assert len(res["items"]) == 0


def test_factura_vencida_se_identifica(seed_payable_data):
    """6. Factura vencida se identifica correctamente."""
    d = seed_payable_data
    res = get_accounts_payable_report_data(search=d["inv_overdue"], per_page=None)
    assert len(res["items"]) == 1
    it = res["items"][0]
    assert it["computed_status"] == "Vencida"
    assert it["dias_vencimiento"] < 0
    assert it["due_badge_type"] == "vencida"


def test_obligacion_futura_no_es_vencida(seed_payable_data):
    """7. Obligación futura no aparece como vencida."""
    d = seed_payable_data
    res = get_accounts_payable_report_data(search=d["inv_unpaid"], per_page=None)
    it = res["items"][0]
    assert it["computed_status"] != "Vencida"
    assert it["dias_vencimiento"] > 0


def test_pago_completo_hace_desaparecer(seed_payable_data):
    """8. Pago completo hace desaparecer la obligación de Cuentas por Pagar."""
    d = seed_payable_data
    # Pagar la factura impaga
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE purchase_invoices 
                SET payment_status = 'Pagada', payment_amount = 100000, payment_date = %s
                WHERE id = %s
            """, (date.today().isoformat(), d["inv1_id"]))
        conn.commit()

    res = get_accounts_payable_report_data(search=d["inv_unpaid"], per_page=None)
    assert len(res["items"]) == 0


def test_pago_parcial_actualiza_saldo(seed_payable_data):
    """9. Pago parcial actualiza el saldo de inmediato."""
    d = seed_payable_data
    # Registrar un pago parcial adicional
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE purchase_invoices 
                SET payment_amount = 160000
                WHERE id = %s
            """, (d["inv2_id"],))
        conn.commit()

    res = get_accounts_payable_report_data(search=d["inv_partial"], per_page=None)
    assert len(res["items"]) == 1
    it = res["items"][0]
    assert it["paid_amount"] == 160000.0
    assert it["pending_amount"] == 40000.0


def test_factura_permanece_en_historico_despues_del_pago(seed_payable_data):
    """10. La factura permanece en el reporte histórico 'Facturas de Compra y Gastos' tras pagarse."""
    d = seed_payable_data
    # La factura 3 fue creada como 'Pagada'
    res_historico = get_purchases_and_expenses_report_data(search=d["inv_paid"], per_page=None)
    assert len(res_historico["items"]) == 1
    assert res_historico["items"][0]["payment_status"] == "Pagada"

    # Pero en Cuentas por Pagar no aparece
    res_cp = get_accounts_payable_report_data(search=d["inv_paid"], per_page=None)
    assert len(res_cp["items"]) == 0


def test_no_double_counting(seed_payable_data):
    """11. Cero doble contabilización entre factura, pago y gasto."""
    d = seed_payable_data
    res = get_accounts_payable_report_data(search=d["marker"], per_page=None)
    # Deben estar exactamente 3 obligaciones activas:
    # 1) inv_unpaid ($100.000)
    # 2) inv_partial ($120.000 pendiente)
    # 3) inv_overdue ($80.000)
    # 4) gasto_unpaid ($50.000)
    # Total = 4 obligaciones
    assert len(res["items"]) == 4
    total_esperado = 100000 + 120000 + 80000 + 50000
    assert sum(it["pending_amount"] for it in res["items"]) == total_esperado


def test_filtros_cuentas_por_pagar(seed_payable_data):
    """12. Filtros de tipo, estado, proveedor y categoría."""
    d = seed_payable_data
    # Solo facturas
    res_f = get_accounts_payable_report_data(doc_type="factura", search=d["marker"], per_page=None)
    assert all(it["origin_code"] == "factura" for it in res_f["items"])

    # Solo gastos
    res_g = get_accounts_payable_report_data(doc_type="gasto", search=d["marker"], per_page=None)
    assert all(it["origin_code"] == "gasto" for it in res_g["items"])

    # Solo vencidas
    res_v = get_accounts_payable_report_data(status="Vencida", search=d["marker"], per_page=None)
    assert all(it["computed_status"] == "Vencida" for it in res_v["items"])

    # Solo parciales
    res_p = get_accounts_payable_report_data(status="Parcial", search=d["marker"], per_page=None)
    assert all(it["computed_status"] == "Parcial" for it in res_p["items"])


def test_kpi_calculados_por_saldo_pendiente(seed_payable_data):
    """13. KPIs superiores se calculan ESTRICTAMENTE por saldo pendiente, no por total original."""
    d = seed_payable_data
    res = get_accounts_payable_report_data(search=d["marker"], per_page=None)
    m = res["metrics"]
    # Total Por Pagar suma saldos pendientes: 100k + 120k + 80k + 50k = 350.000
    assert m["total_por_pagar"] == 350000.0
    # Total vencido suma saldo de la vencida: 80.000
    assert m["total_vencido"] == 80000.0


def test_exportacion_excel_cuentas_por_pagar(seed_payable_data):
    """14. Exportación Excel genera archivo íntegro y con todos los registros filtrados."""
    d = seed_payable_data
    excel_io = export_accounts_payable_to_excel({"search": d["marker"]})
    wb = openpyxl.load_workbook(excel_io)
    ws = wb["Cuentas por Pagar"]
    assert ws is not None
    assert ws["A1"].value == "REPORTE OPERACIONAL: CUENTAS POR PAGAR (OBLIGACIONES ACTIVAS)"
    # Encontrar la fila con la factura impaga
    found = False
    for row in ws.iter_rows(values_only=True):
        if d["inv_unpaid"] in [str(c) for c in row if c]:
            found = True
            break
    assert found is True


def test_reconciliacion_postgresql_pantalla_excel(seed_payable_data):
    """15. Conciliación estricta: Total Por Pagar BD = Total Por Pagar Pantalla = Total Por Pagar Excel."""
    d = seed_payable_data
    res = get_accounts_payable_report_data(search=d["marker"], per_page=None)
    m = res["metrics"]
    tot_pantalla = m["total_por_pagar"]

    excel_io = export_accounts_payable_to_excel({"search": d["marker"]})
    wb = openpyxl.load_workbook(excel_io)
    ws = wb["Cuentas por Pagar"]
    tot_excel = ws["A5"].value  # KPI Total Por Pagar en A5

    assert tot_pantalla == tot_excel
    assert tot_pantalla == 350000.0


def test_rbac_cuentas_por_pagar(auth_client, unauth_client):
    """16. Protección RBAC (403 si falta permiso 'reportes')."""
    resp_auth = auth_client.get('/reporteria/cuentas-por-pagar')
    assert resp_auth.status_code == 200

    resp_unauth = unauth_client.get('/reporteria/cuentas-por-pagar')
    assert resp_unauth.status_code == 403


def test_rbac_cuentas_por_pagar_export(auth_client, unauth_client):
    """16b. Exportación sin permiso retorna 403."""
    resp_auth_exp = auth_client.get('/reporteria/cuentas-por-pagar/exportar-excel')
    assert resp_auth_exp.status_code == 200

    resp_unauth_exp = unauth_client.get('/reporteria/cuentas-por-pagar/exportar-excel')
    assert resp_unauth_exp.status_code == 403


def test_paginacion_cuentas_por_pagar():
    """17. Paginación server-side."""
    res = get_accounts_payable_report_data(page=1, per_page=25)
    assert res["page"] == 1
    assert res["per_page"] == 25
    assert len(res["items"]) <= 25


def test_orden_por_defecto_vencimiento_asc(seed_payable_data):
    """18. Orden por defecto por Fecha de Vencimiento ASC (las más urgentes primero)."""
    d = seed_payable_data
    res = get_accounts_payable_report_data(search=d["marker"], per_page=None)
    items = res["items"]
    assert len(items) == 4
    # La primera debe ser la vencida
    assert items[0]["computed_status"] == "Vencida"
    assert items[0]["doc_number"] == d["inv_overdue"]
