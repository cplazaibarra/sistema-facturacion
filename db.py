import json
import os
import re
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from typing import Any, Dict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_DATA: Dict[str, Any] = {
    "default_roles": [
        {
            "name": "Administrativo",
            "description": "Acceso completo a todas las funciones del sistema",
            "permissions": json.dumps({
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
            }),
        },
        {
            "name": "Gerente",
            "description": "Acceso a ventas, inventario y reportes",
            "permissions": json.dumps({
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
            }),
        },
        {
            "name": "Área Ventas",
            "description": "Acceso limitado a ventas y productos",
            "permissions": json.dumps({
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
            }),
        },
        {
            "name": "Contables",
            "description": "Acceso a revisión de pagos y reportes financieros",
            "permissions": json.dumps({
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
            }),
        },
        {
            "name": "Aprobador",
            "description": "Validación de información de pagos y aprobación de órdenes de compra",
            "permissions": json.dumps({
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
            }),
        },
        {
            "name": "Digitador",
            "description": "Creación de ventas, productos y OCs (sin permisos de aprobación)",
            "permissions": json.dumps({
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
            }),
        },
    ],
    "dashboard_stats": {
        "ventas_hoy": 15420,
        "productos_stock": 1250,
        "ordenes_pendientes": 23,
        "clientes_activos": 456,
    },
    "dashboard_sales_chart": {
        "labels": ["Ene", "Feb", "Mar", "Abr", "May", "Jun"],
        "data": [12000, 19000, 15000, 22000, 18000, 25000],
    },
    "dashboard_products_top": {
        "labels": ["Miel 500g", "Miel 1kg", "Miel 250g", "Polen", "Propóleo"],
        "data": [450, 380, 290, 150, 120],
    },
    "dashboard_recent_sales": [
        {
            "id": "#001",
            "cliente": "María González",
            "producto": "Miel 1kg",
            "cantidad": 3,
            "total": 45.00,
            "estado": "Completado",
        },
        {
            "id": "#002",
            "cliente": "Carlos Ruiz",
            "producto": "Miel 500g",
            "cantidad": 5,
            "total": 37.50,
            "estado": "Pendiente",
        },
        {
            "id": "#003",
            "cliente": "Ana Torres",
            "producto": "Polen 250g",
            "cantidad": 2,
            "total": 28.00,
            "estado": "Completado",
        },
    ],
    "admin_modules": [
        {
            "icon": "👥",
            "title": "Usuarios",
            "desc": "Gestionar usuarios y permisos del sistema",
            "action": "Gestionar",
            "link": "/usuarios",
        },
        {
            "icon": "🏪",
            "title": "Proveedores",
            "desc": "Gestionar empresas proveedoras y contactos",
            "action": "Gestionar",
            "link": "/proveedores",
        },
        {
            "icon": "🏦",
            "title": "Cuentas Bancarias",
            "desc": "Administrar cuentas bancarias para cobros de ventas y pagos a proveedores",
            "action": "Administrar",
            "link": "/administracion/cuentas-bancarias",
        },
        {
            "icon": "🏢",
            "title": "Empresa",
            "desc": "Configuración de datos de la empresa",
            "action": "Configurar",
            "link": "/administracion#empresa",
        },
        {
            "icon": "💳",
            "title": "Métodos de Pago",
            "desc": "Configurar formas de pago aceptadas",
            "action": "Configurar",
            "link": "/administracion#pagos",
        },
        {
            "icon": "📄",
            "title": "Documentos",
            "desc": "Plantillas de facturas y documentos",
            "action": "Editar",
            "link": "/administracion#documentos",
        },
        {
            "icon": "🔔",
            "title": "Notificaciones",
            "desc": "Configurar alertas y notificaciones",
            "action": "Configurar",
            "link": "/administracion#notificaciones",
        },
        {
            "icon": "🔒",
            "title": "Seguridad",
            "desc": "Configuración de seguridad del sistema",
            "action": "Configurar",
            "link": "/administracion#seguridad",
        },
    ],
    "admin_settings": {
        "company_name": "Bodega Miel S.A.",
        "rut": "12.345.678-9",
        "address": "Av. Principal 123, Santiago",
        "phone": "+56 9 1234 5678",
        "email": "contacto@bodegamiel.com",
    },
    "inventory_stats": {
        "total": 245,
        "low_stock": 12,
        "total_value": 125450,
    },
    "inventory_categories": ["Miel", "Polen", "Propóleo"],
    "inventory_stock_filters": [
        "Stock: Todos",
        "Stock Bajo",
        "Stock Normal",
        "Stock Alto",
    ],
    "inventory_items": [
        {
            "code": "PRD001",
            "name": "Miel Pura 1kg",
            "desc": "Miel de abeja pura",
            "category": "Miel",
            "stock": 450,
            "min_stock": 50,
            "price": 15.00,
            "status": "Normal",
            "stock_percent": 75,
        },
        {
            "code": "PRD002",
            "name": "Miel Pura 500g",
            "desc": "Miel de abeja pura",
            "category": "Miel",
            "stock": 680,
            "min_stock": 50,
            "price": 8.50,
            "status": "Normal",
            "stock_percent": 90,
        },
        {
            "code": "PRD003",
            "name": "Polen de Abeja 250g",
            "desc": "Polen natural",
            "category": "Polen",
            "stock": 35,
            "min_stock": 30,
            "price": 12.00,
            "status": "Stock Bajo",
            "stock_percent": 25,
        },
        {
            "code": "PRD004",
            "name": "Propóleo 30ml",
            "desc": "Propóleo concentrado",
            "category": "Propóleo",
            "stock": 180,
            "min_stock": 40,
            "price": 18.00,
            "status": "Normal",
            "stock_percent": 60,
        },
    ],
    "ingreso_default_date": "2026-02-04",
    "ingreso_suppliers": [
        "Apícola San José",
        "Miel del Valle",
        "Productores Unidos",
    ],
    "ingreso_warehouses": ["Almacén Principal", "Almacén Secundario"],
    "ingreso_products": [
        {"name": "Miel Pura 1kg", "price": 15.00},
        {"name": "Miel Pura 500g", "price": 8.50},
        {"name": "Polen de Abeja 250g", "price": 12.00},
        {"name": "Propóleo 30ml", "price": 18.00},
    ],
    "ingreso_recent": [
        {
            "date": "04/02/2026",
            "order": "OC-2026-001",
            "supplier": "Apícola San José",
            "total": 1250.00,
        },
        {
            "date": "03/02/2026",
            "order": "OC-2026-002",
            "supplier": "Miel del Valle",
            "total": 2450.00,
        },
        {
            "date": "02/02/2026",
            "order": "OC-2026-003",
            "supplier": "Productores Unidos",
            "total": 890.00,
        },
    ],
    "proyeccion_stats": [
        {
            "icon": "📊",
            "label": "Proyección Mes Actual",
            "value": "$28,500",
            "change": "+15.2% vs mes anterior",
            "color": "blue",
        },
        {
            "icon": "📈",
            "label": "Tendencia Trimestral",
            "value": "$82,400",
            "change": "+8.5% crecimiento",
            "color": "cyan",
        },
        {
            "icon": "🎯",
            "label": "Meta Anual",
            "value": "$350,000",
            "change": "Progreso: 65%",
            "color": "purple",
        },
    ],
    "proyeccion_chart": {
        "labels": ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago"],
        "projected": [15000, 18000, 21000, 24000, 27000, 29000, 32000, 35000],
        "real": [14500, 17800, 20500, 23200, 25800, None, None, None],
    },
    "proyeccion_table": [
        {
            "product": "Miel 1kg",
            "current": "$12,500",
            "projection": "$14,200",
            "variation": "+13.6%",
            "confidence": "Alta (92%)",
            "level": "high",
        },
        {
            "product": "Miel 500g",
            "current": "$8,200",
            "projection": "$9,100",
            "variation": "+11.0%",
            "confidence": "Alta (88%)",
            "level": "high",
        },
        {
            "product": "Polen 250g",
            "current": "$3,800",
            "projection": "$4,500",
            "variation": "+18.4%",
            "confidence": "Media (75%)",
            "level": "medium",
        },
        {
            "product": "Propóleo 30ml",
            "current": "$2,100",
            "projection": "$2,300",
            "variation": "+9.5%",
            "confidence": "Media (70%)",
            "level": "medium",
        },
    ],
    "proyeccion_insights": [
        {
            "icon": "💡",
            "title": "Tendencia Positiva",
            "desc": "Las ventas de Polen muestran un crecimiento constante del 18% mensual",
        },
        {
            "icon": "⚠️",
            "title": "Alerta de Stock",
            "desc": "Se proyecta falta de stock de Miel 1kg para la próxima semana",
        },
        {
            "icon": "📊",
            "title": "Oportunidad",
            "desc": "Incrementar stock de Polen para aprovechar alta demanda proyectada",
        },
        {
            "icon": "🎯",
            "title": "Meta Mensual",
            "desc": "Se requiere $3,200 adicionales para alcanzar la meta del mes",
        },
    ],
    "ventas_metrics": [
        {
            "icon": "💰",
            "trend": "+12.5%",
            "value": "$45,320",
            "label": "Ventas del Mes",
            "secondary": "vs. $40,285 mes anterior",
            "color": "blue",
        },
        {
            "icon": "📋",
            "trend": "+8.3%",
            "value": "156",
            "label": "Órdenes Completadas",
            "secondary": "23 pendientes",
            "color": "cyan",
        },
        {
            "icon": "📈",
            "trend": "+15.7%",
            "value": "$290",
            "label": "Ticket Promedio",
            "secondary": "vs. $251 anterior",
            "color": "purple",
        },
        {
            "icon": "👥",
            "trend": "...",
            "value": "89",
            "label": "Clientes Activos",
            "secondary": "345 clientes totales",
            "color": "green",
        },
    ],
    "ventas_records": [
        {
            "sale_number": "VTA-00156",
            "customer": {
                "name": "María González",
                "email": "maria@email.com",
                "initials": "MG",
            },
            "date": "04/02/2026",
            "time": "14:30",
            "products": ["Miel 1kg (3)", "Polen 250g (1)"],
            "total": "$59.00",
            "status": {"label": "Completada", "level": "success"},
            "seller": {"name": "Juan Ramírez", "initials": "JR"},
        },
        {
            "sale_number": "VTA-00155",
            "customer": {
                "name": "Carlos Ruiz",
                "email": "carlos@email.com",
                "initials": "CR",
            },
            "date": "04/02/2026",
            "time": "11:15",
            "products": ["Miel 500g (5)"],
            "total": "$42.50",
            "status": {"label": "Pendiente", "level": "warning"},
            "seller": {"name": "Juan Ramírez", "initials": "JR"},
        },
        {
            "sale_number": "VTA-00154",
            "customer": {
                "name": "Ana Torres",
                "email": "ana@email.com",
                "initials": "AT",
            },
            "date": "03/02/2026",
            "time": "16:45",
            "products": ["Propóleo 30ml (2)", "Miel 1kg (1)"],
            "total": "$51.00",
            "status": {"label": "Completada", "level": "success"},
            "seller": {"name": "Laura Sánchez", "initials": "LS"},
        },
        {
            "sale_number": "VTA-00153",
            "customer": {
                "name": "Pedro Martínez",
                "email": "pedro@email.com",
                "initials": "PM",
            },
            "date": "03/02/2026",
            "time": "10:20",
            "products": ["Miel 500g (10)", "+2 más"],
            "total": "$125.00",
            "status": {"label": "Completada", "level": "success"},
            "seller": {"name": "Juan Ramírez", "initials": "JR"},
        },
        {
            "sale_number": "VTA-00152",
            "customer": {
                "name": "Lucía Fernández",
                "email": "lucia@email.com",
                "initials": "LF",
            },
            "date": "02/02/2026",
            "time": "15:30",
            "products": ["Polen 250g (4)"],
            "total": "$48.00",
            "status": {"label": "Cancelada", "level": "danger"},
            "seller": {"name": "Laura Sánchez", "initials": "LS"},
        },
    ],
    "sales_payment_status_options": ["Pendiente", "Pendiente Aprobación Pago", "Pagado", "Parcial"],
    "sales_payment_method_options": [
        "Efectivo",
        "Transferencia",
        "Tarjeta",
        "Crédito",
    ],
    "sales_delivery_status_options": [
        "Pendiente",
        "En Ruta",
        "Entregado",
    ],
}


def get_connection():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "postgres"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
        cursor_factory=psycopg2.extras.RealDictCursor
    )


def init_db() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS page_data (
                    key TEXT PRIMARY KEY,
                    json TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sales_entries (
                    id SERIAL PRIMARY KEY,
                    sku TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price DOUBLE PRECISION NOT NULL,
                    total_price DOUBLE PRECISION NOT NULL,
                    sale_date TEXT NOT NULL,
                    delivery_date TEXT,
                    payment_status TEXT NOT NULL,
                    delivery_status TEXT NOT NULL,
                    payment_method TEXT NOT NULL,
                    customer_name TEXT NOT NULL,
                    seller_name TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    sku TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    description TEXT,
                    photo_url TEXT,
                    barcode TEXT,
                    internal_code TEXT,
                    category TEXT,
                    expiry_date TEXT,
                    width_cm DOUBLE PRECISION,
                    height_cm DOUBLE PRECISION,
                    depth_cm DOUBLE PRECISION,
                    weight_kg DOUBLE PRECISION,
                    created_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'products'
                """
            )
            existing_columns = {row["column_name"] for row in cur.fetchall()}
            missing_columns = {
                "barcode": "TEXT",
                "internal_code": "TEXT",
                "category": "TEXT",
                "expiry_date": "TEXT",
                "product_type": "TEXT DEFAULT 'Final'",
                "cost": "DOUBLE PRECISION DEFAULT 0.0",
                "is_deleted": "BOOLEAN DEFAULT FALSE",
            }
            for column_name, column_type in missing_columns.items():
                if column_name not in existing_columns:
                    cur.execute(
                        f"ALTER TABLE products ADD COLUMN {column_name} {column_type}"
                    )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS roles (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    permissions TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    role_id INTEGER NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (role_id) REFERENCES roles(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sales (
                    id SERIAL PRIMARY KEY,
                    sale_number TEXT NOT NULL UNIQUE,
                    customer_name TEXT NOT NULL,
                    customer_email TEXT,
                    customer_initials TEXT,
                    sale_date TEXT NOT NULL,
                    sale_time TEXT NOT NULL,
                    products_json TEXT NOT NULL,
                    total_amount DOUBLE PRECISION NOT NULL,
                    status TEXT NOT NULL,
                    seller_name TEXT NOT NULL,
                    seller_initials TEXT,
                    payment_method TEXT,
                    payment_status TEXT,
                    delivery_status TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sale_payments (
                    id SERIAL PRIMARY KEY,
                    sale_id INTEGER NOT NULL UNIQUE,
                    invoice_number TEXT,
                    invoice_amount DOUBLE PRECISION,
                    invoice_due_date TEXT,
                    invoice_file TEXT,
                    payment_proof_file TEXT,
                    payment_amount DOUBLE PRECISION,
                    payment_date TEXT,
                    seller_uploaded_at TEXT,
                    payment_uploaded_at TEXT,
                    accounting_approved INTEGER DEFAULT 0,
                    accounting_approved_by TEXT,
                    accounting_approved_at TEXT,
                    accounting_comment TEXT,
                    status TEXT NOT NULL DEFAULT 'Factura pendiente',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (sale_id) REFERENCES sales(id)
                )
                """
            )
            cur.execute(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'sale_payments'
                """
            )
            existing_payment_columns = {row["column_name"] for row in cur.fetchall()}
            payment_missing_columns = {
                "invoice_number": "TEXT",
                "accounting_comment": "TEXT",
                "invoice_due_date": "TEXT",
                "payment_date": "TEXT",
                "invoice_amount": "DOUBLE PRECISION",
                "payment_amount": "DOUBLE PRECISION",
            }
            for column_name, column_type in payment_missing_columns.items():
                if column_name not in existing_payment_columns:
                    cur.execute(
                        f"ALTER TABLE sale_payments ADD COLUMN {column_name} {column_type}"
                    )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sale_payment_items (
                    id SERIAL PRIMARY KEY,
                    sale_id INTEGER NOT NULL,
                    payment_amount DOUBLE PRECISION NOT NULL,
                    payment_date TEXT,
                    payment_proof_file TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (sale_id) REFERENCES sales(id)
                )
                """
            )
            cur.execute("SELECT COUNT(*) as count FROM sale_payment_items")
            if cur.fetchone()["count"] == 0:
                cur.execute(
                    "SELECT sale_id, payment_amount, payment_date, payment_proof_file, created_at FROM sale_payments WHERE payment_amount IS NOT NULL AND payment_amount > 0"
                )
                for row in cur.fetchall():
                    cur.execute(
                        "INSERT INTO sale_payment_items (sale_id, payment_amount, payment_date, payment_proof_file, created_at) VALUES (%s, %s, %s, %s, %s)",
                        (row["sale_id"], row["payment_amount"], row["payment_date"], row["payment_proof_file"], row["created_at"]),
                    )
            cur.execute(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'sale_payment_items'
                """
            )
            existing_item_columns = {row["column_name"] for row in cur.fetchall()}
            item_missing_columns = {
                "accounting_approved": "INTEGER DEFAULT 0",
                "accounting_approved_by": "TEXT",
                "accounting_approved_at": "TEXT",
                "accounting_comment": "TEXT",
                "bank_account_id": "INTEGER REFERENCES bank_accounts(id) ON DELETE SET NULL"
            }
            for col_name, col_type in item_missing_columns.items():
                if col_name not in existing_item_columns:
                    cur.execute(f"ALTER TABLE sale_payment_items ADD COLUMN {col_name} {col_type}")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sales_status_history (
                    id SERIAL PRIMARY KEY,
                    sale_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    user_name TEXT NOT NULL,
                    changed_at TEXT NOT NULL,
                    comment TEXT,
                    FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sales_payment_history (
                    id SERIAL PRIMARY KEY,
                    sale_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    user_name TEXT NOT NULL,
                    changed_at TEXT NOT NULL,
                    details TEXT,
                    FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS suppliers (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    website TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            cur.execute("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS rut TEXT;")
            cur.execute("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS dv TEXT;")
            cur.execute("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS razon_social TEXT;")
            cur.execute("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS giro TEXT;")
            cur.execute("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS direccion TEXT;")
            cur.execute("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS comuna TEXT;")
            cur.execute("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS ciudad TEXT;")
            cur.execute("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS email TEXT;")
            cur.execute("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS phone TEXT;")
            cur.execute("ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS tipo_compra TEXT;")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS supplier_contacts (
                    id SERIAL PRIMARY KEY,
                    supplier_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    phone TEXT,
                    email TEXT,
                    position TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS product_suppliers (
                    id SERIAL PRIMARY KEY,
                    product_id INTEGER NOT NULL,
                    supplier_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
                    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE,
                    UNIQUE(product_id, supplier_id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS purchase_orders (
                    id SERIAL PRIMARY KEY,
                    oc_number TEXT NOT NULL UNIQUE,
                    supplier_id INTEGER NOT NULL,
                    order_date TEXT NOT NULL,
                    status TEXT NOT NULL, -- 'Borrador', 'Emitida', 'Parcialmente Recibida', 'Recibida', 'Facturada'
                    total_amount DOUBLE PRECISION NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS purchase_order_items (
                    id SERIAL PRIMARY KEY,
                    purchase_order_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    quantity_ordered INTEGER NOT NULL,
                    quantity_received INTEGER DEFAULT 0,
                    unit_price DOUBLE PRECISION NOT NULL,
                    total_price DOUBLE PRECISION NOT NULL,
                    FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id) ON DELETE CASCADE,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS inventory_entries (
                    id SERIAL PRIMARY KEY,
                    entry_date TEXT NOT NULL,
                    order_number TEXT NOT NULL,
                    purchase_order_id INTEGER,
                    supplier_id INTEGER NOT NULL,
                    warehouse TEXT NOT NULL,
                    notes TEXT,
                    total_amount DOUBLE PRECISION NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id) ON DELETE SET NULL,
                    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS inventory_entry_items (
                    id SERIAL PRIMARY KEY,
                    inventory_entry_id INTEGER NOT NULL,
                    product_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price DOUBLE PRECISION NOT NULL,
                    total DOUBLE PRECISION NOT NULL,
                    FOREIGN KEY (inventory_entry_id) REFERENCES inventory_entries(id) ON DELETE CASCADE,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
                )
                """
            )
            cur.execute(
                """
                ALTER TABLE inventory_entries ALTER COLUMN supplier_id DROP NOT NULL;
                """
            )
            cur.execute(
                """
                ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS created_by INTEGER REFERENCES users(id) ON DELETE SET NULL;
                """
            )
            cur.execute(
                """
                ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL;
                """
            )
            cur.execute(
                """
                ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS payment_method TEXT DEFAULT 'Efectivo';
                """
            )
            cur.execute("DROP TABLE IF EXISTS product_margins;")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS product_margins (
                    product_sku TEXT PRIMARY KEY,
                    base_margin DOUBLE PRECISION DEFAULT 20.0,
                    category_margins JSONB DEFAULT '{}'::jsonb
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS production_orders (
                    id SERIAL PRIMARY KEY,
                    ot_number TEXT NOT NULL UNIQUE,
                    final_product_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    approved_at TEXT,
                    completed_at TEXT,
                    FOREIGN KEY (final_product_id) REFERENCES products(id) ON DELETE RESTRICT
                )
                """
            )
            cur.execute(
                """
                ALTER TABLE production_orders ADD COLUMN IF NOT EXISTS unit_cost DOUBLE PRECISION;
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS production_order_items (
                    id SERIAL PRIMARY KEY,
                    production_order_id INTEGER NOT NULL,
                    input_product_id INTEGER NOT NULL,
                    quantity_required DOUBLE PRECISION NOT NULL,
                    FOREIGN KEY (production_order_id) REFERENCES production_orders(id) ON DELETE CASCADE,
                    FOREIGN KEY (input_product_id) REFERENCES products(id) ON DELETE RESTRICT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS product_recipes (
                    id SERIAL PRIMARY KEY,
                    final_product_id INTEGER NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (final_product_id) REFERENCES products(id) ON DELETE CASCADE
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS product_recipe_items (
                    id SERIAL PRIMARY KEY,
                    recipe_id INTEGER NOT NULL,
                    input_product_id INTEGER NOT NULL,
                    quantity_required DOUBLE PRECISION NOT NULL,
                    FOREIGN KEY (recipe_id) REFERENCES product_recipes(id) ON DELETE CASCADE,
                    FOREIGN KEY (input_product_id) REFERENCES products(id) ON DELETE RESTRICT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS production_order_additional_items (
                    id SERIAL PRIMARY KEY,
                    production_order_id INTEGER NOT NULL,
                    input_product_id INTEGER NOT NULL,
                    quantity DOUBLE PRECISION NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (production_order_id) REFERENCES production_orders(id) ON DELETE CASCADE,
                    FOREIGN KEY (input_product_id) REFERENCES products(id) ON DELETE RESTRICT
                )
                """
            )
            cur.execute(
                """
                ALTER TABLE production_order_items ADD COLUMN IF NOT EXISTS unit_cost DOUBLE PRECISION;
                """
            )
            cur.execute(
                """
                ALTER TABLE production_order_additional_items ADD COLUMN IF NOT EXISTS unit_cost DOUBLE PRECISION;
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS clients (
                    id SERIAL PRIMARY KEY,
                    rut VARCHAR(20),
                    dv VARCHAR(5),
                    razon_social VARCHAR(255) NOT NULL,
                    tipo_compra VARCHAR(100) DEFAULT 'Del Giro',
                    direccion TEXT,
                    comuna VARCHAR(100),
                    ciudad VARCHAR(100),
                    giro VARCHAR(255),
                    contacto VARCHAR(255),
                    rut_solicita VARCHAR(20),
                    dv_solicita VARCHAR(5),
                    email VARCHAR(255),
                    phone VARCHAR(50),
                    category_id VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                ALTER TABLE clients ALTER COLUMN category_id TYPE VARCHAR(50);

                CREATE TABLE IF NOT EXISTS bank_accounts (
                    id SERIAL PRIMARY KEY,
                    bank_name VARCHAR(100) NOT NULL,
                    account_number VARCHAR(100) NOT NULL UNIQUE,
                    account_type VARCHAR(100) NOT NULL,
                    holder_name VARCHAR(255) NOT NULL,
                    holder_rut VARCHAR(50),
                    email VARCHAR(255),
                    status VARCHAR(50) DEFAULT 'Activa',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
        conn.commit()

    seed_data_if_empty()


def seed_data_if_empty() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            for key, value in DEFAULT_DATA.items():
                if key != "default_roles":
                    cur.execute(
                        "INSERT INTO page_data (key, json) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
                        (key, json.dumps(value, ensure_ascii=False)),
                    )
            
            default_roles = DEFAULT_DATA.get("default_roles", [])
            for role in default_roles:
                cur.execute(
                    """
                    INSERT INTO roles (name, description, permissions, created_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (name) DO UPDATE 
                    SET permissions = EXCLUDED.permissions, description = EXCLUDED.description
                    """,
                    (
                        role["name"],
                        role["description"],
                        role.get("permissions", "{}"),
                        datetime.utcnow().isoformat(timespec='seconds'),
                    ),
                )
            
            cur.execute("SELECT COUNT(*) as count FROM users")
            user_count = cur.fetchone()["count"]
            if user_count == 0:
                cur.execute("SELECT id, name FROM roles")
                roles = cur.fetchall()
                role_map = {r["name"]: r["id"] for r in roles}
                
                default_users = [
                    {
                        "username": "admin",
                        "email": "admin@bodegamiel.com",
                        "password": "admin123",
                        "full_name": "Administrador",
                        "role_id": role_map.get("Administrativo", 1),
                    },
                    {
                        "username": "gerente",
                        "email": "gerente@bodegamiel.com",
                        "password": "gerente123",
                        "full_name": "Gerente",
                        "role_id": role_map.get("Gerente", 2),
                    },
                    {
                        "username": "vendedor",
                        "email": "vendedor@bodegamiel.com",
                        "password": "vendedor123",
                        "full_name": "Vendedor",
                        "role_id": role_map.get("Área Ventas", 3),
                    },
                ]
                
                for user in default_users:
                    cur.execute(
                        "INSERT INTO users (username, email, password, full_name, role_id, is_active, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (username) DO NOTHING",
                        (
                            user["username"],
                            user["email"],
                            user["password"],
                            user["full_name"],
                            user["role_id"],
                            True,
                            datetime.utcnow().isoformat(timespec='seconds'),
                        ),
                    )
            
            cur.execute("SELECT COUNT(*) as count FROM sales")
            sales_count = cur.fetchone()["count"]
            if sales_count == 0:
                default_sales = [
                    {
                        "sale_number": "VTA-00156",
                        "customer_name": "María González",
                        "customer_email": "maria@email.com",
                        "customer_initials": "MG",
                        "sale_date": "2026-02-04",
                        "sale_time": "14:30",
                        "products": ["Miel 1kg (3)", "Polen 250g (1)"],
                        "total_amount": 59.00,
                        "status": "Completada",
                        "seller_name": "Juan Ramírez",
                        "seller_initials": "JR",
                        "payment_method": "Transferencia",
                        "payment_status": "Pagado",
                        "delivery_status": "Entregado",
                        "created_at": datetime.utcnow().isoformat(timespec='seconds'),
                    },
                    {
                        "sale_number": "VTA-00155",
                        "customer_name": "Carlos Ruiz",
                        "customer_email": "carlos@email.com",
                        "customer_initials": "CR",
                        "sale_date": "2026-02-04",
                        "sale_time": "11:15",
                        "products": ["Miel 500g (5)"],
                        "total_amount": 42.50,
                        "status": "Pendiente",
                        "seller_name": "Juan Ramírez",
                        "seller_initials": "JR",
                        "payment_method": "Efectivo",
                        "payment_status": "Pendiente",
                        "delivery_status": "Pendiente",
                        "created_at": datetime.utcnow().isoformat(timespec='seconds'),
                    },
                    {
                        "sale_number": "VTA-00154",
                        "customer_name": "Ana Torres",
                        "customer_email": "ana@email.com",
                        "customer_initials": "AT",
                        "sale_date": "2026-02-03",
                        "sale_time": "16:45",
                        "products": ["Propóleo 30ml (2)", "Miel 1kg (1)"],
                        "total_amount": 51.00,
                        "status": "Completada",
                        "seller_name": "Laura Sánchez",
                        "seller_initials": "LS",
                        "payment_method": "Tarjeta",
                        "payment_status": "Pagado",
                        "delivery_status": "Entregado",
                        "created_at": datetime.utcnow().isoformat(timespec='seconds'),
                    },
                    {
                        "sale_number": "VTA-00153",
                        "customer_name": "Pedro Martínez",
                        "customer_email": "pedro@email.com",
                        "customer_initials": "PM",
                        "sale_date": "2026-02-03",
                        "sale_time": "10:20",
                        "products": ["Miel 500g (10)", "Polen 250g (3)", "Propóleo 30ml (2)"],
                        "total_amount": 125.00,
                        "status": "Completada",
                        "seller_name": "Juan Ramírez",
                        "seller_initials": "JR",
                        "payment_method": "Transferencia",
                        "payment_status": "Pagado",
                        "delivery_status": "Entregado",
                        "created_at": datetime.utcnow().isoformat(timespec='seconds'),
                    },
                    {
                        "sale_number": "VTA-00152",
                        "customer_name": "Lucía Fernández",
                        "customer_email": "lucia@email.com",
                        "customer_initials": "LF",
                        "sale_date": "2026-02-02",
                        "sale_time": "15:30",
                        "products": ["Polen 250g (4)"],
                        "total_amount": 48.00,
                        "status": "Cancelada",
                        "seller_name": "Laura Sánchez",
                        "seller_initials": "LS",
                        "payment_method": "Efectivo",
                        "payment_status": "Cancelado",
                        "delivery_status": "Cancelado",
                        "created_at": datetime.utcnow().isoformat(timespec='seconds'),
                    },
                ]
                
                for sale in default_sales:
                    cur.execute(
                        """
                        INSERT INTO sales (
                            sale_number, customer_name, customer_email, customer_initials,
                            sale_date, sale_time, products_json, total_amount, status,
                            seller_name, seller_initials, payment_method, payment_status,
                            delivery_status, notes, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (sale_number) DO NOTHING
                        """,
                        (
                            sale["sale_number"],
                            sale["customer_name"],
                            sale["customer_email"],
                            sale["customer_initials"],
                            sale["sale_date"],
                            sale["sale_time"],
                            json.dumps(sale["products"], ensure_ascii=False),
                            sale["total_amount"],
                            sale["status"],
                            sale["seller_name"],
                            sale["seller_initials"],
                            sale.get("payment_method", ""),
                            sale.get("payment_status", ""),
                            sale.get("delivery_status", ""),
                            sale.get("notes", ""),
                            sale["created_at"],
                        ),
                    )

            # Sembrar productos si la tabla de productos está vacía
            cur.execute("SELECT COUNT(*) as count FROM products")
            if cur.fetchone()["count"] == 0:
                default_products = DEFAULT_DATA.get("inventory_items", [])
                for p in default_products:
                    cur.execute(
                        """
                        INSERT INTO products (
                            sku, name, description, photo_url, barcode, internal_code,
                            category, width_cm, height_cm, depth_cm, weight_kg, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (sku) DO NOTHING
                        """,
                        (
                            p["code"], # sku
                            p["name"],
                            p["desc"], # description
                            "", # photo_url
                            "", # barcode
                            p["code"], # internal_code
                            p["category"],
                            None, None, None, None, # dimensiones y peso
                            datetime.utcnow().isoformat(timespec='seconds')
                        )
                    )
            
            # Sembrar insumos específicos si no existen en products
            insumos = [
                {"sku": "INS001", "name": "Miel a Granel (kg)", "desc": "Miel de abeja a granel para envasar", "category": "Miel", "product_type": "Insumo", "stock": 1000.0, "min_stock": 100, "price": 4.50},
                {"sku": "INS002", "name": "Frasco de Vidrio 500g", "desc": "Frasco de vidrio vacío", "category": "Propóleo", "product_type": "Insumo", "stock": 500.0, "min_stock": 50, "price": 0.50},
                {"sku": "INS003", "name": "Tapa para Frasco", "desc": "Tapa plástica color amarillo", "category": "Propóleo", "product_type": "Insumo", "stock": 500.0, "min_stock": 50, "price": 0.10}
            ]
            for ins in insumos:
                cur.execute("SELECT id FROM products WHERE sku = %s", (ins["sku"],))
                if not cur.fetchone():
                    cur.execute(
                        """
                        INSERT INTO products (
                            sku, name, description, photo_url, barcode, internal_code,
                            category, product_type, created_at
                        ) VALUES (%s, %s, %s, '', '', %s, %s, %s, %s)
                        """,
                        (
                            ins["sku"],
                            ins["name"],
                            ins["desc"],
                            ins["sku"],
                            ins["category"],
                            ins["product_type"],
                            datetime.utcnow().isoformat(timespec='seconds')
                        )
                    )
            
            # Sembrar en inventory_items (page_data) si no existen
            cur.execute("SELECT json FROM page_data WHERE key = 'inventory_items'")
            row = cur.fetchone()
            if row:
                inv_items = json.loads(row["json"])
                existing_codes = {item.get("code") for item in inv_items}
                updated_inv = False
                for ins in insumos:
                    if ins["sku"] not in existing_codes:
                        inv_items.append({
                            "code": ins["sku"],
                            "name": ins["name"],
                            "desc": ins["desc"],
                            "category": ins["category"],
                            "stock": ins["stock"],
                            "min_stock": ins["min_stock"],
                            "price": ins["price"],
                            "status": "Normal",
                            "stock_percent": 100
                        })
                        updated_inv = True
                if updated_inv:
                    cur.execute(
                        "UPDATE page_data SET json = %s WHERE key = 'inventory_items'",
                        (json.dumps(inv_items, ensure_ascii=False),)
                    )
        conn.commit()



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


def list_products() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, sku, name, description, photo_url, barcode, internal_code,
                       category, expiry_date, width_cm, height_cm, depth_cm, weight_kg, product_type, cost
                FROM products
                WHERE is_deleted = FALSE OR is_deleted IS NULL
                ORDER BY id DESC
                """
            )
            return [dict(row) for row in cur.fetchall()]


def insert_product(product: dict) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO products (
                    sku, name, description, photo_url, barcode, internal_code,
                    category, expiry_date, width_cm, height_cm, depth_cm,
                    weight_kg, product_type, cost, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    product.get("weight_kg"),
                    product.get("product_type", "Final"),
                    product.get("cost", 0.0),
                    product["created_at"],
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
                       category, expiry_date, width_cm, height_cm, depth_cm, weight_kg, product_type, cost
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
            cur.execute(
                """
                UPDATE products SET
                    sku = %s, name = %s, description = %s, photo_url = %s,
                    barcode = %s, internal_code = %s, category = %s, expiry_date = %s,
                    width_cm = %s, height_cm = %s, depth_cm = %s, weight_kg = %s,
                    product_type = %s, cost = %s
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
                    product.get("weight_kg"),
                    product.get("product_type", "Final"),
                    product.get("cost", 0.0),
                    product_id,
                ),
            )
        conn.commit()


def delete_product(product_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE products SET is_deleted = TRUE WHERE id = %s", (product_id,))
        conn.commit()

# Funciones para Roles
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


# Funciones para Usuarios
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
                    user.get("password", "password123"),
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


# === Sales Functions ===

def list_sales(filters: dict = None) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT s.id, s.sale_number, s.customer_name, s.customer_email, s.customer_initials,
                       s.sale_date, s.sale_time, s.products_json, s.total_amount, s.status,
                       s.seller_name, s.seller_initials, s.payment_method, s.payment_status,
                       s.delivery_status, s.notes, s.created_at,
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
            
            query += " ORDER BY (s.sale_date || ' ' || s.sale_time)::timestamp DESC, s.id DESC"
            
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
            query += " ORDER BY (sale_date || ' ' || sale_time)::timestamp DESC, id DESC"
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
            query += " ORDER BY (sale_date || ' ' || sale_time)::timestamp DESC, id DESC"
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
                       delivery_status, notes, created_at
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


def insert_sale(sale: dict) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sales (
                    sale_number, customer_name, customer_email, customer_initials,
                    sale_date, sale_time, products_json, total_amount, status,
                    seller_name, seller_initials, payment_method, payment_status,
                    delivery_status, notes, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    sale["created_at"],
                ),
            )
            inserted_id = cur.fetchone()["id"]
        conn.commit()
        return inserted_id


def update_sale(sale_id: int, sale: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sales SET
                    customer_name = %s, customer_email = %s, customer_initials = %s,
                    sale_date = %s, sale_time = %s, products_json = %s, total_amount = %s,
                    status = %s, seller_name = %s, seller_initials = %s,
                    payment_method = %s, payment_status = %s, delivery_status = %s, notes = %s
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
                    sale_id,
                ),
            )
        conn.commit()


def delete_sale(sale_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sales WHERE id = %s", (sale_id,))
        conn.commit()


# === Bank Accounts Functions ===

def list_bank_accounts() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, bank_name, account_number, account_type, holder_name, holder_rut, email, status, created_at
                FROM bank_accounts
                ORDER BY id DESC
                """
            )
            return [dict(row) for row in cur.fetchall()]


def get_bank_account(account_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, bank_name, account_number, account_type, holder_name, holder_rut, email, status, created_at
                FROM bank_accounts
                WHERE id = %s
                """,
                (account_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None


def insert_bank_account(account: dict) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bank_accounts (bank_name, account_number, account_type, holder_name, holder_rut, email, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    account["bank_name"],
                    account["account_number"],
                    account["account_type"],
                    account["holder_name"],
                    account.get("holder_rut", ""),
                    account.get("email", ""),
                    account.get("status", "Activa")
                )
            )
            inserted_id = cur.fetchone()["id"]
        conn.commit()
        return inserted_id


def update_bank_account(account_id: int, account: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE bank_accounts SET
                    bank_name = %s, account_number = %s, account_type = %s,
                    holder_name = %s, holder_rut = %s, email = %s, status = %s
                WHERE id = %s
                """,
                (
                    account["bank_name"],
                    account["account_number"],
                    account["account_type"],
                    account["holder_name"],
                    account.get("holder_rut", ""),
                    account.get("email", ""),
                    account.get("status", "Activa"),
                    account_id
                )
            )
        conn.commit()


def delete_bank_account(account_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM bank_accounts WHERE id = %s", (account_id,))
        conn.commit()


def get_sale_payments_map() -> dict[int, dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sale_id, invoice_number, invoice_amount, invoice_due_date, invoice_file, payment_proof_file, payment_amount, payment_date,
                       seller_uploaded_at, payment_uploaded_at, accounting_approved, accounting_approved_by,
                       accounting_approved_at, accounting_comment, status, created_at, updated_at
                FROM sale_payments
                """
            )
            rows = cur.fetchall()
            return {row["sale_id"]: dict(row) for row in rows}


def get_sale_payment(sale_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sale_id, invoice_number, invoice_amount, invoice_due_date, invoice_file, payment_proof_file, payment_amount, payment_date,
                       seller_uploaded_at, payment_uploaded_at, accounting_approved, accounting_approved_by,
                       accounting_approved_at, accounting_comment, status, created_at, updated_at
                FROM sale_payments
                WHERE sale_id = %s
                """,
                (sale_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def upsert_sale_payment(sale_id: int, payment: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'sale_payments'
                """
            )
            payment_columns = {row["column_name"] for row in cur.fetchall()}
            has_invoice_number = "invoice_number" in payment_columns
            has_accounting_comment = "accounting_comment" in payment_columns
            has_invoice_due_date = "invoice_due_date" in payment_columns
            has_payment_date = "payment_date" in payment_columns
            has_invoice_amount = "invoice_amount" in payment_columns
            has_payment_amount = "payment_amount" in payment_columns
            
            cur.execute(
                "SELECT id FROM sale_payments WHERE sale_id = %s",
                (sale_id,),
            )
            existing = cur.fetchone()
            if existing:
                if has_invoice_number:
                    cur.execute(
                        """
                        UPDATE sale_payments
                        SET invoice_number = %s, invoice_amount = %s, invoice_due_date = %s, invoice_file = %s, payment_proof_file = %s, payment_amount = %s, payment_date = %s, seller_uploaded_at = %s,
                            payment_uploaded_at = %s, accounting_approved = %s, accounting_approved_by = %s,
                            accounting_approved_at = %s, accounting_comment = %s, status = %s, updated_at = %s
                        WHERE sale_id = %s
                        """,
                        (
                            payment.get("invoice_number"),
                            payment.get("invoice_amount"),
                            payment.get("invoice_due_date"),
                            payment.get("invoice_file"),
                            payment.get("payment_proof_file"),
                            payment.get("payment_amount"),
                            payment.get("payment_date"),
                            payment.get("seller_uploaded_at"),
                            payment.get("payment_uploaded_at"),
                            payment.get("accounting_approved", 0),
                            payment.get("accounting_approved_by"),
                            payment.get("accounting_approved_at"),
                            payment.get("accounting_comment"),
                            payment.get("status", "Factura pendiente"),
                            payment.get("updated_at"),
                            sale_id,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE sale_payments
                        SET invoice_amount = %s, invoice_due_date = %s, invoice_file = %s, payment_proof_file = %s, payment_amount = %s, payment_date = %s, seller_uploaded_at = %s,
                            payment_uploaded_at = %s, accounting_approved = %s, accounting_approved_by = %s,
                            accounting_approved_at = %s, accounting_comment = %s, status = %s, updated_at = %s
                        WHERE sale_id = %s
                        """,
                        (
                            payment.get("invoice_amount"),
                            payment.get("invoice_due_date"),
                            payment.get("invoice_file"),
                            payment.get("payment_proof_file"),
                            payment.get("payment_amount"),
                            payment.get("payment_date"),
                            payment.get("seller_uploaded_at"),
                            payment.get("payment_uploaded_at"),
                            payment.get("accounting_approved", 0),
                            payment.get("accounting_approved_by"),
                            payment.get("accounting_approved_at"),
                            payment.get("accounting_comment"),
                            payment.get("status", "Factura pendiente"),
                            payment.get("updated_at"),
                            sale_id,
                        ),
                    )
            else:
                cur.execute(
                    """
                    INSERT INTO sale_payments (
                        sale_id, invoice_file, payment_proof_file, seller_uploaded_at,
                        payment_uploaded_at, accounting_approved, accounting_approved_by,
                        accounting_approved_at, status, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        sale_id,
                        payment.get("invoice_file"),
                        payment.get("payment_proof_file"),
                        payment.get("seller_uploaded_at"),
                        payment.get("payment_uploaded_at"),
                        payment.get("accounting_approved", 0),
                        payment.get("accounting_approved_by"),
                        payment.get("accounting_approved_at"),
                        payment.get("status", "Factura pendiente"),
                        payment.get("created_at"),
                        payment.get("updated_at"),
                    ),
                )
                if has_invoice_number:
                    cur.execute(
                        "UPDATE sale_payments SET invoice_number = %s WHERE sale_id = %s",
                        (payment.get("invoice_number"), sale_id),
                    )
                if has_invoice_amount:
                    cur.execute(
                        "UPDATE sale_payments SET invoice_amount = %s WHERE sale_id = %s",
                        (payment.get("invoice_amount"), sale_id),
                    )
                if has_payment_amount:
                    cur.execute(
                        "UPDATE sale_payments SET payment_amount = %s WHERE sale_id = %s",
                        (payment.get("payment_amount"), sale_id),
                    )
                if has_invoice_due_date:
                    cur.execute(
                        "UPDATE sale_payments SET invoice_due_date = %s WHERE sale_id = %s",
                        (payment.get("invoice_due_date"), sale_id),
                    )
                if has_payment_date:
                    cur.execute(
                        "UPDATE sale_payments SET payment_date = %s WHERE sale_id = %s",
                        (payment.get("payment_date"), sale_id),
                    )
                if has_accounting_comment:
                    cur.execute(
                        "UPDATE sale_payments SET accounting_comment = %s WHERE sale_id = %s",
                        (payment.get("accounting_comment"), sale_id),
                    )
        conn.commit()


def list_sale_payment_items(sale_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'sale_payment_items'
                """
            )
            cols = [r["column_name"] for r in cur.fetchall()]
            has_approval = "accounting_approved" in cols
            if has_approval:
                select_cols = "id, sale_id, payment_amount, payment_date, payment_proof_file, created_at, accounting_approved, accounting_approved_by, accounting_approved_at, accounting_comment"
            else:
                select_cols = "id, sale_id, payment_amount, payment_date, payment_proof_file, created_at"
            
            cur.execute(
                f"SELECT {select_cols} FROM sale_payment_items WHERE sale_id = %s ORDER BY created_at ASC",
                (sale_id,),
            )
            rows = cur.fetchall()
            items = [dict(row) for row in rows]
            for it in items:
                if not has_approval:
                    it["accounting_approved"] = 0
                    it["accounting_approved_by"] = None
                    it["accounting_approved_at"] = None
                    it["accounting_comment"] = None
                else:
                    it["accounting_approved"] = 1 if it.get("accounting_approved") else 0
            return items


def update_sale_payment_item_approval(item_id: int, approved: bool, approved_by: str, approved_at: str, comment: str = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sale_payment_items
                SET accounting_approved = %s, accounting_approved_by = %s, accounting_approved_at = %s, accounting_comment = %s
                WHERE id = %s
                """,
                (1 if approved else 0, approved_by if approved else None, approved_at if approved else None, comment, item_id),
            )
        conn.commit()


def insert_sale_payment_item(item: dict) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sale_payment_items (sale_id, payment_amount, payment_date, payment_proof_file, created_at, bank_account_id)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (
                    item["sale_id"],
                    item["payment_amount"],
                    item.get("payment_date"),
                    item.get("payment_proof_file"),
                    item["created_at"],
                    item.get("bank_account_id"),
                ),
            )
            inserted_id = cur.fetchone()["id"]
        conn.commit()
        return inserted_id


def update_sale_payment_item_proof(item_id: int, proof_file: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sale_payment_items SET payment_proof_file = %s WHERE id = %s",
                (proof_file, item_id),
            )
        conn.commit()


def update_sale_payment_item_amount_date(item_id: int, payment_amount: float, payment_date: str = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sale_payment_items SET payment_amount = %s, payment_date = %s WHERE id = %s",
                (payment_amount, payment_date or None, item_id),
            )
        conn.commit()


def delete_sale_payment_item(item_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sale_payment_items WHERE id = %s", (item_id,))
        conn.commit()


def get_sale_payment_items_totals(sale_ids: list[int]) -> dict[int, float]:
    if not sale_ids:
        return {}
    placeholders = ",".join(["%s"] * len(sale_ids))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT sale_id, COALESCE(SUM(payment_amount), 0) as total_paid
                FROM sale_payment_items
                WHERE sale_id IN ({placeholders})
                GROUP BY sale_id
                """,
                tuple(sale_ids),
            )
            rows = cur.fetchall()
            return {row["sale_id"]: row["total_paid"] for row in rows}


def get_sales_metrics() -> dict:
    """Calcula las métricas principales del dashboard y sus tendencias reales calculadas."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            now = datetime.now()
            today_str = now.strftime('%Y-%m-%d')
            yesterday_str = (now - timedelta(days=1)).strftime('%Y-%m-%d')
            cur_month_str = now.strftime('%Y-%m')
            prev_month_date = (now.replace(day=1) - timedelta(days=1))
            prev_month_str = prev_month_date.strftime('%Y-%m')

            # 1. Ventas hoy vs ayer
            cur.execute(
                "SELECT COALESCE(SUM(total_amount), 0) as total FROM sales WHERE sale_date = %s AND status NOT IN ('Cancelada', 'Cotización') AND sale_number LIKE 'VTA-%%'",
                (today_str,)
            )
            row_today = cur.fetchone()
            total_today = float(row_today["total"]) if row_today else 0.0

            cur.execute(
                "SELECT COALESCE(SUM(total_amount), 0) as total FROM sales WHERE sale_date = %s AND status NOT IN ('Cancelada', 'Cotización') AND sale_number LIKE 'VTA-%%'",
                (yesterday_str,)
            )
            row_yesterday = cur.fetchone()
            total_yesterday = float(row_yesterday["total"]) if row_yesterday else 0.0

            if total_yesterday > 0:
                diff_pct = round(((total_today - total_yesterday) / total_yesterday) * 100, 1)
                ventas_trend_text = f"{'+' if diff_pct > 0 else ''}{diff_pct:.1f}% vs ayer"
                ventas_trend_type = "positive" if diff_pct >= 0 else "negative"
            elif total_today > 0:
                ventas_trend_text = "+100% vs ayer"
                ventas_trend_type = "positive"
            else:
                ventas_trend_text = "0% vs ayer"
                ventas_trend_type = "neutral"

            # 2. Stock total y productos con bajo stock
            cur.execute("SELECT json FROM page_data WHERE key = 'inventory_items'")
            row_inv = cur.fetchone()
            items = []
            if row_inv and row_inv["json"]:
                try:
                    items = json.loads(row_inv["json"])
                except Exception:
                    items = []
            
            total_stock = sum(int(it.get("stock", 0)) for it in items)
            low_stock_count = sum(1 for it in items if int(it.get("stock", 0)) <= int(it.get("min_stock", 10)))
            
            if low_stock_count > 0:
                stock_trend_text = f"{low_stock_count} bajo stock"
                stock_trend_type = "warning"
            else:
                stock_trend_text = "Stock óptimo"
                stock_trend_type = "positive"

            # 3. Órdenes pendientes vs total
            cur.execute(
                "SELECT COUNT(*) as count FROM sales WHERE status = 'Pendiente' AND sale_number LIKE 'VTA-%%'"
            )
            row_pend = cur.fetchone()
            total_pending = int(row_pend["count"]) if row_pend else 0

            cur.execute(
                "SELECT COUNT(*) as count FROM sales WHERE status NOT IN ('Cancelada', 'Cotización') AND sale_number LIKE 'VTA-%%'"
            )
            row_tot_ord = cur.fetchone()
            total_orders = int(row_tot_ord["count"]) if row_tot_ord else 0

            if total_orders > 0 and total_pending > 0:
                pct_pend = round((total_pending / total_orders) * 100, 1)
                pend_trend_text = f"{pct_pend:.0f}% del total"
                pend_trend_type = "negative" if pct_pend > 50 else "warning"
            elif total_pending == 0:
                pend_trend_text = "Al día (0)"
                pend_trend_type = "positive"
            else:
                pend_trend_text = f"{total_pending} activas"
                pend_trend_type = "warning"

            # 4. Clientes activos y compras recientes (últimos 60 días)
            cur.execute(
                "SELECT COUNT(*) as count FROM clients"
            )
            row_cli = cur.fetchone()
            total_customers = int(row_cli["count"]) if row_cli else 0

            since_60d = (now - timedelta(days=60)).strftime('%Y-%m-%d')
            cur.execute(
                "SELECT COUNT(DISTINCT customer_name) as count FROM sales WHERE sale_number LIKE 'VTA-%%' AND sale_date >= %s",
                (since_60d,)
            )
            row_rec = cur.fetchone()
            recent_active = int(row_rec["count"]) if row_rec else 0

            if total_customers > 0:
                cli_trend_text = f"100% activos"
                cli_trend_type = "positive"
            else:
                cli_trend_text = "0 registrados"
                cli_trend_type = "neutral"

            return {
                "ventas_hoy": round(float(total_today), 2),
                "ventas_hoy_trend": {"text": ventas_trend_text, "type": ventas_trend_type},
                "productos_stock": total_stock,
                "productos_stock_trend": {"text": stock_trend_text, "type": stock_trend_type},
                "ordenes_pendientes": total_pending,
                "ordenes_pendientes_trend": {"text": pend_trend_text, "type": pend_trend_type},
                "clientes_activos": total_customers,
                "clientes_activos_trend": {"text": cli_trend_text, "type": cli_trend_type},
                "ventas_completadas": total_orders - total_pending,
            }


def get_sales_chart_data(year: int = None, period: str = "6months") -> dict:
    """Obtiene los datos mensuales de ventas para el gráfico de barras del Dashboard."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if year:
                cur.execute(
                    """
                    SELECT TO_CHAR(sale_date::date, 'YYYY-MM') as month,
                           COALESCE(SUM(total_amount), 0) as total
                    FROM sales
                    WHERE TO_CHAR(sale_date::date, 'YYYY') = %s AND status NOT IN ('Cancelada', 'Cotización') AND sale_number LIKE 'VTA-%%'
                    GROUP BY month
                    ORDER BY month ASC
                    """,
                    (str(year),)
                )
                rows = cur.fetchall()
            else:
                limit = 12 if period == "12months" else 6
                cur.execute(
                    """
                    SELECT TO_CHAR(sale_date::date, 'YYYY-MM') as month,
                           COALESCE(SUM(total_amount), 0) as total
                    FROM sales
                    WHERE status NOT IN ('Cancelada', 'Cotización') AND sale_number LIKE 'VTA-%%'
                    GROUP BY month
                    ORDER BY month DESC
                    LIMIT %s
                    """,
                    (limit,)
                )
                rows = cur.fetchall()
                rows = list(reversed(rows))
            
            months = []
            amounts = []
            month_names = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
            
            for row in rows:
                if row.get('month'):
                    try:
                        parts = row['month'].split('-')
                        month_num = int(parts[1])
                        months.append(f"{month_names[month_num - 1]} {parts[0]}")
                        amounts.append(round(float(row['total'] or 0), 2))
                    except Exception:
                        pass
            
            return {"labels": months, "data": amounts}


def get_top_products(year: int = None, period: str = "year") -> dict:
    """Calcula los 5 productos más vendidos agrupados por cantidad (soporta formato JSON dict y string)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if year:
                cur.execute(
                    """
                    SELECT products_json
                    FROM sales
                    WHERE TO_CHAR(sale_date::date, 'YYYY') = %s AND status NOT IN ('Cancelada', 'Cotización') AND sale_number LIKE 'VTA-%%'
                    """,
                    (str(year),)
                )
                rows = cur.fetchall()
            elif period == "month":
                current_month = datetime.now().strftime('%Y-%m')
                cur.execute(
                    """
                    SELECT products_json
                    FROM sales
                    WHERE TO_CHAR(sale_date::date, 'YYYY-MM') = %s AND status NOT IN ('Cancelada', 'Cotización') AND sale_number LIKE 'VTA-%%'
                    """,
                    (current_month,)
                )
                rows = cur.fetchall()
            else:
                cur.execute(
                    """
                    SELECT products_json
                    FROM sales
                    WHERE status NOT IN ('Cancelada', 'Cotización') AND sale_number LIKE 'VTA-%%'
                    """
                )
                rows = cur.fetchall()
            
            product_counts = {}
            for row in rows:
                p_raw = row.get('products_json')
                if not p_raw:
                    continue
                if isinstance(p_raw, str):
                    try:
                        products = json.loads(p_raw)
                    except Exception:
                        products = []
                elif isinstance(p_raw, list):
                    products = p_raw
                else:
                    products = []

                if isinstance(products, dict):
                    products = [products]

                for item in products:
                    if isinstance(item, dict):
                        name = item.get('product_name') or item.get('name') or item.get('sku') or 'Producto'
                        try:
                            qty = int(item.get('quantity', 1))
                        except Exception:
                            qty = 1
                    elif isinstance(item, str):
                        name = item.split('(')[0].strip()
                        try:
                            qty = int(item.split('(')[1].split(')')[0])
                        except Exception:
                            qty = 1
                    else:
                        continue
                    
                    if name:
                        product_counts[name] = product_counts.get(name, 0) + qty
            
            sorted_products = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            
            labels = [p[0] for p in sorted_products]
            data = [p[1] for p in sorted_products]
            
            return {"labels": labels, "data": data}


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
                    datetime.utcnow().isoformat(timespec='seconds'),
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


# ==========================================
# GESTIÓN DE ÓRDENES DE COMPRA (OC) Y RECEPCIÓN
# ==========================================

def get_next_oc_number() -> str:
    """Genera el siguiente número correlativo único para una OC"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM purchase_orders ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            next_id = (row["id"] + 1) if row else 1
            return f"OC-{next_id:05d}"

def create_purchase_order(supplier_id: int, order_date: str, notes: str, items: list[dict], status: str = "Emitida", created_by: int = None, payment_method: str = "Efectivo") -> str:
    """Crea una Orden de Compra completa en la base de datos"""
    oc_num = get_next_oc_number()
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Calcular total
            total_amount = sum(item["quantity"] * item["unit_price"] for item in items)
            
            # Insertar cabecera de la OC
            cur.execute(
                """
                INSERT INTO purchase_orders (oc_number, supplier_id, order_date, status, total_amount, notes, created_by, payment_method, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (oc_num, supplier_id, order_date, status, total_amount, notes, created_by, payment_method or 'Efectivo', datetime.utcnow().isoformat(timespec='seconds'))
            )
            po_id = cur.fetchone()["id"]
            
            # Insertar ítems
            for item in items:
                line_total = item["quantity"] * item["unit_price"]
                cur.execute(
                    """
                    INSERT INTO purchase_order_items (purchase_order_id, product_id, quantity_ordered, quantity_received, unit_price, total_price)
                    VALUES (%s, %s, %s, 0, %s, %s)
                    """,
                    (po_id, item["product_id"], item["quantity"], item["unit_price"], line_total)
                )
        conn.commit()
    return oc_num

def update_purchase_order(po_id: int, supplier_id: int, order_date: str, notes: str, items: list[dict], status: str = "Borrador", payment_method: str = "Efectivo") -> None:
    """Actualiza una Orden de Compra (borrador) y sus ítems en la base de datos"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Calcular total
            total_amount = sum(item["quantity"] * item["unit_price"] for item in items)
            
            # Actualizar cabecera
            cur.execute(
                """
                UPDATE purchase_orders
                SET supplier_id = %s, order_date = %s, status = %s, total_amount = %s, notes = %s, payment_method = %s
                WHERE id = %s
                """,
                (supplier_id, order_date, status, total_amount, notes, payment_method or 'Efectivo', po_id)
            )
            
            # Eliminar ítems anteriores para reinsertar los actualizados
            cur.execute("DELETE FROM purchase_order_items WHERE purchase_order_id = %s", (po_id,))
            
            # Insertar ítems actualizados
            for item in items:
                line_total = item["quantity"] * item["unit_price"]
                cur.execute(
                    """
                    INSERT INTO purchase_order_items (purchase_order_id, product_id, quantity_ordered, quantity_received, unit_price, total_price)
                    VALUES (%s, %s, %s, 0, %s, %s)
                    """,
                    (po_id, item["product_id"], item["quantity"], item["unit_price"], line_total)
                )
        conn.commit()

def list_purchase_orders() -> list[dict]:
    """Lista todas las Órdenes de Compra con creadores, aprobadores y facturas asociadas"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT po.id, po.oc_number, po.order_date, po.status, po.total_amount, po.notes, po.supplier_id, po.payment_method,
                       s.name as supplier_name,
                       u1.full_name as creator_name,
                       u2.full_name as approver_name,
                       COALESCE(
                           (
                               SELECT json_agg(json_build_object(
                                   'id', pi.id,
                                   'invoice_number', pi.invoice_number,
                                   'payment_status', pi.payment_status,
                                   'invoice_amount', pi.invoice_amount,
                                   'due_date', pi.due_date,
                                   'document_file', pi.document_file,
                                   'payment_date', pi.payment_date,
                                   'payment_amount', pi.payment_amount,
                                   'payment_method', pi.payment_method,
                                   'bank_name', ba.bank_name,
                                   'account_number', ba.account_number
                               ))
                               FROM purchase_invoices pi
                               LEFT JOIN bank_accounts ba ON ba.id = pi.bank_account_id
                               WHERE pi.purchase_order_id = po.id
                                  OR pi.inventory_entry_id IN (SELECT id FROM inventory_entries WHERE purchase_order_id = po.id)
                           ), '[]'::json
                       ) AS invoices
                FROM purchase_orders po
                JOIN suppliers s ON po.supplier_id = s.id
                LEFT JOIN users u1 ON po.created_by = u1.id
                LEFT JOIN users u2 ON po.approved_by = u2.id
                ORDER BY po.id DESC
                """
            )
            return [dict(row) for row in cur.fetchall()]

def get_purchase_order(po_id: int) -> dict | None:
    """Obtiene la cabecera e información de una OC, incluyendo facturas asociadas"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT po.id, po.oc_number, po.order_date, po.status, po.total_amount, po.notes, po.supplier_id, po.payment_method,
                       s.name as supplier_name, s.description as supplier_description, s.website as supplier_website,
                       u1.full_name as creator_name,
                       u2.full_name as approver_name,
                       COALESCE(
                           (
                               SELECT json_agg(json_build_object(
                                   'id', pi.id,
                                   'invoice_number', pi.invoice_number,
                                   'payment_status', pi.payment_status,
                                   'invoice_amount', pi.invoice_amount,
                                   'due_date', pi.due_date,
                                   'document_file', pi.document_file,
                                   'payment_date', pi.payment_date,
                                   'payment_amount', pi.payment_amount,
                                   'payment_method', pi.payment_method,
                                   'bank_name', ba.bank_name,
                                   'account_number', ba.account_number
                               ))
                               FROM purchase_invoices pi
                               LEFT JOIN bank_accounts ba ON ba.id = pi.bank_account_id
                               WHERE pi.purchase_order_id = po.id
                                  OR pi.inventory_entry_id IN (SELECT id FROM inventory_entries WHERE purchase_order_id = po.id)
                           ), '[]'::json
                       ) AS invoices
                FROM purchase_orders po
                JOIN suppliers s ON po.supplier_id = s.id
                LEFT JOIN users u1 ON po.created_by = u1.id
                LEFT JOIN users u2 ON po.approved_by = u2.id
                WHERE po.id = %s
                """,
                (po_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None

def approve_purchase_order(po_id: int, user_id: int) -> None:
    """Aprueba una Orden de Compra cambiando su estado a 'Emitida' e indicando quién la aprobó"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE purchase_orders
                SET status = 'Emitida', approved_by = %s
                WHERE id = %s
                """,
                (user_id, po_id)
            )
        conn.commit()

def get_purchase_order_items(po_id: int) -> list[dict]:
    """Obtiene los productos asociados a una OC"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT poi.id, poi.product_id, poi.quantity_ordered, poi.quantity_received, poi.unit_price, poi.total_price,
                       p.name as product_name, p.sku as product_sku
                FROM purchase_order_items poi
                JOIN products p ON poi.product_id = p.id
                WHERE poi.purchase_order_id = %s
                ORDER BY p.name
                """,
                (po_id,)
            )
            return [dict(row) for row in cur.fetchall()]

def list_active_purchase_orders_by_supplier(supplier_id: int) -> list[dict]:
    """Lista las OC pendientes de recibir de un proveedor"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, oc_number, order_date, total_amount, status
                FROM purchase_orders
                WHERE supplier_id = %s AND status IN ('Emitida', 'Parcialmente Recibida')
                ORDER BY oc_number
                """,
                (supplier_id,)
            )
            return [dict(row) for row in cur.fetchall()]

def register_inventory_entry(
    po_id: int, order_number: str, entry_date: str,
    warehouse: str, notes: str, items: list,
    document_type: str = 'guia_despacho',
    document_number: str = '',
    document_file: str = None,
) -> int:
    """Registra el ingreso de mercadería cruzando cantidades contra la OC y actualizando stock.
    Retorna el id del registro creado."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, supplier_id FROM purchase_orders WHERE id = %s", (po_id,))
            po = cur.fetchone()
            if not po:
                raise ValueError("Orden de Compra no encontrada.")

            supplier_id  = po["supplier_id"]
            total_amount = sum(item["quantity"] * item["unit_price"] for item in items)

            # 1. Registrar cabecera del ingreso
            cur.execute(
                """
                INSERT INTO inventory_entries
                    (entry_date, order_number, purchase_order_id, supplier_id,
                     warehouse, notes, total_amount, created_at,
                     document_type, document_number, document_file)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (entry_date, order_number, po_id, supplier_id,
                 warehouse, notes, total_amount, datetime.utcnow().isoformat(timespec='seconds'),
                 document_type, document_number, document_file)
            )
            entry_id = cur.fetchone()["id"]

            # 2. Guardar items del ingreso, validar límites y actualizar OC
            for item in items:
                prod_id    = item["product_id"]
                qty        = item["quantity"]
                price      = item["unit_price"]
                line_total = qty * price

                cur.execute(
                    """
                    SELECT id, quantity_ordered, quantity_received
                    FROM purchase_order_items
                    WHERE purchase_order_id = %s AND product_id = %s
                    """,
                    (po_id, prod_id)
                )
                po_item = cur.fetchone()
                if not po_item:
                    raise ValueError(f"El producto con ID {prod_id} no está en la Orden de Compra.")

                pending = po_item["quantity_ordered"] - po_item["quantity_received"]
                if qty > pending:
                    raise ValueError(f"No puedes ingresar {qty} unidades. El máximo pendiente en la OC es {pending}.")

                cur.execute(
                    """
                    INSERT INTO inventory_entry_items (inventory_entry_id, product_id, quantity, unit_price, total)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (entry_id, prod_id, qty, price, line_total)
                )

                new_received = po_item["quantity_received"] + qty
                cur.execute(
                    "UPDATE purchase_order_items SET quantity_received = %s WHERE id = %s",
                    (new_received, po_item["id"])
                )

                avg_cost = get_product_calculated_cost(prod_id)
                if avg_cost and avg_cost > 0:
                    cur.execute("UPDATE products SET cost = %s WHERE id = %s", (avg_cost, prod_id))

            # 3. Actualizar estado de la OC
            cur.execute(
                """
                SELECT SUM(quantity_ordered) as total_ord, SUM(quantity_received) as total_rec
                FROM purchase_order_items WHERE purchase_order_id = %s
                """,
                (po_id,)
            )
            summary       = cur.fetchone()
            total_ordered = summary["total_ord"] or 0
            total_received = summary["total_rec"] or 0

            if total_received >= total_ordered:
                new_status = "Recibida"
            elif total_received > 0:
                new_status = "Parcialmente Recibida"
            else:
                new_status = "Emitida"

            cur.execute("UPDATE purchase_orders SET status = %s WHERE id = %s", (new_status, po_id))
        conn.commit()
        return entry_id


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

def list_inventory_entries() -> list[dict]:
    """Obtiene los ingresos de mercadería recientes"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ie.id, ie.entry_date as date, ie.order_number, ie.warehouse, ie.notes, ie.total_amount,
                       s.name as supplier, po.oc_number,
                       (SELECT COUNT(*) FROM inventory_entry_items WHERE inventory_entry_id = ie.id) as items_count
                FROM inventory_entries ie
                JOIN suppliers s ON ie.supplier_id = s.id
                LEFT JOIN purchase_orders po ON ie.purchase_order_id = po.id
                ORDER BY ie.id DESC
                """
            )
            records = []
            for row in cur.fetchall():
                r = dict(row)
                r["total"] = f"${r['total_amount']:,.2f}"
                r["status"] = "Completado"
                records.append(r)
            return records


def get_income_report_data() -> dict:
    """Calcula datos financieros de Ingresos: pagos históricos realizados y compromisos de cobros futuros."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT s.id, s.sale_number, s.customer_name, s.sale_date, s.total_amount, s.status, s.payment_status,
                       sp.invoice_due_date, sp.payment_date, sp.payment_amount
                FROM sales s
                LEFT JOIN sale_payments sp ON sp.sale_id = s.id
                WHERE s.status NOT IN ('Cancelada', 'Cancelado', 'Cotización')
                ORDER BY s.sale_date ASC
            """
            cur.execute(query)
            sales = cur.fetchall()

    today_str = datetime.now().strftime('%Y-%m-%d')
    
    month_names = {
        "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
        "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
        "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
    }

    monthly_summary = {}
    
    total_historico = 0.0
    total_futuro = 0.0
    monto_retrasado = 0.0
    count_retrasados = 0
    
    futuros_detalles = []
    historicos_detalles = []

    for sale in sales:
        total = float(sale.get("total_amount") or 0.0)
        p_status = sale.get("payment_status") or "Pendiente"
        sale_date = str(sale.get("sale_date") or "")[:10]
        due_date = str(sale.get("invoice_due_date") or "")[:10]
        payment_date = str(sale.get("payment_date") or "")[:10]
        
        if p_status == "Pagado":
            monto_pago = float(sale.get("payment_amount") or total)
            target_month = payment_date[:7] if len(payment_date) >= 7 else (sale_date[:7] if len(sale_date) >= 7 else today_str[:7])
            
            total_historico += monto_pago
            
            if target_month not in monthly_summary:
                y, m = target_month.split("-") if "-" in target_month else (today_str[:4], today_str[5:7])
                monthly_summary[target_month] = {
                    "month_key": target_month,
                    "label": f"{month_names.get(m, m)} {y}",
                    "realizado": 0.0,
                    "comprometido": 0.0,
                }
            monthly_summary[target_month]["realizado"] += monto_pago
            
            historicos_detalles.append({
                "sale_number": sale["sale_number"],
                "customer_name": sale["customer_name"],
                "sale_date": sale_date,
                "payment_date": payment_date or sale_date,
                "monto": monto_pago,
                "status": "Pagado"
            })
        else:
            target_due = due_date if (due_date and due_date != "-") else sale_date
            target_month = target_due[:7] if len(target_due) >= 7 else today_str[:7]
            
            total_futuro += total
            
            is_overdue = False
            if target_due and target_due != "-" and target_due < today_str:
                is_overdue = True
                monto_retrasado += total
                count_retrasados += 1

            if target_month not in monthly_summary:
                y, m = target_month.split("-") if "-" in target_month else (today_str[:4], today_str[5:7])
                monthly_summary[target_month] = {
                    "month_key": target_month,
                    "label": f"{month_names.get(m, m)} {y}",
                    "realizado": 0.0,
                    "comprometido": 0.0,
                }
            monthly_summary[target_month]["comprometido"] += total

            futuros_detalles.append({
                "sale_number": sale["sale_number"],
                "customer_name": sale["customer_name"],
                "sale_date": sale_date,
                "due_date": target_due,
                "monto": total,
                "status": "Retrasada" if is_overdue else "Pendiente",
                "is_overdue": is_overdue
            })

    sorted_months_keys = sorted(monthly_summary.keys())
    chart_labels = [monthly_summary[k]["label"] for k in sorted_months_keys]
    chart_realizados = [round(monthly_summary[k]["realizado"], 2) for k in sorted_months_keys]
    chart_comprometidos = [round(monthly_summary[k]["comprometido"], 2) for k in sorted_months_keys]
    
    table_months = [monthly_summary[k] for k in sorted_months_keys]

    return {
        "total_historico": round(total_historico, 2),
        "total_futuro": round(total_futuro, 2),
        "total_proyectado": round(total_historico + total_futuro, 2),
        "monto_retrasado": round(monto_retrasado, 2),
        "count_retrasados": count_retrasados,
        "chart_labels": chart_labels,
        "chart_realizados": chart_realizados,
        "chart_comprometidos": chart_comprometidos,
        "table_months": table_months,
        "futuros_detalles": futuros_detalles,
        "historicos_detalles": historicos_detalles
    }


def get_cash_flow_data() -> dict:
    """
    Calcula el Flujo de Caja mensual real + proyección 6 meses futuros.
    - Ingresos: pagos cobrados reales (sale_payments con payment_date confirmado).
    - Gastos: recepciones de mercadería (inventory_entries).
    - Impagas: facturas de ventas pendientes de cobro, agrupadas por fecha de vencimiento.
    - Proyección: promedio de los últimos 3 meses con datos + compromisos ya registrados.
    """
    from datetime import date, timedelta

    with get_connection() as conn:
        with conn.cursor() as cur:

            # ── Ingresos cobrados reales por mes ─────────────────────────────
            cur.execute("""
                SELECT SUBSTRING(sp.payment_date, 1, 7) AS mes,
                       SUM(sp.payment_amount) AS total
                FROM sale_payments sp
                WHERE sp.payment_date IS NOT NULL
                  AND sp.payment_amount IS NOT NULL
                  AND sp.payment_amount > 0
                GROUP BY mes
                ORDER BY mes
            """)
            ingresos_reales = {row['mes']: float(row['total'] or 0) for row in cur.fetchall()}

            # ── Gastos reales por mes ─────────────────────────────────────────
            cur.execute("""
                SELECT SUBSTRING(COALESCE(payment_date, created_at), 1, 7) AS mes,
                       SUM(COALESCE(payment_amount, invoice_amount, 0)) AS total
                FROM purchase_invoices
                WHERE payment_status = 'Pagada' AND payment_date IS NOT NULL
                GROUP BY mes
            """)
            pagos_facturas = {row['mes']: float(row['total'] or 0) for row in cur.fetchall()}

            cur.execute("""
                SELECT SUBSTRING(entry_date, 1, 7) AS mes,
                       SUM(total_amount) AS total
                FROM inventory_entries
                WHERE entry_date IS NOT NULL AND total_amount IS NOT NULL
                  AND id NOT IN (SELECT inventory_entry_id FROM purchase_invoices WHERE inventory_entry_id IS NOT NULL)
                GROUP BY mes
            """)
            gastos_entradas = {row['mes']: float(row['total'] or 0) for row in cur.fetchall()}

            gastos_reales = {}
            for mes, val in list(pagos_facturas.items()) + list(gastos_entradas.items()):
                gastos_reales[mes] = gastos_reales.get(mes, 0.0) + val

            # Facturas de proveedores por pagar (futuros compromisos)
            cur.execute("""
                SELECT SUBSTRING(COALESCE(due_date, invoice_date, created_at), 1, 7) AS mes_vence,
                       SUM(invoice_amount) AS total
                FROM purchase_invoices
                WHERE payment_status IN ('Pendiente', 'Vencida')
                GROUP BY mes_vence
            """)
            gastos_por_pagar_mes = {row['mes_vence']: float(row['total'] or 0) for row in cur.fetchall()}

            # ── Facturas impagas por mes de vencimiento ──────────────────────
            cur.execute("""
                SELECT
                    COALESCE(SUBSTRING(sp.invoice_due_date, 1, 7), SUBSTRING(s.sale_date, 1, 7)) AS mes_vence,
                    SUM(s.total_amount) AS total
                FROM sales s
                LEFT JOIN sale_payments sp ON sp.sale_id = s.id
                WHERE s.payment_status != 'Pagado'
                  AND s.status NOT IN ('Cancelada', 'Cancelado', 'Cotización')
                GROUP BY mes_vence
                ORDER BY mes_vence
            """)
            impagas_por_mes = {row['mes_vence']: float(row['total'] or 0) for row in cur.fetchall()}

    # ── KPIs del mes actual ───────────────────────────────────────────────
    today = date.today()
    cur_month = today.strftime('%Y-%m')

    ingreso_mes    = ingresos_reales.get(cur_month, 0.0)
    gasto_mes      = gastos_reales.get(cur_month, 0.0)
    impagas_total  = sum(impagas_por_mes.values())
    flujo_neto_mes = ingreso_mes - gasto_mes

    # ── Helpers de fecha ──────────────────────────────────────────────────
    def last_n_months(ref, n):
        months = []
        d = ref.replace(day=1)
        for _ in range(n):
            months.append(d.strftime('%Y-%m'))
            d = (d - timedelta(days=1)).replace(day=1)
        return list(reversed(months))

    def next_n_months(ref, n):
        months = []
        d = ref.replace(day=1)
        for _ in range(n):
            d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
            months.append(d.strftime('%Y-%m'))
        return months

    MONTHS_ES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
    def month_label(m):
        try:
            y, mo = m.split('-')
            return MONTHS_ES[int(mo)-1] + f" '{y[2:]}"
        except Exception:
            return m

    # ── Serie de 6 históricos + 6 proyectados ────────────────────────────
    hist_months = last_n_months(today, 6)
    fut_months  = next_n_months(today, 6)
    all_months  = hist_months + fut_months

    recent_ing = [ingresos_reales.get(m, 0) for m in hist_months[-3:] if ingresos_reales.get(m, 0) > 0]
    recent_gas = [gastos_reales.get(m, 0)   for m in hist_months[-3:] if gastos_reales.get(m, 0) > 0]
    avg_ing = sum(recent_ing) / len(recent_ing) if recent_ing else 0
    avg_gas = sum(recent_gas) / len(recent_gas) if recent_gas else 0

    rows = []
    acumulado = 0.0
    for m in all_months:
        es_futuro = m > cur_month
        if not es_futuro:
            ing  = ingresos_reales.get(m, 0.0)
            gas  = gastos_reales.get(m, 0.0)
            imp  = impagas_por_mes.get(m, 0.0)
            tipo = 'real'
        else:
            imp  = impagas_por_mes.get(m, 0.0)
            gas_comp = gastos_por_pagar_mes.get(m, 0.0)
            ing  = avg_ing + imp   # tendencia + facturas clientes por cobrar
            gas  = avg_gas + gas_comp # tendencia + facturas proveedores por pagar
            tipo = 'proyectado'

        neto = ing - gas
        acumulado += neto

        rows.append({
            'mes':       m,
            'label':     month_label(m),
            'ingresos':  round(ing, 2),
            'gastos':    round(gas, 2),
            'impagas':   round(imp, 2),
            'neto':      round(neto, 2),
            'acumulado': round(acumulado, 2),
            'tipo':      tipo,
        })

    idx_proyeccion = next((i for i, r in enumerate(rows) if r['tipo'] == 'proyectado'), len(rows))

    return {
        'ingreso_mes':     round(ingreso_mes, 2),
        'gasto_mes':       round(gasto_mes, 2),
        'impagas_total':   round(impagas_total, 2),
        'flujo_neto_mes':  round(flujo_neto_mes, 2),
        'rows':            rows,
        'chart_labels':    [r['label']     for r in rows],
        'chart_ingresos':  [r['ingresos']  for r in rows],
        'chart_gastos':    [r['gastos']    for r in rows],
        'chart_impagas':   [r['impagas']   for r in rows],
        'chart_neto':      [r['neto']      for r in rows],
        'chart_acumulado': [r['acumulado'] for r in rows],
        'idx_proyeccion':  idx_proyeccion,
    }


def get_cash_flow_data_weekly() -> dict:
    """
    Flujo de Caja SEMANAL: 8 semanas históricas + 6 semanas proyectadas.
    Agrupa por semana ISO (lunes–domingo).
    """
    from datetime import date, timedelta

    def week_key(d: date) -> str:
        iso = d.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"

    def week_label(wk: str) -> str:
        try:
            y, w = wk.split('-W')
            monday = date.fromisocalendar(int(y), int(w), 1)
            MONTHS_ES = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic']
            return f"S{int(w)} ({monday.day} {MONTHS_ES[monday.month-1]})"
        except Exception:
            return wk

    def weeks_range(ref: date, back: int, fwd: int):
        monday_ref = ref - timedelta(days=ref.weekday())
        start = monday_ref - timedelta(weeks=back - 1)
        out = []
        d = start
        for _ in range(back + fwd):
            out.append(week_key(d))
            d += timedelta(weeks=1)
        return out

    today = date.today()
    cur_week = week_key(today)

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute("""
                SELECT payment_date, payment_amount FROM sale_payments
                WHERE payment_date IS NOT NULL AND payment_amount IS NOT NULL AND payment_amount > 0
            """)
            ingresos_reales: dict = {}
            for row in cur.fetchall():
                try:
                    d = date.fromisoformat(str(row['payment_date'])[:10])
                    wk = week_key(d)
                    ingresos_reales[wk] = ingresos_reales.get(wk, 0.0) + float(row['payment_amount'])
                except Exception:
                    pass

            # Gastos pagados de facturas
            cur.execute("""
                SELECT COALESCE(payment_date, created_at) AS p_date,
                       COALESCE(payment_amount, invoice_amount, 0) AS total
                FROM purchase_invoices
                WHERE payment_status = 'Pagada' AND payment_date IS NOT NULL
            """)
            gastos_reales: dict = {}
            for row in cur.fetchall():
                try:
                    d = date.fromisoformat(str(row['p_date'])[:10])
                    wk = week_key(d)
                    gastos_reales[wk] = gastos_reales.get(wk, 0.0) + float(row['total'])
                except Exception:
                    pass

            # Entradas sin factura vinculada
            cur.execute("""
                SELECT entry_date, total_amount FROM inventory_entries
                WHERE entry_date IS NOT NULL AND total_amount IS NOT NULL
                  AND id NOT IN (SELECT inventory_entry_id FROM purchase_invoices WHERE inventory_entry_id IS NOT NULL)
            """)
            for row in cur.fetchall():
                try:
                    d = date.fromisoformat(str(row['entry_date'])[:10])
                    wk = week_key(d)
                    gastos_reales[wk] = gastos_reales.get(wk, 0.0) + float(row['total_amount'])
                except Exception:
                    pass

            # Facturas de proveedores por pagar (futuros compromisos)
            cur.execute("""
                SELECT COALESCE(due_date, invoice_date, created_at) AS due_d, invoice_amount
                FROM purchase_invoices
                WHERE payment_status IN ('Pendiente', 'Vencida')
            """)
            gastos_por_pagar_sem: dict = {}
            for row in cur.fetchall():
                try:
                    d = date.fromisoformat(str(row['due_d'])[:10])
                    wk = week_key(d)
                    gastos_por_pagar_sem[wk] = gastos_por_pagar_sem.get(wk, 0.0) + float(row['invoice_amount'])
                except Exception:
                    pass

            # Facturas clientes impagas
            cur.execute("""
                SELECT s.total_amount,
                       COALESCE(sp.invoice_due_date, s.sale_date) AS fecha_vence
                FROM sales s
                LEFT JOIN sale_payments sp ON sp.sale_id = s.id
                WHERE s.payment_status != 'Pagado'
                  AND s.status NOT IN ('Cancelada', 'Cancelado', 'Cotización')
            """)
            impagas_por_semana: dict = {}
            for row in cur.fetchall():
                try:
                    d = date.fromisoformat(str(row['fecha_vence'])[:10])
                    wk = week_key(d)
                    impagas_por_semana[wk] = impagas_por_semana.get(wk, 0.0) + float(row['total_amount'])
                except Exception:
                    pass

    ingreso_sem    = ingresos_reales.get(cur_week, 0.0)
    gasto_sem      = gastos_reales.get(cur_week, 0.0)
    impagas_total  = sum(impagas_por_semana.values())
    flujo_neto_sem = ingreso_sem - gasto_sem

    all_weeks  = weeks_range(today, back=8, fwd=6)
    hist_weeks = [w for w in all_weeks if w <= cur_week]
    recent_ing = [ingresos_reales.get(w, 0) for w in hist_weeks[-4:] if ingresos_reales.get(w, 0) > 0]
    recent_gas = [gastos_reales.get(w, 0)   for w in hist_weeks[-4:] if gastos_reales.get(w, 0) > 0]
    avg_ing = sum(recent_ing) / len(recent_ing) if recent_ing else 0
    avg_gas = sum(recent_gas) / len(recent_gas) if recent_gas else 0

    rows = []
    acumulado = 0.0
    for wk in all_weeks:
        es_futuro = wk > cur_week
        if not es_futuro:
            ing  = ingresos_reales.get(wk, 0.0)
            gas  = gastos_reales.get(wk, 0.0)
            imp  = impagas_por_semana.get(wk, 0.0)
            tipo = 'real'
        else:
            imp      = impagas_por_semana.get(wk, 0.0)
            gas_comp = gastos_por_pagar_sem.get(wk, 0.0)
            ing      = avg_ing + imp
            gas      = avg_gas + gas_comp
            tipo     = 'proyectado'

        neto = ing - gas
        acumulado += neto
        rows.append({
            'mes':       wk,
            'label':     week_label(wk),
            'ingresos':  round(ing, 2),
            'gastos':    round(gas, 2),
            'impagas':   round(imp, 2),
            'neto':      round(neto, 2),
            'acumulado': round(acumulado, 2),
            'tipo':      tipo,
        })

    idx_proyeccion = next((i for i, r in enumerate(rows) if r['tipo'] == 'proyectado'), len(rows))

    return {
        'ingreso_mes':     round(ingreso_sem, 2),
        'gasto_mes':       round(gasto_sem, 2),
        'impagas_total':   round(impagas_total, 2),
        'flujo_neto_mes':  round(flujo_neto_sem, 2),
        'rows':            rows,
        'chart_labels':    [r['label']     for r in rows],
        'chart_ingresos':  [r['ingresos']  for r in rows],
        'chart_gastos':    [r['gastos']    for r in rows],
        'chart_impagas':   [r['impagas']   for r in rows],
        'chart_neto':      [r['neto']      for r in rows],
        'chart_acumulado': [r['acumulado'] for r in rows],
        'idx_proyeccion':  idx_proyeccion,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PURCHASE INVOICES — Facturas de Proveedores y Pagos
# ─────────────────────────────────────────────────────────────────────────────

def create_purchase_invoice(data: dict) -> int:
    """Crea un registro de factura de proveedor. Retorna el id creado."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO purchase_invoices (
                    inventory_entry_id, purchase_order_id, supplier_id,
                    invoice_number, invoice_amount, invoice_date, due_date,
                    document_file, payment_status, notes, bank_account_id, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()::text)
                RETURNING id
            """, (
                data.get('inventory_entry_id'),
                data.get('purchase_order_id'),
                data.get('supplier_id'),
                data.get('invoice_number', ''),
                data.get('invoice_amount', 0),
                data.get('invoice_date', ''),
                data.get('due_date', ''),
                data.get('document_file'),
                data.get('payment_status', 'Pendiente'),
                data.get('notes', ''),
                data.get('bank_account_id'),
            ))
            inv_id = cur.fetchone()['id']

            # Si está vinculada a una entrada de bodega, actualizar tipo y archivo de la entrada
            if data.get('inventory_entry_id'):
                cur.execute("""
                    UPDATE inventory_entries
                    SET document_type = 'factura',
                        document_number = CASE WHEN %s <> '' THEN %s ELSE document_number END,
                        document_file = COALESCE(%s, document_file)
                    WHERE id = %s
                """, (
                    data.get('invoice_number', ''),
                    data.get('invoice_number', ''),
                    data.get('document_file'),
                    data.get('inventory_entry_id')
                ))

            conn.commit()
            return inv_id


def get_purchase_invoice(invoice_id: int) -> dict:
    """Obtiene una factura de proveedor por id con datos de proveedor y cuenta bancaria."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT pi.*, s.name AS supplier_name,
                       ie.order_number AS entry_number, ie.entry_date,
                       po.oc_number,
                       ba.bank_name, ba.account_number, ba.account_type
                FROM purchase_invoices pi
                LEFT JOIN suppliers s ON s.id = pi.supplier_id
                LEFT JOIN inventory_entries ie ON ie.id = pi.inventory_entry_id
                LEFT JOIN purchase_orders po ON po.id = pi.purchase_order_id
                LEFT JOIN bank_accounts ba ON ba.id = pi.bank_account_id
                WHERE pi.id = %s
            """, (invoice_id,))
            return cur.fetchone()


def list_purchase_invoices(status_filter: str = None) -> list:
    """Lista facturas de proveedor con datos del proveedor, entrada de bodega y cuenta bancaria."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            where = "WHERE pi.payment_status = %s" if status_filter else ""
            params = (status_filter,) if status_filter else ()
            cur.execute(f"""
                SELECT pi.*, s.name AS supplier_name,
                       ie.order_number AS entry_number, ie.entry_date,
                       po.oc_number,
                       ba.bank_name, ba.account_number, ba.account_type
                FROM purchase_invoices pi
                LEFT JOIN suppliers s ON s.id = pi.supplier_id
                LEFT JOIN inventory_entries ie ON ie.id = pi.inventory_entry_id
                LEFT JOIN purchase_orders po ON po.id = pi.purchase_order_id
                LEFT JOIN bank_accounts ba ON ba.id = pi.bank_account_id
                {where}
                ORDER BY
                    CASE pi.payment_status
                        WHEN 'Vencida'   THEN 1
                        WHEN 'Pendiente' THEN 2
                        WHEN 'Pagada'    THEN 3
                        ELSE 4
                    END,
                    COALESCE(pi.due_date, pi.created_at) ASC
            """, params)
            return cur.fetchall()


def count_pending_invoices() -> int:
    """Cuenta facturas de proveedor en estado Pendiente o Vencida."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS n FROM purchase_invoices
                WHERE payment_status IN ('Pendiente', 'Vencida')
            """)
            return cur.fetchone()['n']


def update_invoice_payment_status() -> int:
    """Marca como Vencidas las facturas cuyo due_date ya pasó. Retorna cuántas actualizó."""
    from datetime import date
    today = date.today().isoformat()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE purchase_invoices
                SET payment_status = 'Vencida'
                WHERE payment_status = 'Pendiente'
                  AND due_date <> '' AND due_date IS NOT NULL
                  AND due_date < %s
            """, (today,))
            conn.commit()
            return cur.rowcount


def register_purchase_payment(invoice_id: int, data: dict) -> bool:
    """Registra el pago de una factura de proveedor indicando cuenta bancaria de egreso."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE purchase_invoices SET
                    payment_status     = 'Pagada',
                    payment_date       = %s,
                    payment_amount     = %s,
                    payment_method     = %s,
                    bank_account_id    = %s,
                    payment_proof_file = %s,
                    notes              = COALESCE(notes, '') || %s
                WHERE id = %s
            """, (
                data.get('payment_date', ''),
                data.get('payment_amount', 0),
                data.get('payment_method', ''),
                data.get('bank_account_id'),
                data.get('payment_proof_file'),
                ('\nPago: ' + data.get('payment_notes', '')) if data.get('payment_notes') else '',
                invoice_id,
            ))
            conn.commit()
            return cur.rowcount > 0


def list_pending_invoice_alerts(days_ahead: int = 7) -> list:
    """Retorna facturas vencidas o que vencen en los próximos N días, para alertas en dashboard."""
    from datetime import date, timedelta
    today = date.today().isoformat()
    limit_date = (date.today() + timedelta(days=days_ahead)).isoformat()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT pi.id, pi.invoice_number, pi.invoice_amount, pi.due_date,
                       pi.payment_status, s.name AS supplier_name
                FROM purchase_invoices pi
                LEFT JOIN suppliers s ON s.id = pi.supplier_id
                WHERE pi.payment_status IN ('Pendiente', 'Vencida')
                  AND (pi.due_date IS NULL OR pi.due_date = '' OR pi.due_date <= %s)
                ORDER BY pi.due_date ASC NULLS FIRST
                LIMIT 10
            """, (limit_date,))
            return cur.fetchall()


def list_entries_missing_invoice() -> list:
    """Retorna recepciones con document_type='guia_despacho' que no tienen factura vinculada."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ie.id, ie.entry_date, ie.order_number, ie.document_number,
                       ie.total_amount, ie.supplier_id, ie.purchase_order_id,
                       s.name AS supplier_name, po.oc_number
                FROM inventory_entries ie
                LEFT JOIN suppliers s ON s.id = ie.supplier_id
                LEFT JOIN purchase_orders po ON po.id = ie.purchase_order_id
                LEFT JOIN purchase_invoices pi ON pi.inventory_entry_id = ie.id
                WHERE (ie.document_type = 'guia_despacho' OR ie.document_type IS NULL OR ie.document_type = '')
                  AND pi.id IS NULL
                ORDER BY ie.entry_date DESC
            """)
            return cur.fetchall()


def link_invoice_to_entry(invoice_id: int, entry_id: int) -> bool:
    """Vincula una factura existente a una entrada de bodega (guía de despacho)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE purchase_invoices SET inventory_entry_id = %s WHERE id = %s
            """, (entry_id, invoice_id))
            cur.execute("""
                UPDATE inventory_entries SET document_type = 'factura' WHERE id = %s
            """, (entry_id,))
            conn.commit()
            return cur.rowcount > 0


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

EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
)

def is_valid_email(email: str) -> bool:
    """Valida que el correo tenga la estructura correcta (ej: usuario@dominio.com, .cl, etc.)."""
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    if not EMAIL_REGEX.match(email):
        return False
    parts = email.split('@')
    if len(parts) != 2:
        return False
    domain = parts[1]
    domain_parts = domain.split('.')
    if len(domain_parts) < 2:
        return False
    for part in domain_parts:
        if not part or not re.match(r'^[a-zA-Z0-9-]+$', part):
            return False
    tld = domain_parts[-1]
    if len(tld) < 2 or not tld.isalpha():
        return False
    return True


def normalize_rut_str(rut_str: str, dv_str: str = None) -> tuple[str, str]:
    """Normaliza y separa el cuerpo y el dígito verificador del RUT chileno."""
    if not rut_str:
        return "", ""
    clean = str(rut_str).strip().replace(".", "").upper()
    if "-" in clean:
        parts = clean.split("-", 1)
        r_body = parts[0].strip()
        r_dv = parts[1].strip()
    else:
        r_body = clean
        r_dv = str(dv_str or "").strip().upper()
    return r_body, r_dv


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
                    giro, contacto, rut_solicita, dv_solicita, email, phone, category_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    email = %s, phone = %s, category_id = %s
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
                       giro, contacto, rut_solicita, dv_solicita, email, phone, category_id
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
            "category_id": category_id or existing.get("category_id")
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
            "category_id": category_id
        }
        return insert_client(new_client)


def get_system_notifications() -> list[dict]:
    """Genera las notificaciones y alertas activas del sistema (facturas vencidas/por vencer, stock bajo, ventas pendientes)."""
    notifications = []
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    next_7d_str = (now + timedelta(days=7)).strftime('%Y-%m-%d')

    # 1. Facturas de compra vencidas o por vencer (Cuentas por Pagar)
    invoices = list_purchase_invoices()
    for inv in invoices:
        p_status = inv.get('payment_status', 'Pendiente')
        due = inv.get('due_date') or ''
        num = inv.get('invoice_number') or f"ID #{inv.get('id')}"
        supp = inv.get('supplier_name') or 'Proveedor'
        amt = float(inv.get('invoice_amount') or 0)
        
        if p_status != 'Pagada' and due:
            if due < today_str:
                notifications.append({
                    'id': f"inv-{inv['id']}",
                    'type': 'danger',
                    'icon': 'fa-solid fa-file-circle-xmark',
                    'title': f'Factura Vencida: {num}',
                    'desc': f'{supp} · ${amt:,.0f} · Venció el {due}',
                    'link': '/compras/cuentas-por-pagar',
                    'time': 'Cuentas por Pagar'
                })
            elif due <= next_7d_str:
                notifications.append({
                    'id': f"inv-{inv['id']}",
                    'type': 'warning',
                    'icon': 'fa-solid fa-file-invoice-dollar',
                    'title': f'Factura por Vencer: {num}',
                    'desc': f'{supp} · ${amt:,.0f} · Vence el {due}',
                    'link': '/compras/cuentas-por-pagar',
                    'time': 'Cuentas por Pagar'
                })

    # 2. Stock crítico en Bodega
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT json FROM page_data WHERE key = 'inventory_items'")
            row = cur.fetchone()
            if row and row['json']:
                try:
                    items = json.loads(row['json'])
                    for it in items:
                        stk = int(it.get('stock', 0))
                        min_stk = int(it.get('min_stock', 10))
                        if stk <= min_stk:
                            notifications.append({
                                'id': f"stock-{it.get('code')}",
                                'type': 'warning',
                                'icon': 'fa-solid fa-boxes-stacked',
                                'title': f"Stock Bajo: {it.get('name', 'Insumo')}",
                                'desc': f"Quedan {stk} unidades (mínimo requerido: {min_stk})",
                                'link': '/inventario',
                                'time': 'Bodega'
                            })
                except Exception:
                    pass

    # 3. Ventas pendientes por gestionar
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM sales WHERE status = 'Pendiente' AND sale_number LIKE 'VTA-%%'")
            row_pend = cur.fetchone()
            pend = int(row_pend['count']) if row_pend else 0
            if pend > 0:
                notifications.append({
                    'id': 'sales-pending',
                    'type': 'info',
                    'icon': 'fa-solid fa-clock',
                    'title': f'{pend} Ventas Pendientes',
                    'desc': 'Pedidos pendientes de pago o despacho',
                    'link': '/ventas',
                    'time': 'Ventas'
                })

    return notifications




