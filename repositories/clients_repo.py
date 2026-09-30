"""
repositories/clients_repo.py
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
from core.utils import normalize_rut_str


def list_clients() -> list:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.*
                FROM clients c
                ORDER BY c.razon_social ASC
            """)
            return cur.fetchall()


def get_client_by_id(client_id: int) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM clients WHERE id = %s", (client_id,))
            return cur.fetchone()


def insert_client(data: dict) -> int:
    """Inserta un nuevo cliente o actualiza el existente si el RUT ya está registrado (evita duplicados)."""
    rut_raw = data.get("rut", "").strip()
    dv_raw = data.get("dv", "").strip()
    r_body, r_dv = normalize_rut_str(rut_raw, dv_raw)

    if r_body:
        existing = get_client_by_rut(r_body, r_dv)
        if existing:
            update_client(existing["id"], data)
            return existing["id"]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO clients (
                    rut, dv, razon_social, tipo_compra, direccion, comuna, ciudad,
                    giro, contacto, rut_solicita, dv_solicita, email, phone, category_id,
                    delivery_address
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    r_body or rut_raw,
                    r_dv or dv_raw,
                    data.get("razon_social", "").strip(),
                    data.get("tipo_compra", "Del Giro").strip(),
                    data.get("direccion", "").strip(),
                    data.get("comuna", "").strip(),
                    data.get("ciudad", "").strip(),
                    data.get("giro", "").strip(),
                    data.get("contacto", "").strip(),
                    data.get("rut_solicita", "").strip(),
                    data.get("dv_solicita", "").strip(),
                    data.get("email", "").strip(),
                    data.get("phone", "").strip(),
                    str(data["category_id"]).strip() if data.get("category_id") else None,
                    data.get("delivery_address", "").strip(),
                ),
            )
            client_id = cur.fetchone()["id"]
        conn.commit()
        return client_id


def update_client(client_id: int, data: dict) -> None:
    rut_raw = data.get("rut", "").strip()
    dv_raw = data.get("dv", "").strip()
    r_body, r_dv = normalize_rut_str(rut_raw, dv_raw)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE clients SET
                    rut = %s, dv = %s, razon_social = %s, tipo_compra = %s,
                    direccion = %s, comuna = %s, ciudad = %s, giro = %s,
                    contacto = %s, rut_solicita = %s, dv_solicita = %s,
                    email = %s, phone = %s, category_id = %s, delivery_address = %s
                WHERE id = %s
                """,
                (
                    r_body or rut_raw,
                    r_dv or dv_raw,
                    data.get("razon_social", "").strip(),
                    data.get("tipo_compra", "Del Giro").strip(),
                    data.get("direccion", "").strip(),
                    data.get("comuna", "").strip(),
                    data.get("ciudad", "").strip(),
                    data.get("giro", "").strip(),
                    data.get("contacto", "").strip(),
                    data.get("rut_solicita", "").strip(),
                    data.get("dv_solicita", "").strip(),
                    data.get("email", "").strip(),
                    data.get("phone", "").strip(),
                    str(data["category_id"]).strip() if data.get("category_id") else None,
                    data.get("delivery_address", "").strip(),
                    client_id,
                ),
            )
        conn.commit()


def delete_client(client_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM clients WHERE id = %s", (client_id,))
        conn.commit()


def get_client_by_rut(rut: str, dv: str = None) -> dict:
    """Busca un cliente por RUT normalizado (con o sin puntos, guiones y DV)."""
    if not rut:
        return None
    r_body, r_dv = normalize_rut_str(rut, dv)
    if not r_body:
        return None
    with get_connection() as conn:
        with conn.cursor() as cur:
            if r_dv:
                cur.execute("""
                    SELECT * FROM clients 
                    WHERE (REPLACE(REPLACE(rut, '.', ''), '-', '') = %s AND (UPPER(COALESCE(dv, '')) = %s OR COALESCE(dv, '') = ''))
                       OR (REPLACE(REPLACE(rut, '.', ''), '-', '') || UPPER(COALESCE(dv, ''))) = (%s || %s)
                       OR REPLACE(REPLACE(rut, '.', ''), '-', '') = %s
                    ORDER BY id ASC LIMIT 1
                """, (r_body, r_dv, r_body, r_dv, r_body))
            else:
                cur.execute("""
                    SELECT * FROM clients 
                    WHERE REPLACE(REPLACE(rut, '.', ''), '-', '') = %s
                       OR (REPLACE(REPLACE(rut, '.', ''), '-', '') || UPPER(COALESCE(dv, ''))) = %s
                    ORDER BY id ASC LIMIT 1
                """, (r_body, r_body))
            row = cur.fetchone()
            return dict(row) if row else None


def search_clients(query: str, limit: int = 10) -> list[dict]:
    """Busca clientes por razón social / nombre, contacto, email o RUT."""
    if not query or not query.strip():
        return []
    q = query.strip()
    pattern = f"%{q}%"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, rut, dv, razon_social, tipo_compra, direccion, comuna, ciudad,
                       giro, contacto, rut_solicita, dv_solicita, email, phone, category_id,
                       delivery_address
                FROM clients
                WHERE razon_social ILIKE %s
                   OR contacto ILIKE %s
                   OR email ILIKE %s
                   OR REPLACE(REPLACE(rut, '.', ''), '-', '') ILIKE %s
                ORDER BY
                    CASE
                        WHEN razon_social ILIKE %s THEN 1
                        WHEN razon_social ILIKE %s THEN 2
                        ELSE 3
                    END,
                    razon_social ASC
                LIMIT %s
            """, (pattern, pattern, pattern, pattern, f"{q}", f"{q}%", limit))
            return [dict(r) for r in cur.fetchall()]


def upsert_client_by_rut(data: dict) -> int:
    """Inserta o actualiza un cliente asegurando unicidad estricta por RUT."""
    rut_raw = data.get("rut", "").strip()
    dv_raw = data.get("dv", "").strip()
    if not rut_raw:
        return None
    r_body, r_dv = normalize_rut_str(rut_raw, dv_raw)
    existing = get_client_by_rut(r_body, r_dv)
    
    razon_social = data.get("razon_social", "").strip()
    email = data.get("email", "").strip()
    category_id = str(data["category_id"]).strip() if data.get("category_id") else None

    if existing:
        client_id = existing["id"]
        update_data = {
            "rut": r_body,
            "dv": r_dv or existing.get("dv", ""),
            "razon_social": razon_social or existing.get("razon_social", ""),
            "tipo_compra": data.get("tipo_compra") or existing.get("tipo_compra") or "Del Giro",
            "direccion": data.get("direccion") or existing.get("direccion") or "",
            "comuna": data.get("comuna") or existing.get("comuna") or "",
            "ciudad": data.get("ciudad") or existing.get("ciudad") or "",
            "giro": data.get("giro") or existing.get("giro") or "",
            "contacto": data.get("contacto") or existing.get("contacto") or "",
            "rut_solicita": data.get("rut_solicita") or existing.get("rut_solicita") or "",
            "dv_solicita": data.get("dv_solicita") or existing.get("dv_solicita") or "",
            "email": email or existing.get("email", ""),
            "phone": data.get("phone") or existing.get("phone") or "",
            "category_id": category_id or existing.get("category_id"),
            "delivery_address": data.get("delivery_address") or existing.get("delivery_address") or "",
        }
        update_client(client_id, update_data)
        return client_id
    else:
        new_client = {
            "rut": r_body,
            "dv": r_dv,
            "razon_social": razon_social,
            "tipo_compra": data.get("tipo_compra", "Del Giro"),
            "direccion": data.get("direccion", ""),
            "comuna": data.get("comuna", ""),
            "ciudad": data.get("ciudad", ""),
            "giro": data.get("giro", ""),
            "contacto": data.get("contacto", ""),
            "rut_solicita": data.get("rut_solicita", ""),
            "dv_solicita": data.get("dv_solicita", ""),
            "email": email,
            "phone": data.get("phone", ""),
            "category_id": category_id,
            "delivery_address": data.get("delivery_address", ""),
        }
        return insert_client(new_client)
