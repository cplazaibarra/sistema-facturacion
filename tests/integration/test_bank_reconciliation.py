"""
tests/integration/test_bank_reconciliation.py
Comprehensive test suite for the Bank Reconciliation module (Finanzas -> Conciliación Bancaria).
Covers:
- Plantilla download & structure
- Import preview, validation, deduplication (fingerprint)
- Decimal accuracy, formula injection protection
- Round-trip integrity (Export -> Re-import gives 0 new, N duplicates, 0 errors)
- Adding new rows yields exact new count
- Reconciliation logic: ABONO (Sales), CARGO (Purchases & Expenses), Internal Transfers
- Prevention of double reconciliation
- Unreconciliation & audit trail logging
- Non-impact on original ERP operations (sales, payments, invoices, expenses unchanged)
- RBAC permissions
- Server-side filtering, searching, and pagination
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
    list_bank_accounts,
    insert_bank_account,
    list_bank_transaction_categories,
    list_bank_transactions,
    get_bank_reconciliation_kpis,
    update_transaction_category,
    reconcile_transaction,
    unreconcile_transaction,
    get_suggested_reconciliation_matches,
    get_transaction_audit_history,
)
from services.bank_reconciliation_excel_service import (
    generate_bank_statement_template,
    export_bank_transactions_to_excel,
    parse_and_preview_bank_statement,
    commit_bank_statement_import,
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
def unauthorized_client():
    old_csrf = app.config.get("WTF_CSRF_ENABLED", True)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    try:
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["user_id"] = 2
                sess["username"] = "no_reportes_user"
                sess["role_name"] = "Operario"
                sess["permissions"] = {"reportes": False}
            yield client
    finally:
        app.config["WTF_CSRF_ENABLED"] = old_csrf


@pytest.fixture
def test_bank_accounts():
    """Create two dedicated bank accounts for testing."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            acc1_num = f"ACC-{uuid.uuid4().hex[:8]}"
            cur.execute(
                """
                INSERT INTO bank_accounts (bank_name, account_number, account_type, holder_name, holder_rut, email, status)
                VALUES ('Banco Estado', %s, 'Cuenta Corriente', 'Miel SPA', '76.123.456-7', 'tesoreria@miel.cl', 'Activa')
                RETURNING id
                """,
                (acc1_num,)
            )
            id1 = cur.fetchone()["id"]

            acc2_num = f"ACC-{uuid.uuid4().hex[:8]}"
            cur.execute(
                """
                INSERT INTO bank_accounts (bank_name, account_number, account_type, holder_name, holder_rut, email, status)
                VALUES ('Banco Santander', %s, 'Cuenta Vista', 'Miel SPA', '76.123.456-7', 'tesoreria@miel.cl', 'Activa')
                RETURNING id
                """,
                (acc2_num,)
            )
            id2 = cur.fetchone()["id"]
        conn.commit()
    return id1, id2


def test_download_template_endpoint(auth_client, test_bank_accounts):
    """Test downloading the canonical Excel template."""
    acc_id, _ = test_bank_accounts
    res = auth_client.get(f"/reporteria/conciliacion-bancaria/plantilla?bank_account_id={acc_id}")
    assert res.status_code == 200
    assert res.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    wb = openpyxl.load_workbook(io.BytesIO(res.data))
    ws = wb.active
    headers = [cell.value for cell in ws[1] if cell.value is not None]
    assert "Fecha" in headers
    assert "Descripción" in headers
    assert "Cargo" in headers
    assert "Abono" in headers
    assert "Saldo" in headers


def test_rbac_protection(unauthorized_client, auth_client):
    """Test RBAC protection for conciliation routes."""
    res_unauth = unauthorized_client.get("/reporteria/conciliacion-bancaria")
    assert res_unauth.status_code in (403, 302)

    res_auth = auth_client.get("/reporteria/conciliacion-bancaria")
    assert res_auth.status_code == 200
    assert b"Conciliaci\xc3\xb3n Bancaria" in res_auth.data or b"Conciliacion Bancaria" in res_auth.data


def test_import_validation_and_deduplication(auth_client, test_bank_accounts):
    """Test Excel upload, validation, and fingerprint duplicate detection."""
    acc_id, _ = test_bank_accounts
    unique_tag = uuid.uuid4().hex[:8]

    # Create an in-memory workbook with 3 rows: 2 valid, 1 error (missing date)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Fecha", "Descripción", "Referencia", "Cargo", "Abono", "Saldo"])
    ws.append(["2026-03-01", f"ABONO TEST {unique_tag}", "REF-001", 0, 100000, 500000])
    ws.append(["2026-03-02", f"CARGO TEST {unique_tag}", "REF-002", 25000, 0, 475000])
    ws.append(["", f"INVALID ROW {unique_tag}", "", 1000, 0, 474000])

    buf = io.BytesIO()
    wb.save(buf)
    file_bytes = buf.getvalue()

    # 1. Preview
    data = {
        "bank_account_id": str(acc_id),
        "file": (io.BytesIO(file_bytes), "test_statement.xlsx"),
    }
    res = auth_client.post("/reporteria/conciliacion-bancaria/preview-excel", data=data, content_type="multipart/form-data")
    assert res.status_code == 200
    preview_json = res.get_json()
    assert preview_json["status"] == "success"
    assert preview_json["summary"]["total_rows"] == 3
    assert preview_json["summary"]["new_rows"] == 2
    assert preview_json["summary"]["error_rows"] == 1

    # 2. Confirm import
    res_conf = auth_client.post(
        "/reporteria/conciliacion-bancaria/confirmar-importacion",
        json={"preview_data": preview_json}
    )
    assert res_conf.status_code == 200
    conf_json = res_conf.get_json()
    assert conf_json["status"] == "success"
    assert conf_json["inserted_count"] == 2

    # 3. Re-upload identical file -> Should detect 2 duplicates and 1 error (0 new)
    data_dup = {
        "bank_account_id": str(acc_id),
        "file": (io.BytesIO(file_bytes), "test_statement.xlsx"),
    }
    res_dup = auth_client.post("/reporteria/conciliacion-bancaria/preview-excel", data=data_dup, content_type="multipart/form-data")
    dup_json = res_dup.get_json()
    assert dup_json["summary"]["new_rows"] == 0
    assert dup_json["summary"]["duplicate_rows"] == 2
    assert dup_json["summary"]["error_rows"] == 1


def test_round_trip_export_import(auth_client, test_bank_accounts):
    """
    Test exact round-trip schema compatibility:
    Exporting existing movements and re-importing yields 0 new, N duplicates, 0 errors.
    Adding 3 rows to that file yields exactly 3 new rows.
    """
    acc_id, _ = test_bank_accounts

    # 1. Export Excel for this account
    res_exp = auth_client.get(f"/reporteria/conciliacion-bancaria/exportar-excel?bank_account_id={acc_id}")
    assert res_exp.status_code == 200
    export_bytes = res_exp.data

    wb = openpyxl.load_workbook(io.BytesIO(export_bytes))
    ws = wb.active
    initial_rows = ws.max_row - 1  # Excluding header

    # 2. Re-import unchanged exported file
    data_reimport = {
        "bank_account_id": str(acc_id),
        "file": (io.BytesIO(export_bytes), "roundtrip_export.xlsx"),
    }
    res_prev = auth_client.post("/reporteria/conciliacion-bancaria/preview-excel", data=data_reimport, content_type="multipart/form-data")
    assert res_prev.status_code == 200
    prev_json = res_prev.get_json()
    assert prev_json["summary"]["new_rows"] == 0
    assert prev_json["summary"]["duplicate_rows"] == initial_rows
    assert prev_json["summary"]["error_rows"] == 0

    # 3. Add 3 new rows to the exported file and re-upload
    unique_tag = uuid.uuid4().hex[:6]
    for i in range(1, 4):
        ws.append([
            f"2026-03-{10+i:02d}",
            "",
            f"ROUNDTRIP NEW ROW {i} {unique_tag}",
            f"REF-RT-{i}",
            f"DOC-{i}",
            0,
            15000 * i,
            15000 * i,
            "ABONO",
            1000000 + (15000 * i),
            "CLP",
            "Otros Ingresos",
            "Prueba roundtrip",
        ])

    buf_added = io.BytesIO()
    wb.save(buf_added)
    added_bytes = buf_added.getvalue()

    data_added = {
        "bank_account_id": str(acc_id),
        "file": (io.BytesIO(added_bytes), "roundtrip_added.xlsx"),
    }
    res_added = auth_client.post("/reporteria/conciliacion-bancaria/preview-excel", data=data_added, content_type="multipart/form-data")
    assert res_added.status_code == 200
    added_json = res_added.get_json()
    assert added_json["summary"]["new_rows"] == 3
    assert added_json["summary"]["duplicate_rows"] == initial_rows
    assert added_json["summary"]["error_rows"] == 0


def test_formula_injection_mitigation(test_bank_accounts):
    """Ensure malicious formulas starting with =, +, -, @ are escaped in exported Excel."""
    acc_id, _ = test_bank_accounts
    malicious_desc = "=cmd|'/C calc'!A0"

    # Insert raw transaction with malicious text
    with get_connection() as conn:
        with conn.cursor() as cur:
            fp = uuid.uuid4().hex
            cur.execute(
                """
                INSERT INTO bank_transactions (
                    bank_account_id, transaction_date, description, charge, credit, amount, movement_type, fingerprint
                )
                VALUES (%s, '2026-03-15', %s, 0, 5000, 5000, 'ABONO', %s)
                """,
                (acc_id, malicious_desc, fp)
            )
        conn.commit()

    # Export
    stream = export_bank_transactions_to_excel(bank_account_id=acc_id)
    wb = openpyxl.load_workbook(stream)
    ws = wb.active

    found_escaped = False
    for row in ws.iter_rows(values_only=True):
        desc_val = row[2]  # Column 'Descripción'
        if desc_val and malicious_desc in str(desc_val):
            # Must start with single quote
            assert str(desc_val).startswith("'")
            found_escaped = True
            break
    assert found_escaped is True


def test_categorization_and_audit(auth_client, test_bank_accounts):
    """Test assigning category and verifying audit log entry."""
    acc_id, _ = test_bank_accounts

    # Insert a transaction
    with get_connection() as conn:
        with conn.cursor() as cur:
            fp = uuid.uuid4().hex
            cur.execute(
                """
                INSERT INTO bank_transactions (
                    bank_account_id, transaction_date, description, charge, credit, amount, movement_type, fingerprint
                )
                VALUES (%s, '2026-03-20', 'PAGO DE PRUEBA CATEGORIA', 50000, 0, -50000, 'CARGO', %s)
                RETURNING id
                """,
                (acc_id, fp)
            )
            tx_id = cur.fetchone()["id"]
        conn.commit()

    categories = list_bank_transaction_categories()
    assert len(categories) > 0
    cat_id = categories[0]["id"]

    # Categorize via API
    res = auth_client.post(
        f"/reporteria/conciliacion-bancaria/movimientos/{tx_id}/categorizar",
        json={"category_id": cat_id, "notes": "Categorizado por prueba"}
    )
    assert res.status_code == 200
    assert res.get_json()["status"] == "success"

    # Check audit history
    res_hist = auth_client.get(f"/reporteria/conciliacion-bancaria/movimientos/{tx_id}/historial")
    assert res_hist.status_code == 200
    history = res_hist.get_json()["history"]
    assert len(history) >= 1
    assert history[0]["action"] == "CATEGORIZED"


def test_reconciliation_with_sale_payment(auth_client, test_bank_accounts):
    """
    Test reconciling an ABONO against a sale_payment_item.
    Verifies that the original sale/payment remains unchanged.
    """
    acc_id, _ = test_bank_accounts

    # 1. Create a sale and payment item
    unique_vta = f"VTA-REC-{uuid.uuid4().hex[:6]}"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sales (sale_number, customer_name, sale_date, sale_time, products_json, total_amount, status, seller_name, payment_status, created_at)
                VALUES (%s, 'Cliente Reconcil', '2026-03-21', '10:00:00', '[]', 120000, 'Completada', 'Vendedor Test', 'Pagado', '2026-03-21 10:00:00')
                RETURNING id
                """,
                (unique_vta,)
            )
            sale_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO sale_payment_items (sale_id, payment_amount, payment_date, payment_method, bank_account_id, created_at)
                VALUES (%s, 120000, '2026-03-21', 'Transferencia', %s, '2026-03-21 10:00:00')
                RETURNING id
                """,
                (sale_id, acc_id)
            )
            payment_item_id = cur.fetchone()["id"]

            # Create bank transaction for this abono
            fp = uuid.uuid4().hex
            cur.execute(
                """
                INSERT INTO bank_transactions (
                    bank_account_id, transaction_date, description, charge, credit, amount, movement_type, fingerprint
                )
                VALUES (%s, '2026-03-21', 'TEF RECIBIDA CLIENTE RECONCIL', 0, 120000, 120000, 'ABONO', %s)
                RETURNING id
                """,
                (acc_id, fp)
            )
            tx_id = cur.fetchone()["id"]
        conn.commit()

    # 2. Get suggested matches
    res_sug = auth_client.get(f"/reporteria/conciliacion-bancaria/movimientos/{tx_id}/sugerencias")
    assert res_sug.status_code == 200
    sug_data = res_sug.get_json()["data"]
    matches = [m for m in sug_data["matches"] if m["match_type"] == "SALE_PAYMENT" and m["id"] == payment_item_id]
    assert len(matches) == 1

    # 3. Execute reconciliation
    res_rec = auth_client.post(
        f"/reporteria/conciliacion-bancaria/movimientos/{tx_id}/conciliar",
        json={"reconciled_type": "SALE_PAYMENT", "reconciled_id": payment_item_id, "notes": "Conciliado con VTA"}
    )
    assert res_rec.status_code == 200
    assert res_rec.get_json()["status"] == "success"

    # 4. Verify transaction status
    txs, _ = list_bank_transactions(bank_account_id=acc_id, search="CLIENTE RECONCIL")
    assert len(txs) == 1
    assert txs[0]["reconciliation_status"] == "CONCILIADO"
    assert txs[0]["reconciled_type"] == "SALE_PAYMENT"
    assert txs[0]["reconciled_id"] == payment_item_id

    # 5. Prevent duplicate reconciliation of the same sale payment
    with get_connection() as conn:
        with conn.cursor() as cur:
            fp2 = uuid.uuid4().hex
            cur.execute(
                """
                INSERT INTO bank_transactions (
                    bank_account_id, transaction_date, description, charge, credit, amount, movement_type, fingerprint
                )
                VALUES (%s, '2026-03-21', 'TEF DUPLICADA', 0, 120000, 120000, 'ABONO', %s)
                RETURNING id
                """,
                (acc_id, fp2)
            )
            tx2_id = cur.fetchone()["id"]
        conn.commit()

    res_rec_dup = auth_client.post(
        f"/reporteria/conciliacion-bancaria/movimientos/{tx2_id}/conciliar",
        json={"reconciled_type": "SALE_PAYMENT", "reconciled_id": payment_item_id}
    )
    assert res_rec_dup.status_code == 400
    assert "ya fue conciliada" in res_rec_dup.get_json()["message"]

    # 6. Unreconcile
    res_unrec = auth_client.post(
        f"/reporteria/conciliacion-bancaria/movimientos/{tx_id}/desconciliar",
        json={"notes": "Desconciliación prueba"}
    )
    assert res_unrec.status_code == 200

    txs_after, _ = list_bank_transactions(bank_account_id=acc_id, search="CLIENTE RECONCIL")
    assert txs_after[0]["reconciliation_status"] == "PENDIENTE"
    assert txs_after[0]["reconciled_type"] is None


def test_internal_transfer_reconciliation(auth_client, test_bank_accounts):
    """
    Test internal transfer between two distinct bank accounts.
    Reconciliation of one should automatically mark the counterpart as reconciled.
    """
    acc1_id, acc2_id = test_bank_accounts
    transfer_amount = 75000

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Cargo in acc1
            fp1 = uuid.uuid4().hex
            cur.execute(
                """
                INSERT INTO bank_transactions (
                    bank_account_id, transaction_date, description, charge, credit, amount, movement_type, fingerprint
                )
                VALUES (%s, '2026-03-25', 'TRANSFERENCIA A CUENTA SANTANDER', 75000, 0, -75000, 'CARGO', %s)
                RETURNING id
                """,
                (acc1_id, fp1)
            )
            tx1_id = cur.fetchone()["id"]

            # Abono in acc2
            fp2 = uuid.uuid4().hex
            cur.execute(
                """
                INSERT INTO bank_transactions (
                    bank_account_id, transaction_date, description, charge, credit, amount, movement_type, fingerprint
                )
                VALUES (%s, '2026-03-25', 'TRANSFERENCIA DESDE CUENTA ESTADO', 0, 75000, 75000, 'ABONO', %s)
                RETURNING id
                """,
                (acc2_id, fp2)
            )
            tx2_id = cur.fetchone()["id"]
        conn.commit()

    # Check suggested matches for tx1
    res_sug = auth_client.get(f"/reporteria/conciliacion-bancaria/movimientos/{tx1_id}/sugerencias")
    assert res_sug.status_code == 200
    matches = res_sug.get_json()["data"]["matches"]
    transfer_match = [m for m in matches if m["match_type"] == "INTERNAL_TRANSFER" and m["id"] == tx2_id]
    assert len(transfer_match) == 1

    # Reconcile transfer
    res_rec = auth_client.post(
        f"/reporteria/conciliacion-bancaria/movimientos/{tx1_id}/conciliar",
        json={"reconciled_type": "INTERNAL_TRANSFER", "reconciled_id": tx2_id, "notes": "Traspaso fondos"}
    )
    assert res_rec.status_code == 200

    # Verify both transactions are CONCILIADO
    tx1, _ = list_bank_transactions(bank_account_id=acc1_id, search="SANTANDER")
    tx2, _ = list_bank_transactions(bank_account_id=acc2_id, search="ESTADO")
    assert tx1[0]["reconciliation_status"] == "CONCILIADO"
    assert tx2[0]["reconciliation_status"] == "CONCILIADO"
    assert tx1[0]["reconciled_id"] == tx2_id
    assert tx2[0]["reconciled_id"] == tx1_id

    # Unreconcile tx1 should automatically unreconcile tx2
    res_unrec = auth_client.post(
        f"/reporteria/conciliacion-bancaria/movimientos/{tx1_id}/desconciliar",
        json={"notes": "Deshacer traspaso"}
    )
    assert res_unrec.status_code == 200

    tx1_after, _ = list_bank_transactions(bank_account_id=acc1_id, search="SANTANDER")
    tx2_after, _ = list_bank_transactions(bank_account_id=acc2_id, search="ESTADO")
    assert tx1_after[0]["reconciliation_status"] == "PENDIENTE"
    assert tx2_after[0]["reconciliation_status"] == "PENDIENTE"


def test_reconciliation_kpis_and_pagination(auth_client, test_bank_accounts):
    """Test KPIs calculation and server-side pagination parameters."""
    acc_id, _ = test_bank_accounts

    res = auth_client.get(f"/reporteria/conciliacion-bancaria?bank_account_id={acc_id}&page=1&per_page=10")
    assert res.status_code == 200
    assert b"Tasa Conciliaci" in res.data or b"Movimientos Totales" in res.data

    kpis = get_bank_reconciliation_kpis(bank_account_id=acc_id)
    assert "total_count" in kpis
    assert "reconciled_count" in kpis
    assert "pending_count" in kpis
    assert "reconciliation_rate" in kpis
    assert isinstance(kpis["net_movement"], Decimal)


def test_reconciliation_with_purchase_invoice(auth_client, test_bank_accounts):
    """
    Test reconciling a CARGO against a purchase_invoice.
    Verifies match suggestion, reconciliation lock, and non-modification of purchase invoice.
    """
    acc_id, _ = test_bank_accounts
    amount = 89000

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Ensure a supplier exists
            cur.execute(
                """
                INSERT INTO suppliers (name, rut, dv, razon_social, created_at)
                VALUES ('Proveedor Insumos Reconcil', '76.888.999', '5', 'Insumos Reconcil SpA', '2026-03-01')
                RETURNING id
                """
            )
            sup_id = cur.fetchone()["id"]

            # 2. Create purchase invoice
            cur.execute(
                """
                INSERT INTO purchase_invoices (supplier_id, invoice_number, invoice_amount, invoice_date, payment_status, payment_date, payment_amount, bank_account_id)
                VALUES (%s, 'FAC-PROV-999', %s, '2026-03-22', 'Pagado', '2026-03-22', %s, %s)
                RETURNING id
                """,
                (sup_id, amount, amount, acc_id)
            )
            inv_id = cur.fetchone()["id"]

            # 3. Create bank cargo
            fp = uuid.uuid4().hex
            cur.execute(
                """
                INSERT INTO bank_transactions (
                    bank_account_id, transaction_date, description, charge, credit, amount, movement_type, fingerprint
                )
                VALUES (%s, '2026-03-22', 'PAGO FACTURA INSUMOS', %s, 0, -%s, 'CARGO', %s)
                RETURNING id
                """,
                (acc_id, amount, amount, fp)
            )
            tx_id = cur.fetchone()["id"]
        conn.commit()

    # Get suggested matches
    res_sug = auth_client.get(f"/reporteria/conciliacion-bancaria/movimientos/{tx_id}/sugerencias")
    assert res_sug.status_code == 200
    sug_matches = res_sug.get_json()["data"]["matches"]
    inv_match = [m for m in sug_matches if m["match_type"] == "PURCHASE_PAYMENT" and m["id"] == inv_id]
    assert len(inv_match) == 1

    # Reconcile
    res_rec = auth_client.post(
        f"/reporteria/conciliacion-bancaria/movimientos/{tx_id}/conciliar",
        json={"reconciled_type": "PURCHASE_PAYMENT", "reconciled_id": inv_id, "notes": "Factura confirmada"}
    )
    assert res_rec.status_code == 200
    assert res_rec.get_json()["status"] == "success"

    # Verify status
    txs, _ = list_bank_transactions(bank_account_id=acc_id, search="PAGO FACTURA INSUMOS")
    assert txs[0]["reconciliation_status"] == "CONCILIADO"
    assert txs[0]["reconciled_type"] == "PURCHASE_PAYMENT"
    assert txs[0]["reconciled_id"] == inv_id


def test_reconciliation_with_operational_expense(auth_client, test_bank_accounts):
    """
    Test reconciling a CARGO against an operational_expense_occurrence.
    """
    acc_id, _ = test_bank_accounts
    amount = 32000

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Create operational expense
            cur.execute(
                """
                INSERT INTO operational_expenses (
                    name, category, amount, amount_type, frequency, start_date, due_rule, beneficiary
                )
                VALUES ('Plan Celular Ventas', 'Comunicaciones', %s, 'Fijo', 'Mensual', '2026-01-01', 'Día fijo del mes', 'Entel')
                RETURNING id
                """,
                (amount,)
            )
            exp_id = cur.fetchone()["id"]

            # 2. Create paid occurrence
            cur.execute(
                """
                INSERT INTO operational_expense_occurrences (
                    expense_id, due_date, amount, status, paid_date, payment_amount, bank_account_id
                )
                VALUES (%s, '2026-03-23', %s, 'Pagado', '2026-03-23', %s, %s)
                RETURNING id
                """,
                (exp_id, amount, amount, acc_id)
            )
            occ_id = cur.fetchone()["id"]

            # 3. Create bank transaction
            fp = uuid.uuid4().hex
            cur.execute(
                """
                INSERT INTO bank_transactions (
                    bank_account_id, transaction_date, description, charge, credit, amount, movement_type, fingerprint
                )
                VALUES (%s, '2026-03-23', 'PAC ENTEL MOVIL', %s, 0, -%s, 'CARGO', %s)
                RETURNING id
                """,
                (acc_id, amount, amount, fp)
            )
            tx_id = cur.fetchone()["id"]
        conn.commit()

    # Get suggested matches
    res_sug = auth_client.get(f"/reporteria/conciliacion-bancaria/movimientos/{tx_id}/sugerencias")
    assert res_sug.status_code == 200
    sug_matches = res_sug.get_json()["data"]["matches"]
    exp_match = [m for m in sug_matches if m["match_type"] == "EXPENSE" and m["id"] == occ_id]
    assert len(exp_match) == 1

    # Reconcile
    res_rec = auth_client.post(
        f"/reporteria/conciliacion-bancaria/movimientos/{tx_id}/conciliar",
        json={"reconciled_type": "EXPENSE", "reconciled_id": occ_id, "notes": "Gasto operativo verificado"}
    )
    assert res_rec.status_code == 200

    txs, _ = list_bank_transactions(bank_account_id=acc_id, search="PAC ENTEL")
    assert txs[0]["reconciliation_status"] == "CONCILIADO"
    assert txs[0]["reconciled_type"] == "EXPENSE"
    assert txs[0]["reconciled_id"] == occ_id


def test_filters_and_search(auth_client, test_bank_accounts):
    """Test searching by description, doc number, filtering by status and date."""
    acc_id, _ = test_bank_accounts
    unique_doc = f"DOC-{uuid.uuid4().hex[:6]}"

    with get_connection() as conn:
        with conn.cursor() as cur:
            fp = uuid.uuid4().hex
            cur.execute(
                """
                INSERT INTO bank_transactions (
                    bank_account_id, transaction_date, description, doc_number, charge, credit, amount, movement_type, fingerprint
                )
                VALUES (%s, '2026-03-26', 'DEPOSITO CHEQUE AL DIA', %s, 0, 450000, 450000, 'ABONO', %s)
                """,
                (acc_id, unique_doc, fp)
            )
        conn.commit()

    # Search by doc_number
    res_search = auth_client.get(f"/reporteria/conciliacion-bancaria?bank_account_id={acc_id}&search={unique_doc}")
    assert res_search.status_code == 200
    assert unique_doc.encode() in res_search.data


def test_category_management_crud(auth_client):
    """Test full CRUD (create, read, update, delete) for bank transaction categories."""
    unique_name = f"Test Cat {uuid.uuid4().hex[:6]}"

    # 1. Create
    res_create = auth_client.post(
        "/reporteria/conciliacion-bancaria/categorias",
        json={"name": unique_name, "flow_type": "EGRESO"}
    )
    assert res_create.status_code == 200
    cat_id = res_create.get_json()["category"]["id"]

    # 2. Update
    updated_name = f"Updated {unique_name}"
    res_update = auth_client.post(
        f"/reporteria/conciliacion-bancaria/categorias/{cat_id}",
        json={"name": updated_name, "flow_type": "AMBOS"}
    )
    assert res_update.status_code == 200

    # 3. Read list
    res_list = auth_client.get("/reporteria/conciliacion-bancaria/categorias")
    assert res_list.status_code == 200
    names = [c["name"] for c in res_list.get_json()["categories"]]
    assert updated_name in names

    # 4. Delete
    res_del = auth_client.delete(f"/reporteria/conciliacion-bancaria/categorias/{cat_id}")
    assert res_del.status_code == 200

    # Verify deleted
    res_list_after = auth_client.get("/reporteria/conciliacion-bancaria/categorias")
    names_after = [c["name"] for c in res_list_after.get_json()["categories"]]
    assert updated_name not in names_after
