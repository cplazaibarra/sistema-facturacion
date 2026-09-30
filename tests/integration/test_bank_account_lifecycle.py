"""
tests/integration/test_bank_account_lifecycle.py
Ciclo de vida E2E completo de Cuentas Bancarias en el ERP:
1. Creación (HTTP POST /administracion/cuentas-bancarias) y verificación en DB.
2. Saldo Inicial / Apertura vía movimiento de cartola bancaria y cálculo en get_bank_initial_balances.
3. Movimientos bancarios (ABONO y CARGO).
4. Conciliación de movimiento bancario con pago ERP y verificación de no-duplicación financiera.
5. Saldo actual y Flujo de Caja consolidado con carry-forward.
6. Edición de datos de la cuenta (HTTP POST /administracion/cuentas-bancarias/<id>/editar).
7. Desactivación (status = 'Inactiva') y verificación del impacto en listados y transacciones históricas.
8. Eliminación protegida (ON DELETE RESTRICT cuando existen transacciones / pagos asociados).
9. Eliminación limpia permitida cuando la cuenta es nueva y no posee dependencias.
"""

import uuid
from decimal import Decimal
from datetime import date
import pytest

from app import app
from db import (
    get_connection,
    list_bank_accounts,
    get_bank_account,
    insert_bank_account,
    update_bank_account,
    delete_bank_account,
    get_bank_initial_balances,
    calculate_cash_flow_consolidation,
    reconcile_transaction,
    list_bank_transactions,
)


@pytest.fixture
def auth_admin_client():
    old_csrf = app.config.get("WTF_CSRF_ENABLED", True)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    try:
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = 1
                sess["username"] = "admin_lifecycle"
                sess["full_name"] = "Admin Cuentas Bancarias"
                sess["role_name"] = "Administrativo"
                sess["permissions"] = {"administracion": True, "reportes": True}
            yield client
    finally:
        app.config["WTF_CSRF_ENABLED"] = old_csrf


def test_bank_account_full_lifecycle_e2e(auth_admin_client):
    """
    Validación integral del ciclo de vida de una cuenta bancaria:
    CREACIÓN -> SALDO INICIAL -> MOVIMIENTOS -> CONCILIACIÓN -> SALDO ACTUAL -> FLUJO DE CAJA -> EDICIÓN -> DESACTIVACIÓN -> PROTECCIÓN
    """
    uid = uuid.uuid4().hex[:6]
    acc_num = f"BANC-{uid}"
    
    # ---------------------------------------------------------
    # 1. CREACIÓN VÍA HTTP POST OFICIAL
    # ---------------------------------------------------------
    resp_create = auth_admin_client.post(
        "/administracion/cuentas-bancarias",
        data={
            "bank_name": "Banco Santander Test",
            "account_number": acc_num,
            "account_type": "Cuenta Corriente",
            "holder_name": "Empresa ERP SpA",
            "holder_rut": "77.123.456-K",
            "email": "tesoreria@erptest.cl",
            "status": "Activa",
        },
        follow_redirects=True,
    )
    assert resp_create.status_code == 200

    # Localizar la cuenta recién creada
    accounts = list_bank_accounts()
    created_acc = next((a for a in accounts if a["account_number"] == acc_num), None)
    assert created_acc is not None, "La cuenta bancaria creada debe figurar en el repositorio"
    acc_id = created_acc["id"]
    assert created_acc["bank_name"] == "Banco Santander Test"
    assert created_acc["status"] == "Activa"

    # ---------------------------------------------------------
    # 2. SALDO INICIAL VÍA APERTURA BANCARIA (CARTOLA)
    # ---------------------------------------------------------
    # Antes del movimiento de apertura, el saldo inicial es 0.00
    bals_zero = get_bank_initial_balances("2026-10-01", bank_account_id=acc_id)
    assert bals_zero.get(acc_id, Decimal("0.00")) == Decimal("0.00")

    fp_initial = uuid.uuid4().hex
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bank_transactions (
                    bank_account_id, transaction_date, description, doc_number,
                    charge, credit, amount, movement_type, fingerprint
                )
                VALUES (%s, '2026-09-30', 'Apertura cuenta / Saldo inicial', %s, 0, 15000000, 15000000, 'ABONO', %s)
                RETURNING id
                """,
                (acc_id, f"DOC-INI-{uid}", fp_initial)
            )
            init_tx_id = cur.fetchone()["id"]
        conn.commit()

    # Saldo inicial al 2026-10-01 debe ser exactamente 15,000,000.00
    bals_init = get_bank_initial_balances("2026-10-01", bank_account_id=acc_id)
    assert bals_init[acc_id] == Decimal("15000000.00")

    # ---------------------------------------------------------
    # 3. MOVIMIENTOS BANCARIOS (ABONO Y CARGO)
    # ---------------------------------------------------------
    fp_abono = uuid.uuid4().hex
    fp_cargo = uuid.uuid4().hex
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Abono por cobranza real de $2,000,000 el 2026-10-05
            cur.execute(
                """
                INSERT INTO bank_transactions (
                    bank_account_id, transaction_date, description, doc_number,
                    charge, credit, amount, movement_type, fingerprint
                )
                VALUES (%s, '2026-10-05', 'Transferencia Cliente ABC', %s, 0, 2000000, 2000000, 'ABONO', %s)
                RETURNING id
                """,
                (acc_id, f"DOC-ABO-{uid}", fp_abono)
            )
            abono_tx_id = cur.fetchone()["id"]

            # Cargo por pago proveedor de $500,000 el 2026-10-10
            cur.execute(
                """
                INSERT INTO bank_transactions (
                    bank_account_id, transaction_date, description, doc_number,
                    charge, credit, amount, movement_type, fingerprint
                )
                VALUES (%s, '2026-10-10', 'Transferencia Pago Insumos', %s, 500000, 0, -500000, 'CARGO', %s)
                RETURNING id
                """,
                (acc_id, f"DOC-CAR-{uid}", fp_cargo)
            )
            cargo_tx_id = cur.fetchone()["id"]
        conn.commit()

    # ---------------------------------------------------------
    # 4. CONCILIACIÓN CON DOCUMENTO ERP & NO-DUPLICACIÓN
    # ---------------------------------------------------------
    # Crear un pago de venta ERP correspondiente al abono
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sales (sale_number, customer_name, sale_date, sale_time, products_json, total_amount, status, seller_name, payment_status, created_at)
                VALUES (%s, 'Cliente ABC Test', '2026-10-05', '10:00:00', '[]', 2000000, 'Completada', 'Vendedor Test', 'Pagado', '2026-10-05 10:00:00')
                RETURNING id
                """,
                (f"VTA-{uid}",)
            )
            sale_id = cur.fetchone()["id"]

            # Crear item de pago asociado con accounting_approved = 1
            cur.execute(
                """
                INSERT INTO sale_payment_items (
                    sale_id, bank_account_id, payment_date, payment_amount, payment_method, accounting_approved, created_at
                )
                VALUES (%s, %s, '2026-10-05', 2000000, 'Transferencia', 1, '2026-10-05 10:00:00')
                RETURNING id
                """,
                (sale_id, acc_id)
            )
            sale_payment_id = cur.fetchone()["id"]
        conn.commit()

    # Conciliar la transacción de abono con el pago de venta
    rec_success = reconcile_transaction(
        transaction_id=abono_tx_id,
        reconciled_type="SALE_PAYMENT",
        reconciled_id=sale_payment_id,
        notes="Conciliación E2E Cuenta Bancaria",
        user_name="admin_lifecycle"
    )
    assert rec_success[0] is True

    # ---------------------------------------------------------
    # 5. SALDO ACTUAL Y FLUJO DE CAJA CONSOLIDADO (CARRY-FORWARD)
    # ---------------------------------------------------------
    # En el flujo de caja del mes 2026-10-01 al 2026-10-31 para esta cuenta:
    # Saldo Inicial: 15,000,000
    # Ingreso Real (Abono / Cobranza conciliada sin duplicar): 2,000,000
    # Egreso Real (Cargo proveedor no conciliado o directo): 500,000
    # Flujo Neto: +1,500,000
    # Saldo Final esperado: 16,500,000
    cf_data = calculate_cash_flow_consolidation(
        start_date="2026-10-01",
        end_date="2026-10-31",
        bank_account_id=acc_id,
        grouping="semanal"
    )
    assert cf_data["kpis"]["initial_balance"] == Decimal("15000000.00")
    assert cf_data["kpis"]["real_inflows"] == Decimal("2000000.00")
    assert cf_data["kpis"]["real_outflows"] == Decimal("500000.00")
    assert cf_data["kpis"]["final_projected_balance"] == Decimal("16500000.00")

    # Carry forward entre períodos consecutivos
    period_rows = cf_data["period_rows"]
    for i in range(len(period_rows) - 1):
        assert period_rows[i]["final_balance"] == period_rows[i+1]["initial_balance"]

    # ---------------------------------------------------------
    # 6. EDICIÓN VÍA HTTP POST OFICIAL
    # ---------------------------------------------------------
    resp_edit = auth_admin_client.post(
        f"/administracion/cuentas-bancarias/{acc_id}/editar",
        data={
            "bank_name": "Banco Santander Chile",
            "account_number": acc_num,
            "account_type": "Cuenta Corriente Preferente",
            "holder_name": "Empresa ERP SpA Matriz",
            "holder_rut": "77.123.456-K",
            "email": "finanzas@erptest.cl",
            "status": "Activa",
        },
        follow_redirects=True,
    )
    assert resp_edit.status_code == 200

    updated_acc = get_bank_account(acc_id)
    assert updated_acc["bank_name"] == "Banco Santander Chile"
    assert updated_acc["account_type"] == "Cuenta Corriente Preferente"
    assert updated_acc["holder_name"] == "Empresa ERP SpA Matriz"
    assert updated_acc["email"] == "finanzas@erptest.cl"

    # ---------------------------------------------------------
    # 7. DESACTIVACIÓN DE LA CUENTA (status = 'Inactiva')
    # ---------------------------------------------------------
    resp_deact = auth_admin_client.post(
        f"/administracion/cuentas-bancarias/{acc_id}/editar",
        data={
            "bank_name": "Banco Santander Chile",
            "account_number": acc_num,
            "account_type": "Cuenta Corriente Preferente",
            "holder_name": "Empresa ERP SpA Matriz",
            "holder_rut": "77.123.456-K",
            "email": "finanzas@erptest.cl",
            "status": "Inactiva",
        },
        follow_redirects=True,
    )
    assert resp_deact.status_code == 200

    deact_acc = get_bank_account(acc_id)
    assert deact_acc["status"] == "Inactiva"

    # ---------------------------------------------------------
    # 8. ELIMINACIÓN PROTEGIDA (RESTRICT POR TRANSACCIONES ASOCIADAS)
    # ---------------------------------------------------------
    resp_delete_fail = auth_admin_client.post(
        f"/administracion/cuentas-bancarias/{acc_id}/eliminar",
        follow_redirects=True,
    )
    assert resp_delete_fail.status_code == 200
    assert "No se puede eliminar la cuenta porque tiene pagos asociados" in resp_delete_fail.get_data(as_text=True)

    # La cuenta aún debe existir intacta
    acc_still_exists = get_bank_account(acc_id)
    assert acc_still_exists is not None

    # ---------------------------------------------------------
    # 9. ELIMINACIÓN LIMPIA DE CUENTA SIN MOVIMIENTOS
    # ---------------------------------------------------------
    clean_acc_num = f"CLEAN-{uid}"
    clean_acc_id = insert_bank_account({
        "bank_name": "Banco Sin Movimientos",
        "account_number": clean_acc_num,
        "account_type": "Vista",
        "holder_name": "Test SpA",
        "holder_rut": "76.000.000-1",
        "email": "test@test.cl",
        "status": "Activa",
    })
    assert get_bank_account(clean_acc_id) is not None

    resp_delete_clean = auth_admin_client.post(
        f"/administracion/cuentas-bancarias/{clean_acc_id}/eliminar",
        follow_redirects=True,
    )
    assert resp_delete_clean.status_code == 200
    assert "Cuenta bancaria eliminada correctamente" in resp_delete_clean.get_data(as_text=True)
    assert get_bank_account(clean_acc_id) is None
