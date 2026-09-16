"""
repositories/legacy_repo.py
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


def get_page_data(key: str) -> Any:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT json FROM page_data WHERE key = %s", (key,))
            row = cur.fetchone()
            if not row:
                return None
            return json.loads(row["json"])


def set_page_data(key: str, value: Any) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO page_data (key, json) VALUES (%s, %s) "
                "ON CONFLICT(key) DO UPDATE SET json = EXCLUDED.json",
                (key, json.dumps(value, ensure_ascii=False)),
            )
        conn.commit()


def list_sales_entries() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, sku, product_name, quantity, unit_price, total_price,
                       sale_date, delivery_date, payment_status, delivery_status,
                       payment_method, customer_name, seller_name, notes
                FROM sales_entries
                ORDER BY created_at::timestamp DESC, id DESC
                """
            )
            return [dict(row) for row in cur.fetchall()]


def insert_sales_entry(entry: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sales_entries (
                    sku, product_name, quantity, unit_price, total_price,
                    sale_date, delivery_date, payment_status, delivery_status,
                    payment_method, customer_name, seller_name, notes, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    entry["sku"],
                    entry["product_name"],
                    entry["quantity"],
                    entry["unit_price"],
                    entry["total_price"],
                    entry["sale_date"],
                    entry["delivery_date"],
                    entry["payment_status"],
                    entry["delivery_status"],
                    entry["payment_method"],
                    entry["customer_name"],
                    entry["seller_name"],
                    entry["notes"],
                    entry["created_at"],
                ),
            )
        conn.commit()

