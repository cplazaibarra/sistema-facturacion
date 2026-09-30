"""
repositories/bank_reconciliation_repo.py
Domain repository for Bank Reconciliation (Conciliación Bancaria).
Handles bank transactions, categories, statement imports, reconciliation matching, audit logs, and metrics.
"""

import hashlib
import json
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import psycopg2
import psycopg2.extras

from core.database import get_connection
from core.pagination import PAGE_SIZE, pagination_meta


# ---------------------------------------------------------
# Fingerprint Helper
# ---------------------------------------------------------
def generate_transaction_fingerprint(
    bank_account_id: int,
    transaction_date: str,
    value_date: Optional[str],
    amount: Decimal | float,
    movement_type: str,
    reference: Optional[str],
    doc_number: Optional[str],
    description: str,
) -> str:
    """
    Generates a deterministic unique SHA-256 fingerprint for a bank transaction.
    """
    amt_decimal = Decimal(str(amount)).quantize(Decimal("0.01"))
    raw_str = (
        f"{bank_account_id}|"
        f"{str(transaction_date).strip()}|"
        f"{(str(value_date).strip() if value_date else '')}|"
        f"{amt_decimal:.2f}|"
        f"{str(movement_type).strip().upper()}|"
        f"{(str(reference).strip().lower() if reference else '')}|"
        f"{(str(doc_number).strip().lower() if doc_number else '')}|"
        f"{str(description).strip().lower()}"
    )
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


# ---------------------------------------------------------
# Categories
# ---------------------------------------------------------
def list_bank_transaction_categories(active_only: bool = True) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            query = "SELECT id, name, flow_type, is_active, created_at FROM bank_transaction_categories"
            if active_only:
                query += " WHERE is_active = TRUE"
            query += " ORDER BY flow_type ASC, name ASC"
            cur.execute(query)
            return [dict(r) for r in cur.fetchall()]


def get_bank_transaction_category(category_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, flow_type, is_active, created_at FROM bank_transaction_categories WHERE id = %s",
                (category_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def create_bank_transaction_category(name: str, flow_type: str) -> Tuple[bool, str, Optional[int]]:
    """
    Creates a new category for bank transactions.
    flow_type must be 'INGRESO', 'EGRESO', or 'AMBOS'.
    """
    clean_name = name.strip()
    clean_flow = flow_type.strip().upper()
    if not clean_name:
        return False, "El nombre de la categoría no puede estar vacío", None
    if clean_flow not in ("INGRESO", "EGRESO", "AMBOS"):
        return False, "El tipo de flujo debe ser INGRESO, EGRESO o AMBOS", None

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM bank_transaction_categories WHERE LOWER(name) = LOWER(%s)", (clean_name,))
            if cur.fetchone():
                return False, f"Ya existe una categoría llamada '{clean_name}'", None

            cur.execute(
                """
                INSERT INTO bank_transaction_categories (name, flow_type)
                VALUES (%s, %s)
                RETURNING id
                """,
                (clean_name, clean_flow),
            )
            new_id = cur.fetchone()["id"]
            return True, "Categoría creada exitosamente", new_id


def update_bank_transaction_category(category_id: int, name: str, flow_type: str) -> Tuple[bool, str]:
    """
    Updates the name and flow_type of an existing category.
    """
    clean_name = name.strip()
    clean_flow = flow_type.strip().upper()
    if not clean_name:
        return False, "El nombre de la categoría no puede estar vacío"
    if clean_flow not in ("INGRESO", "EGRESO", "AMBOS"):
        return False, "El tipo de flujo debe ser INGRESO, EGRESO o AMBOS"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM bank_transaction_categories WHERE LOWER(name) = LOWER(%s) AND id != %s",
                (clean_name, category_id),
            )
            if cur.fetchone():
                return False, f"Ya existe otra categoría llamada '{clean_name}'"

            cur.execute(
                """
                UPDATE bank_transaction_categories
                SET name = %s, flow_type = %s
                WHERE id = %s
                """,
                (clean_name, clean_flow, category_id),
            )
            if cur.rowcount == 0:
                return False, "Categoría no encontrada"
            return True, "Categoría actualizada exitosamente"


def delete_bank_transaction_category(category_id: int) -> Tuple[bool, str]:
    """
    Deletes or deactivates a category.
    If it is assigned to any transactions, it clears their assignment or unlinks safely, then deletes.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM bank_transaction_categories WHERE id = %s", (category_id,))
            row = cur.fetchone()
            if not row:
                return False, "Categoría no encontrada"
            cat_name = row["name"]

            # Unlink from bank transactions
            cur.execute("UPDATE bank_transactions SET category_id = NULL WHERE category_id = %s", (category_id,))
            cur.execute("DELETE FROM bank_transaction_categories WHERE id = %s", (category_id,))
            return True, f"Categoría '{cat_name}' eliminada exitosamente"


# ---------------------------------------------------------
# Statement Imports Log
# ---------------------------------------------------------
def log_bank_transaction_import(
    filename: str,
    bank_account_id: int,
    imported_by: str,
    total_rows: int,
    new_rows: int,
    duplicate_rows: int,
    error_rows: int,
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bank_transaction_imports (
                    filename, bank_account_id, imported_by,
                    total_rows, new_rows, duplicate_rows, error_rows
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    filename,
                    bank_account_id,
                    imported_by,
                    total_rows,
                    new_rows,
                    duplicate_rows,
                    error_rows,
                ),
            )
            return cur.fetchone()["id"]


# ---------------------------------------------------------
# Bank Transactions CRUD & Filtering
# ---------------------------------------------------------
def get_existing_fingerprints(fingerprints: List[str]) -> set[str]:
    if not fingerprints:
        return set()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT fingerprint FROM bank_transactions WHERE fingerprint = ANY(%s)",
                (fingerprints,),
            )
            return {r["fingerprint"] for r in cur.fetchall()}


def insert_bank_transactions_bulk(
    transactions: List[Dict[str, Any]],
    import_id: Optional[int],
    bank_account_id: int,
) -> int:
    """
    Inserts a list of validated transactions skipping duplicates deterministically.
    Returns the count of successfully inserted transactions.
    """
    if not transactions:
        return 0

    inserted_count = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            for tx in transactions:
                cur.execute(
                    """
                    INSERT INTO bank_transactions (
                        bank_account_id, import_id, transaction_date, value_date,
                        description, reference, doc_number, charge, credit,
                        amount, movement_type, balance, currency, category_id,
                        reconciliation_status, notes, fingerprint
                    )
                    VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        'PENDIENTE', %s, %s
                    )
                    ON CONFLICT (fingerprint) DO NOTHING
                    RETURNING id
                    """,
                    (
                        bank_account_id,
                        import_id,
                        tx["transaction_date"],
                        tx.get("value_date"),
                        tx["description"],
                        tx.get("reference"),
                        tx.get("doc_number"),
                        Decimal(str(tx.get("charge") or 0)),
                        Decimal(str(tx.get("credit") or 0)),
                        Decimal(str(tx["amount"])),
                        tx["movement_type"],
                        Decimal(str(tx["balance"])) if tx.get("balance") is not None else None,
                        tx.get("currency", "CLP"),
                        tx.get("category_id"),
                        tx.get("notes"),
                        tx["fingerprint"],
                    ),
                )
                res = cur.fetchone()
                if res:
                    inserted_count += 1
    return inserted_count


def get_bank_transaction(transaction_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    bt.*,
                    ba.bank_name,
                    ba.account_number,
                    ba.account_type,
                    btc.name as category_name,
                    btc.flow_type as category_flow_type
                FROM bank_transactions bt
                JOIN bank_accounts ba ON bt.bank_account_id = ba.id
                LEFT JOIN bank_transaction_categories btc ON bt.category_id = btc.id
                WHERE bt.id = %s
                """,
                (transaction_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def _transaction_filters(bank_account_id=None, start_date=None, end_date=None,
                         movement_type=None, reconciliation_status=None,
                         category_id=None, search=None):
    where_clauses = ["1=1"]
    params: List[Any] = []

    if bank_account_id:
        where_clauses.append("bt.bank_account_id = %s")
        params.append(bank_account_id)

    if start_date:
        where_clauses.append("bt.transaction_date >= %s")
        params.append(start_date)

    if end_date:
        where_clauses.append("bt.transaction_date <= %s")
        params.append(end_date)

    if movement_type and movement_type.upper() in ("ABONO", "CARGO"):
        where_clauses.append("bt.movement_type = %s")
        params.append(movement_type.upper())

    if reconciliation_status and reconciliation_status.upper() in ("PENDIENTE", "CONCILIADO", "REVISAR"):
        where_clauses.append("bt.reconciliation_status = %s")
        params.append(reconciliation_status.upper())

    if category_id:
        where_clauses.append("bt.category_id = %s")
        params.append(category_id)

    if search:
        search_term = f"%{search.strip()}%"
        where_clauses.append(
            """
            (
                bt.description ILIKE %s OR
                COALESCE(bt.reference, '') ILIKE %s OR
                COALESCE(bt.doc_number, '') ILIKE %s OR
                COALESCE(bt.notes, '') ILIKE %s OR
                ba.bank_name ILIKE %s OR
                ba.account_number ILIKE %s
            )
            """
        )
        params.extend([search_term] * 6)

    where_str = " AND ".join(where_clauses)

    return where_str, params


def list_bank_transactions(
    bank_account_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    movement_type: Optional[str] = None,
    reconciliation_status: Optional[str] = None,
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    sort_by: str = "transaction_date",
    order: str = "desc",
    page: int = 1,
    per_page: int = PAGE_SIZE,
    *, export_all: bool = False,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    List consolidated bank movements with multi-filter and server-side pagination.
    """
    allowed_sorts = {
        "transaction_date": "bt.transaction_date",
        "amount": "bt.amount",
        "movement_type": "bt.movement_type",
        "bank_name": "ba.bank_name",
        "reconciliation_status": "bt.reconciliation_status",
        "category_name": "btc.name",
        "id": "bt.id",
    }
    sort_column = allowed_sorts.get(sort_by, "bt.transaction_date")
    direction = "DESC" if order.lower() == "desc" else "ASC"

    where_str, params = _transaction_filters(
        bank_account_id, start_date, end_date, movement_type,
        reconciliation_status, category_id, search)

    with get_connection() as conn:
        with conn.cursor() as cur:
            count_query = f"""
                SELECT COUNT(*) as total
                FROM bank_transactions bt
                JOIN bank_accounts ba ON bt.bank_account_id = ba.id
                LEFT JOIN bank_transaction_categories btc ON bt.category_id = btc.id
                WHERE {where_str}
            """
            cur.execute(count_query, params)
            total = cur.fetchone()["total"]

            pagination = pagination_meta(total, page)
            offset = pagination["offset"]
            data_query = f"""
                SELECT 
                    bt.id,
                    bt.bank_account_id,
                    bt.import_id,
                    bt.transaction_date,
                    bt.value_date,
                    bt.description,
                    bt.reference,
                    bt.doc_number,
                    bt.charge,
                    bt.credit,
                    bt.amount,
                    bt.movement_type,
                    bt.balance,
                    bt.currency,
                    bt.category_id,
                    bt.reconciliation_status,
                    bt.reconciled_type,
                    bt.reconciled_id,
                    bt.reconciled_at,
                    bt.reconciled_by,
                    bt.notes,
                    bt.fingerprint,
                    bt.created_at,
                    ba.bank_name,
                    ba.account_number,
                    ba.account_type,
                    btc.name as category_name,
                    btc.flow_type as category_flow_type
                FROM bank_transactions bt
                JOIN bank_accounts ba ON bt.bank_account_id = ba.id
                LEFT JOIN bank_transaction_categories btc ON bt.category_id = btc.id
                WHERE {where_str}
                ORDER BY {sort_column} {direction}, bt.id DESC
            """
            detail_params = list(params)
            if not export_all:
                data_query += " LIMIT %s OFFSET %s"
                detail_params.extend([PAGE_SIZE, offset])
            cur.execute(data_query, detail_params)
            rows = [dict(r) for r in cur.fetchall()]
            return rows, total


def get_bank_reconciliation_kpis(
    bank_account_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    movement_type: Optional[str] = None,
    reconciliation_status: Optional[str] = None,
    category_id: Optional[int] = None,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """Aggregate the complete universe selected by the detail filters."""
    where_str, params = _transaction_filters(
        bank_account_id, start_date, end_date, movement_type,
        reconciliation_status, category_id, search)

    with get_connection() as conn:
        with conn.cursor() as cur:
            query = f"""
                SELECT
                    COUNT(*) as total_count,
                    COUNT(*) FILTER (WHERE reconciliation_status = 'CONCILIADO') as reconciled_count,
                    COUNT(*) FILTER (WHERE reconciliation_status = 'PENDIENTE') as pending_count,
                    COUNT(*) FILTER (WHERE reconciliation_status = 'REVISAR') as review_count,
                    COALESCE(SUM(credit), 0) as total_abonos,
                    COALESCE(SUM(charge), 0) as total_cargos,
                    COALESCE(SUM(credit) FILTER (WHERE reconciliation_status = 'CONCILIADO'), 0) as reconciled_abonos,
                    COALESCE(SUM(charge) FILTER (WHERE reconciliation_status = 'CONCILIADO'), 0) as reconciled_cargos,
                    COALESCE(SUM(credit) FILTER (WHERE reconciliation_status = 'PENDIENTE'), 0) as pending_abonos,
                    COALESCE(SUM(charge) FILTER (WHERE reconciliation_status = 'PENDIENTE'), 0) as pending_cargos
                FROM bank_transactions bt
                JOIN bank_accounts ba ON ba.id = bt.bank_account_id
                WHERE {where_str}
            """
            cur.execute(query, params)
            row = cur.fetchone()
            total_count = row["total_count"] or 0
            reconciled_count = row["reconciled_count"] or 0
            rate = round((reconciled_count / total_count * 100), 1) if total_count > 0 else 0.0

            return {
                "total_count": total_count,
                "reconciled_count": reconciled_count,
                "pending_count": row["pending_count"] or 0,
                "review_count": row["review_count"] or 0,
                "reconciliation_rate": rate,
                "total_abonos": Decimal(str(row["total_abonos"])),
                "total_cargos": Decimal(str(row["total_cargos"])),
                "net_movement": Decimal(str(row["total_abonos"])) - Decimal(str(row["total_cargos"])),
                "reconciled_abonos": Decimal(str(row["reconciled_abonos"])),
                "reconciled_cargos": Decimal(str(row["reconciled_cargos"])),
                "pending_abonos": Decimal(str(row["pending_abonos"])),
                "pending_cargos": Decimal(str(row["pending_cargos"])),
            }


# ---------------------------------------------------------
# Categorization & Audit
# ---------------------------------------------------------
def update_transaction_category(
    transaction_id: int,
    category_id: Optional[int],
    user_name: str,
    notes: Optional[str] = None,
) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, category_id, notes, reconciliation_status FROM bank_transactions WHERE id = %s FOR UPDATE",
                (transaction_id,),
            )
            current = cur.fetchone()
            if not current:
                return False

            prev_state = {
                "category_id": current["category_id"],
                "notes": current["notes"],
            }
            new_state = {
                "category_id": category_id,
                "notes": notes if notes is not None else current["notes"],
            }

            cur.execute(
                """
                UPDATE bank_transactions
                SET category_id = %s,
                    notes = COALESCE(%s, notes)
                WHERE id = %s
                """,
                (category_id, notes, transaction_id),
            )

            cur.execute(
                """
                INSERT INTO bank_reconciliation_audit (
                    bank_transaction_id, action, previous_state, new_state, user_name, notes
                )
                VALUES (%s, 'CATEGORIZED', %s, %s, %s, %s)
                """,
                (
                    transaction_id,
                    json.dumps(prev_state),
                    json.dumps(new_state),
                    user_name,
                    notes or "Categoría actualizada",
                ),
            )
            return True


# ---------------------------------------------------------
# Deterministic Reconciliation & Matching
# ---------------------------------------------------------
def get_suggested_reconciliation_matches(transaction_id: int) -> Dict[str, Any]:
    """
    Finds deterministic candidates to reconcile against a bank transaction.
    - If ABONO: checks sale_payment_items (or sales) where amount matches and date within +/- 15 days.
    - If CARGO: checks purchase_invoices and operational_expense_occurrences where amount matches +/- 15 days.
    - Also checks internal transfers (opposing transaction in another account with exact same amount).
    """
    tx = get_bank_transaction(transaction_id)
    if not tx:
        return {"error": "Movimiento no encontrado", "matches": []}

    matches = []
    tx_date = tx["transaction_date"]
    if isinstance(tx_date, str):
        tx_dt = datetime.strptime(tx_date, "%Y-%m-%d").date()
    else:
        tx_dt = tx_date

    min_date = (tx_dt - timedelta(days=15)).strftime("%Y-%m-%d")
    max_date = (tx_dt + timedelta(days=15)).strftime("%Y-%m-%d")
    tx_amount = Decimal(str(tx["amount"]))

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Internal Transfers (Opposite sign, different account)
            cur.execute(
                """
                SELECT 
                    bt.id,
                    bt.bank_account_id,
                    bt.transaction_date,
                    bt.amount,
                    bt.movement_type,
                    bt.description,
                    ba.bank_name,
                    ba.account_number
                FROM bank_transactions bt
                JOIN bank_accounts ba ON bt.bank_account_id = ba.id
                WHERE bt.id != %s
                  AND bt.bank_account_id != %s
                  AND bt.amount = %s
                  AND bt.reconciliation_status != 'CONCILIADO'
                  AND bt.transaction_date BETWEEN %s AND %s
                ORDER BY ABS(bt.transaction_date - %s) ASC, bt.id DESC
                LIMIT 15
                """,
                (tx["id"], tx["bank_account_id"], -tx_amount, min_date, max_date, tx_dt),
            )
            for row in cur.fetchall():
                matches.append({
                    "match_type": "INTERNAL_TRANSFER",
                    "id": row["id"],
                    "title": f"Transferencia: {row['bank_name']} ({row['account_number']})",
                    "detail": f"{row['movement_type']} ${abs(Decimal(str(row['amount']))):,.0f} - {row['description']}",
                    "date": str(row["transaction_date"]),
                    "amount": float(abs(Decimal(str(row["amount"])))),
                    "score": 95 if str(row["transaction_date"]) == str(tx_dt) else 80,
                })

            if tx["movement_type"] == "ABONO":
                # Abono matches Sale Payments (Cobranzas)
                abs_amt = abs(tx_amount)
                cur.execute(
                    """
                    SELECT 
                        spi.id,
                        spi.sale_id,
                        spi.payment_amount,
                        spi.payment_date,
                        spi.payment_method,
                        s.sale_number,
                        s.customer_name,
                        spi.bank_account_id
                    FROM sale_payment_items spi
                    JOIN sales s ON spi.sale_id = s.id
                    WHERE spi.payment_amount = %s
                      AND (spi.payment_date BETWEEN %s AND %s)
                      AND NOT EXISTS (
                          SELECT 1 FROM bank_transactions bt 
                          WHERE bt.reconciled_type = 'SALE_PAYMENT' 
                            AND bt.reconciled_id = spi.id
                            AND bt.reconciliation_status = 'CONCILIADO'
                      )
                    ORDER BY
                      (spi.bank_account_id = %s) DESC NULLS LAST,
                      ABS(spi.payment_date::date - %s::date) ASC, spi.id DESC
                    LIMIT 10
                    """,
                    (abs_amt, min_date, max_date, tx["bank_account_id"], tx_dt),
                )
                for row in cur.fetchall():
                    account_match = (row["bank_account_id"] == tx["bank_account_id"])
                    date_match = (str(row["payment_date"]) == str(tx_dt))
                    score = 90 if (account_match and date_match) else (85 if account_match else (75 if date_match else 65))
                    matches.append({
                        "match_type": "SALE_PAYMENT",
                        "id": row["id"],
                        "title": f"Pago Venta: {row['sale_number']} - {row['customer_name']}",
                        "detail": f"Monto: ${Decimal(str(row['payment_amount'])):,.0f} | Fecha: {row['payment_date']} | Método: {row['payment_method']}",
                        "date": str(row["payment_date"]),
                        "amount": float(Decimal(str(row["payment_amount"]))),
                        "score": score,
                    })

            elif tx["movement_type"] == "CARGO":
                # Cargo matches Purchase Invoices (Pagos a Proveedores) or Operational Expenses
                abs_amt = abs(tx_amount)

                # Purchase Invoices
                cur.execute(
                    """
                    SELECT 
                        pi.id,
                        pi.invoice_number,
                        COALESCE(sup.name, 'Proveedor Sin Nombre') as supplier_name,
                        COALESCE(pi.payment_amount, pi.invoice_amount) as amount,
                        pi.payment_date,
                        pi.bank_account_id
                    FROM purchase_invoices pi
                    LEFT JOIN suppliers sup ON pi.supplier_id = sup.id
                    WHERE COALESCE(pi.payment_amount, pi.invoice_amount) = %s
                      AND pi.payment_date IS NOT NULL
                      AND (pi.payment_date BETWEEN %s AND %s)
                      AND NOT EXISTS (
                          SELECT 1 FROM bank_transactions bt 
                          WHERE bt.reconciled_type = 'PURCHASE_PAYMENT' 
                            AND bt.reconciled_id = pi.id
                            AND bt.reconciliation_status = 'CONCILIADO'
                      )
                    ORDER BY
                      (pi.bank_account_id = %s) DESC NULLS LAST,
                      ABS(pi.payment_date::date - %s::date) ASC, pi.id DESC
                    LIMIT 10
                    """,
                    (abs_amt, min_date, max_date, tx["bank_account_id"], tx_dt),
                )
                for row in cur.fetchall():
                    account_match = (row["bank_account_id"] == tx["bank_account_id"])
                    date_match = (str(row["payment_date"]) == str(tx_dt))
                    score = 90 if (account_match and date_match) else (85 if account_match else (75 if date_match else 65))
                    matches.append({
                        "match_type": "PURCHASE_PAYMENT",
                        "id": row["id"],
                        "title": f"Factura Compra: {row['invoice_number']} - {row['supplier_name']}",
                        "detail": f"Monto: ${Decimal(str(row['amount'])):,.0f} | Fecha Pago: {row['payment_date']}",
                        "date": str(row["payment_date"]),
                        "amount": float(Decimal(str(row["amount"]))),
                        "score": score,
                    })

                # Operational Expenses
                cur.execute(
                    """
                    SELECT 
                        oeo.id,
                        oe.name as expense_name,
                        oe.beneficiary,
                        COALESCE(oeo.payment_amount, oeo.amount) as amount,
                        oeo.paid_date,
                        oeo.bank_account_id
                    FROM operational_expense_occurrences oeo
                    JOIN operational_expenses oe ON oeo.expense_id = oe.id
                    WHERE COALESCE(oeo.payment_amount, oeo.amount) = %s
                      AND oeo.paid_date IS NOT NULL
                      AND (oeo.paid_date BETWEEN %s AND %s)
                      AND NOT EXISTS (
                          SELECT 1 FROM bank_transactions bt 
                          WHERE bt.reconciled_type = 'EXPENSE' 
                            AND bt.reconciled_id = oeo.id
                            AND bt.reconciliation_status = 'CONCILIADO'
                      )
                    ORDER BY
                      (oeo.bank_account_id = %s) DESC NULLS LAST,
                      ABS(oeo.paid_date::date - %s::date) ASC, oeo.id DESC
                    LIMIT 10
                    """,
                    (abs_amt, min_date, max_date, tx["bank_account_id"], tx_dt),
                )
                for row in cur.fetchall():
                    account_match = (row["bank_account_id"] == tx["bank_account_id"])
                    date_match = (str(row["paid_date"]) == str(tx_dt))
                    score = 90 if (account_match and date_match) else (85 if account_match else (75 if date_match else 65))
                    matches.append({
                        "match_type": "EXPENSE",
                        "id": row["id"],
                        "title": f"Gasto Operacional: {row['expense_name']} ({row['beneficiary'] or 'Sin beneficiario'})",
                        "detail": f"Monto: ${Decimal(str(row['amount'])):,.0f} | Fecha Pago: {row['paid_date']}",
                        "date": str(row["paid_date"]),
                        "amount": float(Decimal(str(row["amount"]))),
                        "score": score,
                    })

                # Debt Installment Payments (Pagos de Deudas Financieras)
                cur.execute(
                    """
                    SELECT 
                        dp.id,
                        d.name as debt_name,
                        d.creditor_name,
                        di.installment_number,
                        dp.payment_amount as amount,
                        dp.payment_date,
                        dp.bank_account_id
                    FROM debt_payments dp
                    JOIN debt_installments di ON dp.debt_installment_id = di.id
                    JOIN debts d ON di.debt_id = d.id
                    WHERE dp.payment_amount = %s
                      AND dp.payment_date IS NOT NULL
                      AND (dp.payment_date BETWEEN %s AND %s)
                      AND NOT EXISTS (
                          SELECT 1 FROM bank_transactions bt 
                          WHERE bt.reconciled_type = 'DEBT_PAYMENT' 
                            AND bt.reconciled_id = dp.id
                            AND bt.reconciliation_status = 'CONCILIADO'
                      )
                    ORDER BY
                      (dp.bank_account_id = %s) DESC NULLS LAST,
                      ABS(dp.payment_date::date - %s::date) ASC, dp.id DESC
                    LIMIT 10
                    """,
                    (abs_amt, min_date, max_date, tx["bank_account_id"], tx_dt),
                )
                for row in cur.fetchall():
                    account_match = (row["bank_account_id"] == tx["bank_account_id"])
                    date_match = (str(row["payment_date"]) == str(tx_dt))
                    score = 90 if (account_match and date_match) else (85 if account_match else (75 if date_match else 65))
                    matches.append({
                        "match_type": "DEBT_PAYMENT",
                        "id": row["id"],
                        "title": f"Pago Cuota #{row['installment_number']}: {row['debt_name']} ({row['creditor_name']})",
                        "detail": f"Monto: ${Decimal(str(row['amount'])):,.0f} | Fecha Pago: {row['payment_date']}",
                        "date": str(row["payment_date"]),
                        "amount": float(Decimal(str(row["amount"]))),
                        "score": score,
                    })

    # Sort matches by score descending
    matches.sort(key=lambda m: m["score"], reverse=True)
    return {"transaction": tx, "matches": matches}


def reconcile_transaction(
    transaction_id: int,
    reconciled_type: str,
    reconciled_id: int,
    user_name: str,
    notes: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Reconciles a bank transaction against an ERP operation or internal transfer.
    Never alters or creates financial records in ERP tables.
    """
    valid_types = {"SALE_PAYMENT", "PURCHASE_PAYMENT", "EXPENSE", "DEBT_PAYMENT", "INTERNAL_TRANSFER"}
    if reconciled_type not in valid_types:
        return False, f"Tipo de conciliación inválido: {reconciled_type}"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM bank_transactions WHERE id = %s FOR UPDATE",
                (transaction_id,),
            )
            tx = cur.fetchone()
            if not tx:
                return False, "Movimiento bancario no encontrado"

            if tx["reconciliation_status"] == "CONCILIADO":
                return False, "El movimiento ya se encuentra conciliado"

            # Check if target is already reconciled elsewhere
            cur.execute(
                """
                SELECT id FROM bank_transactions
                WHERE reconciled_type = %s 
                  AND reconciled_id = %s 
                  AND reconciliation_status = 'CONCILIADO'
                  AND id != %s
                """,
                (reconciled_type, reconciled_id, transaction_id),
            )
            conflict = cur.fetchone()
            if conflict:
                return False, f"La operación de destino ya fue conciliada con el movimiento #{conflict['id']}"

            # Verify target existence
            if reconciled_type == "SALE_PAYMENT":
                cur.execute("SELECT id FROM sale_payment_items WHERE id = %s", (reconciled_id,))
                if not cur.fetchone():
                    return False, f"Pago de venta #{reconciled_id} no existe"
            elif reconciled_type == "PURCHASE_PAYMENT":
                cur.execute("SELECT id FROM purchase_invoices WHERE id = %s", (reconciled_id,))
                if not cur.fetchone():
                    return False, f"Factura de compra #{reconciled_id} no existe"
            elif reconciled_type == "EXPENSE":
                cur.execute("SELECT id FROM operational_expense_occurrences WHERE id = %s", (reconciled_id,))
                if not cur.fetchone():
                    return False, f"Ocurrencia de gasto #{reconciled_id} no existe"
            elif reconciled_type == "INTERNAL_TRANSFER":
                cur.execute("SELECT id, bank_account_id, amount FROM bank_transactions WHERE id = %s FOR UPDATE", (reconciled_id,))
                c_tx = cur.fetchone()
                if not c_tx:
                    return False, f"Movimiento de contraparte #{reconciled_id} no existe"
                if c_tx["bank_account_id"] == tx["bank_account_id"]:
                    return False, "Una transferencia interna debe ser entre cuentas bancarias distintas"

            prev_state = {
                "reconciliation_status": tx["reconciliation_status"],
                "reconciled_type": tx["reconciled_type"],
                "reconciled_id": tx["reconciled_id"],
                "reconciled_at": tx["reconciled_at"].isoformat() if tx.get("reconciled_at") else None,
                "reconciled_by": tx["reconciled_by"],
            }

            now = datetime.now(timezone.utc)
            cur.execute(
                """
                UPDATE bank_transactions
                SET reconciliation_status = 'CONCILIADO',
                    reconciled_type = %s,
                    reconciled_id = %s,
                    reconciled_at = %s,
                    reconciled_by = %s,
                    notes = COALESCE(%s, notes)
                WHERE id = %s
                """,
                (reconciled_type, reconciled_id, now, user_name, notes, transaction_id),
            )

            new_state = {
                "reconciliation_status": "CONCILIADO",
                "reconciled_type": reconciled_type,
                "reconciled_id": reconciled_id,
                "reconciled_at": now.isoformat(),
                "reconciled_by": user_name,
            }

            cur.execute(
                """
                INSERT INTO bank_reconciliation_audit (
                    bank_transaction_id, action, previous_state, new_state, user_name, notes
                )
                VALUES (%s, 'RECONCILED', %s, %s, %s, %s)
                """,
                (transaction_id, json.dumps(prev_state), json.dumps(new_state), user_name, notes or "Conciliado"),
            )

            # If internal transfer, also reconcile the counterpart
            if reconciled_type == "INTERNAL_TRANSFER":
                cur.execute(
                    """
                    UPDATE bank_transactions
                    SET reconciliation_status = 'CONCILIADO',
                        reconciled_type = 'INTERNAL_TRANSFER',
                        reconciled_id = %s,
                        reconciled_at = %s,
                        reconciled_by = %s
                    WHERE id = %s
                    """,
                    (transaction_id, now, user_name, reconciled_id),
                )
                cur.execute(
                    """
                    INSERT INTO bank_reconciliation_audit (
                        bank_transaction_id, action, previous_state, new_state, user_name, notes
                    )
                    VALUES (%s, 'RECONCILED', %s, %s, %s, %s)
                    """,
                    (
                        reconciled_id,
                        json.dumps({"reconciliation_status": "PENDIENTE"}),
                        json.dumps({"reconciliation_status": "CONCILIADO", "reconciled_id": transaction_id}),
                        user_name,
                        f"Conciliado recíprocamente por transferencia con #{transaction_id}",
                    ),
                )

            return True, "Movimiento conciliado exitosamente"


def unreconcile_transaction(
    transaction_id: int,
    user_name: str,
    notes: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Unreconciles a bank transaction and restores pending status, recording audit trail.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM bank_transactions WHERE id = %s FOR UPDATE",
                (transaction_id,),
            )
            tx = cur.fetchone()
            if not tx:
                return False, "Movimiento bancario no encontrado"

            if tx["reconciliation_status"] != "CONCILIADO":
                return False, "El movimiento no se encuentra conciliado"

            prev_state = {
                "reconciliation_status": tx["reconciliation_status"],
                "reconciled_type": tx["reconciled_type"],
                "reconciled_id": tx["reconciled_id"],
                "reconciled_at": tx["reconciled_at"].isoformat() if tx.get("reconciled_at") else None,
                "reconciled_by": tx["reconciled_by"],
            }

            cur.execute(
                """
                UPDATE bank_transactions
                SET reconciliation_status = 'PENDIENTE',
                    reconciled_type = NULL,
                    reconciled_id = NULL,
                    reconciled_at = NULL,
                    reconciled_by = NULL
                WHERE id = %s
                """,
                (transaction_id,),
            )

            new_state = {
                "reconciliation_status": "PENDIENTE",
                "reconciled_type": None,
                "reconciled_id": None,
                "reconciled_at": None,
                "reconciled_by": None,
            }

            cur.execute(
                """
                INSERT INTO bank_reconciliation_audit (
                    bank_transaction_id, action, previous_state, new_state, user_name, notes
                )
                VALUES (%s, 'UNRECONCILED', %s, %s, %s, %s)
                """,
                (
                    transaction_id,
                    json.dumps(prev_state),
                    json.dumps(new_state),
                    user_name,
                    notes or "Desconciliación manual",
                ),
            )

            # If it was an internal transfer counterpart, unreconcile it too
            if prev_state.get("reconciled_type") == "INTERNAL_TRANSFER" and prev_state.get("reconciled_id"):
                counterpart_id = prev_state["reconciled_id"]
                cur.execute(
                    """
                    UPDATE bank_transactions
                    SET reconciliation_status = 'PENDIENTE',
                        reconciled_type = NULL,
                        reconciled_id = NULL,
                        reconciled_at = NULL,
                        reconciled_by = NULL
                    WHERE id = %s AND reconciliation_status = 'CONCILIADO'
                    """,
                    (counterpart_id,),
                )
                cur.execute(
                    """
                    INSERT INTO bank_reconciliation_audit (
                        bank_transaction_id, action, previous_state, new_state, user_name, notes
                    )
                    VALUES (%s, 'UNRECONCILED', %s, %s, %s, %s)
                    """,
                    (
                        counterpart_id,
                        json.dumps({"reconciliation_status": "CONCILIADO"}),
                        json.dumps({"reconciliation_status": "PENDIENTE"}),
                        user_name,
                        f"Desconciliado automáticamente por desconciliación de transferencia #{transaction_id}",
                    ),
                )

            return True, "Movimiento desconciliado exitosamente"


def get_transaction_audit_history(transaction_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, bank_transaction_id, action, previous_state, new_state, user_name, notes, created_at
                FROM bank_reconciliation_audit
                WHERE bank_transaction_id = %s
                ORDER BY created_at DESC, id DESC
                """,
                (transaction_id,),
            )
            return [dict(r) for r in cur.fetchall()]
