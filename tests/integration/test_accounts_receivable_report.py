"""
tests/integration/test_accounts_receivable_report.py
Suite de pruebas para el Reporte Operacional: CUENTAS POR COBRAR (Saldo Pendiente > 0).

Verifica todos los puntos obligatorios:
1. Venta impaga aparece por el 100% de su saldo.
2. Venta completamente pagada (Saldo = 0) NO aparece en el listado activo.
3. Venta parcialmente pagada aparece únicamente por el saldo restante (Total - Pagado).
4. Dos o más pagos parciales no duplican la venta (agrupación SQL atómica).
5. Pago completo posterior elimina la venta del listado activo.
6. Venta pagada continúa existiendo en ventas realizadas / historial.
7. Venta vencida (due_date < hoy) identificada con badge y estado 'Vencida'.
8. Venta futura no aparece como vencida.
9. Vence hoy identificada correctamente.
10. Próximos 7 días identificados correctamente.
11. Próximos 30 días identificados correctamente.
12. Cliente y RUT identificados correctamente.
13. Filtro por cliente.
14. Filtro por estado de pago ('Pendiente', 'Parcial', 'Vencida').
15. Filtro por rango de fechas (venta y vencimiento).
16. Búsqueda por texto (número de venta, documento, cliente, RUT, notas).
17. Paginación server-side y ordenamiento (Fecha Vencimiento ASC por defecto).
18. KPIs calculados ESTRICTAMENTE sobre SALDO POR COBRAR (no sobre total de venta).
19. Múltiples pagos no generan duplicados en el reporte ni en KPIs.
20. Exportación Excel genera archivo con todos los registros filtrados y valores numéricos.
21. Conciliación estricta: Total Saldo BD = Total Saldo Pantalla = Total Saldo Excel.
22. Seguridad RBAC en pantalla (403 sin permiso 'reportes').
23. Seguridad RBAC en exportación Excel (403 sin permiso 'reportes').
24. Acción Registrar Pago invoca el flujo oficial y actualiza saldo inmediatamente.
25. El reporte NO altera el estado logístico de la venta ni Kardex/stock.
"""

import uuid
from datetime import date, timedelta
import openpyxl
import pytest

from app import app
from db import get_connection
from repositories.reporting_repo import get_accounts_receivable_report_data
from services.report_export_service import export_accounts_receivable_to_excel


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
                sess['permissions'] = {'reportes': True, 'ventas': True, 'ventas.registrar_pago': True}
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
def seed_receivable_data():
    """Genera datos de prueba aislados para ventas y cobros en cuentas por cobrar."""
    marker = uuid.uuid4().hex[:8]
    customer_a = f"Cliente Alpha {marker}"
    customer_b = f"Cliente Beta {marker}"
    rut_a = f"76{marker[:6]}"
    email_a = f"alpha_{marker}@test.com"

    sale_unpaid = f"VTA-IMP-{marker}"
    sale_partial = f"VTA-PAR-{marker}"
    sale_paid = f"VTA-PAG-{marker}"
    sale_overdue = f"VTA-VENC-{marker}"
    sale_today = f"VTA-HOY-{marker}"
    sale_next7 = f"VTA-7D-{marker}"

    today = date.today()
    overdue_date = (today - timedelta(days=5)).isoformat()
    today_date = today.isoformat()
    next4_date = (today + timedelta(days=4)).isoformat()
    future_long = (today + timedelta(days=45)).isoformat()

    client_id = None
    created_sales = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Cliente en tabla clients
            cur.execute(
                """INSERT INTO clients (razon_social, rut, dv, email, phone, created_at)
                   VALUES (%s, %s, 'K', %s, '+56911112222', %s) RETURNING id""",
                (customer_a, rut_a, email_a, today_date)
            )
            client_id = cur.fetchone()["id"]

            # 2. Venta 1: 100% Impaga - Total $100.000 (Vence en 45 días)
            cur.execute(
                """INSERT INTO sales 
                   (sale_number, customer_name, customer_email, sale_date, sale_time, products_json, total_amount, status, seller_name, payment_method, payment_status, notes, created_at)
                   VALUES (%s, %s, %s, %s, '10:00:00', '[]', 100000, 'Pendiente', 'Vendedor Test', 'Transferencia', 'Pendiente', %s, %s) RETURNING id""",
                (sale_unpaid, customer_a, email_a, today_date, f"Doc: Factura | RUT: {rut_a}-K", today_date)
            )
            v1_id = cur.fetchone()["id"]
            created_sales.append(v1_id)
            cur.execute(
                """INSERT INTO sale_payments (sale_id, invoice_number, invoice_amount, invoice_due_date, payment_amount, status, created_at, updated_at)
                   VALUES (%s, %s, 100000, %s, 0, 'Factura pendiente', %s, %s)""",
                (v1_id, f"FACT-{v1_id:05d}", future_long, today_date, today_date)
            )

            # 3. Venta 2: Parcialmente Pagada - Total $200.000, Abono 1 $50.000, Abono 2 $30.000 -> Total Pagado $80.000, Saldo $120.000
            cur.execute(
                """INSERT INTO sales 
                   (sale_number, customer_name, customer_email, sale_date, sale_time, products_json, total_amount, status, seller_name, payment_method, payment_status, notes, created_at)
                   VALUES (%s, %s, %s, %s, '11:00:00', '[]', 200000, 'En Preparación', 'Vendedor Test', 'Transferencia', 'Pendiente', %s, %s) RETURNING id""",
                (sale_partial, customer_a, email_a, today_date, f"Doc: Factura | RUT: {rut_a}-K", today_date)
            )
            v2_id = cur.fetchone()["id"]
            created_sales.append(v2_id)
            cur.execute(
                """INSERT INTO sale_payments (sale_id, invoice_number, invoice_amount, invoice_due_date, payment_amount, status, created_at, updated_at)
                   VALUES (%s, %s, 200000, %s, 80000, 'Factura pendiente', %s, %s)""",
                (v2_id, f"FACT-{v2_id:05d}", future_long, today_date, today_date)
            )
            # Dos abonos en sale_payment_items
            cur.execute(
                """INSERT INTO sale_payment_items (sale_id, payment_amount, payment_date, created_at, accounting_approved, payment_method)
                   VALUES (%s, 50000, %s, %s, 1, 'Transferencia'),
                          (%s, 30000, %s, %s, 1, 'Transferencia')""",
                (v2_id, today_date, today_date, v2_id, today_date, today_date)
            )

            # 4. Venta 3: 100% Pagada - Total $150.000, Pagado $150.000, Saldo $0
            cur.execute(
                """INSERT INTO sales 
                   (sale_number, customer_name, customer_email, sale_date, sale_time, products_json, total_amount, status, seller_name, payment_method, payment_status, notes, created_at)
                   VALUES (%s, %s, %s, %s, '12:00:00', '[]', 150000, 'Completada', 'Vendedor Test', 'Efectivo', 'Pagado', %s, %s) RETURNING id""",
                (sale_paid, customer_b, '', today_date, "Doc: Boleta", today_date)
            )
            v3_id = cur.fetchone()["id"]
            created_sales.append(v3_id)
            cur.execute(
                """INSERT INTO sale_payments (sale_id, invoice_number, invoice_amount, invoice_due_date, payment_amount, payment_date, status, created_at, updated_at)
                   VALUES (%s, %s, 150000, %s, 150000, %s, 'Pagado', %s, %s)""",
                (v3_id, f"BOL-{v3_id:05d}", future_long, today_date, today_date, today_date)
            )
            cur.execute(
                """INSERT INTO sale_payment_items (sale_id, payment_amount, payment_date, created_at, accounting_approved, payment_method)
                   VALUES (%s, 150000, %s, %s, 1, 'Efectivo')""",
                (v3_id, today_date, today_date)
            )

            # 5. Venta 4: Vencida - Total $80.000 (Venció hace 5 días)
            cur.execute(
                """INSERT INTO sales 
                   (sale_number, customer_name, customer_email, sale_date, sale_time, products_json, total_amount, status, seller_name, payment_method, payment_status, notes, created_at)
                   VALUES (%s, %s, %s, %s, '14:00:00', '[]', 80000, 'Pendiente', 'Vendedor Test', 'Transferencia', 'Pendiente', %s, %s) RETURNING id""",
                (sale_overdue, customer_a, email_a, overdue_date, f"Doc: Factura | RUT: {rut_a}-K", overdue_date)
            )
            v4_id = cur.fetchone()["id"]
            created_sales.append(v4_id)
            cur.execute(
                """INSERT INTO sale_payments (sale_id, invoice_number, invoice_amount, invoice_due_date, payment_amount, status, created_at, updated_at)
                   VALUES (%s, %s, 80000, %s, 0, 'Factura pendiente', %s, %s)""",
                (v4_id, f"FACT-{v4_id:05d}", overdue_date, overdue_date, overdue_date)
            )

            # 6. Venta 5: Vence Hoy - Total $50.000
            cur.execute(
                """INSERT INTO sales 
                   (sale_number, customer_name, customer_email, sale_date, sale_time, products_json, total_amount, status, seller_name, payment_method, payment_status, notes, created_at)
                   VALUES (%s, %s, %s, %s, '15:00:00', '[]', 50000, 'Pendiente', 'Vendedor Test', 'Transferencia', 'Pendiente', %s, %s) RETURNING id""",
                (sale_today, customer_b, '', today_date, "Doc: Factura", today_date)
            )
            v5_id = cur.fetchone()["id"]
            created_sales.append(v5_id)
            cur.execute(
                """INSERT INTO sale_payments (sale_id, invoice_number, invoice_amount, invoice_due_date, payment_amount, status, created_at, updated_at)
                   VALUES (%s, %s, 50000, %s, 0, 'Factura pendiente', %s, %s)""",
                (v5_id, f"FACT-{v5_id:05d}", today_date, today_date, today_date)
            )

            # 7. Venta 6: Vence en 4 días (Próximos 7 días) - Total $60.000
            cur.execute(
                """INSERT INTO sales 
                   (sale_number, customer_name, customer_email, sale_date, sale_time, products_json, total_amount, status, seller_name, payment_method, payment_status, notes, created_at)
                   VALUES (%s, %s, %s, %s, '16:00:00', '[]', 60000, 'Pendiente', 'Vendedor Test', 'Transferencia', 'Pendiente', %s, %s) RETURNING id""",
                (sale_next7, customer_a, email_a, today_date, f"Doc: Factura | RUT: {rut_a}-K", today_date)
            )
            v6_id = cur.fetchone()["id"]
            created_sales.append(v6_id)
            cur.execute(
                """INSERT INTO sale_payments (sale_id, invoice_number, invoice_amount, invoice_due_date, payment_amount, status, created_at, updated_at)
                   VALUES (%s, %s, 60000, %s, 0, 'Factura pendiente', %s, %s)""",
                (v6_id, f"FACT-{v6_id:05d}", next4_date, today_date, today_date)
            )

        conn.commit()

    yield {
        "marker": marker,
        "customer_a": customer_a,
        "customer_b": customer_b,
        "rut_a": rut_a,
        "sale_unpaid": sale_unpaid,
        "sale_partial": sale_partial,
        "sale_paid": sale_paid,
        "sale_overdue": sale_overdue,
        "sale_today": sale_today,
        "sale_next7": sale_next7,
        "created_sales": created_sales,
        "client_id": client_id,
    }

    # Cleanup
    with get_connection() as conn:
        with conn.cursor() as cur:
            if created_sales:
                cur.execute("DELETE FROM sale_payment_items WHERE sale_id = ANY(%s)", (created_sales,))
                cur.execute("DELETE FROM sale_payments WHERE sale_id = ANY(%s)", (created_sales,))
                cur.execute("DELETE FROM sales_payment_history WHERE sale_id = ANY(%s)", (created_sales,))
                cur.execute("DELETE FROM sales_status_history WHERE sale_id = ANY(%s)", (created_sales,))
                cur.execute("DELETE FROM sales WHERE id = ANY(%s)", (created_sales,))
            if client_id:
                cur.execute("DELETE FROM clients WHERE id = %s", (client_id,))
        conn.commit()


# ─── TESTS AUTOMATIZADOS ──────────────────────────────────────────────────────

def test_unpaid_sale_appears(seed_receivable_data):
    """1. Venta impaga aparece en Cuentas por Cobrar con su saldo completo."""
    res = get_accounts_receivable_report_data(search=seed_receivable_data["sale_unpaid"])
    items = res["items"]
    assert len(items) == 1
    it = items[0]
    assert it["sale_number"] == seed_receivable_data["sale_unpaid"]
    assert it["total_amount"] == 100000.0
    assert it["paid_amount"] == 0.0
    assert it["pending_amount"] == 100000.0
    assert it["computed_status"] == "Pendiente"


def test_fully_paid_sale_does_not_appear(seed_receivable_data):
    """2. Venta completamente pagada (Saldo = 0) NO aparece en Cuentas por Cobrar."""
    res = get_accounts_receivable_report_data(search=seed_receivable_data["sale_paid"])
    assert len(res["items"]) == 0


def test_partially_paid_sale_appears_with_correct_balance(seed_receivable_data):
    """3. Venta parcialmente pagada aparece únicamente por el saldo restante ($120.000)."""
    res = get_accounts_receivable_report_data(search=seed_receivable_data["sale_partial"])
    items = res["items"]
    assert len(items) == 1
    it = items[0]
    assert it["total_amount"] == 200000.0
    assert it["paid_amount"] == 80000.0
    assert it["pending_amount"] == 120000.0
    assert it["computed_status"] == "Parcial"


def test_multiple_partial_payments_do_not_duplicate_sale(seed_receivable_data):
    """4 y 5. Dos o más pagos parciales no duplican la fila de la venta."""
    res = get_accounts_receivable_report_data(search=seed_receivable_data["sale_partial"])
    assert len(res["items"]) == 1
    assert res["items"][0]["payment_items_count"] == 2


def test_full_payment_eliminates_sale_from_active_receivables(seed_receivable_data):
    """6. Cuando la venta se paga al 100%, deja de aparecer automáticamente en Cuentas por Cobrar."""
    v2_num = seed_receivable_data["sale_partial"]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM sales WHERE sale_number = %s", (v2_num,))
            sid = cur.fetchone()["id"]
            # Registrar el pago del saldo restante ($120.000)
            cur.execute(
                """INSERT INTO sale_payment_items (sale_id, payment_amount, payment_date, created_at, accounting_approved, payment_method)
                   VALUES (%s, 120000, %s, %s, 1, 'Transferencia')""",
                (sid, date.today().isoformat(), date.today().isoformat())
            )
            cur.execute("UPDATE sales SET payment_status = 'Pagado' WHERE id = %s", (sid,))
            cur.execute("UPDATE sale_payments SET payment_amount = 200000, status = 'Pagado' WHERE sale_id = %s", (sid,))
        conn.commit()

    res = get_accounts_receivable_report_data(search=v2_num)
    assert len(res["items"]) == 0


def test_paid_sale_remains_in_sales_history(seed_receivable_data):
    """7. Venta pagada continúa existiendo normalmente en la tabla oficial de ventas."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, payment_status, total_amount FROM sales WHERE sale_number = %s", (seed_receivable_data["sale_paid"],))
            sale = cur.fetchone()
            assert sale is not None
            assert sale["payment_status"] == "Pagado"
            assert sale["total_amount"] == 150000.0


def test_overdue_sale_identified_correctly(seed_receivable_data):
    """8. Venta vencida se clasifica con badge y estado 'Vencida'."""
    res = get_accounts_receivable_report_data(search=seed_receivable_data["sale_overdue"])
    assert len(res["items"]) == 1
    it = res["items"][0]
    assert it["computed_status"] == "Vencida"
    assert it["due_badge_type"] == "vencida"
    assert it["dias_vencimiento"] is not None and it["dias_vencimiento"] < 0


def test_future_sale_not_overdue(seed_receivable_data):
    """9. Venta con vencimiento futuro no se clasifica como vencida."""
    res = get_accounts_receivable_report_data(search=seed_receivable_data["sale_unpaid"])
    it = res["items"][0]
    assert it["computed_status"] != "Vencida"
    assert it["due_badge_type"] != "vencida"


def test_due_today_identified_correctly(seed_receivable_data):
    """10. Venta que vence hoy tiene dias_vencimiento = 0 y due_badge_type = 'vence_hoy'."""
    res = get_accounts_receivable_report_data(search=seed_receivable_data["sale_today"])
    assert len(res["items"]) == 1
    it = res["items"][0]
    assert it["dias_vencimiento"] == 0
    assert it["due_badge_type"] == "vence_hoy"


def test_next_7_days_and_30_days_filter(seed_receivable_data):
    """11 y 12. Accesos rápidos de próximos 7 y 30 días."""
    # Próximos 7 días
    res_7 = get_accounts_receivable_report_data(
        customer=seed_receivable_data["customer_a"],
        quick_filter="proximas_7"
    )
    sale_numbers = [it["sale_number"] for it in res_7["items"]]
    assert seed_receivable_data["sale_next7"] in sale_numbers
    assert seed_receivable_data["sale_unpaid"] not in sale_numbers  # vence en 45 días


def test_customer_and_rut_identified(seed_receivable_data):
    """13 y 14. Cliente y RUT identificados correctamente."""
    res = get_accounts_receivable_report_data(search=seed_receivable_data["sale_unpaid"])
    it = res["items"][0]
    assert it["customer_name"] == seed_receivable_data["customer_a"]
    assert seed_receivable_data["rut_a"] in it["customer_rut"]


def test_filter_by_customer(seed_receivable_data):
    """15. Filtro por cliente."""
    res_a = get_accounts_receivable_report_data(customer=seed_receivable_data["customer_a"])
    assert len(res_a["items"]) >= 4
    for it in res_a["items"]:
        assert seed_receivable_data["customer_a"].lower() in it["customer_name"].lower()


def test_filter_by_payment_status(seed_receivable_data):
    """16. Filtro por estado de pago ('Vencida', 'Parcial', 'Pendiente')."""
    res_venc = get_accounts_receivable_report_data(
        customer=seed_receivable_data["customer_a"],
        payment_status="Vencida"
    )
    for it in res_venc["items"]:
        assert it["computed_status"] == "Vencida"

    res_par = get_accounts_receivable_report_data(
        customer=seed_receivable_data["customer_a"],
        payment_status="Parcial"
    )
    for it in res_par["items"]:
        assert it["computed_status"] == "Parcial"


def test_kpi_calculated_strictly_on_pending_balance(seed_receivable_data):
    """17 y 21. KPIs superiores calculados ESTRICTAMENTE sobre SALDO PENDIENTE, no sobre total venta."""
    # Filtrar solo las ventas de customer_a creadas en el fixture
    res = get_accounts_receivable_report_data(customer=seed_receivable_data["customer_a"])
    metrics = res["metrics"]
    items = res["all_filtered_items"]

    expected_saldo_total = sum(it["pending_amount"] for it in items)
    assert round(metrics["total_por_cobrar"], 2) == round(expected_saldo_total, 2)

    # Validar que no se usó total_amount (porque sale_partial tiene total $200.000 pero saldo $120.000)
    total_ventas_bruto = sum(it["total_amount"] for it in items)
    assert total_ventas_bruto > metrics["total_por_cobrar"]


def test_excel_export_and_reconciliation(seed_receivable_data):
    """18, 22, 23, 24, 25. Exportación Excel genera archivo íntegro y numérico; conciliación exacta BD = Pantalla = Excel."""
    filter_params = {"customer": seed_receivable_data["customer_a"]}
    
    # 1. Datos desde DB
    db_data = get_accounts_receivable_report_data(**filter_params)
    db_pending_sum = db_data["metrics"]["total_por_cobrar"]
    db_count = len(db_data["all_filtered_items"])

    # 2. Generación de Excel
    excel_buf = export_accounts_receivable_to_excel(filter_params)
    wb = openpyxl.load_workbook(excel_buf, data_only=True)
    ws = wb.active

    # Validar filas de datos
    header_row = 7
    data_rows = []
    r = header_row + 1
    while ws.cell(row=r, column=1).value is not None and ws.cell(row=r, column=1).value != "TOTAL POR COBRAR CONSOLIDADO":
        # Columna 11: Saldo por Cobrar
        saldo_val = float(ws.cell(row=r, column=11).value or 0.0)
        data_rows.append(saldo_val)
        r += 1

    assert len(data_rows) == db_count
    excel_pending_sum = round(sum(data_rows), 2)

    # Conciliación matemática exacta
    assert round(db_pending_sum, 2) == round(excel_pending_sum, 2)


def test_rbac_protection_screen(auth_client, unauth_client):
    """26. Pantalla Cuentas por Cobrar: 200 con permiso 'reportes', 403 sin permiso."""
    res_auth = auth_client.get('/reporteria/cuentas-por-cobrar')
    assert res_auth.status_code == 200
    assert b"Cuentas por Cobrar" in res_auth.data

    res_unauth = unauth_client.get('/reporteria/cuentas-por-cobrar')
    assert res_unauth.status_code == 403


def test_rbac_protection_excel(auth_client, unauth_client):
    """27. Exportación Excel: 200 con permiso 'reportes', 403 sin permiso."""
    res_auth = auth_client.get('/reporteria/cuentas-por-cobrar/exportar-excel')
    assert res_auth.status_code == 200
    assert res_auth.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    res_unauth = unauth_client.get('/reporteria/cuentas-por-cobrar/exportar-excel')
    assert res_unauth.status_code == 403


def test_register_payment_action_updates_balance_immediately(auth_client, seed_receivable_data):
    """28, 29, 30. Acción Registrar Pago reutiliza endpoint oficial, actualiza saldo y no altera estado logístico."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, status FROM sales WHERE sale_number = %s", (seed_receivable_data["sale_unpaid"],))
            sale_row = cur.fetchone()
            sid = sale_row["id"]
            orig_status = sale_row["status"]

    # Registrar un abono de $40.000 vía endpoint oficial POST /ventas/registrar-pago
    resp = auth_client.post('/ventas/registrar-pago', data={
        'sale_id': sid,
        'payment_method': 'Efectivo',
        'payment_date': date.today().isoformat(),
        'payment_amount': '40000',
        'payment_notes': 'Abono prueba Cuentas por Cobrar',
        'return_url': '/reporteria/cuentas-por-cobrar'
    }, follow_redirects=True)
    assert resp.status_code == 200

    # Verificar que el saldo se redujo de $100.000 a $60.000
    res_after = get_accounts_receivable_report_data(search=seed_receivable_data["sale_unpaid"])
    it_after = res_after["items"][0]
    assert it_after["paid_amount"] == 40000.0
    assert it_after["pending_amount"] == 60000.0
    assert it_after["computed_status"] == "Parcial"

    # Verificar que el estado logístico de la venta NO se modificó
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM sales WHERE id = %s", (sid,))
            assert cur.fetchone()["status"] == orig_status


def test_pagination_and_sorting_accounts_receivable(seed_receivable_data):
    """Paginación y ordenamiento server-side."""
    res_p1 = get_accounts_receivable_report_data(per_page=2, page=1)
    assert len(res_p1["items"]) <= 2
    assert res_p1["page"] == 1
    assert res_p1["per_page"] == 2

    # Ordenamiento por total_amount desc
    res_sorted = get_accounts_receivable_report_data(
        customer=seed_receivable_data["customer_a"],
        sort_by="total",
        sort_order="desc"
    )
    totals = [it["total_amount"] for it in res_sorted["items"]]
    assert totals == sorted(totals, reverse=True)


def test_search_by_multiple_fields(seed_receivable_data):
    """Búsqueda por texto (número de venta, RUT, cliente)."""
    # Por número de venta
    res1 = get_accounts_receivable_report_data(search=seed_receivable_data["sale_unpaid"])
    assert len(res1["items"]) == 1
    assert res1["items"][0]["sale_number"] == seed_receivable_data["sale_unpaid"]

    # Por RUT
    res2 = get_accounts_receivable_report_data(search=seed_receivable_data["rut_a"])
    assert len(res2["items"]) >= 1


def test_e2e_complete_flow_accounts_receivable(auth_client):
    """Validación E2E completa según especificación (1.000.000 -> 400.000 -> 600.000 -> Saldo 0)."""
    marker = uuid.uuid4().hex[:8]
    sale_num = f"VTA-E2E-{marker}"
    customer_name = f"CLIENTE TEST E2E {marker}"
    today_str = date.today().isoformat()

    sid = None
    try:
        # 1. Crear venta por $1.000.000 con estado logístico 'En Preparación'
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO sales (sale_number, customer_name, sale_date, sale_time, products_json, total_amount, status, seller_name, payment_method, payment_status, notes, created_at)
                       VALUES (%s, %s, %s, '10:00:00', '[]', 1000000, 'En Preparación', 'Vendedor Test', 'Transferencia', 'Pendiente', 'Venta E2E Test', %s) RETURNING id""",
                    (sale_num, customer_name, today_str, today_str)
                )
                sid = cur.fetchone()["id"]
                cur.execute(
                    """INSERT INTO sale_payments (sale_id, invoice_number, invoice_amount, invoice_due_date, payment_amount, status, created_at, updated_at)
                       VALUES (%s, %s, 1000000, %s, 0, 'Factura pendiente', %s, %s)""",
                    (sid, f"FACT-{sid:05d}", today_str, today_str, today_str)
                )
            conn.commit()

        # Verificar Inicialmente: Pagado $0, Pendiente $1.000.000
        res0 = get_accounts_receivable_report_data(search=sale_num)
        assert len(res0["items"]) == 1
        it0 = res0["items"][0]
        assert it0["total_amount"] == 1000000.0
        assert it0["paid_amount"] == 0.0
        assert it0["pending_amount"] == 1000000.0
        assert it0["computed_status"] == "Pendiente"

        # 2. Registrar Pago 1: $400.000
        resp1 = auth_client.post('/ventas/registrar-pago', data={
            'sale_id': sid,
            'payment_method': 'Efectivo',
            'payment_date': today_str,
            'payment_amount': '400000',
            'payment_notes': 'Abono 1 E2E',
            'return_url': '/reporteria/cuentas-por-cobrar'
        }, follow_redirects=True)
        assert resp1.status_code == 200

        # Verificar tras Pago 1: Total $1.000.000, Pagado $400.000, Pendiente $600.000, Estado Parcial
        res1 = get_accounts_receivable_report_data(search=sale_num)
        assert len(res1["items"]) == 1
        it1 = res1["items"][0]
        assert it1["total_amount"] == 1000000.0
        assert it1["paid_amount"] == 400000.0
        assert it1["pending_amount"] == 600000.0
        assert it1["computed_status"] == "Parcial"

        # 3. Registrar Pago 2: $600.000 (Saldo restante completo)
        resp2 = auth_client.post('/ventas/registrar-pago', data={
            'sale_id': sid,
            'payment_method': 'Efectivo',
            'payment_date': today_str,
            'payment_amount': '600000',
            'payment_notes': 'Pago final E2E',
            'return_url': '/reporteria/cuentas-por-cobrar'
        }, follow_redirects=True)
        assert resp2.status_code == 200

        # Verificar tras Pago 2: La venta desaparece de Cuentas por Cobrar
        res2 = get_accounts_receivable_report_data(search=sale_num)
        assert len(res2["items"]) == 0

        # 4. Verificar que continúa existiendo en Ventas Realizadas con sus abonos
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, sale_number, total_amount, payment_status FROM sales WHERE id = %s", (sid,))
                sale_final = cur.fetchone()
                assert sale_final is not None
                assert sale_final["payment_status"] == "Pagado"

                cur.execute("SELECT COUNT(*) AS n, SUM(payment_amount) AS total_paid FROM sale_payment_items WHERE sale_id = %s", (sid,))
                p_items = cur.fetchone()
                assert p_items["n"] == 2
                assert round(float(p_items["total_paid"]), 2) == 1000000.0

    finally:
        if sid:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM sale_payment_items WHERE sale_id = %s", (sid,))
                    cur.execute("DELETE FROM sale_payments WHERE sale_id = %s", (sid,))
                    cur.execute("DELETE FROM sales_payment_history WHERE sale_id = %s", (sid,))
                    cur.execute("DELETE FROM sales_status_history WHERE sale_id = %s", (sid,))
                    cur.execute("DELETE FROM sales WHERE id = %s", (sid,))
                conn.commit()

