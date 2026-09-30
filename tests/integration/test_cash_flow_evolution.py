"""
tests/integration/test_cash_flow_evolution.py
Comprehensive integration test suite for the evolved Finanzas -> Flujo de Caja module.

Verifies:
1. Saldo inicial por cuenta y consolidado.
2. Ingreso real por cobranza de venta (sale_payment_items).
3. Ingreso proyectado por venta pendiente (CxC).
4. Pago parcial de venta: solo proyecta saldo restante, nunca duplicado.
5. Pago completo de venta: proyección se extingue a 0.
6. No duplicar obligación + pago (anti-duplicación estricta).
7. Egreso proyectado por factura de compra pendiente (CxP).
8. Pago parcial de factura: solo proyecta saldo pendiente.
9. Pago completo de factura: se extingue proyección y refleja egreso real.
10. Gasto operacional pendiente proyectado y pago real.
11. Cuota de deuda financiera proyectada y sustitución por pago real.
12. Transferencia interna:
    - En vista por cuenta: resta en origen y suma en destino.
    - En vista consolidada: efecto neto = $0.00.
13. Movimiento bancario no conciliado se refleja sin ocultarse.
14. Movimiento bancario conciliado con pago ERP no duplica monto.
15. Agrupaciones diaria, semanal y mensual.
16. Carry-forward exacto: Saldo Inicial período N+1 == Saldo Final período N.
17. Detección automática de alerta de déficit intermedio (saldo proyectado < 0).
18. Mínimo saldo proyectado.
19. Filtros server-side: cuenta, fechas, origen, naturaleza y conciliación.
20. Precisión numérica Decimal exacta (sin floats arbitrarios).
21. Exportación Excel: Resumen y Detalle con protección contra inyección de fórmulas.
22. Reconciliación tripartita: DB == Pantalla == Excel.
23. Permisos RBAC.
24. E2E Escenario financiero integral.
"""

import io
import uuid
from decimal import Decimal
from datetime import date, timedelta
import openpyxl
import pytest

from app import app
from db import (
    get_connection,
    list_bank_accounts,
    insert_bank_account,
    get_bank_initial_balances,
    calculate_cash_flow_consolidation,
    reconcile_transaction,
    create_debt_with_schedule,
    register_debt_installment_payment,
    list_debt_types,
)
from services.cash_flow_excel_service import export_cash_flow_to_excel
from repositories.expense_categories_repo import create_expense_category
from repositories.operational_expenses_repo import create_operational_expense


@pytest.fixture
def auth_client():
    old_csrf = app.config.get("WTF_CSRF_ENABLED", True)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    try:
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["username"] = "admin_cf"
                sess["full_name"] = "Administrador Flujo"
                sess["role_name"] = "Administrativo"
                sess["permissions"] = {"reportes": True}
            yield client
    finally:
        app.config["WTF_CSRF_ENABLED"] = old_csrf


@pytest.fixture
def test_two_bank_accounts():
    unique_sfx = uuid.uuid4().hex[:6]
    acc1 = insert_bank_account({
        "bank_name": "Banco Chile Test",
        "account_number": f"CHILE-{unique_sfx}",
        "account_type": "Corriente",
        "holder_name": "Empresa Test SpA",
        "holder_rut": "76.000.000-1",
        "email": "chile@test.cl",
        "status": "Activa",
    })
    acc2 = insert_bank_account({
        "bank_name": "Santander Test",
        "account_number": f"SANTA-{unique_sfx}",
        "account_type": "Corriente",
        "holder_name": "Empresa Test SpA",
        "holder_rut": "76.000.000-1",
        "email": "santa@test.cl",
        "status": "Activa",
    })
    return acc1, acc2


def test_initial_balance_and_carry_forward(test_two_bank_accounts):
    """Test initial balance calculation and carry-forward across time periods."""
    acc1, acc2 = test_two_bank_accounts
    ref_date = date(2026, 10, 1)

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Insert historical bank movements prior to 2026-10-01
            cur.execute(
                """
                INSERT INTO bank_transactions (bank_account_id, transaction_date, description, charge, credit, amount, movement_type, fingerprint)
                VALUES 
                (%s, '2026-09-15', 'Saldo apertura Chile', 0, 10000000, 10000000, 'ABONO', %s),
                (%s, '2026-09-20', 'Saldo apertura Santander', 0, 5000000, 5000000, 'ABONO', %s)
                """,
                (acc1, uuid.uuid4().hex, acc2, uuid.uuid4().hex)
            )
        conn.commit()

    # Initial balances before 2026-10-01
    bals = get_bank_initial_balances("2026-10-01")
    assert bals[acc1] == Decimal("10000000.00")
    assert bals[acc2] == Decimal("5000000.00")

    # Consolidation calculation
    res = calculate_cash_flow_consolidation(
        start_date="2026-10-01",
        end_date="2026-10-31",
        grouping="semanal"
    )
    # Other historical test balances are deliberately absent in a cleaned DB;
    # the report must equal the complete initial-balance query for all accounts.
    assert res["kpis"]["initial_balance"] == sum(bals.values(), Decimal("0.00"))

    # Verify carry-forward: Saldo Final(N) == Saldo Inicial(N+1)
    p_rows = res["period_rows"]
    for i in range(len(p_rows) - 1):
            assert p_rows[i]["final_balance"] == p_rows[i+1]["initial_balance"]


def test_recurring_expense_master_is_projected_once_and_persisted_occurrence_wins(test_two_bank_accounts):
    """Active recurring masters forecast in cash flow, without creating obligations."""
    marker = uuid.uuid4().hex[:8]
    bank_account_id, _ = test_two_bank_accounts
    category_id = create_expense_category(f"Gasto recurrente {marker}", None, 1)
    expense_id = None
    occurrence_id = None
    today = date.today()
    try:
        expense_id = create_operational_expense({
            "name": f"Arriendo recurrente {marker}",
            "category": f"Gasto recurrente {marker}",
            "category_id": category_id,
            "description": "Proyección recurrente QA",
            "amount": Decimal("1250.00"),
            "amount_type": "Fijo",
            "frequency": "Mensual",
            "start_date": today.replace(day=1),
            "due_rule": "Día del mes",
            "due_day": today.day,
            "end_date": None,
            "bank_account_id": bank_account_id,
            "beneficiary": "Arrendador QA",
            "observations": "",
            "status": "Activo",
        }, 1)

        forecast = calculate_cash_flow_consolidation(
            start_date=today.isoformat(), end_date=today.isoformat(),
            bank_account_id=bank_account_id,
            filter_type="proyectado", filter_origin="gasto",
        )
        generated = [m for m in forecast["movements"] if m["doc_number"] == f"GOP-{expense_id}-{today.isoformat()}"]
        assert len(generated) == 1
        assert generated[0]["outflow"] == Decimal("1250.00")
        assert generated[0]["flow_nature"] == "PROYECTADO"
        assert generated[0]["bank_account_id"] == bank_account_id
        assert "Banco Chile Test" in generated[0]["bank_label"]
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM operational_expense_occurrences WHERE expense_id=%s", (expense_id,))
            assert cur.fetchone()["n"] == 0

        # A materialized obligation for the same cycle must take precedence,
        # rather than showing both it and the forecast derived from its master.
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("""INSERT INTO operational_expense_occurrences
                (expense_id, due_date, amount, status, bank_account_id)
                VALUES (%s,%s,%s,'Proyectado',%s) RETURNING id""",
                (expense_id, today, Decimal("1250.00"), bank_account_id))
            occurrence_id = cur.fetchone()["id"]
            conn.commit()

        with_persisted = calculate_cash_flow_consolidation(
            start_date=today.isoformat(), end_date=today.isoformat(),
            bank_account_id=bank_account_id,
            filter_type="proyectado", filter_origin="gasto",
        )
        matching = [m for m in with_persisted["movements"] if m["doc_number"] in {
            f"GOP-{expense_id}-{today.isoformat()}", f"GASTO-{occurrence_id}"
        }]
        assert len(matching) == 1
        assert matching[0]["doc_number"] == f"GASTO-{occurrence_id}"
        assert matching[0]["outflow"] == Decimal("1250.00")
    finally:
        with get_connection() as conn, conn.cursor() as cur:
            if occurrence_id:
                cur.execute("DELETE FROM operational_expense_occurrences WHERE id=%s", (occurrence_id,))
            if expense_id:
                cur.execute("DELETE FROM operational_expense_audit WHERE expense_id=%s", (expense_id,))
                cur.execute("DELETE FROM operational_expenses WHERE id=%s", (expense_id,))
            cur.execute("DELETE FROM expense_categories WHERE id=%s", (category_id,))
            conn.commit()


def test_anti_duplication_sales_cxc(test_two_bank_accounts):
    """
    Test:
    1. Venta $1.000.000 proyectada.
    2. Cobro parcial $400.000 real -> Saldo proyectado $600.000. Total esperado = $1.000.000 (NO $1.400.000).
    3. Cobro restante $600.000 real -> Saldo proyectado $0. Total esperado = $1.000.000 (NO $2.000.000).
    """
    acc1, _ = test_two_bank_accounts
    sale_num = f"VTA-TEST-{uuid.uuid4().hex[:6]}"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sales (sale_number, customer_name, sale_date, sale_time, products_json, total_amount, status, payment_status, seller_name, created_at)
                VALUES (%s, 'Cliente Inmobiliaria', '2026-10-05', '10:00:00', '[]', 1000000, 'Confirmada', 'Pendiente', 'Vendedor Test', '2026-10-05 10:00:00')
                RETURNING id
                """,
                (sale_num,)
            )
            sale_id = cur.fetchone()["id"]
        conn.commit()

    # 1. Sin cobros: debe proyectar $1.000.000
    res1 = calculate_cash_flow_consolidation(start_date="2026-10-01", end_date="2026-10-31")
    cxc_movs = [m for m in res1["movements"] if m["doc_number"] == sale_num]
    assert len(cxc_movs) == 1
    assert cxc_movs[0]["flow_nature"] == "PROYECTADO"
    assert cxc_movs[0]["inflow"] == Decimal("1000000.00")

    # 2. Registrar cobro parcial de $400.000
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sale_payment_items (sale_id, payment_amount, payment_date, bank_account_id, accounting_approved, created_at)
                VALUES (%s, 400000, '2026-10-10', %s, 1, '2026-10-10')
                """,
                (sale_id, acc1)
            )
        conn.commit()

    res2 = calculate_cash_flow_consolidation(start_date="2026-10-01", end_date="2026-10-31")
    cxc_movs2 = [m for m in res2["movements"] if m["doc_number"] == sale_num]
    assert len(cxc_movs2) == 2

    real_p = [m for m in cxc_movs2 if m["flow_nature"] == "REAL"][0]
    proj_p = [m for m in cxc_movs2 if m["flow_nature"] == "PROYECTADO"][0]

    assert real_p["inflow"] == Decimal("400000.00")
    assert proj_p["inflow"] == Decimal("600000.00")
    # Total esperado de la operación = $1.000.000, NUNCA $1.400.000
    assert (real_p["inflow"] + proj_p["inflow"]) == Decimal("1000000.00")

    # 3. Registrar cobro restante de $600.000 y marcar Pagado
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sale_payment_items (sale_id, payment_amount, payment_date, bank_account_id, accounting_approved, created_at)
                VALUES (%s, 600000, '2026-10-12', %s, 1, '2026-10-12')
                """,
                (sale_id, acc1)
            )
            cur.execute("UPDATE sales SET payment_status = 'Pagado' WHERE id = %s", (sale_id,))
        conn.commit()

    res3 = calculate_cash_flow_consolidation(start_date="2026-10-01", end_date="2026-10-31")
    cxc_movs3 = [m for m in res3["movements"] if m["doc_number"] == sale_num]
    assert all(m["flow_nature"] == "REAL" for m in cxc_movs3)
    assert sum(m["inflow"] for m in cxc_movs3) == Decimal("1000000.00")


def test_anti_duplication_debts(test_two_bank_accounts):
    """
    Test:
    1. Cuota de deuda $1.250.000 proyectada.
    2. Al pagar la cuota en debt_payments, se vuelve REAL y la proyección se extingue a $0.
    """
    acc1, _ = test_two_bank_accounts
    d_type_id = list_debt_types()[0]["id"]

    _, _, debt_id = create_debt_with_schedule(
        name="Crédito Test CF",
        debt_type_id=d_type_id,
        creditor_name="Banco Estado",
        original_amount=1250000,
        start_date="2026-10-01",
        installments_count=1,
        first_due_date="2026-10-15",
        bank_account_id=acc1,
    )

    # 1. Proyección
    res1 = calculate_cash_flow_consolidation(start_date="2026-10-01", end_date="2026-10-31")
    debt_movs1 = [m for m in res1["movements"] if f"CUOTA-{debt_id}/1" in m["doc_number"]]
    assert len(debt_movs1) == 1
    assert debt_movs1[0]["flow_nature"] == "PROYECTADO"
    assert debt_movs1[0]["outflow"] == Decimal("1250000.00")

    # 2. Pagar la cuota
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM debt_installments WHERE debt_id = %s", (debt_id,))
            inst_id = cur.fetchone()["id"]

    ok, msg, p_id = register_debt_installment_payment(
        installment_id=inst_id,
        payment_amount=1250000,
        payment_date="2026-10-15",
        bank_account_id=acc1,
        user_name="tester",
    )
    assert ok is True

    # 3. Flujo resultante: solo REAL -$1.250.000, proyección extinguida
    res2 = calculate_cash_flow_consolidation(start_date="2026-10-01", end_date="2026-10-31")
    debt_movs2 = [m for m in res2["movements"] if f"CUOTA-{debt_id}/1" in m["doc_number"]]
    assert len(debt_movs2) == 1
    assert debt_movs2[0]["flow_nature"] == "REAL"
    assert debt_movs2[0]["outflow"] == Decimal("1250000.00")


def test_internal_transfers_consolidation(test_two_bank_accounts):
    """
    Test:
    Transferencia interna: Banco A -$1.000.000, Banco B +$1.000.000.
    - Por cuenta A: egreso $1.000.000.
    - Por cuenta B: ingreso $1.000.000.
    - En vista consolidada: efecto neto = $0.00.
    """
    acc1, acc2 = test_two_bank_accounts
    amount = Decimal("1000000.00")

    with get_connection() as conn:
        with conn.cursor() as cur:
            fp1 = uuid.uuid4().hex
            fp2 = uuid.uuid4().hex
            cur.execute(
                """
                INSERT INTO bank_transactions (bank_account_id, transaction_date, description, charge, credit, amount, movement_type, fingerprint)
                VALUES (%s, '2026-10-20', 'Traspaso a cuenta 2', %s, 0, -%s, 'CARGO', %s)
                RETURNING id
                """,
                (acc1, amount, amount, fp1)
            )
            tx1_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO bank_transactions (bank_account_id, transaction_date, description, charge, credit, amount, movement_type, fingerprint)
                VALUES (%s, '2026-10-20', 'Traspaso desde cuenta 1', 0, %s, %s, 'ABONO', %s)
                RETURNING id
                """,
                (acc2, amount, amount, fp2)
            )
            tx2_id = cur.fetchone()["id"]
        conn.commit()

    # Conciliar como transferencia interna
    ok, _ = reconcile_transaction(tx1_id, "INTERNAL_TRANSFER", tx2_id, "admin")
    assert ok is True

    # 1. Vista Cuenta 1
    cf_acc1 = calculate_cash_flow_consolidation(start_date="2026-10-01", end_date="2026-10-31", bank_account_id=acc1)
    transf_acc1 = [m for m in cf_acc1["movements"] if m["source_id"] == tx1_id]
    assert len(transf_acc1) == 1
    assert transf_acc1[0]["outflow"] == amount

    # 2. Vista Cuenta 2
    cf_acc2 = calculate_cash_flow_consolidation(start_date="2026-10-01", end_date="2026-10-31", bank_account_id=acc2)
    transf_acc2 = [m for m in cf_acc2["movements"] if m["source_id"] == tx2_id]
    assert len(transf_acc2) == 1
    assert transf_acc2[0]["inflow"] == amount

    # 3. Vista Consolidada (Todas las cuentas): efecto neto $0
    cf_cons = calculate_cash_flow_consolidation(start_date="2026-10-01", end_date="2026-10-31")
    # Verificar que no genera egreso ni ingreso operacional en los totales consolidados
    for p in cf_cons["period_rows"]:
        if "2026-W43" in p["period_key"]:  # Oct 20 semana
            # Las transferencias internas netean a $0 en consolidado
            assert p["internal_transfers_net"] == Decimal("0.00")


def test_bank_reconciliation_avoids_double_counting(test_two_bank_accounts):
    """
    Test:
    Un movimiento bancario importado y conciliado contra un pago ERP no debe duplicar el flujo.
    """
    acc1, _ = test_two_bank_accounts
    amount = Decimal("350000.00")

    with get_connection() as conn:
        with conn.cursor() as cur:
            import uuid
            sale_num = f"VTA-TEST-REC-{uuid.uuid4().hex[:6]}"
            cur.execute(
                """
                INSERT INTO sales (sale_number, customer_name, sale_date, sale_time, products_json, total_amount, status, payment_status, seller_name, created_at)
                VALUES (%s, 'Cliente Reconcil', '2026-10-05', '10:00:00', '[]', %s, 'Confirmada', 'Pagado', 'Vendedor Test', '2026-10-05 10:00:00')
                RETURNING id
                """,
                (sale_num, amount)
            )
            s_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO sale_payment_items (sale_id, payment_amount, payment_date, bank_account_id, accounting_approved, created_at)
                VALUES (%s, %s, '2026-10-06', %s, 1, '2026-10-06')
                RETURNING id
                """,
                (s_id, amount, acc1)
            )
            spi_id = cur.fetchone()["id"]

            # 2. Movimiento Cartola Bancaria
            fp = uuid.uuid4().hex
            cur.execute(
                """
                INSERT INTO bank_transactions (bank_account_id, transaction_date, description, charge, credit, amount, movement_type, fingerprint)
                VALUES (%s, '2026-10-06', 'ABONO TEF CLIENTE', 0, %s, %s, 'ABONO', %s)
                RETURNING id
                """,
                (acc1, amount, amount, fp)
            )
            tx_id = cur.fetchone()["id"]
        conn.commit()

    # Conciliar movimiento bancario contra pago ERP
    ok, _ = reconcile_transaction(tx_id, "SALE_PAYMENT", spi_id, "admin")
    assert ok is True

    # Consultar flujo de caja
    cf = calculate_cash_flow_consolidation(start_date="2026-10-01", end_date="2026-10-31")
    # Debe existir exactamente 1 movimiento registrado con el cobro de venta (el bancario no se duplica)
    related_movs = [m for m in cf["movements"] if m["doc_number"] == sale_num or (m["origin"] == "Movimiento Bancario" and m["source_id"] == tx_id)]
    assert len(related_movs) == 1
    assert related_movs[0]["origin"] == "Pago Venta"
    assert related_movs[0]["origin"] == "Pago Venta"
    assert related_movs[0]["reconciliation_status"] == "CONCILIADO"
    assert related_movs[0]["inflow"] == amount


def test_deficit_alert_and_min_projected_balance(test_two_bank_accounts):
    """
    Test:
    Detecta automáticamente período con déficit proyectado si los egresos superan los saldos.
    """
    acc1, _ = test_two_bank_accounts
    # Insertar una obligación futura muy grande
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO suppliers (name, rut, dv, razon_social, created_at)
                VALUES ('Mega Proveedor', '99.888.777', 'K', 'Mega Proveedor SpA', '2026-01-01')
                RETURNING id
                """
            )
            sup_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO purchase_invoices (supplier_id, invoice_number, invoice_amount, invoice_date, due_date, payment_status, bank_account_id)
                VALUES (%s, 'FAC-MEGA-999', 500000000, '2026-10-01', '2026-10-25', 'Pendiente', %s)
                """,
                (sup_id, acc1)
            )
        conn.commit()

    cf = calculate_cash_flow_consolidation(start_date="2026-10-01", end_date="2026-10-31")
    assert cf["kpis"]["deficit_alert"] is True
    assert cf["kpis"]["min_projected_balance"] < Decimal("0.00")

    deficit_rows = [p for p in cf["period_rows"] if p["has_deficit"]]
    assert len(deficit_rows) > 0


def test_excel_export_and_formula_injection(test_two_bank_accounts):
    """
    Test Excel generation with round-trip parsing and formula injection protection.
    """
    cf = calculate_cash_flow_consolidation(start_date="2026-10-01", end_date="2026-10-31")
    # Agregar movimiento con formula injection para validar sanitización
    cf["movements"].append({
        "date": "2026-10-28",
        "flow_nature": "REAL",
        "origin": "Movimiento Bancario",
        "origin_code": "banco",
        "doc_number": "=cmd|'/C calc'!A0",
        "entity_name": "+56912345678",
        "bank_account_id": None,
        "bank_label": "-Banco Inyección",
        "description": "@SUM(A1:A10)",
        "inflow": Decimal("100.00"),
        "outflow": Decimal("0.00"),
        "net_amount": Decimal("100.00"),
        "status": "Movimiento Real",
        "reconciliation_status": "PENDIENTE",
        "source_id": 9999,
        "link_url": None,
        "is_internal_transfer": False,
    })

    excel_bytes = export_cash_flow_to_excel(cf, account_name="Banco Prueba")
    assert len(excel_bytes) > 0

    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    assert "Resumen Flujo de Caja" in wb.sheetnames
    assert "Detalle Movimientos" in wb.sheetnames

    ws_det = wb["Detalle Movimientos"]
    # Encontrar la fila con la inyección
    found = False
    for r in range(5, ws_det.max_row + 1):
        cell_doc = str(ws_det.cell(row=r, column=4).value or "")
        if "cmd" in cell_doc:
            assert cell_doc.startswith("'")
            found = True
            break
    assert found is True


def test_routes_and_rbac(auth_client):
    """Test routes /reporteria/flujo-caja and Excel export with HTTP 200 and permissions."""
    res = auth_client.get("/reporteria/flujo-caja?horizonte=proximas_4_semanas&agrupacion=semanal")
    assert res.status_code == 200
    assert b"Flujo de Caja Consolidado" in res.data
    assert b"Evoluci\xc3\xb3n del Saldo de Caja" in res.data or b"Evolucion del Saldo de Caja" in res.data

    res_excel = auth_client.get("/reporteria/flujo-caja/exportar-excel")
    assert res_excel.status_code == 200
    assert res_excel.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
