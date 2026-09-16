"""
repositories/sales_repo.py
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


def list_sales(filters: dict = None) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT s.id, s.sale_number, s.customer_name, s.customer_email, s.customer_initials,
                       s.sale_date, s.sale_time, s.products_json, s.total_amount, s.status,
                       s.seller_name, s.seller_initials, s.payment_method, s.payment_status,
                       s.delivery_status, s.notes, s.quotation_status, s.win_probability, s.created_at,
                       sp.invoice_due_date, sp.payment_date, sp.payment_proof_file, sp.invoice_file, sp.invoice_number
                FROM sales s
                LEFT JOIN sale_payments sp ON sp.sale_id = s.id
                WHERE 1=1
            """
            params = []
            
            if filters:
                if filters.get('status'):
                    query += " AND s.status = %s"
                    params.append(filters['status'])
                if filters.get('exclude_status'):
                    query += " AND s.status != %s"
                    params.append(filters['exclude_status'])
                if filters.get('prefix'):
                    query += " AND s.sale_number LIKE %s"
                    params.append(f"{filters['prefix']}%")
                if filters.get('customer_name'):
                    query += " AND s.customer_name ILIKE %s"
                    params.append(f"%{filters['customer_name']}%")
                if filters.get('date_from'):
                    query += " AND s.sale_date >= %s"
                    params.append(filters['date_from'])
                if filters.get('date_to'):
                    query += " AND s.sale_date <= %s"
                    params.append(filters['date_to'])
            
            query += " ORDER BY (COALESCE(NULLIF(s.sale_date, ''), '1970-01-01') || ' ' || COALESCE(NULLIF(s.sale_time, ''), '00:00:00'))::timestamp DESC, s.id DESC"
            
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            sales = []
            for row in rows:
                sale = dict(row)
                sale['products'] = json.loads(sale['products_json'])
                del sale['products_json']
                sales.append(sale)
            return sales


def count_sales(filters: dict = None) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            query = "SELECT COUNT(*) as count FROM sales WHERE 1=1"
            params = []
            if filters:
                if filters.get('status'):
                    query += " AND status = %s"
                    params.append(filters['status'])
                if filters.get('customer_name'):
                    query += " AND customer_name ILIKE %s"
                    params.append(f"%{filters['customer_name']}%")
                if filters.get('date_from'):
                    query += " AND sale_date >= %s"
                    params.append(filters['date_from'])
                if filters.get('date_to'):
                    query += " AND sale_date <= %s"
                    params.append(filters['date_to'])
            cur.execute(query, tuple(params))
            return cur.fetchone()["count"]


def list_sales_page(limit: int, offset: int, filters: dict = None) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT id, sale_number, customer_name, customer_email, customer_initials,
                       sale_date, sale_time, products_json, total_amount, status,
                       seller_name, seller_initials, payment_method, payment_status,
                       delivery_status, notes, created_at
                FROM sales
                WHERE 1=1
            """
            params = []
            if filters:
                if filters.get('status'):
                    query += " AND status = %s"
                    params.append(filters['status'])
                if filters.get('customer_name'):
                    query += " AND customer_name ILIKE %s"
                    params.append(f"%{filters['customer_name']}%")
                if filters.get('date_from'):
                    query += " AND sale_date >= %s"
                    params.append(filters['date_from'])
                if filters.get('date_to'):
                    query += " AND sale_date <= %s"
                    params.append(filters['date_to'])
            query += " ORDER BY (COALESCE(NULLIF(sale_date, ''), '1970-01-01') || ' ' || COALESCE(NULLIF(sale_time, ''), '00:00:00'))::timestamp DESC, id DESC"
            query += " LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            sales = []
            for row in rows:
                sale = dict(row)
                sale['products'] = json.loads(sale['products_json'])
                del sale['products_json']
                sales.append(sale)
            return sales


def list_sales_page_light(limit: int, offset: int, filters: dict = None) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT id, sale_number, customer_name, customer_email, customer_initials,
                       sale_date, sale_time, total_amount, status,
                       seller_name, seller_initials, payment_method, payment_status,
                       delivery_status, notes, created_at
                FROM sales
                WHERE 1=1
            """
            params = []
            if filters:
                if filters.get('status'):
                    query += " AND status = %s"
                    params.append(filters['status'])
                if filters.get('customer_name'):
                    query += " AND customer_name ILIKE %s"
                    params.append(f"%{filters['customer_name']}%")
                if filters.get('date_from'):
                    query += " AND sale_date >= %s"
                    params.append(filters['date_from'])
                if filters.get('date_to'):
                    query += " AND sale_date <= %s"
                    params.append(filters['date_to'])
            query += " ORDER BY (COALESCE(NULLIF(sale_date, ''), '1970-01-01') || ' ' || COALESCE(NULLIF(sale_time, ''), '00:00:00'))::timestamp DESC, id DESC"
            query += " LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return [dict(row) for row in rows]


def get_sale_payments_for_sales(sale_ids: list[int]) -> dict[int, dict]:
    if not sale_ids:
        return {}
    placeholders = ",".join(["%s"] * len(sale_ids))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT sale_id, invoice_number, invoice_amount, invoice_due_date, invoice_file, payment_proof_file, payment_amount, payment_date,
                       seller_uploaded_at, payment_uploaded_at, accounting_approved, accounting_approved_by,
                       accounting_approved_at, accounting_comment, status, created_at, updated_at
                FROM sale_payments
                WHERE sale_id IN ({placeholders})
                """,
                tuple(sale_ids),
            )
            rows = cur.fetchall()
            return {row["sale_id"]: dict(row) for row in rows}


def get_sale(sale_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, sale_number, customer_name, customer_email, customer_initials,
                       sale_date, sale_time, products_json, total_amount, status,
                       seller_name, seller_initials, payment_method, payment_status,
                       delivery_status, notes, quotation_status, win_probability, created_at
                FROM sales
                WHERE id = %s
                """,
                (sale_id,),
            )
            row = cur.fetchone()
            if row:
                sale = dict(row)
                sale['products'] = json.loads(sale['products_json'])
                del sale['products_json']
                return sale
            return None


def insert_sale(sale: dict, conn=None) -> int:
    def _execute(cursor):
        cursor.execute(
            """
            INSERT INTO sales (
                sale_number, customer_name, customer_email, customer_initials,
                sale_date, sale_time, products_json, total_amount, status,
                seller_name, seller_initials, payment_method, payment_status,
                delivery_status, notes, quotation_status, win_probability, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                sale["sale_number"],
                sale["customer_name"],
                sale.get("customer_email", ""),
                sale.get("customer_initials", ""),
                sale["sale_date"],
                sale["sale_time"],
                json.dumps(sale["products"], ensure_ascii=False),
                sale["total_amount"],
                sale["status"],
                sale["seller_name"],
                sale.get("seller_initials", ""),
                sale.get("payment_method", ""),
                sale.get("payment_status", "Pendiente"),
                sale.get("delivery_status", "Pendiente"),
                sale.get("notes", ""),
                sale.get("quotation_status", "Activa"),
                sale.get("win_probability", 50),
                sale["created_at"],
            ),
        )
        return cursor.fetchone()["id"]

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                ins_id = _execute(cur)
            c.commit()
            return ins_id


def update_sale(sale_id: int, sale: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sales SET
                    customer_name = %s, customer_email = %s, customer_initials = %s,
                    sale_date = %s, sale_time = %s, products_json = %s, total_amount = %s,
                    status = %s, seller_name = %s, seller_initials = %s,
                    payment_method = %s, payment_status = %s, delivery_status = %s, notes = %s,
                    quotation_status = COALESCE(%s, quotation_status),
                    win_probability = COALESCE(%s, win_probability)
                WHERE id = %s
                """,
                (
                    sale.get("customer_name"),
                    sale.get("customer_email", ""),
                    sale.get("customer_initials", ""),
                    sale.get("sale_date"),
                    sale.get("sale_time"),
                    json.dumps(sale.get("products", []), ensure_ascii=False),
                    sale.get("total_amount"),
                    sale.get("status"),
                    sale.get("seller_name"),
                    sale.get("seller_initials", ""),
                    sale.get("payment_method", ""),
                    sale.get("payment_status", ""),
                    sale.get("delivery_status", ""),
                    sale.get("notes", ""),
                    sale.get("quotation_status"),
                    sale.get("win_probability"),
                    sale_id,
                ),
            )
        conn.commit()


def update_quotation_status(sale_id: int, status: str, probability: int = None) -> None:
    """Actualiza el estado (Activa, Ganada, Perdida) y la probabilidad de una cotización."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if probability is not None:
                cur.execute(
                    "UPDATE sales SET quotation_status = %s, win_probability = %s WHERE id = %s",
                    (status, probability, sale_id)
                )
            else:
                cur.execute(
                    "UPDATE sales SET quotation_status = %s WHERE id = %s",
                    (status, sale_id)
                )
        conn.commit()


def delete_sale(sale_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sales WHERE id = %s", (sale_id,))
        conn.commit()


def get_next_sale_number(prefix: str = "VTA", conn=None) -> str:
    """Genera el siguiente número correlativo único para una venta o cotización (ej: VTA-00001, COT-00001)"""
    def _execute(cursor):
        cursor.execute("SELECT nextval('sales_number_seq') as val")
        val = cursor.fetchone()["val"]
        return f"{prefix}-{val:05d}"

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                val_str = _execute(cur)
            c.commit()
            return val_str

