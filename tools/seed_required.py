#!/usr/bin/env python3
"""
tools/seed_required.py
Seeds mandatory catalogs, system roles, base users, and initial page_data essential for system operation.
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

DEFAULT_ROLES = [
    {
        "name": "Administrativo",
        "description": "Acceso completo a todas las funciones del sistema",
        "permissions": {
            "dashboard": True,
            "usuarios": True,
            "ventas": True,
            "inventario": True,
            "productos": True,
            "administracion": True,
            "reportes": True,
            "configuracion": True,
            "crear_registros": True,
            "aprobar_registros": True,
            "solo_ver": False,
        },
    },
    {
        "name": "Gerente",
        "description": "Acceso a ventas, inventario y reportes",
        "permissions": {
            "dashboard": True,
            "usuarios": False,
            "ventas": True,
            "inventario": True,
            "productos": True,
            "administracion": False,
            "reportes": True,
            "configuracion": False,
            "crear_registros": True,
            "aprobar_registros": True,
            "solo_ver": False,
        },
    },
    {
        "name": "Área Ventas",
        "description": "Acceso limitado a ventas y productos",
        "permissions": {
            "dashboard": False,
            "usuarios": False,
            "ventas": True,
            "inventario": False,
            "productos": True,
            "administracion": False,
            "reportes": False,
            "configuracion": False,
            "crear_registros": True,
            "aprobar_registros": False,
            "solo_ver": False,
        },
    },
    {
        "name": "Contables",
        "description": "Acceso a revisión de pagos y reportes financieros",
        "permissions": {
            "dashboard": False,
            "usuarios": False,
            "ventas": True,
            "inventario": False,
            "productos": False,
            "administracion": False,
            "reportes": True,
            "configuracion": False,
            "crear_registros": False,
            "aprobar_registros": False,
            "solo_ver": True,
        },
    },
    {
        "name": "Aprobador",
        "description": "Validación de información de pagos y aprobación de órdenes de compra",
        "permissions": {
            "dashboard": True,
            "usuarios": False,
            "ventas": True,
            "inventario": True,
            "productos": True,
            "administracion": True,
            "reportes": True,
            "configuracion": False,
            "crear_registros": True,
            "aprobar_registros": True,
            "solo_ver": False,
        },
    },
    {
        "name": "Digitador",
        "description": "Creación de ventas, productos y OCs (sin permisos de aprobación)",
        "permissions": {
            "dashboard": True,
            "usuarios": False,
            "ventas": True,
            "inventario": True,
            "productos": True,
            "administracion": False,
            "reportes": False,
            "configuracion": False,
            "crear_registros": True,
            "aprobar_registros": False,
            "solo_ver": False,
        },
    },
]

REQUIRED_PAGE_DATA = {
    "admin_modules": [
        {"icon": "👥", "title": "Usuarios", "desc": "Gestionar usuarios y permisos del sistema", "action": "Gestionar", "link": "/usuarios"},
        {"icon": "🏪", "title": "Proveedores", "desc": "Gestionar empresas proveedoras y contactos", "action": "Gestionar", "link": "/proveedores"},
        {"icon": "🏦", "title": "Cuentas Bancarias", "desc": "Administrar cuentas bancarias para cobros y pagos", "action": "Administrar", "link": "/administracion/cuentas-bancarias"},
        {"icon": "🏢", "title": "Empresa", "desc": "Configuración de datos de la empresa", "action": "Configurar", "link": "/administracion#empresa"},
        {"icon": "💳", "title": "Métodos de Pago", "desc": "Configurar formas de pago aceptadas", "action": "Configurar", "link": "/administracion#pagos"},
        {"icon": "📄", "title": "Documentos", "desc": "Plantillas de facturas y documentos", "action": "Editar", "link": "/administracion#documentos"},
        {"icon": "🔔", "title": "Notificaciones", "desc": "Configurar alertas y notificaciones", "action": "Configurar", "link": "/administracion#notificaciones"},
        {"icon": "🔒", "title": "Seguridad", "desc": "Configuración de seguridad del sistema", "action": "Configurar", "link": "/administracion#seguridad"},
    ],
    "admin_settings": {
        "company_name": "Bodega Miel S.A.",
        "rut": "12.345.678-9",
        "address": "Av. Principal 123, Santiago",
        "phone": "+56 9 1234 5678",
        "email": "contacto@bodegamiel.com",
    },
    "inventory_categories": ["Miel", "Polen", "Propóleo"],
    "inventory_stock_filters": ["Stock: Todos", "Stock Bajo", "Stock Normal", "Stock Alto"],
    "ingreso_default_date": "2026-02-04",
    "ingreso_warehouses": ["Almacén Principal", "Almacén Secundario"],
    "sales_delivery_status_options": ["Pendiente", "En Ruta", "Entregado"],
    "sales_payment_method_options": ["Transferencia", "Efectivo", "Cheque", "Crédito 30 días"],
    "sales_payment_status_options": ["Pendiente", "Aprobado", "Rechazado"],
}


def seed_required_catalogs(conn):
    now_str = datetime.now(timezone.utc).isoformat(timespec='seconds')
    with conn.cursor() as cur:
        # 1. Roles
        for r in DEFAULT_ROLES:
            cur.execute(
                """
                INSERT INTO roles (name, description, permissions, created_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE 
                SET permissions = EXCLUDED.permissions, description = EXCLUDED.description;
                """,
                (r["name"], r["description"], json.dumps(r["permissions"]), now_str)
            )

        # 2. Base Admin User (if no users exist)
        cur.execute("SELECT COUNT(*) as count FROM users;")
        if cur.fetchone()["count"] == 0:
            cur.execute("SELECT id FROM roles WHERE name = 'Administrativo';")
            role_row = cur.fetchone()
            admin_role_id = role_row["id"] if role_row else 1
            cur.execute(
                """
                INSERT INTO users (username, email, password, full_name, role_id, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    "admin",
                    "admin@bodegamiel.com",
                    generate_password_hash("admin123"),
                    "Administrador Sistema",
                    admin_role_id,
                    True,
                    now_str,
                )
            )

        # 3. Required page_data configuration entries
        for key, value in REQUIRED_PAGE_DATA.items():
            cur.execute(
                """
                INSERT INTO page_data (key, json) VALUES (%s, %s)
                ON CONFLICT (key) DO NOTHING;
                """,
                (key, json.dumps(value, ensure_ascii=False))
            )

        # Ensure empty inventory_items array exists in page_data if absent
        cur.execute(
            """
            INSERT INTO page_data (key, json) VALUES ('inventory_items', '[]')
            ON CONFLICT (key) DO NOTHING;
            """
        )

        # 4. Bank Account por defecto (si no existe)
        cur.execute("SELECT COUNT(*) as count FROM bank_accounts;")
        if cur.fetchone()["count"] == 0:
            cur.execute(
                """
                INSERT INTO bank_accounts (bank_name, account_number, account_type, holder_name, holder_rut, email, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                ("Banco de Chile", "00-123-45678-09", "Cuenta Corriente", "Bodega Miel S.A.", "76.123.456-7", "pagos@bodegamiel.com", "Activa")
            )

    conn.commit()
    print("Required catalogs and seeds successfully ensured.")


def main():
    import tools.migrate as mig
    with mig.get_connection() as conn:
        seed_required_catalogs(conn)


if __name__ == "__main__":
    main()
