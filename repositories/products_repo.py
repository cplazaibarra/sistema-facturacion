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


def get_products_paginated(
    page: int = 1,
    per_page: int = 30,
    search: str = None,
    category: str = None,
    product_type: str = None,
    conn=None
) -> dict:
    """
    Retorna productos paginados server-side con filtros opcionales de búsqueda, categoría y tipo.
    - page: int >= 1 (default 1)
    - per_page: fixed server-controlled PAGE_SIZE
    - search: búsqueda por SKU, Nombre, Código Interno, Código de Barra, Variedad, Línea, etc.
    - category: filtro por categoría
    - product_type: filtro por tipo de producto
    """
    # 1. Sanitizar y validar parámetros
    try:
        page = int(page)
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    from core.pagination import PAGE_SIZE
    per_page = PAGE_SIZE

    offset = (page - 1) * per_page

    def _execute(cur):
        where_clauses = ["(is_deleted = FALSE OR is_deleted IS NULL)"]
        params = []

        if category and category.strip():
            where_clauses.append("LOWER(category) = LOWER(%s)")
            params.append(category.strip())

        if product_type and product_type.strip():
            where_clauses.append("LOWER(product_type) = LOWER(%s)")
            params.append(product_type.strip())

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            where_clauses.append(
                """(
                    LOWER(sku) LIKE %s OR 
                    LOWER(name) LIKE %s OR 
                    LOWER(COALESCE(category, '')) LIKE %s OR 
                    LOWER(COALESCE(product_type, '')) LIKE %s OR 
                    LOWER(COALESCE(line, '')) LIKE %s OR 
                    LOWER(COALESCE(variety, '')) LIKE %s OR 
                    LOWER(COALESCE(line_variety, '')) LIKE %s OR 
                    LOWER(COALESCE(format_capacity, '')) LIKE %s OR 
                    LOWER(COALESCE(barcode, '')) LIKE %s OR 
                    LOWER(COALESCE(internal_code, '')) LIKE %s OR
                    LOWER(COALESCE(subcategory_material, '')) LIKE %s
                )"""
            )
            params.extend([term] * 11)

        where_sql = "WHERE " + " AND ".join(where_clauses)

        # Contar total de registros coincidentes
        cur.execute(f"SELECT COUNT(*) as total FROM products {where_sql}", params)
        total_row = cur.fetchone()
        total_count = int(total_row["total"] if total_row else 0)

        total_pages = max(1, (total_count + per_page - 1) // per_page)
        nonlocal page
        if page > total_pages and total_pages > 0:
            page = total_pages
            actual_offset = (page - 1) * per_page
        else:
            actual_offset = offset

        # Consulta paginada
        select_sql = f"""
            SELECT id, sku, name, description, photo_url, barcode, internal_code,
                   category, expiry_date, width_cm, height_cm, depth_cm, weight_kg, product_type, cost,
                   COALESCE(requires_lot, FALSE) as requires_lot,
                   subcategory_material, line_variety, format_capacity, associated_kg,
                   unit_of_measure, min_stock, COALESCE(status, 'Activo') as status,
                   notes, attachment_url, line, variety, bom_recipe, labeling
            FROM products
            {where_sql}
            ORDER BY id DESC
            LIMIT %s OFFSET %s
        """
        data_params = list(params) + [per_page, actual_offset]
        cur.execute(select_sql, data_params)
        rows = cur.fetchall()

        return {
            "items": [dict(r) for r in rows],
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "start": actual_offset + 1 if total_count else 0,
            "end": min(actual_offset + per_page, total_count),
        }

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


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


def create_product(
    sku: str,
    name: str,
    category: str = "General",
    product_type: str = "Final",
    cost: float = 0.0,
    requires_lot: bool = False,
    unit_of_measure: str = "UN",
    min_stock: float = 0.0,
    status: str = "Activo",
    **kwargs
) -> int:
    """Helper para creación programática de productos."""
    product_dict = {
        "sku": sku,
        "name": name,
        "category": category,
        "product_type": product_type,
        "cost": cost,
        "requires_lot": requires_lot,
        "unit_of_measure": unit_of_measure,
        "min_stock": min_stock,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }
    product_dict.update(kwargs)
    return insert_product(product_dict)


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
                return float(last_purchase["unit_price"])
                
    return None


def get_product_by_sku(sku: str) -> dict | None:
    """Busca un producto por su SKU exacto."""
    clean_sku = (sku or "").strip()
    if not clean_sku:
        return None
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, sku, name, description, photo_url, barcode, internal_code,
                       category, expiry_date, width_cm, height_cm, depth_cm, weight_kg, product_type, cost,
                       COALESCE(requires_lot, FALSE) as requires_lot,
                       subcategory_material, line_variety, format_capacity, associated_kg,
                       unit_of_measure, min_stock, COALESCE(status, 'Activo') as status
                FROM products
                WHERE sku = %s AND (is_deleted = FALSE OR is_deleted IS NULL)
                ORDER BY id DESC
                LIMIT 1;
                """,
                (clean_sku,)
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_products_batch_calculated_cost(product_ids: list[int], conn=None) -> dict[int, float]:
    """
    Calcula en BATCH el costo de múltiples productos en máximo 2 consultas SQL (0 N+1 queries):
    1. Promedio ponderado de compras en los últimos 30 días.
    2. Si no hay compras en 30 días, el valor unitario de la última compra registrada.
    """
    if not product_ids:
        return {}

    from datetime import datetime, timedelta
    limit_date = (datetime.today() - timedelta(days=30)).strftime('%Y-%m-%d')
    pids_tuple = list(product_ids)

    def _execute(cur):
        # 1. Compras últimos 30 días
        cur.execute(
            """
            SELECT items.product_id, SUM(items.total) / NULLIF(SUM(items.quantity), 0) as avg_30d
            FROM inventory_entry_items items
            JOIN inventory_entries entries ON items.inventory_entry_id = entries.id
            WHERE items.product_id = ANY(%s) AND entries.entry_date >= %s
            GROUP BY items.product_id
            HAVING SUM(items.quantity) > 0
            """,
            (pids_tuple, limit_date)
        )
        cost_map = {}
        for r in cur.fetchall():
            if r["avg_30d"] is not None:
                cost_map[r["product_id"]] = float(r["avg_30d"])

        # 2. Para los productos restantes, última compra registrada
        remaining_pids = [pid for pid in pids_tuple if pid not in cost_map]
        if remaining_pids:
            cur.execute(
                """
                SELECT DISTINCT ON (items.product_id) items.product_id, items.unit_price
                FROM inventory_entry_items items
                JOIN inventory_entries entries ON items.inventory_entry_id = entries.id
                WHERE items.product_id = ANY(%s)
                ORDER BY items.product_id, entries.entry_date DESC, entries.id DESC
                """,
                (remaining_pids,)
            )
            for r in cur.fetchall():
                if r["unit_price"] is not None:
                    cost_map[r["product_id"]] = float(r["unit_price"])

        return cost_map

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


def get_price_list_products_paginated(
    page: int = 1,
    per_page: int = 25,
    search: str = None,
    conn=None
) -> dict:
    """
    Retorna productos paginados server-side para la lista de precios (excluyendo Insumos).
    """
    try:
        page = int(page)
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = int(per_page)
        if per_page not in (25, 50, 100):
            per_page = 25
    except (ValueError, TypeError):
        per_page = 25

    offset = (page - 1) * per_page

    def _execute(cur):
        where_clauses = [
            "(is_deleted = FALSE OR is_deleted IS NULL)",
            "COALESCE(product_type, 'Final') != 'Insumo'"
        ]
        params = []

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            where_clauses.append(
                """(
                    LOWER(sku) LIKE %s OR 
                    LOWER(name) LIKE %s OR 
                    LOWER(COALESCE(category, '')) LIKE %s OR
                    LOWER(COALESCE(internal_code, '')) LIKE %s
                )"""
            )
            params.extend([term] * 4)

        where_sql = "WHERE " + " AND ".join(where_clauses)

        # 1. Total de productos
        cur.execute(f"SELECT COUNT(*) as total FROM products {where_sql}", params)
        total_row = cur.fetchone()
        total_count = int(total_row["total"] if total_row else 0)

        total_pages = max(1, (total_count + per_page - 1) // per_page)
        nonlocal page
        if page > total_pages and total_pages > 0:
            page = total_pages
            actual_offset = (page - 1) * per_page
        else:
            actual_offset = offset

        # 2. Productos paginados de la página activa
        cur.execute(
            f"""
            SELECT id, sku, name, cost, category, product_type
            FROM products
            {where_sql}
            ORDER BY id DESC
            LIMIT %s OFFSET %s
            """,
            list(params) + [per_page, actual_offset]
        )
        products = [dict(r) for r in cur.fetchall()]

        return {
            "items": products,
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        }

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


def list_all_products_for_export(search: str = None, category: str = None, product_type: str = None, conn=None) -> list[dict]:
    """
    Retorna el catálogo completo de productos (sin paginación) para exportación masiva en Excel,
    soportando filtros opcionales de búsqueda, categoría y tipo.
    """
    def _execute(cur):
        where_clauses = ["(is_deleted = FALSE OR is_deleted IS NULL)"]
        params = []

        if category and category.strip():
            where_clauses.append("category = %s")
            params.append(category.strip())

        if product_type and product_type.strip():
            where_clauses.append("product_type = %s")
            params.append(product_type.strip())

        if search and search.strip():
            s_pat = f"%{search.strip()}%"
            where_clauses.append(
                """(
                    sku ILIKE %s OR name ILIKE %s OR internal_code ILIKE %s 
                    OR barcode ILIKE %s OR category ILIKE %s OR line ILIKE %s 
                    OR variety ILIKE %s OR bom_recipe ILIKE %s
                )"""
            )
            params.extend([s_pat, s_pat, s_pat, s_pat, s_pat, s_pat, s_pat, s_pat])

        where_sql = "WHERE " + " AND ".join(where_clauses)

        cur.execute(
            f"""
            SELECT id, sku, name, description, photo_url, barcode, internal_code,
                   category, expiry_date, width_cm, height_cm, depth_cm, weight_kg, product_type, cost,
                   COALESCE(requires_lot, FALSE) as requires_lot,
                   subcategory_material, line_variety, format_capacity, associated_kg,
                   unit_of_measure, min_stock, COALESCE(status, 'Activo') as status,
                   notes, attachment_url, line, variety, bom_recipe, labeling
            FROM products
            {where_sql}
            ORDER BY id ASC
            """,
            params
        )
        return [dict(r) for r in cur.fetchall()]

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


def get_products_lookup_maps(conn=None) -> tuple[dict, dict]:
    """
    Retorna dos diccionarios para búsqueda rápida de productos activos:
    - by_sku: dict[sku_lower -> product_dict]
    - by_id: dict[id_int -> product_dict]
    """
    def _execute(cur):
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
            """
        )
        by_sku = {}
        by_id = {}
        for r in cur.fetchall():
            d = dict(r)
            by_id[d["id"]] = d
            sku_clean = (d.get("sku") or "").strip().lower()
            if sku_clean:
                by_sku[sku_clean] = d
        return by_sku, by_id

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


