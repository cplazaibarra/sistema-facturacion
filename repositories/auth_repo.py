"""
repositories/auth_repo.py
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


def list_roles() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, description, permissions FROM roles ORDER BY id"
            )
            return [dict(row) for row in cur.fetchall()]


def get_role(role_id: int) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, description, permissions FROM roles WHERE id = %s",
                (role_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def insert_role(role: dict) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO roles (name, description, permissions, created_at)
                VALUES (%s, %s, %s, %s) RETURNING id
                """,
                (
                    role["name"],
                    role.get("description"),
                    role.get("permissions"),
                    role["created_at"],
                ),
            )
            inserted_id = cur.fetchone()["id"]
        conn.commit()
        return inserted_id


def update_role(role_id: int, role: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE roles SET name = %s, description = %s, permissions = %s
                WHERE id = %s
                """,
                (role.get("name"), role.get("description"), role.get("permissions"), role_id),
            )
        conn.commit()


def delete_role(role_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM roles WHERE id = %s", (role_id,))
        conn.commit()


def list_users() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.username, u.email, u.full_name, u.role_id, u.is_active,
                       r.name as role_name, u.created_at
                FROM users u
                JOIN roles r ON u.role_id = r.id
                ORDER BY u.created_at DESC
                """
            )
            return [dict(row) for row in cur.fetchall()]


def get_user(user_id: int) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.username, u.email, u.full_name, u.is_active, u.role_id,
                       r.name as role_name
                FROM users u
                JOIN roles r ON u.role_id = r.id
                WHERE u.id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def insert_user(user: dict) -> int:
    raw_pw = user.get("password", "password123")
    if raw_pw and not raw_pw.startswith(('scrypt:', 'pbkdf2:', 'argon2:')):
        stored_pw = generate_password_hash(raw_pw)
    else:
        stored_pw = raw_pw or generate_password_hash("password123")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (username, email, password, full_name, role_id, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (
                    user["username"],
                    user["email"],
                    stored_pw,
                    user["full_name"],
                    user["role_id"],
                    bool(user.get("is_active", True)),
                    user["created_at"],
                ),
            )
            inserted_id = cur.fetchone()["id"]
        conn.commit()
        return inserted_id


def update_user(user_id: int, user: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if "password" in user and user["password"]:
                raw_pw = user["password"]
                if not raw_pw.startswith(('scrypt:', 'pbkdf2:', 'argon2:')):
                    pw_hash = generate_password_hash(raw_pw)
                else:
                    pw_hash = raw_pw
                cur.execute(
                    """
                    UPDATE users SET email = %s, full_name = %s, role_id = %s, is_active = %s, password = %s
                    WHERE id = %s
                    """,
                    (
                        user.get("email"),
                        user.get("full_name"),
                        user.get("role_id"),
                        bool(user.get("is_active", True)),
                        pw_hash,
                        user_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    UPDATE users SET email = %s, full_name = %s, role_id = %s, is_active = %s
                    WHERE id = %s
                    """,
                    (
                        user.get("email"),
                        user.get("full_name"),
                        user.get("role_id"),
                        bool(user.get("is_active", True)),
                        user_id,
                    ),
                )
        conn.commit()


def delete_user(user_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()

