import json
import os
import psycopg2
import psycopg2.extras
from datetime import datetime
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
                       category, expiry_date, width_cm, height_cm, depth_cm, weight_kg, product_type
                FROM products
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
                    weight_kg, product_type, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                       category, expiry_date, width_cm, height_cm, depth_cm, weight_kg, product_type
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
                    product_type = %s
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
                    product_id,
                ),
            )
        conn.commit()


def delete_product(product_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
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
                INSERT INTO sale_payment_items (sale_id, payment_amount, payment_date, payment_proof_file, created_at)
                VALUES (%s, %s, %s, %s, %s) RETURNING id
                """,
                (
                    item["sale_id"],
                    item["payment_amount"],
                    item.get("payment_date"),
                    item.get("payment_proof_file"),
                    item["created_at"],
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
    with get_connection() as conn:
        with conn.cursor() as cur:
            today = datetime.now().strftime('%Y-%m-%d')
            cur.execute(
                "SELECT COALESCE(SUM(total_amount), 0) as total FROM sales WHERE sale_date = %s",
                (today,)
            )
            total_today = cur.fetchone()["total"]
            
            cur.execute(
                "SELECT COUNT(*) as count FROM sales WHERE status = 'Completada'"
            )
            total_completed = cur.fetchone()["count"]
            
            cur.execute(
                "SELECT COUNT(*) as count FROM sales WHERE status = 'Pendiente'"
            )
            total_pending = cur.fetchone()["count"]
            
            cur.execute(
                "SELECT COUNT(DISTINCT customer_name) as count FROM sales"
            )
            total_customers = cur.fetchone()["count"]
            
            return {
                "ventas_hoy": round(float(total_today), 2),
                "ventas_completadas": total_completed,
                "ventas_pendientes": total_pending,
                "clientes_activos": total_customers,
            }


def get_sales_chart_data(year: int = None, period: str = "6months") -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if year:
                cur.execute(
                    """
                    SELECT TO_CHAR(sale_date::date, 'YYYY-MM') as month,
                           SUM(total_amount) as total
                    FROM sales
                    WHERE TO_CHAR(sale_date::date, 'YYYY') = %s
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
                           SUM(total_amount) as total
                    FROM sales
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
                if row['total']:
                    month_num = int(row['month'].split('-')[1])
                    months.append(month_names[month_num - 1])
                    amounts.append(round(float(row['total']), 2))
            
            return {"labels": months, "data": amounts}


def get_top_products(year: int = None, period: str = "year") -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            if year:
                cur.execute(
                    """
                    SELECT products_json
                    FROM sales
                    WHERE TO_CHAR(sale_date::date, 'YYYY') = %s AND status = 'Completada'
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
                    WHERE TO_CHAR(sale_date::date, 'YYYY-MM') = %s AND status = 'Completada'
                    """,
                    (current_month,)
                )
                rows = cur.fetchall()
            else:
                cur.execute(
                    """
                    SELECT products_json
                    FROM sales
                    WHERE status = 'Completada'
                    """
                )
                rows = cur.fetchall()
            
            product_counts = {}
            for row in rows:
                products = json.loads(row['products_json'])
                for product_str in products:
                    product_name = product_str.split('(')[0].strip()
                    try:
                        quantity = int(product_str.split('(')[1].split(')')[0])
                    except:
                        quantity = 1
                    
                    product_counts[product_name] = product_counts.get(product_name, 0) + quantity
            
            sorted_products = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            
            labels = [p[0] for p in sorted_products]
            data = [p[1] for p in sorted_products]
            
            return {"labels": labels, "data": data}


def list_suppliers() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, description, website, created_at
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
                SELECT id, name, description, website, created_at
                FROM suppliers
                WHERE id = %s
                """,
                (supplier_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def insert_supplier(supplier: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO suppliers (name, description, website, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    supplier["name"],
                    supplier.get("description"),
                    supplier.get("website"),
                    supplier.get("created_at", datetime.utcnow().isoformat(timespec='seconds')),
                ),
            )
        conn.commit()


def update_supplier(supplier_id: int, supplier: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE suppliers
                SET name = %s, description = %s, website = %s
                WHERE id = %s
                """,
                (
                    supplier.get("name"),
                    supplier.get("description"),
                    supplier.get("website"),
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

def create_purchase_order(supplier_id: int, order_date: str, notes: str, items: list[dict], status: str = "Emitida", created_by: int = None) -> str:
    """Crea una Orden de Compra completa en la base de datos"""
    oc_num = get_next_oc_number()
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Calcular total
            total_amount = sum(item["quantity"] * item["unit_price"] for item in items)
            
            # Insertar cabecera de la OC
            cur.execute(
                """
                INSERT INTO purchase_orders (oc_number, supplier_id, order_date, status, total_amount, notes, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (oc_num, supplier_id, order_date, status, total_amount, notes, created_by, datetime.utcnow().isoformat(timespec='seconds'))
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

def update_purchase_order(po_id: int, supplier_id: int, order_date: str, notes: str, items: list[dict], status: str = "Borrador") -> None:
    """Actualiza una Orden de Compra (borrador) y sus ítems en la base de datos"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Calcular total
            total_amount = sum(item["quantity"] * item["unit_price"] for item in items)
            
            # Actualizar cabecera
            cur.execute(
                """
                UPDATE purchase_orders
                SET supplier_id = %s, order_date = %s, status = %s, total_amount = %s, notes = %s
                WHERE id = %s
                """,
                (supplier_id, order_date, status, total_amount, notes, po_id)
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
    """Lista todas las Órdenes de Compra con creadores y aprobadores"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT po.id, po.oc_number, po.order_date, po.status, po.total_amount, po.notes,
                       s.name as supplier_name,
                       u1.full_name as creator_name,
                       u2.full_name as approver_name
                FROM purchase_orders po
                JOIN suppliers s ON po.supplier_id = s.id
                LEFT JOIN users u1 ON po.created_by = u1.id
                LEFT JOIN users u2 ON po.approved_by = u2.id
                ORDER BY po.id DESC
                """
            )
            return [dict(row) for row in cur.fetchall()]

def get_purchase_order(po_id: int) -> dict | None:
    """Obtiene la cabecera e información de una OC"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT po.id, po.oc_number, po.order_date, po.status, po.total_amount, po.notes, po.supplier_id,
                       s.name as supplier_name, s.description as supplier_description, s.website as supplier_website,
                       u1.full_name as creator_name,
                       u2.full_name as approver_name
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

def register_inventory_entry(po_id: int, order_number: str, entry_date: str, warehouse: str, notes: str, items: list[dict]) -> None:
    """Registra el ingreso de mercadería cruzando cantidades contra la OC y actualizando stock"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Obtener datos de la OC
            cur.execute("SELECT id, supplier_id FROM purchase_orders WHERE id = %s", (po_id,))
            po = cur.fetchone()
            if not po:
                raise ValueError("Orden de Compra no encontrada.")
                
            supplier_id = po["supplier_id"]
            total_amount = sum(item["quantity"] * item["unit_price"] for item in items)
            
            # 1. Registrar cabecera del ingreso
            cur.execute(
                """
                INSERT INTO inventory_entries (entry_date, order_number, purchase_order_id, supplier_id, warehouse, notes, total_amount, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (entry_date, order_number, po_id, supplier_id, warehouse, notes, total_amount, datetime.utcnow().isoformat(timespec='seconds'))
            )
            entry_id = cur.fetchone()["id"]
            
            # 2. Guardar items del ingreso, validar límites y actualizar OC
            for item in items:
                prod_id = item["product_id"]
                qty = item["quantity"]
                price = item["unit_price"]
                line_total = qty * price
                
                # Validar contra la OC lo pendiente por recibir
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
                
                # Registrar item del ingreso
                cur.execute(
                    """
                    INSERT INTO inventory_entry_items (inventory_entry_id, product_id, quantity, unit_price, total)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (entry_id, prod_id, qty, price, line_total)
                )
                
                # Actualizar cantidad recibida en la OC
                new_received = po_item["quantity_received"] + qty
                cur.execute(
                    """
                    UPDATE purchase_order_items 
                    SET quantity_received = %s 
                    WHERE id = %s
                    """,
                    (new_received, po_item["id"])
                )
            
            # 3. Validar el nuevo estado de la OC
            cur.execute(
                """
                SELECT SUM(quantity_ordered) as total_ord, SUM(quantity_received) as total_rec
                FROM purchase_order_items
                WHERE purchase_order_id = %s
                """,
                (po_id,)
            )
            summary = cur.fetchone()
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

