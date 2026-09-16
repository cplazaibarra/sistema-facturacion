#!/usr/bin/env python3
"""
tools/seed_demo.py
Optional demo/mock data seeder for local development and testing.
NEVER run automatically in production or init_db().
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras
from werkzeug.security import generate_password_hash

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DEMO_USERS = [
    {"username": "gerente", "email": "gerente@bodegamiel.com", "role": "Gerente", "full_name": "Gerente General"},
    {"username": "vendedor", "email": "vendedor@bodegamiel.com", "role": "Área Ventas", "full_name": "Ejecutivo Ventas"},
    {"username": "contable", "email": "contable@bodegamiel.com", "role": "Contables", "full_name": "Auditor Contable"},
    {"username": "aprobador", "email": "aprobador@bodegamiel.com", "role": "Aprobador", "full_name": "Jefe Compras"},
    {"username": "digitador", "email": "digitador@bodegamiel.com", "role": "Digitador", "full_name": "Digitador Operativo"},
]

DEMO_PRODUCTS = [
    {"sku": "DEMO-001", "name": "Miel Multiflora 1kg", "category": "Miel", "cost": 3500.0, "requires_lot": True},
    {"sku": "DEMO-002", "name": "Polen Granulado 250g", "category": "Polen", "cost": 2200.0, "requires_lot": True},
    {"sku": "DEMO-003", "name": "Propóleo Gotas 30ml", "category": "Propóleo", "cost": 1800.0, "requires_lot": True},
]

DEMO_SUPPLIERS = [
    {"name": "Apícola Central SpA", "rut": "76.543.210-K", "email": "ventas@apicolacentral.cl", "phone": "+56911223344"},
    {"name": "Envases del Sur Ltda", "rut": "77.889.900-1", "email": "contacto@envasesdelsur.cl", "phone": "+56955667788"},
]


def seed_demo_data(conn):
    now_str = datetime.now(timezone.utc).isoformat(timespec='seconds')
    with conn.cursor() as cur:
        # 1. Demo Users
        cur.execute("SELECT id, name FROM roles;")
        roles_map = {r["name"]: r["id"] for r in cur.fetchall()}
        for u in DEMO_USERS:
            role_id = roles_map.get(u["role"], 1)
            cur.execute(
                """
                INSERT INTO users (username, email, password, full_name, role_id, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (username) DO NOTHING;
                """,
                (u["username"], u["email"], generate_password_hash("demo1234"), u["full_name"], role_id, True, now_str)
            )

        # 2. Demo Suppliers
        for s in DEMO_SUPPLIERS:
            cur.execute(
                """
                INSERT INTO suppliers (name, rut, email, phone, created_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
                """,
                (s["name"], s["rut"], s["email"], s["phone"], now_str)
            )

        # 3. Demo Products
        for p in DEMO_PRODUCTS:
            cur.execute(
                """
                INSERT INTO products (sku, name, category, cost, requires_lot, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (sku) DO NOTHING;
                """,
                (p["sku"], p["name"], p["category"], p["cost"], p["requires_lot"], now_str)
            )

    conn.commit()
    print("Demo data successfully seeded.")


def main():
    import tools.migrate as mig
    with mig.get_connection() as conn:
        seed_demo_data(conn)


if __name__ == "__main__":
    main()
