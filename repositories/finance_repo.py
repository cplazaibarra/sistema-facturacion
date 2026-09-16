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
                select_cols = "id, sale_id, payment_amount, payment_date, payment_proof_file, created_at, accounting_approved, accounting_approved_by, accounting_approved_at, accounting_comment"
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
    """Registra el pago de una factura de proveedor indicando cuenta bancaria de egreso de forma atómica e idempotente."""
    def _execute(cur):
        # 1. Bloquear la factura de compra
        cur.execute(
            """
            SELECT id, invoice_number, invoice_amount, payment_status, payment_amount
            FROM purchase_invoices
            WHERE id = %s
            FOR UPDATE
            """,
            (invoice_id,)
        )
        inv = cur.fetchone()
        if not inv:
            return False

        # Si ya está pagada, rechazar pago duplicado (idempotencia defensiva)
        if inv["payment_status"] == 'Pagada':
            return False

        # 2. Actualizar estado y registrar pago
        cur.execute("""
            UPDATE purchase_invoices SET
                payment_status     = 'Pagada',
                payment_date       = %s,
                payment_amount     = %s,
                payment_method     = %s,
                bank_account_id    = %s,
                payment_proof_file = %s,
                notes              = COALESCE(notes, '') || %s
            WHERE id = %s
        """, (
            data.get('payment_date', ''),
            data.get('payment_amount', 0),
            data.get('payment_method', ''),
            data.get('bank_account_id'),
            data.get('payment_proof_file'),
            ('\nPago: ' + data.get('payment_notes', '')) if data.get('payment_notes') else '',
            invoice_id,
        ))
        return cur.rowcount > 0

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                res = _execute(cur)
            c.commit()
            return res


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

