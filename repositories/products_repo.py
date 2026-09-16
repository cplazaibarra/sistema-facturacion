"""
repositories/products_repo.py
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


def list_products() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, sku, name, description, photo_url, barcode, internal_code,
                       category, expiry_date, width_cm, height_cm, depth_cm, weight_kg, product_type, cost,
                       COALESCE(requires_lot, FALSE) as requires_lot,
                       subcategory_material, line_variety, format_capacity, associated_kg,
                       unit_of_measure, min_stock, COALESCE(status, 'Activo') as status,
                       notes, attachment_url, line, variety, bom_recipe, labeling
                FROM products
                WHERE is_deleted = FALSE OR is_deleted IS NULL
                ORDER BY id DESC
                """
            )
            return [dict(row) for row in cur.fetchall()]


def insert_product(product: dict) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            assoc_kg = product.get("associated_kg")
            if assoc_kg is None and product.get("weight_kg") is not None:
                assoc_kg = product.get("weight_kg")
            weight = product.get("weight_kg")
            if weight is None and assoc_kg is not None:
                weight = assoc_kg

            cur.execute(
                """
                INSERT INTO products (
                    sku, name, description, photo_url, barcode, internal_code,
                    category, expiry_date, width_cm, height_cm, depth_cm,
                    weight_kg, product_type, cost, requires_lot, created_at,
                    subcategory_material, line_variety, format_capacity, associated_kg,
                    unit_of_measure, min_stock, status, notes, attachment_url,
                    line, variety, bom_recipe, labeling
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    product["sku"],
                    product["name"],
                    product.get("description"),
                    product.get("photo_url"),
                    product.get("barcode"),
                    product.get("internal_code"),
                    product.get("category"),
                    product.get("expiry_date"),
                    product.get("width_cm"),
                    product.get("height_cm"),
                    product.get("depth_cm"),
                    weight,
                    product.get("product_type", "Final"),
                    product.get("cost", 0.0),
                    bool(product.get("requires_lot", False)),
                    product["created_at"],
                    product.get("subcategory_material"),
                    product.get("line_variety"),
                    product.get("format_capacity"),
                    assoc_kg,
                    product.get("unit_of_measure"),
                    product.get("min_stock", 0.0) or 0.0,
                    product.get("status", "Activo") or "Activo",
                    product.get("notes"),
                    product.get("attachment_url"),
                    product.get("line"),
                    product.get("variety"),
                    product.get("bom_recipe"),
                    product.get("labeling"),
                ),
            )
            inserted_id = cur.fetchone()["id"]
        conn.commit()
        return inserted_id


def get_product(product_id: int) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, sku, name, description, photo_url, barcode, internal_code,
                       category, expiry_date, width_cm, height_cm, depth_cm, weight_kg, product_type, cost,
                       COALESCE(requires_lot, FALSE) as requires_lot,
                       subcategory_material, line_variety, format_capacity, associated_kg,
                       unit_of_measure, min_stock, COALESCE(status, 'Activo') as status,
                       notes, attachment_url, line, variety, bom_recipe, labeling
                FROM products
                WHERE id = %s
                """,
                (product_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def update_product(product_id: int, product: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            assoc_kg = product.get("associated_kg")
            if assoc_kg is None and product.get("weight_kg") is not None:
                assoc_kg = product.get("weight_kg")
            weight = product.get("weight_kg")
            if weight is None and assoc_kg is not None:
                weight = assoc_kg

            cur.execute(
                """
                UPDATE products SET
                    sku = %s, name = %s, description = %s, photo_url = %s,
                    barcode = %s, internal_code = %s, category = %s, expiry_date = %s,
                    width_cm = %s, height_cm = %s, depth_cm = %s, weight_kg = %s,
                    product_type = %s, cost = %s, requires_lot = %s,
                    subcategory_material = %s, line_variety = %s, format_capacity = %s,
                    associated_kg = %s, unit_of_measure = %s, min_stock = %s,
                    status = %s, notes = %s, attachment_url = %s,
                    line = %s, variety = %s, bom_recipe = %s, labeling = %s
                WHERE id = %s
                """,
                (
                    product.get("sku"),
                    product.get("name"),
                    product.get("description"),
                    product.get("photo_url"),
                    product.get("barcode"),
                    product.get("internal_code"),
                    product.get("category"),
                    product.get("expiry_date"),
                    product.get("width_cm"),
                    product.get("height_cm"),
                    product.get("depth_cm"),
                    weight,
                    product.get("product_type", "Final"),
                    product.get("cost", 0.0),
                    bool(product.get("requires_lot", False)),
                    product.get("subcategory_material"),
                    product.get("line_variety"),
                    product.get("format_capacity"),
                    assoc_kg,
                    product.get("unit_of_measure"),
                    product.get("min_stock", 0.0) or 0.0,
                    product.get("status", "Activo") or "Activo",
                    product.get("notes"),
                    product.get("attachment_url"),
                    product.get("line"),
                    product.get("variety"),
                    product.get("bom_recipe"),
                    product.get("labeling"),
                    product_id,
                ),
            )
        conn.commit()


def delete_product(product_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE products SET is_deleted = TRUE WHERE id = %s", (product_id,))
        conn.commit()


def list_product_suppliers(product_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ps.id, ps.product_id, ps.supplier_id, ps.created_at,
                       s.name as supplier_name, s.website
                FROM product_suppliers ps
                JOIN suppliers s ON ps.supplier_id = s.id
                WHERE ps.product_id = %s
                ORDER BY s.name
                """,
                (product_id,),
            )
            return [dict(row) for row in cur.fetchall()]


def list_products_by_supplier(supplier_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.id, p.sku, p.name
                FROM products p
                JOIN product_suppliers ps ON ps.product_id = p.id
                WHERE ps.supplier_id = %s
                ORDER BY p.name
                """,
                (supplier_id,),
            )
            return [dict(row) for row in cur.fetchall()]


def add_product_supplier(product_id: int, supplier_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO product_suppliers (product_id, supplier_id, created_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (product_id, supplier_id) DO NOTHING
                """,
                (
                    product_id,
                    supplier_id,
                    datetime.now(timezone.utc).isoformat(timespec='seconds'),
                ),
            )
        conn.commit()


def remove_product_supplier(product_id: int, supplier_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM product_suppliers
                WHERE product_id = %s AND supplier_id = %s
                """,
                (product_id, supplier_id),
            )
        conn.commit()


def rename_category(old_category: str, new_category: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE products
                SET category = %s
                WHERE category = %s
                """,
                (new_category, old_category),
            )
        conn.commit()


def delete_category(category: str) -> None:
    normalized = (category or "").strip().lower()
    prefixed = f"categoria-{normalized}" if normalized else ""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE products
                SET category = NULL
                WHERE lower(category) = %s OR lower(category) = %s
                """,
                (normalized, prefixed),
                )
        conn.commit()


def get_product_calculated_cost(product_id: int) -> float | None:
    """Calcula el costo del producto según:
       1. Promedio ponderado de las compras de los últimos 30 días.
       2. Si no hay compras los últimos 30 días, el valor unitario de la última compra registrada.
       3. Si no hay registros de compra en absoluto, retorna None.
    """
    from datetime import datetime, timedelta
    limit_date = (datetime.today() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Intentar primero en los últimos 30 días
            cur.execute(
                """
                SELECT SUM(items.quantity) as total_qty, SUM(items.total) as total_spent
                FROM inventory_entry_items items
                JOIN inventory_entries entries ON items.inventory_entry_id = entries.id
                WHERE items.product_id = %s AND entries.entry_date >= %s
                """,
                (product_id, limit_date)
            )
            row = cur.fetchone()
            if row and row["total_qty"] and row["total_qty"] > 0:
                return row["total_spent"] / row["total_qty"]
            
            # Si no hay compras en los últimos 30 días, tomar el valor unitario de la última compra registrada
            cur.execute(
                """
                SELECT items.unit_price
                FROM inventory_entry_items items
                JOIN inventory_entries entries ON items.inventory_entry_id = entries.id
                WHERE items.product_id = %s
                ORDER BY entries.entry_date DESC, entries.id DESC
                LIMIT 1
                """,
                (product_id,)
            )
            last_purchase = cur.fetchone()
            if last_purchase:
                return last_purchase["unit_price"]
                
    return None

