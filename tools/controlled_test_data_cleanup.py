#!/usr/bin/env python3
"""Dry-run / transactional cleanup of independently verified test fixtures.

This deliberately does not purge inventory, purchase orders or sales with any
financial, reservation, lot or stock-ledger dependency. Dry-run is the default.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[1]
BACKUP_MARKER = b"PostgreSQL database dump complete"


def connect():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def prepare(cur):
    cur.execute("""
        CREATE TEMP TABLE cleanup_keep_accounts ON COMMIT DROP AS
        SELECT id FROM bank_accounts WHERE id=1
        UNION
        (SELECT id FROM bank_accounts WHERE id<>1 ORDER BY created_at DESC,id DESC LIMIT 9)
    """)
    cur.execute("""
        CREATE TEMP TABLE cleanup_delete_accounts ON COMMIT DROP AS
        SELECT id FROM bank_accounts WHERE id NOT IN (SELECT id FROM cleanup_keep_accounts)
    """)
    cur.execute("""
        CREATE TEMP TABLE cleanup_delete_debts ON COMMIT DROP AS
        SELECT id FROM debts WHERE bank_account_id IN (SELECT id FROM cleanup_delete_accounts)
    """)
    cur.execute("""
        CREATE TEMP TABLE cleanup_delete_installments ON COMMIT DROP AS
        SELECT id FROM debt_installments WHERE debt_id IN (SELECT id FROM cleanup_delete_debts)
    """)
    cur.execute("""
        CREATE TEMP TABLE cleanup_delete_debt_payments ON COMMIT DROP AS
        SELECT id FROM debt_payments
        WHERE debt_installment_id IN (SELECT id FROM cleanup_delete_installments)
           OR bank_account_id IN (SELECT id FROM cleanup_delete_accounts)
    """)
    cur.execute("""
        CREATE TEMP TABLE cleanup_delete_quotes ON COMMIT DROP AS
        WITH ranked AS (
            SELECT s.id,
                   row_number() OVER (ORDER BY s.created_at::timestamptz DESC,s.id DESC) AS rn
            FROM sales s
            WHERE s.status='Cotización' OR s.sale_number LIKE 'COT-%'
        )
        SELECT r.id FROM ranked r WHERE r.rn>30
          AND NOT EXISTS (SELECT 1 FROM sale_items x WHERE x.sale_id=r.id)
          AND NOT EXISTS (SELECT 1 FROM sale_payments x WHERE x.sale_id=r.id)
          AND NOT EXISTS (SELECT 1 FROM sale_payment_items x WHERE x.sale_id=r.id)
          AND NOT EXISTS (SELECT 1 FROM sale_packaging_items x WHERE x.sale_id=r.id)
          AND NOT EXISTS (SELECT 1 FROM sale_lot_movements x WHERE x.sale_id=r.id)
          AND NOT EXISTS (SELECT 1 FROM inventory_movements x
                          WHERE x.reference_type IN ('sale','sale_cancellation') AND x.reference_id=r.id)
    """)
    cur.execute("""
        CREATE TEMP TABLE cleanup_delete_sales ON COMMIT DROP AS
        WITH ranked AS (
            SELECT s.id,s.status,s.sale_number,
                   row_number() OVER (ORDER BY s.created_at::timestamptz DESC,s.id DESC) AS rn
            FROM sales s
            WHERE NOT (s.status='Cotización' OR s.sale_number LIKE 'COT-%')
        )
        SELECT r.id FROM ranked r
        JOIN sales s ON s.id=r.id
        WHERE r.rn>30 AND r.status<>'Pendiente' AND r.sale_number LIKE 'VTA-TEST-%'
          AND NOT EXISTS (SELECT 1 FROM sale_items x WHERE x.sale_id=r.id)
          AND NOT EXISTS (SELECT 1 FROM sale_payments x WHERE x.sale_id=r.id)
          AND NOT EXISTS (SELECT 1 FROM sale_payment_items x WHERE x.sale_id=r.id)
          AND NOT EXISTS (SELECT 1 FROM sale_packaging_items x WHERE x.sale_id=r.id)
          AND NOT EXISTS (SELECT 1 FROM sale_lot_movements x WHERE x.sale_id=r.id)
          AND NOT EXISTS (SELECT 1 FROM inventory_movements x
                          WHERE x.reference_type IN ('sale','sale_cancellation') AND x.reference_id=r.id)
    """)
    cur.execute("""
        CREATE TEMP TABLE cleanup_delete_suppliers ON COMMIT DROP AS
        SELECT s.id FROM suppliers s
        WHERE (s.name ~ '[0-9]{10,}$' OR s.name ILIKE '%test%'
               OR s.name ILIKE '%csrf%' OR s.name ILIKE '%normalizacion%')
          AND NOT EXISTS (SELECT 1 FROM purchase_orders x WHERE x.supplier_id=s.id)
          AND NOT EXISTS (SELECT 1 FROM purchase_invoices x WHERE x.supplier_id=s.id)
          AND NOT EXISTS (SELECT 1 FROM inventory_entries x WHERE x.supplier_id=s.id)
          AND NOT EXISTS (SELECT 1 FROM lots x WHERE x.supplier_id=s.id)
    """)
    cur.execute("""
        CREATE TEMP TABLE cleanup_delete_bank_transactions ON COMMIT DROP AS
        SELECT bt.id FROM bank_transactions bt
        WHERE bt.bank_account_id IN (SELECT id FROM cleanup_delete_accounts)
           OR (bt.reconciled_type='DEBT_PAYMENT' AND bt.reconciled_id IN
               (SELECT id FROM cleanup_delete_debt_payments))
    """)


def scalar(cur, sql, params=()):
    cur.execute(sql, params)
    return int(cur.fetchone()["n"])


def plan(cur):
    counts = {
        "sales": scalar(cur, "SELECT count(*) n FROM sales"),
        "quotes": scalar(cur, "SELECT count(*) n FROM sales WHERE status='Cotización' OR sale_number LIKE 'COT-%%'"),
        "purchase_orders": scalar(cur, "SELECT count(*) n FROM purchase_orders"),
        "bank_accounts": scalar(cur, "SELECT count(*) n FROM bank_accounts"),
        "products": scalar(cur, "SELECT count(*) n FROM products"),
        "suppliers": scalar(cur, "SELECT count(*) n FROM suppliers"),
        "bank_transactions": scalar(cur, "SELECT count(*) n FROM bank_transactions"),
        "bank_transaction_imports": scalar(cur, "SELECT count(*) n FROM bank_transaction_imports"),
        "debts": scalar(cur, "SELECT count(*) n FROM debts"),
        "debt_installments": scalar(cur, "SELECT count(*) n FROM debt_installments"),
        "debt_payments": scalar(cur, "SELECT count(*) n FROM debt_payments"),
        "inventory_entries": scalar(cur, "SELECT count(*) n FROM inventory_entries"),
        "inventory_movements": scalar(cur, "SELECT count(*) n FROM inventory_movements"),
        "lots": scalar(cur, "SELECT count(*) n FROM lots"),
        "production_orders": scalar(cur, "SELECT count(*) n FROM production_orders"),
        "product_recipes": scalar(cur, "SELECT count(*) n FROM product_recipes"),
    }
    remove = {
        "sales_without_financial_or_stock_links": scalar(cur, "SELECT count(*) n FROM cleanup_delete_sales"),
        "quotes_without_lineage": scalar(cur, "SELECT count(*) n FROM cleanup_delete_quotes"),
        "purchase_orders": 0,
        "bank_accounts": scalar(cur, "SELECT count(*) n FROM cleanup_delete_accounts"),
        "suppliers_marked_test_and_unreferenced": scalar(cur, "SELECT count(*) n FROM cleanup_delete_suppliers"),
        "debts_linked_to_removed_test_accounts": scalar(cur, "SELECT count(*) n FROM cleanup_delete_debts"),
        "debt_installments_cascade": scalar(cur, "SELECT count(*) n FROM cleanup_delete_installments"),
        "debt_payments": scalar(cur, "SELECT count(*) n FROM cleanup_delete_debt_payments"),
        "bank_transactions_and_audits": scalar(cur, "SELECT count(*) n FROM cleanup_delete_bank_transactions"),
        "bank_imports_cascade": scalar(cur, """SELECT count(*) n FROM bank_transaction_imports
            WHERE bank_account_id IN (SELECT id FROM cleanup_delete_accounts)"""),
        "supplier_contacts_cascade": scalar(cur, """SELECT count(*) n FROM supplier_contacts
            WHERE supplier_id IN (SELECT id FROM cleanup_delete_suppliers)"""),
        "debt_audit_cascade": scalar(cur, """SELECT count(*) n FROM debt_audit
            WHERE debt_id IN (SELECT id FROM cleanup_delete_debts)"""),
        "bank_audit_cascade": scalar(cur, """SELECT count(*) n FROM bank_reconciliation_audit a
            WHERE a.bank_transaction_id IN (SELECT id FROM cleanup_delete_bank_transactions)"""),
        "sale_payment_account_fk_set_null": scalar(cur, """SELECT count(*) n FROM sale_payment_items
            WHERE bank_account_id IN (SELECT id FROM cleanup_delete_accounts)"""),
        "purchase_invoice_account_fk_set_null": scalar(cur, """SELECT count(*) n FROM purchase_invoices
            WHERE bank_account_id IN (SELECT id FROM cleanup_delete_accounts)"""),
        "expense_account_fk_set_null": scalar(cur, """SELECT count(*) n FROM operational_expenses
            WHERE bank_account_id IN (SELECT id FROM cleanup_delete_accounts)"""),
        "expense_occurrence_account_fk_set_null": scalar(cur, """SELECT count(*) n FROM operational_expense_occurrences
            WHERE bank_account_id IN (SELECT id FROM cleanup_delete_accounts)"""),
        "debt_payments_owned_by_retained_debts_but_using_removed_account": scalar(cur, """SELECT count(*) n
            FROM debt_payments dp JOIN debt_installments di ON di.id=dp.debt_installment_id
            WHERE dp.bank_account_id IN (SELECT id FROM cleanup_delete_accounts)
              AND di.debt_id NOT IN (SELECT id FROM cleanup_delete_debts)"""),
    }
    return {"before": counts, "delete_plan": remove}


def lock_tables(cur):
    cur.execute("""LOCK TABLE bank_accounts,bank_transaction_imports,bank_transactions,
        bank_reconciliation_audit,debts,debt_audit,debt_installments,debt_payments,
        operational_expense_occurrences,operational_expenses,purchase_invoices,
        sale_items,sale_payments,sale_payment_items,sale_packaging_items,sale_lot_movements,
        sales,sales_payment_history,sales_status_history,collection_actions,
        suppliers,supplier_contacts,product_suppliers IN SHARE ROW EXCLUSIVE MODE""")


def assert_plan(p):
    r = p["delete_plan"]
    expected_quote_deletions = r["quotes_without_lineage"]
    if p["before"]["quotes"] - expected_quote_deletions != 30:
        raise RuntimeError("No todas las cotizaciones antiguas están libres de dependencias; ROLLBACK")
    if p["before"]["bank_accounts"] - r["bank_accounts"] != 10:
        raise RuntimeError("El conjunto de cuentas no deja exactamente 10; ROLLBACK")
    if r["debt_payments_owned_by_retained_debts_but_using_removed_account"]:
        raise RuntimeError("Hay pagos de deuda conservada en cuenta candidata; ROLLBACK")


def execute(cur):
    deleted = {}
    for label, sql in [
        ("debt_payments", "DELETE FROM debt_payments WHERE id IN (SELECT id FROM cleanup_delete_debt_payments)"),
        ("debts", "DELETE FROM debts WHERE id IN (SELECT id FROM cleanup_delete_debts)"),
        ("bank_transactions", "DELETE FROM bank_transactions WHERE id IN (SELECT id FROM cleanup_delete_bank_transactions)"),
        ("sales_test_without_dependencies", "DELETE FROM sales WHERE id IN (SELECT id FROM cleanup_delete_sales)"),
        ("quotes_without_lineage", "DELETE FROM sales WHERE id IN (SELECT id FROM cleanup_delete_quotes)"),
        ("suppliers_unreferenced_test", "DELETE FROM suppliers WHERE id IN (SELECT id FROM cleanup_delete_suppliers)"),
        ("bank_accounts", "DELETE FROM bank_accounts WHERE id IN (SELECT id FROM cleanup_delete_accounts)"),
    ]:
        cur.execute(sql)
        deleted[label] = cur.rowcount
    return deleted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--confirm")
    ap.add_argument("--backup", type=Path)
    args = ap.parse_args()
    if args.execute:
        if args.confirm != "LIMPIEZA_CONTROLADA":
            ap.error("--execute requiere --confirm LIMPIEZA_CONTROLADA")
        if not args.backup or not args.backup.is_file():
            ap.error("Se exige --backup apuntando al dump completo verificado")
        data = args.backup.read_bytes()
        if len(data) == 0 or BACKUP_MARKER not in data[-4096:]:
            ap.error("Backup vacío o sin marcador final de dump completo")
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout='10s'")
            cur.execute("SET LOCAL statement_timeout='5min'")
            if args.execute:
                lock_tables(cur)
            prepare(cur)
            p = plan(cur)
            assert_plan(p)
            print(json.dumps({"mode": "execute" if args.execute else "dry-run",
                              **p, "backup": str(args.backup) if args.backup else None},
                             indent=2, default=str))
            if args.execute:
                p["deleted"] = execute(cur)
                cur.execute("SELECT count(*) n FROM bank_accounts")
                final_accounts = int(cur.fetchone()["n"])
                cur.execute("SELECT count(*) n FROM sales WHERE status='Cotización' OR sale_number LIKE 'COT-%'")
                final_quotes = int(cur.fetchone()["n"])
                cur.execute("SELECT count(*) n FROM sales")
                final_sales = int(cur.fetchone()["n"])
                if final_accounts != 10 or final_quotes != 30:
                    raise RuntimeError(f"Validación transaccional falló: cuentas={final_accounts}, cotizaciones={final_quotes}")
                p["after_in_transaction"] = {"bank_accounts": final_accounts,
                                               "quotes": final_quotes,
                                               "sales_total": final_sales}
                conn.commit()
                print(json.dumps({"committed": True, "result": p["deleted"],
                                  "after": p["after_in_transaction"]}, indent=2))
            else:
                conn.rollback()
                print("DRY-RUN: ROLLBACK; no se modificaron datos")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
