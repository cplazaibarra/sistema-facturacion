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


def list_suppliers() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, description, website, rut, dv, razon_social, giro, direccion, comuna, ciudad, email, phone, tipo_compra, created_at
                FROM suppliers
                ORDER BY name
                """
            )
            return [dict(row) for row in cur.fetchall()]


def get_supplier(supplier_id: int) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, description, website, rut, dv, razon_social, giro, direccion, comuna, ciudad, email, phone, tipo_compra, created_at
                FROM suppliers
                WHERE id = %s
                """,
                (supplier_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def insert_supplier(supplier: dict) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO suppliers (name, description, website, rut, dv, razon_social, giro, direccion, comuna, ciudad, email, phone, tipo_compra, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    supplier["name"],
                    supplier.get("description"),
                    supplier.get("website"),
                    supplier.get("rut"),
                    supplier.get("dv"),
                    supplier.get("razon_social") or supplier["name"],
                    supplier.get("giro"),
                    supplier.get("direccion"),
                    supplier.get("comuna"),
                    supplier.get("ciudad"),
                    supplier.get("email"),
                    supplier.get("phone"),
                    supplier.get("tipo_compra", "Del Giro"),
                    supplier.get("created_at", datetime.utcnow().isoformat(timespec='seconds')),
                ),
            )
            supplier_id = cur.fetchone()["id"]
        conn.commit()
        return supplier_id


def update_supplier(supplier_id: int, supplier: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
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
                    supplier.get("rut"),
                    supplier.get("dv"),
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
                    contact.get("created_at", datetime.utcnow().isoformat(timespec='seconds')),
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

