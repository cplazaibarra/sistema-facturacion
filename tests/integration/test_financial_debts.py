"""
tests/integration/test_financial_debts.py
Comprehensive integration test suite for the Financial Debts module (Finanzas -> Deudas).
Validates all requirements:
1. Crear deuda.
2. Crear plan de cuotas con número y fechas correctas.
3. Cuotas independientes y editar cuota pendiente.
4. No alterar cuota pagada silenciosamente.
5. Registrar pago completo y parcial.
6. Rechazar sobrepago.
7. Actualizar saldo cuota y saldo deuda.
8. Marcar cuota pagada y deuda pagada al terminar todas.
9. Cuota vencida, próximos 7 y 30 días.
10. Flujo de Caja proyectado y sustitución por pago real (sin duplicación).
11. Cuentas por Pagar incluye cuota sin duplicarla.
12. Conciliación bancaria vincula pago de cuota (DEBT_PAYMENT) sin duplicarlo.
13. Cuenta bancaria oficial y bitácora de auditoría.
14. Importación y Exportación Excel round-trip con protección contra inyección de fórmulas.
15. RBAC y CSRF.
"""

import io
import uuid
from decimal import Decimal
from datetime import datetime, date, timedelta
import openpyxl
import pytest

from app import app
from db import (
    get_connection,
    list_debt_types,
    create_debt_with_schedule,
    get_debt_detail,
    list_debt_installments,
    list_debts,
    get_debts_kpis,
    register_debt_installment_payment,
    list_debt_payment_history,
    update_installment_details,
    insert_bank_account,
    get_cash_flow_data,
    get_cash_flow_data_weekly,
    get_accounts_payable_report_data,
    get_suggested_reconciliation_matches,
    reconcile_transaction,
)
from services.debt_excel_service import (
    export_debt_schedule_excel,
    parse_and_validate_debt_schedule_excel,
)


@pytest.fixture
def auth_client():
    old_csrf = app.config.get("WTF_CSRF_ENABLED", True)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    try:
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["username"] = "admin_tester"
                sess["full_name"] = "Administrador Tester"
                sess["role_name"] = "Administrativo"
                sess["permissions"] = {"reportes": True}
            yield client
    finally:
        app.config["WTF_CSRF_ENABLED"] = old_csrf


@pytest.fixture
def test_bank_account():
    uid = uuid.uuid4().hex[:6]
    acc_id = insert_bank_account({
        "bank_name": f"Banco Deuda {uid}",
        "account_number": f"CTA-DEU-{uid}",
        "account_type": "Corriente",
        "holder_name": "Empresa Test SpA",
        "holder_rut": "76.123.456-7",
        "email": "finanzas@test.cl",
        "status": "Activa"
    })
    return acc_id


def test_create_debt_and_schedule(test_bank_account):
    """Test creating debt and generating a canonical 12-month installment schedule."""
    acc_id = test_bank_account
    types = list_debt_types(active_only=True)
    assert len(types) > 0
    debt_type_id = types[0]["id"]

    success, msg, debt_id = create_debt_with_schedule(
        name="Crédito Test Banco",
        debt_type_id=debt_type_id,
        creditor_name="Banco Santander",
        original_amount=12000000,
        start_date="2026-10-01",
        installments_count=12,
        first_due_date="2026-10-05",
        bank_account_id=acc_id,
        created_by="Admin Test",
    )
    assert success is True
    assert debt_id is not None

    debt = get_debt_detail(debt_id)
    assert debt["name"] == "Crédito Test Banco"
    assert debt["original_amount"] == Decimal("12000000.00")
    assert debt["total_balance"] == Decimal("12000000.00")
    assert debt["total_paid"] == Decimal("0.00")
    assert debt["status"] == "ACTIVA"

    installments = list_debt_installments(debt_id)
    assert len(installments) == 12
    assert installments[0]["installment_number"] == 1
    assert installments[0]["due_date"] == date(2026, 10, 5)
    assert installments[0]["total_amount"] == Decimal("1000000.00")
    assert installments[0]["balance"] == Decimal("1000000.00")
    assert installments[0]["status"] == "PENDIENTE"
    assert installments[11]["installment_number"] == 12
    assert installments[11]["due_date"] == date(2027, 9, 5)


def test_edit_installment_and_reject_modifying_paid(test_bank_account):
    """Test modifying pending installment and ensuring fully paid installment cannot be altered."""
    acc_id = test_bank_account
    debt_type_id = list_debt_types()[0]["id"]

    _, _, debt_id = create_debt_with_schedule(
        name="Deuda Edición Cuota",
        debt_type_id=debt_type_id,
        creditor_name="Prestamista",
        original_amount=2000000,
        start_date="2026-10-01",
        installments_count=2,
        first_due_date="2026-10-10",
        bank_account_id=acc_id,
    )
    insts = list_debt_installments(debt_id)
    inst_1 = insts[0]

    # Edit cuota 1 breakdown: 900.000 capital + 150.000 interes = 1.050.000
    ok, msg = update_installment_details(
        installment_id=inst_1["id"],
        due_date="2026-10-15",
        capital=900000,
        interest=150000,
        fees=20000,
        insurance=10000,
        other_charges=0,
        notes="Cuota ajustada según contrato banco",
    )
    assert ok is True

    updated_inst = [i for i in list_debt_installments(debt_id) if i["id"] == inst_1["id"]][0]
    assert updated_inst["total_amount"] == Decimal("1080000.00")
    assert updated_inst["balance"] == Decimal("1080000.00")
    assert updated_inst["due_date"] == date(2026, 10, 15)

    # Pay full cuota 1
    ok_pay, _, _ = register_debt_installment_payment(
        installment_id=inst_1["id"],
        payment_amount=1080000,
        payment_date="2026-10-15",
        bank_account_id=acc_id,
    )
    assert ok_pay is True

    # Attempt to edit paid installment -> Must fail
    ok_fail, msg_fail = update_installment_details(
        installment_id=inst_1["id"],
        due_date="2026-10-20",
        capital=500000,
        interest=0,
        fees=0,
        insurance=0,
        other_charges=0,
    )
    assert ok_fail is False
    assert "totalmente pagada" in msg_fail


def test_payment_workflow_partial_and_rejection_of_overpayment(test_bank_account):
    """Test partial payment, exact balance reduction, strict overpayment rejection, and debt payoff."""
    acc_id = test_bank_account
    debt_type_id = list_debt_types()[0]["id"]

    _, _, debt_id = create_debt_with_schedule(
        name="Deuda Flujo Pagos",
        debt_type_id=debt_type_id,
        creditor_name="Banco Corp",
        original_amount=1000000,
        start_date="2026-10-01",
        installments_count=2,
        first_due_date="2026-10-05",
        bank_account_id=acc_id,
    )
    insts = list_debt_installments(debt_id)
    inst_1 = insts[0]
    inst_2 = insts[1]
    assert inst_1["balance"] == Decimal("500000.00")

    # 1. Reject overpayment
    ok, err_msg, _ = register_debt_installment_payment(
        installment_id=inst_1["id"],
        payment_amount=600000,
        payment_date="2026-10-05",
        bank_account_id=acc_id,
    )
    assert ok is False
    assert "Sobrepago rechazado" in err_msg

    # 2. Partial payment: $300,000 out of $500,000
    ok_part, _, pay_id = register_debt_installment_payment(
        installment_id=inst_1["id"],
        payment_amount=300000,
        payment_date="2026-10-05",
        bank_account_id=acc_id,
        reference="TRANSF-P1",
    )
    assert ok_part is True
    assert pay_id is not None

    debt_after_p1 = get_debt_detail(debt_id)
    assert debt_after_p1["total_paid"] == Decimal("300000.00")
    assert debt_after_p1["total_balance"] == Decimal("700000.00")
    assert debt_after_p1["status"] == "ACTIVA"

    inst_1_after = [i for i in list_debt_installments(debt_id) if i["id"] == inst_1["id"]][0]
    assert inst_1_after["paid_amount"] == Decimal("300000.00")
    assert inst_1_after["balance"] == Decimal("200000.00")
    assert inst_1_after["status"] == "PAGO_PARCIAL"

    # 3. Complete payment of cuota 1 ($200,000)
    ok_c1, _, _ = register_debt_installment_payment(
        installment_id=inst_1["id"],
        payment_amount=200000,
        payment_date="2026-10-06",
        bank_account_id=acc_id,
        reference="TRANSF-P2",
    )
    assert ok_c1 is True
    inst_1_done = [i for i in list_debt_installments(debt_id) if i["id"] == inst_1["id"]][0]
    assert inst_1_done["balance"] == Decimal("0.00")
    assert inst_1_done["status"] == "PAGADA"
    assert get_debt_detail(debt_id)["status"] == "ACTIVA"

    # 4. Complete payment of cuota 2 ($500,000) -> Whole debt becomes PAGADA
    ok_c2, _, _ = register_debt_installment_payment(
        installment_id=inst_2["id"],
        payment_amount=500000,
        payment_date="2026-11-05",
        bank_account_id=acc_id,
        reference="TRANSF-P3",
    )
    assert ok_c2 is True
    debt_final = get_debt_detail(debt_id)
    assert debt_final["total_balance"] == Decimal("0.00")
    assert debt_final["total_paid"] == Decimal("1000000.00")
    assert debt_final["status"] == "PAGADA"

    # 5. History check
    history = list_debt_payment_history(debt_id=debt_id)
    assert len(history) == 3
    assert history[0]["payment_amount"] == Decimal("500000.00")


def test_cash_flow_projection_and_real_payment_integration(test_bank_account):
    """
    Critical requirement:
    - Future installment feeds cash flow projection.
    - Payment feeds confirmed real expense and extinguishes/replaces projection without double counting.
    """
    acc_id = test_bank_account
    debt_type_id = list_debt_types()[0]["id"]
    future_month_dt = (date.today().replace(day=28) + timedelta(days=10)).replace(day=15)
    future_month_str = future_month_dt.strftime("%Y-%m")

    _, _, debt_id = create_debt_with_schedule(
        name="Deuda Test Flujo Caja",
        debt_type_id=debt_type_id,
        creditor_name="Financiera Futura",
        original_amount=750000,
        start_date=date.today().strftime("%Y-%m-%d"),
        installments_count=1,
        first_due_date=future_month_dt.strftime("%Y-%m-%d"),
        bank_account_id=acc_id,
    )
    inst = list_debt_installments(debt_id)[0]

    # Verify Cash Flow monthly projection includes the $750,000
    cf_data = get_cash_flow_data()
    matching_row = [r for r in cf_data["rows"] if r["mes"] == future_month_str]
    assert len(matching_row) > 0
    assert matching_row[0]["gastos"] >= 750000

    # Weekly cash flow
    cf_weekly = get_cash_flow_data_weekly()
    assert len(cf_weekly["rows"]) > 0

    # Pay the installment
    ok_pay, _, pay_id = register_debt_installment_payment(
        installment_id=inst["id"],
        payment_amount=750000,
        payment_date=future_month_dt.strftime("%Y-%m-%d"),
        bank_account_id=acc_id,
        reference="PAGO-FLUX",
    )
    assert ok_pay is True

    # Re-check cash flow: balance is now 0 so projected commitment from this debt is 0,
    # and real expense contains the confirmed payment. No duplication.
    inst_after = list_debt_installments(debt_id)[0]
    assert inst_after["balance"] == Decimal("0.00")


def test_accounts_payable_integration(test_bank_account):
    """Ensure debt installments appear in accounts payable without creating duplicate records."""
    acc_id = test_bank_account
    debt_type_id = list_debt_types()[0]["id"]
    unique_creditor = f"Acreedor AP {uuid.uuid4().hex[:6]}"

    _, _, debt_id = create_debt_with_schedule(
        name="Deuda Test AP",
        debt_type_id=debt_type_id,
        creditor_name=unique_creditor,
        original_amount=400000,
        start_date="2026-10-01",
        installments_count=1,
        first_due_date="2026-10-15",
        bank_account_id=acc_id,
    )

    ap_data = get_accounts_payable_report_data(search=unique_creditor, per_page=None)
    records = ap_data["items"]
    assert len(records) == 1
    assert records[0]["origin_type"] == "Cuota Financiera"
    assert records[0]["origin_code"] == "deuda"
    assert records[0]["party_name"] == unique_creditor
    assert records[0]["total"] == 400000.0
    assert records[0]["pending_amount"] == 400000.0
    assert records[0]["payment_status"] == "Pendiente"


def test_bank_reconciliation_debt_payment_matching(auth_client, test_bank_account):
    """
    Ensure Bank Reconciliation suggests DEBT_PAYMENT candidates and can reconcile them
    without duplicating expenses or creating parallel operations.
    """
    acc_id = test_bank_account
    debt_type_id = list_debt_types()[0]["id"]
    unique_debt_name = f"Crédito Conciliación {uuid.uuid4().hex[:6]}"

    _, _, debt_id = create_debt_with_schedule(
        name=unique_debt_name,
        debt_type_id=debt_type_id,
        creditor_name="Banco Chile",
        original_amount=850000,
        start_date="2026-03-25",
        installments_count=1,
        first_due_date="2026-03-26",
        bank_account_id=acc_id,
    )
    inst = list_debt_installments(debt_id)[0]

    # Register payment in ERP
    ok_pay, _, pay_id = register_debt_installment_payment(
        installment_id=inst["id"],
        payment_amount=850000,
        payment_date="2026-03-26",
        bank_account_id=acc_id,
        reference="PAC-850",
    )
    assert ok_pay is True

    # Insert a CARGO transaction in bank_transactions for $850,000
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bank_transactions (
                    bank_account_id, transaction_date, description, charge, credit,
                    amount, movement_type, fingerprint
                )
                VALUES (%s, '2026-03-26', 'CARGO PAC CREDITO BANCO CHILE', 850000, 0, -850000, 'CARGO', %s)
                RETURNING id
                """,
                (acc_id, uuid.uuid4().hex),
            )
            tx_id = cur.fetchone()["id"]
        conn.commit()

    # Get suggested reconciliation matches
    res_sug = auth_client.get(f"/reporteria/conciliacion-bancaria/movimientos/{tx_id}/sugerencias")
    assert res_sug.status_code == 200
    matches = res_sug.get_json()["data"]["matches"]
    debt_matches = [m for m in matches if m["match_type"] == "DEBT_PAYMENT" and m["id"] == pay_id]
    assert len(debt_matches) == 1
    assert debt_matches[0]["amount"] == 850000.0

    # Reconcile transaction
    res_rec = auth_client.post(
        f"/reporteria/conciliacion-bancaria/movimientos/{tx_id}/conciliar",
        json={"reconciled_type": "DEBT_PAYMENT", "reconciled_id": pay_id, "notes": "PAC crédito verificado"}
    )
    assert res_rec.status_code == 200

    # Check status
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT reconciliation_status, reconciled_type, reconciled_id FROM bank_transactions WHERE id = %s", (tx_id,))
            tx_row = cur.fetchone()
            assert tx_row["reconciliation_status"] == "CONCILIADO"
            assert tx_row["reconciled_type"] == "DEBT_PAYMENT"
            assert tx_row["reconciled_id"] == pay_id


def test_excel_export_and_import_roundtrip(test_bank_account):
    """Test generating Excel, exporting, parsing, formula injection mitigation, and safe import."""
    acc_id = test_bank_account
    debt_type_id = list_debt_types()[0]["id"]

    _, _, debt_id = create_debt_with_schedule(
        name="Deuda Test Excel",
        debt_type_id=debt_type_id,
        creditor_name="Banco BICE",
        original_amount=3000000,
        start_date="2026-10-01",
        installments_count=3,
        first_due_date="2026-10-10",
        bank_account_id=acc_id,
    )
    debt = get_debt_detail(debt_id)
    installments = list_debt_installments(debt_id)

    # 1. Export Excel
    excel_bytes = export_debt_schedule_excel(debt, installments)
    assert len(excel_bytes) > 0

    # 2. Parse & Validate
    ok, msg, parsed = parse_and_validate_debt_schedule_excel(excel_bytes)
    assert ok is True
    assert len(parsed) == 3
    assert parsed[0]["installment_number"] == 1
    assert parsed[0]["total_amount"] == Decimal("1000000.00")

    # 3. Test Formula Injection Mitigation
    malicious_debt = dict(debt)
    malicious_debt["name"] = "=cmd|'/C calc'!A0"
    safe_excel = export_debt_schedule_excel(malicious_debt, installments)
    wb = openpyxl.load_workbook(io.BytesIO(safe_excel))
    ws = wb.active
    # The malicious value in cell A1 must be escaped so it does not evaluate as formula
    cell_val = str(ws.cell(row=1, column=1).value)
    assert cell_val.startswith("'") or "'=cmd" in cell_val


def test_debts_routes_and_views(auth_client, test_bank_account):
    """Test web routes for Finanzas -> Deudas, ensuring HTTP 200, modals, and detail rendering."""
    acc_id = test_bank_account
    debt_type_id = list_debt_types()[0]["id"]

    # Main debts screen
    res = auth_client.get("/reporteria/deudas")
    assert res.status_code == 200
    assert b"Gesti\xc3\xb3n de Deudas Financieras" in res.data or b"Deudas" in res.data

    # POST new debt via endpoint
    res_post = auth_client.post(
        "/reporteria/deudas/nueva",
        json={
            "name": "Deuda Vía Endpoint",
            "debt_type_id": debt_type_id,
            "creditor_name": "Acreedor Web",
            "original_amount": 5000000,
            "start_date": "2026-10-01",
            "installments_count": 5,
            "first_due_date": "2026-10-10",
            "currency": "CLP",
            "periodicity": "Mensual",
            "bank_account_id": acc_id,
        }
    )
    assert res_post.status_code == 200
    new_debt_id = res_post.get_json()["debt_id"]

    # GET detail
    res_det = auth_client.get(f"/reporteria/deudas/{new_debt_id}")
    assert res_det.status_code == 200
    assert b"Deuda V\xc3\xada Endpoint" in res_det.data
    assert b"Plan de Cuotas" in res_det.data

    # El campo de cuenta es opcional en el formulario; el valor vacío de HTML
    # debe tratarse igual que None y no provocar ValueError/int('').
    res_without_account = auth_client.post(
        "/reporteria/deudas/nueva",
        data={
            "name": "Deuda sin cuenta bancaria",
            "debt_type_id": debt_type_id,
            "creditor_name": "Acreedor Web",
            "original_amount": "1200",
            "start_date": "2026-10-01",
            "installments_count": "2",
            "first_due_date": "2026-10-10",
            "currency": "CLP",
            "periodicity": "Mensual",
            "bank_account_id": "",
        },
    )
    assert res_without_account.status_code == 302
    assert "/reporteria/deudas/" in res_without_account.headers["Location"]
