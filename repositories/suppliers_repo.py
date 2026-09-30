"""
repositories/suppliers_repo.py
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
from core.utils import (
    VALID_PAYMENT_TERMS,
    DEFAULT_PAYMENT_TERMS,
    normalize_rut_str,
    validate_chilean_rut,
    format_chilean_rut,
)


def list_suppliers() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, description, website, rut, dv, razon_social, giro, direccion, comuna, ciudad, email, phone, tipo_compra, default_payment_terms, created_at
                FROM suppliers
                ORDER BY name
                """
            )
            return [dict(row) for row in cur.fetchall()]


def search_supplier_options(search: str = "", limit: int = 30) -> dict:
    """Small remote selector response; never serializes the full supplier catalog."""
    from core.pagination import PAGE_SIZE
    term=(search or "").strip()
    pattern=f"%{term}%"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT COUNT(*) AS total FROM suppliers
                WHERE (%s = '' OR name ILIKE %s OR razon_social ILIKE %s OR rut ILIKE %s)""",
                (term,pattern,pattern,pattern))
            total=cur.fetchone()['total']
            cur.execute("""SELECT id,name,razon_social,rut FROM suppliers
                WHERE (%s = '' OR name ILIKE %s OR razon_social ILIKE %s OR rut ILIKE %s)
                ORDER BY name,id LIMIT %s""",(term,pattern,pattern,pattern,min(PAGE_SIZE,max(1,int(limit)))))
            return {'items':[dict(r) for r in cur.fetchall()],'total':total}


def get_suppliers_paginated(
    page: int = 1,
    per_page: int = 25,
    search: str = ""
) -> dict:
    """
    Retorna la lista de proveedores paginada server-side con búsqueda.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            where_clauses = []
            params = []

            if search and search.strip():
                s_pat = f"%{search.strip()}%"
                where_clauses.append(
                    "(name ILIKE %s OR razon_social ILIKE %s OR rut ILIKE %s OR email ILIKE %s OR description ILIKE %s)"
                )
                params.extend([s_pat, s_pat, s_pat, s_pat, s_pat])

            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            # Conteo total
            count_sql = f"SELECT COUNT(*)::int as total FROM suppliers {where_sql}"
            cur.execute(count_sql, tuple(params))
            total = cur.fetchone()["total"]

            total_pages = max(1, (total + per_page - 1) // per_page)
            if page > total_pages and total > 0:
                page = total_pages
            offset = (page - 1) * per_page

            # Consulta paginada
            data_sql = f"""
                SELECT id, name, description, website, rut, dv, razon_social, giro, direccion, comuna, ciudad, email, phone, tipo_compra, default_payment_terms, created_at
                FROM suppliers
                {where_sql}
                ORDER BY name ASC
                LIMIT %s OFFSET %s
            """
            cur.execute(data_sql, tuple(params + [per_page, offset]))
            items = [dict(row) for row in cur.fetchall()]

            return {
                "items": items,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages
            }


def get_supplier(supplier_id: int) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, description, website, rut, dv, razon_social, giro, direccion, comuna, ciudad, email, phone, tipo_compra, default_payment_terms, created_at
                FROM suppliers
                WHERE id = %s
                """,
                (supplier_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_supplier_by_rut(rut: str, dv: str = None) -> dict:
    """Busca un proveedor por RUT normalizado (con o sin puntos, guiones y DV)."""
    if not rut:
        return None
    r_body, r_dv = normalize_rut_str(rut, dv)
    if not r_body:
        return None

    clean_target = f"{r_body}{r_dv.upper()}" if r_dv else r_body

    with get_connection() as conn:
        with conn.cursor() as cur:
            if r_dv:
                cur.execute(
                    """
                    SELECT id, name, description, website, rut, dv, razon_social, giro, direccion, comuna, ciudad, email, phone, tipo_compra, default_payment_terms, created_at
                    FROM suppliers
                    WHERE REPLACE(REPLACE(rut, '.', ''), '-', '') = %s
                       OR (REPLACE(REPLACE(rut, '.', ''), '-', '') || UPPER(COALESCE(dv, ''))) = %s
                       OR (REPLACE(REPLACE(rut, '.', ''), '-', '') = %s AND UPPER(COALESCE(dv, '')) = %s)
                    ORDER BY id ASC LIMIT 1
                    """,
                    (clean_target, clean_target, r_body, r_dv.upper()),
                )
            else:
                cur.execute(
                    """
                    SELECT id, name, description, website, rut, dv, razon_social, giro, direccion, comuna, ciudad, email, phone, tipo_compra, default_payment_terms, created_at
                    FROM suppliers
                    WHERE REPLACE(REPLACE(rut, '.', ''), '-', '') = %s
                       OR (REPLACE(REPLACE(rut, '.', ''), '-', '') || UPPER(COALESCE(dv, ''))) = %s
                    ORDER BY id ASC LIMIT 1
                    """,
                    (clean_target, clean_target),
                )
            row = cur.fetchone()
            return dict(row) if row else None


def insert_supplier(supplier: dict) -> int:
    terms = str(supplier.get("default_payment_terms") or DEFAULT_PAYMENT_TERMS).strip().upper()
    if terms not in VALID_PAYMENT_TERMS:
        terms = DEFAULT_PAYMENT_TERMS

    # Normalizar RUT y DV
    raw_rut = supplier.get("rut") or ""
    raw_dv = supplier.get("dv") or ""
    r_body, r_dv = normalize_rut_str(raw_rut, raw_dv)
    
    if r_body and r_dv:
        formatted_rut = format_chilean_rut(r_body, r_dv)
        final_dv = r_dv.upper()
    elif r_body:
        formatted_rut = r_body
        final_dv = (raw_dv or "").strip().upper() or None
    else:
        formatted_rut = None
        final_dv = None

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO suppliers (name, description, website, rut, dv, razon_social, giro, direccion, comuna, ciudad, email, phone, tipo_compra, default_payment_terms, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    supplier["name"],
                    supplier.get("description"),
                    supplier.get("website"),
                    formatted_rut,
                    final_dv,
                    supplier.get("razon_social") or supplier["name"],
                    supplier.get("giro"),
                    supplier.get("direccion"),
                    supplier.get("comuna"),
                    supplier.get("ciudad"),
                    supplier.get("email"),
                    supplier.get("phone"),
                    supplier.get("tipo_compra", "Del Giro"),
                    terms,
                    supplier.get("created_at", datetime.now(timezone.utc).isoformat(timespec='seconds')),
                ),
            )
            supplier_id = cur.fetchone()["id"]
        conn.commit()
        return supplier_id


def update_supplier(supplier_id: int, supplier: dict) -> None:
    raw_terms = supplier.get("default_payment_terms")
    if raw_terms is not None:
        terms = str(raw_terms).strip().upper()
        if terms not in VALID_PAYMENT_TERMS:
            terms = DEFAULT_PAYMENT_TERMS
    else:
        terms = None

    # Normalizar RUT y DV
    raw_rut = supplier.get("rut") or ""
    raw_dv = supplier.get("dv") or ""
    r_body, r_dv = normalize_rut_str(raw_rut, raw_dv)
    if r_body and r_dv:
        formatted_rut = format_chilean_rut(r_body, r_dv)
        final_dv = r_dv.upper()
    elif r_body:
        formatted_rut = r_body
        final_dv = (raw_dv or "").strip().upper() or None
    else:
        formatted_rut = supplier.get("rut")
        final_dv = supplier.get("dv")

    with get_connection() as conn:
        with conn.cursor() as cur:
            if terms is not None:
                cur.execute(
                    """
                    UPDATE suppliers
                    SET name = %s, description = %s, website = %s, rut = %s, dv = %s, razon_social = %s, giro = %s, direccion = %s, comuna = %s, ciudad = %s, email = %s, phone = %s, tipo_compra = %s, default_payment_terms = %s
                    WHERE id = %s
                    """,
                    (
                        supplier.get("name"),
                        supplier.get("description"),
                        supplier.get("website"),
                        formatted_rut,
                        final_dv,
                        supplier.get("razon_social"),
                        supplier.get("giro"),
                        supplier.get("direccion"),
                        supplier.get("comuna"),
                        supplier.get("ciudad"),
                        supplier.get("email"),
                        supplier.get("phone"),
                        supplier.get("tipo_compra"),
                        terms,
                        supplier_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    UPDATE suppliers
                    SET name = %s, description = %s, website = %s, rut = %s, dv = %s, razon_social = %s, giro = %s, direccion = %s, comuna = %s, ciudad = %s, email = %s, phone = %s, tipo_compra = %s
                    WHERE id = %s
                    """,
                    (
                        supplier.get("name"),
                        supplier.get("description"),
                        supplier.get("website"),
                        formatted_rut,
                        final_dv,
                        supplier.get("razon_social"),
                        supplier.get("giro"),
                        supplier.get("direccion"),
                        supplier.get("comuna"),
                        supplier.get("ciudad"),
                        supplier.get("email"),
                        supplier.get("phone"),
                        supplier.get("tipo_compra"),
                        supplier_id,
                    ),
                )
        conn.commit()


def delete_supplier(supplier_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM supplier_contacts WHERE supplier_id = %s", (supplier_id,))
            cur.execute("DELETE FROM suppliers WHERE id = %s", (supplier_id,))
        conn.commit()


def list_supplier_contacts(supplier_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, supplier_id, name, phone, email, position, created_at
                FROM supplier_contacts
                WHERE supplier_id = %s
                ORDER BY name
                """,
                (supplier_id,),
            )
            return [dict(row) for row in cur.fetchall()]


def get_supplier_contact(contact_id: int) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, supplier_id, name, phone, email, position, created_at
                FROM supplier_contacts
                WHERE id = %s
                """,
                (contact_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def insert_supplier_contact(contact: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO supplier_contacts (supplier_id, name, phone, email, position, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    contact["supplier_id"],
                    contact["name"],
                    contact.get("phone"),
                    contact.get("email"),
                    contact.get("position"),
                    contact.get("created_at", datetime.now(timezone.utc).isoformat(timespec='seconds')),
                ),
            )
        conn.commit()


def update_supplier_contact(contact_id: int, contact: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE supplier_contacts
                SET name = %s, phone = %s, email = %s, position = %s
                WHERE id = %s
                """,
                (
                    contact.get("name"),
                    contact.get("phone"),
                    contact.get("email"),
                    contact.get("position"),
                    contact_id,
                ),
            )
        conn.commit()


def delete_supplier_contact(contact_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM supplier_contacts WHERE id = %s", (contact_id,))
        conn.commit()
