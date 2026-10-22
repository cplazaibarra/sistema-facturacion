"""
repositories/finance_repo.py
Domain repository extracted from db.py.
Preserves exact implementation, parameters, locks, and return types.
"""

import os
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import psycopg2
import psycopg2.extras
from werkzeug.security import generate_password_hash

from core.database import get_connection
from core.pagination import PAGE_SIZE, pagination_meta


def get_bank_accounts_page(page=1):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM bank_accounts")
            pagination = pagination_meta(cur.fetchone()['n'], page)
            cur.execute("""SELECT id, bank_name, account_number, account_type, holder_name,
                                  holder_rut, email, status, created_at
                           FROM bank_accounts ORDER BY id DESC LIMIT %s OFFSET %s""",
                        (PAGE_SIZE, pagination['offset']))
            return [dict(row) for row in cur.fetchall()], pagination


def search_bank_account_options(search: str = "", limit: int = 30) -> dict:
    """Small remote selector response for bank account choices."""
    from core.pagination import PAGE_SIZE
    term=(search or "").strip()
    pattern=f"%{term}%"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT COUNT(*) AS total FROM bank_accounts
                WHERE (%s='' OR bank_name ILIKE %s OR account_number ILIKE %s OR holder_name ILIKE %s)""",
                (term,pattern,pattern,pattern))
            total=cur.fetchone()['total']
            cur.execute("""SELECT id,bank_name,account_number,account_type,holder_name FROM bank_accounts
                WHERE (%s='' OR bank_name ILIKE %s OR account_number ILIKE %s OR holder_name ILIKE %s)
                ORDER BY id DESC LIMIT %s""",(term,pattern,pattern,pattern,min(PAGE_SIZE,max(1,int(limit)))))
            return {'items':[dict(r) for r in cur.fetchall()],'total':total}


def list_bank_accounts() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, bank_name, account_number, account_type, holder_name, holder_rut, email, status, created_at
                FROM bank_accounts
                ORDER BY id DESC
                """
            )
            return [dict(row) for row in cur.fetchall()]


def get_bank_account(account_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, bank_name, account_number, account_type, holder_name, holder_rut, email, status, created_at
                FROM bank_accounts
                WHERE id = %s
                """,
                (account_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None


def insert_bank_account(account: dict) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bank_accounts (bank_name, account_number, account_type, holder_name, holder_rut, email, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    account["bank_name"],
                    account["account_number"],
                    account["account_type"],
                    account["holder_name"],
                    account.get("holder_rut", ""),
                    account.get("email", ""),
                    account.get("status", "Activa")
                )
            )
            inserted_id = cur.fetchone()["id"]
        conn.commit()
        return inserted_id


def update_bank_account(account_id: int, account: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE bank_accounts SET
                    bank_name = %s, account_number = %s, account_type = %s,
                    holder_name = %s, holder_rut = %s, email = %s, status = %s
                WHERE id = %s
                """,
                (
                    account["bank_name"],
                    account["account_number"],
                    account["account_type"],
                    account["holder_name"],
                    account.get("holder_rut", ""),
                    account.get("email", ""),
                    account.get("status", "Activa"),
                    account_id
                )
            )
        conn.commit()


def delete_bank_account(account_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM bank_accounts WHERE id = %s", (account_id,))
        conn.commit()


def get_sale_payments_map() -> dict[int, dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sale_id, invoice_number, invoice_amount, invoice_due_date, invoice_file, payment_proof_file, payment_amount, payment_date,
                       seller_uploaded_at, payment_uploaded_at, accounting_approved, accounting_approved_by,
                       accounting_approved_at, accounting_comment, status, created_at, updated_at
                FROM sale_payments
                """
            )
            rows = cur.fetchall()
            return {row["sale_id"]: dict(row) for row in rows}


def get_sale_payment(sale_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sale_id, invoice_number, invoice_amount, invoice_due_date, invoice_file, payment_proof_file, payment_amount, payment_date,
                       seller_uploaded_at, payment_uploaded_at, accounting_approved, accounting_approved_by,
                       accounting_approved_at, accounting_comment, status, created_at, updated_at
                FROM sale_payments
                WHERE sale_id = %s
                """,
                (sale_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def upsert_sale_payment(sale_id: int, payment: dict, conn=None) -> None:
    def _execute(cur):
        cur.execute(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'sale_payments'
            """
        )
        payment_columns = {row["column_name"] for row in cur.fetchall()}
        has_invoice_number = "invoice_number" in payment_columns
        has_accounting_comment = "accounting_comment" in payment_columns
        has_invoice_due_date = "invoice_due_date" in payment_columns
        has_payment_date = "payment_date" in payment_columns
        has_invoice_amount = "invoice_amount" in payment_columns
        has_payment_amount = "payment_amount" in payment_columns
        
        cur.execute(
            "SELECT id FROM sale_payments WHERE sale_id = %s",
            (sale_id,),
        )
        existing = cur.fetchone()
        if existing:
            if has_invoice_number:
                cur.execute(
                    """
                    UPDATE sale_payments
                    SET invoice_number = %s, invoice_amount = %s, invoice_due_date = %s, invoice_file = %s, payment_proof_file = %s, payment_amount = %s, payment_date = %s, seller_uploaded_at = %s,
                        payment_uploaded_at = %s, accounting_approved = %s, accounting_approved_by = %s,
                        accounting_approved_at = %s, accounting_comment = %s, status = %s, updated_at = %s
                    WHERE sale_id = %s
                    """,
                    (
                        payment.get("invoice_number"),
                        payment.get("invoice_amount"),
                        payment.get("invoice_due_date"),
                        payment.get("invoice_file"),
                        payment.get("payment_proof_file"),
                        payment.get("payment_amount"),
                        payment.get("payment_date"),
                        payment.get("seller_uploaded_at"),
                        payment.get("payment_uploaded_at"),
                        payment.get("accounting_approved", 0),
                        payment.get("accounting_approved_by"),
                        payment.get("accounting_approved_at"),
                        payment.get("accounting_comment"),
                        payment.get("status", "Factura pendiente"),
                        payment.get("updated_at"),
                        sale_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    UPDATE sale_payments
                    SET invoice_amount = %s, invoice_due_date = %s, invoice_file = %s, payment_proof_file = %s, payment_amount = %s, payment_date = %s, seller_uploaded_at = %s,
                        payment_uploaded_at = %s, accounting_approved = %s, accounting_approved_by = %s,
                        accounting_approved_at = %s, accounting_comment = %s, status = %s, updated_at = %s
                    WHERE sale_id = %s
                    """,
                    (
                        payment.get("invoice_amount"),
                        payment.get("invoice_due_date"),
                        payment.get("invoice_file"),
                        payment.get("payment_proof_file"),
                        payment.get("payment_amount"),
                        payment.get("payment_date"),
                        payment.get("seller_uploaded_at"),
                        payment.get("payment_uploaded_at"),
                        payment.get("accounting_approved", 0),
                        payment.get("accounting_approved_by"),
                        payment.get("accounting_approved_at"),
                        payment.get("accounting_comment"),
                        payment.get("status", "Factura pendiente"),
                        payment.get("updated_at"),
                        sale_id,
                    ),
                )
        else:
            cur.execute(
                """
                INSERT INTO sale_payments (
                    sale_id, invoice_file, payment_proof_file, seller_uploaded_at,
                    payment_uploaded_at, accounting_approved, accounting_approved_by,
                    accounting_approved_at, status, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    sale_id,
                    payment.get("invoice_file"),
                    payment.get("payment_proof_file"),
                    payment.get("seller_uploaded_at"),
                    payment.get("payment_uploaded_at"),
                    payment.get("accounting_approved", 0),
                    payment.get("accounting_approved_by"),
                    payment.get("accounting_approved_at"),
                    payment.get("status", "Factura pendiente"),
                    payment.get("created_at"),
                    payment.get("updated_at"),
                ),
            )
            if has_invoice_number:
                cur.execute(
                    "UPDATE sale_payments SET invoice_number = %s WHERE sale_id = %s",
                    (payment.get("invoice_number"), sale_id),
                )
            if has_invoice_amount:
                cur.execute(
                    "UPDATE sale_payments SET invoice_amount = %s WHERE sale_id = %s",
                    (payment.get("invoice_amount"), sale_id),
                )
            if has_payment_amount:
                cur.execute(
                    "UPDATE sale_payments SET payment_amount = %s WHERE sale_id = %s",
                    (payment.get("payment_amount"), sale_id),
                )
            if has_invoice_due_date:
                cur.execute(
                    "UPDATE sale_payments SET invoice_due_date = %s WHERE sale_id = %s",
                    (payment.get("invoice_due_date"), sale_id),
                )
            if has_payment_date:
                cur.execute(
                    "UPDATE sale_payments SET payment_date = %s WHERE sale_id = %s",
                    (payment.get("payment_date"), sale_id),
                )
            if has_accounting_comment:
                cur.execute(
                    "UPDATE sale_payments SET accounting_comment = %s WHERE sale_id = %s",
                    (payment.get("accounting_comment"), sale_id),
                )

    if conn is not None:
        with conn.cursor() as cur:
            _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                _execute(cur)
            c.commit()


def list_sale_payment_items(sale_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'sale_payment_items'
                """
            )
            cols = [r["column_name"] for r in cur.fetchall()]
            has_approval = "accounting_approved" in cols
            if has_approval:
                select_cols = "id, sale_id, payment_amount, payment_date, payment_proof_file, created_at, accounting_approved, accounting_approved_by, accounting_approved_at, accounting_comment, payment_method, registered_by, registered_at, bank_name_snapshot, account_number_snapshot, payment_notes"
            else:
                select_cols = "id, sale_id, payment_amount, payment_date, payment_proof_file, created_at"
            
            cur.execute(
                f"SELECT {select_cols} FROM sale_payment_items WHERE sale_id = %s ORDER BY created_at ASC",
                (sale_id,),
            )
            rows = cur.fetchall()
            items = [dict(row) for row in rows]
            for it in items:
                if not has_approval:
                    it["accounting_approved"] = 0
                    it["accounting_approved_by"] = None
                    it["accounting_approved_at"] = None
                    it["accounting_comment"] = None
                else:
                    it["accounting_approved"] = 1 if it.get("accounting_approved") else 0
            return items


def update_sale_payment_item_approval(item_id: int, approved: bool, approved_by: str, approved_at: str, comment: str = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sale_payment_items
                SET accounting_approved = %s, accounting_approved_by = %s, accounting_approved_at = %s, accounting_comment = %s
                WHERE id = %s
                """,
                (1 if approved else 0, approved_by if approved else None, approved_at if approved else None, comment, item_id),
            )
        conn.commit()


def insert_sale_payment_item(item: dict) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sale_payment_items (sale_id, payment_amount, payment_date, payment_proof_file, created_at, bank_account_id)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (
                    item["sale_id"],
                    item["payment_amount"],
                    item.get("payment_date"),
                    item.get("payment_proof_file"),
                    item["created_at"],
                    item.get("bank_account_id"),
                ),
            )
            inserted_id = cur.fetchone()["id"]
        conn.commit()
        return inserted_id


def update_sale_payment_item_proof(item_id: int, proof_file: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sale_payment_items SET payment_proof_file = %s WHERE id = %s",
                (proof_file, item_id),
            )
        conn.commit()


def update_sale_payment_item_amount_date(item_id: int, payment_amount: float, payment_date: str = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sale_payment_items SET payment_amount = %s, payment_date = %s WHERE id = %s",
                (payment_amount, payment_date or None, item_id),
            )
        conn.commit()


def delete_sale_payment_item(item_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sale_payment_items WHERE id = %s", (item_id,))
        conn.commit()


def get_sale_payment_items_totals(sale_ids: list[int]) -> dict[int, float]:
    if not sale_ids:
        return {}
    placeholders = ",".join(["%s"] * len(sale_ids))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT sale_id, COALESCE(SUM(payment_amount), 0) as total_paid
                FROM sale_payment_items
                WHERE sale_id IN ({placeholders})
                GROUP BY sale_id
                """,
                tuple(sale_ids),
            )
            rows = cur.fetchall()
            return {row["sale_id"]: row["total_paid"] for row in rows}


def count_pending_invoices() -> int:
    """Cuenta facturas de proveedor en estado Pendiente o Vencida."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS n FROM purchase_invoices
                WHERE payment_status IN ('Pendiente', 'Vencida')
            """)
            return cur.fetchone()['n']


def update_invoice_payment_status() -> int:
    """Marca como Vencidas las facturas cuyo due_date ya pasó. Retorna cuántas actualizó."""
    from datetime import date
    today = date.today().isoformat()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE purchase_invoices
                SET payment_status = 'Vencida'
                WHERE payment_status = 'Pendiente'
                  AND due_date <> '' AND due_date IS NOT NULL
                  AND due_date < %s
            """, (today,))
            conn.commit()
            return cur.rowcount


def register_purchase_payment(invoice_id: int, data: dict, conn=None) -> bool:
    """Append an installment under the invoice lock; never rewrite prior payments."""
    from decimal import Decimal, InvalidOperation
    from datetime import date
    import hashlib
    try:
        amount = Decimal(str(data.get('payment_amount', '')))
        if not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal('.01')):
            return False
        payment_date = date.fromisoformat(str(data.get('payment_date', '')))
    except (InvalidOperation, ValueError, TypeError):
        return False
    method = str(data.get('payment_method') or '')
    account = data.get('bank_account_id') or None
    # Older callers have no key: identical requests are defensive retries.
    payload = [str(amount.normalize()), str(payment_date), method, str(account)]
    key = str(data.get('idempotency_key') or hashlib.sha256(json.dumps(payload).encode()).hexdigest())
    if len(key) > 200 or not method:
        return False

    def _execute(cur):
        cur.execute("SELECT * FROM purchase_invoices WHERE id=%s FOR UPDATE", (invoice_id,))
        inv = cur.fetchone()
        if not inv or inv['payment_status'] in ('Anulada', 'Anulado'):
            return False
        cur.execute("SELECT * FROM purchase_payment_items WHERE invoice_id=%s AND idempotency_key=%s", (invoice_id,key))
        previous = cur.fetchone()
        if previous:
            if not data.get('idempotency_key'):return False
            return (previous['payment_amount'] == amount and previous['payment_date'] == payment_date
                    and previous['bank_account_id'] == account and previous['payment_method'] == method)
        cur.execute("SELECT COALESCE(SUM(payment_amount),0) AS paid,COUNT(*) AS n FROM purchase_payment_items WHERE invoice_id=%s", (invoice_id,))
        ledger = cur.fetchone()
        legacy_paid = Decimal(str(inv['payment_amount'] or 0))
        # A previously closed legacy invoice remains closed, even without metadata.
        if not ledger['n'] and inv['payment_status'] in ('Pagada','Pagado') and legacy_paid == 0:
            return False
        cur.execute('SELECT payment_amount FROM purchase_payment_openings WHERE invoice_id=%s',(invoice_id,))
        opening=cur.fetchone()
        paid = ledger['paid'] + (opening['payment_amount'] if opening else Decimal(0)) if ledger['n'] else legacy_paid
        total = Decimal(str(inv['invoice_amount'] or 0))
        if not total.is_finite() or not paid.is_finite() or total <= 0 or paid < 0 or amount > total-paid:
            return False
        if account:
            cur.execute("SELECT id FROM bank_accounts WHERE id=%s AND status='Activa'", (account,))
            if not cur.fetchone(): return False
        elif method != 'Efectivo':
            return False
        if not ledger['n'] and legacy_paid > 0:
            if not inv.get('payment_date'):return False
            cur.execute('''INSERT INTO purchase_payment_openings(invoice_id,payment_amount,payment_date,payment_method,bank_account_id,payment_proof_file)
                VALUES(%s,%s,%s,%s,%s,%s)''',(invoice_id,legacy_paid,inv['payment_date'],inv.get('payment_method'),inv.get('bank_account_id'),inv.get('payment_proof_file')))
        cur.execute("""INSERT INTO purchase_payment_items
            (invoice_id,payment_amount,payment_date,payment_method,bank_account_id,payment_proof_file,notes,idempotency_key)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (invoice_id,amount,payment_date,method,account,data.get('payment_proof_file'),data.get('payment_notes') or '',key))
        cumulative = paid + amount
        due = str(inv.get('due_date') or '')
        status = 'Pagada' if cumulative == total else ('Vencida' if due and due < date.today().isoformat() else 'Pendiente')
        cur.execute("""UPDATE purchase_invoices SET payment_status=%s,payment_date=%s,
            payment_amount=%s,payment_method=%s,bank_account_id=%s,payment_proof_file=%s WHERE id=%s""",
            (status,str(payment_date),cumulative,method,account,data.get('payment_proof_file'),invoice_id))
        return True

    if conn is not None:
        with conn.cursor() as cur: return _execute(cur)
    with get_connection() as c:
        with c.cursor() as cur: result = _execute(cur)
        c.commit()
        return result


def list_pending_invoice_alerts(days_ahead: int = 7) -> list:
    """Retorna facturas vencidas o que vencen en los próximos N días, para alertas en dashboard."""
    from datetime import date, timedelta
    today = date.today().isoformat()
    limit_date = (date.today() + timedelta(days=days_ahead)).isoformat()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT pi.id, pi.invoice_number, pi.invoice_amount, pi.due_date,
                       pi.payment_status, s.name AS supplier_name
                FROM purchase_invoices pi
                LEFT JOIN suppliers s ON s.id = pi.supplier_id
                WHERE pi.payment_status IN ('Pendiente', 'Vencida')
                  AND (pi.due_date IS NULL OR pi.due_date = '' OR pi.due_date <= %s)
                ORDER BY pi.due_date ASC NULLS FIRST
                LIMIT 10
            """, (limit_date,))
            return cur.fetchall()


def link_invoice_to_entry(invoice_id: int, entry_id: int) -> bool:
    """Vincula una factura existente a una entrada de bodega (guía de despacho)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE purchase_invoices SET inventory_entry_id = %s WHERE id = %s
            """, (entry_id, invoice_id))
            cur.execute("""
                UPDATE inventory_entries SET document_type = 'factura' WHERE id = %s
            """, (entry_id,))
            conn.commit()
            return cur.rowcount > 0
