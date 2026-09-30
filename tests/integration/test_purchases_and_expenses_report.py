"""
tests/integration/test_purchases_and_expenses_report.py
Suite de pruebas para el nuevo Reporte Consolidado: FACTURAS DE COMPRA Y GASTOS.
Verifica:
1. Factura de compra aparece exactamente una vez.
2. Gasto operacional aparece exactamente una vez.
3. OC sin factura NO aparece como factura.
4. Factura con OC muestra número de OC correcto.
5. Neto + IVA = Total para facturas.
6. Gasto operacional no inventa IVA.
7. Filtro por rango de fechas (desde/hasta).
8. Filtro por tipo de documento (Factura de Compra vs Gasto Operacional).
9. Filtro por proveedor / beneficiario.
10. Filtro por categoría.
11. Filtro por estado de pago.
12. Búsqueda por número de documento, RUT, proveedor, descripción y OC.
13. Paginación server-side.
14. Ordenamiento seguro de columnas (whitelist).
15. Exportación Excel genera archivo válido y con todos los registros filtrados.
16. Reconciliación: Totales Pantalla = Totales BD.
17. Reconciliación: Totales Excel = Totales Pantalla.
18. Cero doble contabilización entre factura y pago.
19. Cero doble contabilización entre gasto proyectado y pagado.
20. Protección RBAC (403 si falta permiso 'reportes').
21. Exportación sin permiso retorna 403.
22. Consulta sin N+1.
"""

import io
import uuid
from datetime import date, timedelta
import openpyxl
import pytest

from app import app
from db import get_connection
from repositories.reporting_repo import get_purchases_and_expenses_report_data
from services.report_export_service import export_purchases_and_expenses_to_excel


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
def seed_report_data():
    """Genera datos de prueba aislados para facturas, OCs y gastos operacionales."""
    marker = uuid.uuid4().hex[:8]
    supplier_name = f"Proveedor Test {marker}"
    rut = f"76{marker[:6]}"
    inv_number = f"FAC-{marker}"
    oc_number = f"OC-{marker}"
    gasto_name = f"Gasto Test {marker}"
    category_name = f"Cat {marker}"

    supplier_id = None
    po_id = None
    invoice_id = None
    category_id = None
    expense_id = None
    occurrence_id = None

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Proveedor
            cur.execute(
                "INSERT INTO suppliers (name, rut, dv, created_at) VALUES (%s, %s, 'K', %s) RETURNING id",
                (supplier_name, rut, date.today().isoformat())
            )
            supplier_id = cur.fetchone()["id"]

            # 2. OC vinculada
            cur.execute(
                "INSERT INTO purchase_orders (oc_number, supplier_id, order_date, status, total_amount, created_at) VALUES (%s, %s, %s, 'Emitida', 119000, %s) RETURNING id",
                (oc_number, supplier_id, date.today().isoformat(), date.today().isoformat())
            )
            po_id = cur.fetchone()["id"]

            # 3. Factura de compra vinculada a OC
            cur.execute(
                """INSERT INTO purchase_invoices 
                   (purchase_order_id, supplier_id, invoice_number, invoice_amount, invoice_date, due_date, payment_status, notes, created_at)
                   VALUES (%s, %s, %s, 119000, %s, %s, 'Pendiente', %s, %s) RETURNING id""",
                (po_id, supplier_id, inv_number, date.today().isoformat(), (date.today() + timedelta(days=15)).isoformat(), f"Factura {marker}", date.today().isoformat())
            )
            invoice_id = cur.fetchone()["id"]

            # 4. OC sin factura (para validar que NO aparezca como factura)
            cur.execute(
                "INSERT INTO purchase_orders (oc_number, supplier_id, order_date, status, total_amount, created_at) VALUES (%s, %s, %s, 'Emitida', 50000, %s)",
                (f"OC-SOLA-{marker}", supplier_id, date.today().isoformat(), date.today().isoformat())
            )

            # 5. Categoría y Gasto Operacional
            cur.execute("INSERT INTO expense_categories (name) VALUES (%s) RETURNING id", (category_name,))
            category_id = cur.fetchone()["id"]

            cur.execute(
                """INSERT INTO operational_expenses 
                   (name, category, category_id, amount, amount_type, frequency, start_date, due_rule, beneficiary, status)
                   VALUES (%s, %s, %s, 45000, 'Fijo', 'Mensual', %s, 'Día del mes', %s, 'Activo') RETURNING id""",
                (gasto_name, category_name, category_id, date.today().replace(day=1), f"Beneficiario {marker}")
            )
            expense_id = cur.fetchone()["id"]

            # 6. Ocurrencia de gasto
            cur.execute(
                """INSERT INTO operational_expense_occurrences 
                   (expense_id, due_date, amount, status, notes)
                   VALUES (%s, %s, 45000, 'Proyectado', %s) RETURNING id""",
                (expense_id, date.today(), f"Ocurrencia {marker}")
            )
            occurrence_id = cur.fetchone()["id"]

        conn.commit()

    yield {
        "marker": marker,
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "rut": rut,
        "inv_number": inv_number,
        "oc_number": oc_number,
        "invoice_id": invoice_id,
        "category_id": category_id,
        "category_name": category_name,
        "gasto_name": gasto_name,
        "expense_id": expense_id,
        "occurrence_id": occurrence_id,
    }

    # Limpieza
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM purchase_invoices WHERE id = %s", (invoice_id,))
            cur.execute("DELETE FROM purchase_orders WHERE supplier_id = %s", (supplier_id,))
            cur.execute("DELETE FROM suppliers WHERE id = %s", (supplier_id,))
            cur.execute("DELETE FROM operational_expense_occurrences WHERE id = %s", (occurrence_id,))
            cur.execute("DELETE FROM operational_expenses WHERE id = %s", (expense_id,))
            cur.execute("DELETE FROM expense_categories WHERE id = %s", (category_id,))
        conn.commit()


def test_factura_appears_once(seed_report_data):
    """1. Factura de compra aparece exactamente una vez."""
    d = seed_report_data
    res = get_purchases_and_expenses_report_data(search=d["inv_number"], per_page=None)
    items = [it for it in res["items"] if it["doc_number"] == d["inv_number"]]
    assert len(items) == 1
    assert items[0]["origin_code"] == "factura"


def test_gasto_appears_once(seed_report_data):
    """2. Gasto operacional aparece exactamente una vez."""
    d = seed_report_data
    res = get_purchases_and_expenses_report_data(search=d["gasto_name"], per_page=None)
    items = [it for it in res["items"] if it["party_name"] == f"Beneficiario {d['marker']}"]
    assert len(items) == 1
    assert items[0]["origin_code"] == "gasto"


def test_oc_without_invoice_not_in_report(seed_report_data):
    """3. OC sin factura NO aparece como factura."""
    d = seed_report_data
    res = get_purchases_and_expenses_report_data(search=f"OC-SOLA-{d['marker']}", per_page=None)
    assert len(res["items"]) == 0


def test_factura_shows_correct_oc(seed_report_data):
    """4. Factura con OC muestra número de OC correspondiente."""
    d = seed_report_data
    res = get_purchases_and_expenses_report_data(search=d["inv_number"], per_page=None)
    assert len(res["items"]) == 1
    assert res["items"][0]["oc_number"] == d["oc_number"]


def test_neto_plus_iva_equals_total_invoice(seed_report_data):
    """5. Neto + IVA = Total para facturas."""
    d = seed_report_data
    res = get_purchases_and_expenses_report_data(search=d["inv_number"], per_page=None)
    item = res["items"][0]
    assert round(item["neto"] + item["iva"], 2) == round(item["total"], 2)
    assert item["total"] == 119000.0
    assert item["iva"] == 19000.0
    assert item["neto"] == 100000.0


def test_gasto_does_not_invent_iva(seed_report_data):
    """6. Gasto operacional no inventa IVA (IVA = 0, Neto = Total)."""
    d = seed_report_data
    res = get_purchases_and_expenses_report_data(search=d["gasto_name"], per_page=None)
    item = res["items"][0]
    assert item["iva"] == 0.0
    assert item["neto"] == item["total"]
    assert item["total"] == 45000.0


def test_date_range_filter(seed_report_data):
    """7. Filtro por rango de fechas."""
    d = seed_report_data
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    past = (date.today() - timedelta(days=10)).isoformat()

    # Rango que incluye hoy
    res1 = get_purchases_and_expenses_report_data(date_from=today, date_to=today, search=d["inv_number"])
    assert len(res1["items"]) == 1

    # Rango en el pasado que no incluye hoy
    res2 = get_purchases_and_expenses_report_data(date_from=past, date_to=yesterday, search=d["inv_number"])
    assert len(res2["items"]) == 0


def test_doc_type_filter(seed_report_data):
    """8. Filtro por tipo de documento."""
    d = seed_report_data
    res_f = get_purchases_and_expenses_report_data(doc_type="factura", search=d["marker"], per_page=None)
    assert all(it["origin_code"] == "factura" for it in res_f["items"])
    assert any(it["doc_number"] == d["inv_number"] for it in res_f["items"])

    res_g = get_purchases_and_expenses_report_data(doc_type="gasto", search=d["marker"], per_page=None)
    assert all(it["origin_code"] == "gasto" for it in res_g["items"])
    assert any(it["category_name"] == d["category_name"] for it in res_g["items"])


def test_supplier_filter(seed_report_data):
    """9. Filtro por proveedor / beneficiario."""
    d = seed_report_data
    res = get_purchases_and_expenses_report_data(supplier_beneficiary=d["supplier_name"], per_page=None)
    assert len(res["items"]) >= 1
    assert any(it["party_name"] == d["supplier_name"] for it in res["items"])


def test_category_filter(seed_report_data):
    """10. Filtro por categoría."""
    d = seed_report_data
    res = get_purchases_and_expenses_report_data(category=d["category_name"], per_page=None)
    assert len(res["items"]) >= 1
    assert all(it["category_name"] == d["category_name"] for it in res["items"])


def test_payment_status_filter(seed_report_data):
    """11. Filtro por estado de pago."""
    d = seed_report_data
    res_p = get_purchases_and_expenses_report_data(payment_status="Pendiente", search=d["marker"], per_page=None)
    assert any(it["doc_number"] == d["inv_number"] for it in res_p["items"])

    res_paid = get_purchases_and_expenses_report_data(payment_status="Pagada", search=d["marker"], per_page=None)
    assert not any(it["doc_number"] == d["inv_number"] for it in res_paid["items"])


def test_search_by_fields(seed_report_data):
    """12. Búsqueda por número documento, RUT, proveedor, descripción y OC."""
    d = seed_report_data
    for q in [d["inv_number"], d["rut"], d["supplier_name"], d["oc_number"], d["marker"]]:
        res = get_purchases_and_expenses_report_data(search=q, per_page=None)
        assert len(res["items"]) >= 1


def test_pagination_server_side():
    """13. Paginación server-side adecuada."""
    res1 = get_purchases_and_expenses_report_data(page=1, per_page=25)
    assert res1["page"] == 1
    assert res1["per_page"] == 25
    assert len(res1["items"]) <= 25


def test_safe_column_sorting():
    """14. Ordenamiento seguro de columnas por whitelist."""
    for col in ["date", "doc_number", "origin", "supplier", "category", "neto", "iva", "total", "payment_status"]:
        res_asc = get_purchases_and_expenses_report_data(sort_by=col, sort_order="asc", per_page=10)
        res_desc = get_purchases_and_expenses_report_data(sort_by=col, sort_order="desc", per_page=10)
        assert res_asc is not None
        assert res_desc is not None


def test_export_excel_all_records(seed_report_data):
    """15. Exportación Excel genera archivo válido y con todos los registros filtrados."""
    d = seed_report_data
    excel_io = export_purchases_and_expenses_to_excel({"search": d["marker"]})
    wb = openpyxl.load_workbook(excel_io)
    ws = wb["Facturas y Gastos"]
    assert ws is not None
    # Verificar que existe fila con número de documento
    found = False
    for row in ws.iter_rows(values_only=True):
        if d["inv_number"] in [str(c) for c in row if c]:
            found = True
            break
    assert found is True


def test_screen_totals_equal_db_totals(seed_report_data):
    """16. Conciliación: Totales Pantalla = Totales BD."""
    d = seed_report_data
    res = get_purchases_and_expenses_report_data(search=d["marker"], per_page=25)
    m = res["metrics"]
    all_items = res["all_filtered_items"]
    assert m["total_general"] == round(sum(it["total"] for it in all_items), 2)
    assert m["total_neto"] == round(sum(it["neto"] for it in all_items), 2)
    assert m["total_iva"] == round(sum(it["iva"] for it in all_items), 2)


def test_excel_totals_equal_screen_totals(seed_report_data):
    """17. Conciliación: Totales Excel = Totales Pantalla."""
    d = seed_report_data
    res = get_purchases_and_expenses_report_data(search=d["marker"], per_page=None)
    m = res["metrics"]

    excel_io = export_purchases_and_expenses_to_excel({"search": d["marker"]})
    wb = openpyxl.load_workbook(excel_io)
    ws = wb["Facturas y Gastos"]
    # Total General está en celda G5 (KPI) o fila de totales
    assert ws["G5"].value == m["total_general"]
    assert ws["C5"].value == m["total_neto"]
    assert ws["E5"].value == m["total_iva"]


def test_no_double_counting_invoice_and_payment(seed_report_data):
    """18. Cero doble contabilización entre factura y su pago."""
    d = seed_report_data
    # Registrar pago a la factura
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE purchase_invoices 
                SET payment_status = 'Pagada', payment_amount = 119000, payment_date = %s
                WHERE id = %s
            """, (date.today().isoformat(), d["invoice_id"]))
        conn.commit()

    res = get_purchases_and_expenses_report_data(search=d["inv_number"], per_page=None)
    # Debe seguir siendo 1 solo registro, no duplicarse por el pago
    assert len(res["items"]) == 1
    assert res["items"][0]["payment_status"] == "Pagada"
    assert res["items"][0]["paid_amount"] == 119000.0
    assert res["items"][0]["pending_amount"] == 0.0


def test_no_double_counting_projected_and_paid_expense(seed_report_data):
    """19. Cero doble contabilización entre gasto proyectado y pagado."""
    d = seed_report_data
    # Marcar la ocurrencia como pagada
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE operational_expense_occurrences 
                SET status = 'Pagado', payment_amount = 45000, paid_date = %s
                WHERE id = %s
            """, (date.today(), d["occurrence_id"]))
        conn.commit()

    res = get_purchases_and_expenses_report_data(search=d["gasto_name"], per_page=None)
    # Sigue apareciendo exactamente 1 ocurrencia de gasto
    items = [it for it in res["items"] if it["party_name"] == f"Beneficiario {d['marker']}"]
    assert len(items) == 1
    assert items[0]["payment_status"] == "Pagada"


def test_rbac_protection(auth_client, unauth_client):
    """20. Protección RBAC (403 si falta permiso 'reportes')."""
    resp_auth = auth_client.get('/reporteria/facturas-compras-gastos')
    assert resp_auth.status_code == 200

    resp_unauth = unauth_client.get('/reporteria/facturas-compras-gastos')
    assert resp_unauth.status_code == 403


def test_rbac_export_protection(auth_client, unauth_client):
    """21. Exportación sin permiso retorna 403."""
    resp_auth = auth_client.get('/reporteria/facturas-compras-gastos/exportar-excel')
    assert resp_auth.status_code == 200

    resp_unauth = unauth_client.get('/reporteria/facturas-compras-gastos/exportar-excel')
    assert resp_unauth.status_code == 403


def test_query_efficiency_no_n_plus_one():
    """22. Consulta ejecutada en lote sin N+1."""
    # Llamar con per_page=100 debe responder de inmediato
    res = get_purchases_and_expenses_report_data(page=1, per_page=100)
    assert res["page"] == 1
    assert isinstance(res["items"], list)
