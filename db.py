import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "app.db")

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
    "sales_payment_status_options": ["Pendiente", "Pagado", "Parcial"],
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


def _ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    _ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    _ensure_dirs()
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS page_data (
                key TEXT PRIMARY KEY,
                json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sales_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT NOT NULL,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                total_price REAL NOT NULL,
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT,
                photo_url TEXT,
                width_cm REAL,
                height_cm REAL,
                depth_cm REAL,
                weight_kg REAL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                permissions TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role_id INTEGER NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY (role_id) REFERENCES roles(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_number TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL,
                customer_email TEXT,
                customer_initials TEXT,
                sale_date TEXT NOT NULL,
                sale_time TEXT NOT NULL,
                products_json TEXT NOT NULL,
                total_amount REAL NOT NULL,
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
        conn.commit()

    seed_data_if_empty()


def seed_data_if_empty() -> None:
    with get_connection() as conn:
        # Seed page_data
        for key, value in DEFAULT_DATA.items():
            if key != "default_roles":
                conn.execute(
                    "INSERT OR IGNORE INTO page_data (key, json) VALUES (?, ?)",
                    (key, json.dumps(value, ensure_ascii=False)),
                )
        
        # Seed default roles
        default_roles = DEFAULT_DATA.get("default_roles", [])
        for role in default_roles:
            conn.execute(
                "INSERT OR IGNORE INTO roles (name, description, permissions, created_at) VALUES (?, ?, ?, ?)",
                (
                    role["name"],
                    role["description"],
                    role.get("permissions", "{}"),
                    datetime.utcnow().isoformat(timespec='seconds'),
                ),
            )
        
        # Seed default users (only if no users exist)
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count == 0:
            # Get role IDs
            roles = conn.execute("SELECT id, name FROM roles").fetchall()
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
                conn.execute(
                    "INSERT OR IGNORE INTO users (username, email, password, full_name, role_id, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        user["username"],
                        user["email"],
                        user["password"],
                        user["full_name"],
                        user["role_id"],
                        1,
                        datetime.utcnow().isoformat(timespec='seconds'),
                    ),
                )
        
        # Seed default sales (only if no sales exist)
        sales_count = conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
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
                conn.execute(
                    """
                    INSERT INTO sales (
                        sale_number, customer_name, customer_email, customer_initials,
                        sale_date, sale_time, products_json, total_amount, status,
                        seller_name, seller_initials, payment_method, payment_status,
                        delivery_status, notes, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        
        conn.commit()



def get_page_data(key: str) -> Any:
    with get_connection() as conn:
        row = conn.execute("SELECT json FROM page_data WHERE key = ?", (key,)).fetchone()
        if not row:
            return None
        return json.loads(row["json"])


def set_page_data(key: str, value: Any) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO page_data (key, json) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET json = excluded.json",
            (key, json.dumps(value, ensure_ascii=False)),
        )
        conn.commit()


def list_sales_entries() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, sku, product_name, quantity, unit_price, total_price,
                   sale_date, delivery_date, payment_status, delivery_status,
                   payment_method, customer_name, seller_name, notes
            FROM sales_entries
            ORDER BY datetime(created_at) DESC, id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def insert_sales_entry(entry: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO sales_entries (
                sku, product_name, quantity, unit_price, total_price,
                sale_date, delivery_date, payment_status, delivery_status,
                payment_method, customer_name, seller_name, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        rows = conn.execute(
            """
            SELECT id, sku, name, description, photo_url, barcode, internal_code,
                   width_cm, height_cm, depth_cm, weight_kg
            FROM products
            ORDER BY id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def insert_product(product: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO products (
                sku, name, description, photo_url, barcode, internal_code,
                width_cm, height_cm, depth_cm, weight_kg, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product["sku"],
                product["name"],
                product.get("description"),
                product.get("photo_url"),
                product.get("barcode"),
                product.get("internal_code"),
                product.get("width_cm"),
                product.get("height_cm"),
                product.get("depth_cm"),
                product.get("weight_kg"),
                product["created_at"],
            ),
        )
        conn.commit()


def get_product(product_id: int) -> dict:
    """Get a single product by ID"""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, sku, name, description, photo_url, barcode, internal_code,
                   width_cm, height_cm, depth_cm, weight_kg
            FROM products
            WHERE id = ?
            """,
            (product_id,),
        ).fetchone()
        return dict(row) if row else None


def update_product(product_id: int, product: dict) -> None:
    """Update an existing product"""
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE products SET
                sku = ?, name = ?, description = ?, photo_url = ?,
                barcode = ?, internal_code = ?,
                width_cm = ?, height_cm = ?, depth_cm = ?, weight_kg = ?
            WHERE id = ?
            """,
            (
                product.get("sku"),
                product.get("name"),
                product.get("description"),
                product.get("photo_url"),
                product.get("barcode"),
                product.get("internal_code"),
                product.get("width_cm"),
                product.get("height_cm"),
                product.get("depth_cm"),
                product.get("weight_kg"),
                product_id,
            ),
        )
        conn.commit()


def delete_product(product_id: int) -> None:
    """Delete a product"""
    with get_connection() as conn:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()

# Funciones para Roles
def list_roles() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, description, permissions FROM roles ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]


def get_role(role_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, description, permissions FROM roles WHERE id = ?",
            (role_id,),
        ).fetchone()
        return dict(row) if row else None


def insert_role(role: dict) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO roles (name, description, permissions, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                role["name"],
                role.get("description"),
                role.get("permissions"),
                role["created_at"],
            ),
        )
        conn.commit()
        return cursor.lastrowid


def update_role(role_id: int, role: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE roles SET name = ?, description = ?, permissions = ?
            WHERE id = ?
            """,
            (role.get("name"), role.get("description"), role.get("permissions"), role_id),
        )
        conn.commit()


def delete_role(role_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM roles WHERE id = ?", (role_id,))
        conn.commit()


# Funciones para Usuarios
def list_users() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.username, u.email, u.full_name, u.is_active,
                   r.name as role_name, u.created_at
            FROM users u
            JOIN roles r ON u.role_id = r.id
            ORDER BY u.created_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def get_user(user_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.username, u.email, u.full_name, u.is_active, u.role_id,
                   r.name as role_name
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE u.id = ?
            """,
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def insert_user(user: dict) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (username, email, password, full_name, role_id, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["username"],
                user["email"],
                user.get("password", "password123"),
                user["full_name"],
                user["role_id"],
                user.get("is_active", 1),
                user["created_at"],
            ),
        )
        conn.commit()
        return cursor.lastrowid


def update_user(user_id: int, user: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE users SET email = ?, full_name = ?, role_id = ?, is_active = ?
            WHERE id = ?
            """,
            (
                user.get("email"),
                user.get("full_name"),
                user.get("role_id"),
                user.get("is_active", 1),
                user_id,
            ),
        )
        conn.commit()


def delete_user(user_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()


# === Sales Functions ===

def list_sales(filters: dict = None) -> list[dict]:
    """List all sales with optional filters"""
    with get_connection() as conn:
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
                query += " AND status = ?"
                params.append(filters['status'])
            if filters.get('customer_name'):
                query += " AND customer_name LIKE ?"
                params.append(f"%{filters['customer_name']}%")
            if filters.get('date_from'):
                query += " AND sale_date >= ?"
                params.append(filters['date_from'])
            if filters.get('date_to'):
                query += " AND sale_date <= ?"
                params.append(filters['date_to'])
        
        query += " ORDER BY datetime(sale_date || ' ' || sale_time) DESC, id DESC"
        
        rows = conn.execute(query, params).fetchall()
        sales = []
        for row in rows:
            sale = dict(row)
            sale['products'] = json.loads(sale['products_json'])
            del sale['products_json']
            sales.append(sale)
        return sales


def get_sale(sale_id: int) -> dict | None:
    """Get a single sale by ID"""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, sale_number, customer_name, customer_email, customer_initials,
                   sale_date, sale_time, products_json, total_amount, status,
                   seller_name, seller_initials, payment_method, payment_status,
                   delivery_status, notes, created_at
            FROM sales
            WHERE id = ?
            """,
            (sale_id,),
        ).fetchone()
        if row:
            sale = dict(row)
            sale['products'] = json.loads(sale['products_json'])
            del sale['products_json']
            return sale
        return None


def insert_sale(sale: dict) -> int:
    """Insert a new sale"""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO sales (
                sale_number, customer_name, customer_email, customer_initials,
                sale_date, sale_time, products_json, total_amount, status,
                seller_name, seller_initials, payment_method, payment_status,
                delivery_status, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        conn.commit()
        return cursor.lastrowid


def update_sale(sale_id: int, sale: dict) -> None:
    """Update an existing sale"""
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE sales SET
                customer_name = ?, customer_email = ?, customer_initials = ?,
                sale_date = ?, sale_time = ?, products_json = ?, total_amount = ?,
                status = ?, seller_name = ?, seller_initials = ?,
                payment_method = ?, payment_status = ?, delivery_status = ?, notes = ?
            WHERE id = ?
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
    """Delete a sale"""
    with get_connection() as conn:
        conn.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
        conn.commit()


def get_sales_metrics() -> dict:
    """Get sales metrics for dashboard and sales page"""
    with get_connection() as conn:
        # Total de ventas hoy
        today = datetime.now().strftime('%Y-%m-%d')
        total_today = conn.execute(
            "SELECT COALESCE(SUM(total_amount), 0) FROM sales WHERE sale_date = ?",
            (today,)
        ).fetchone()[0]
        
        # Total de ventas completadas
        total_completed = conn.execute(
            "SELECT COUNT(*) FROM sales WHERE status = 'Completada'"
        ).fetchone()[0]
        
        # Total de ventas pendientes
        total_pending = conn.execute(
            "SELECT COUNT(*) FROM sales WHERE status = 'Pendiente'"
        ).fetchone()[0]
        
        # Clientes únicos
        total_customers = conn.execute(
            "SELECT COUNT(DISTINCT customer_name) FROM sales"
        ).fetchone()[0]
        
        return {
            "ventas_hoy": round(total_today, 2),
            "ventas_completadas": total_completed,
            "ventas_pendientes": total_pending,
            "clientes_activos": total_customers,
        }


def get_sales_chart_data(year: int = None, period: str = "6months") -> dict:
    """Get monthly sales data for charts
    
    Args:
        year: Optional year to filter (e.g., 2026)
        period: '6months' or '12months'
    """
    with get_connection() as conn:
        if year:
            # Get all months for the specified year
            rows = conn.execute(
                """
                SELECT strftime('%Y-%m', sale_date) as month,
                       SUM(total_amount) as total
                FROM sales
                WHERE strftime('%Y', sale_date) = ?
                GROUP BY month
                ORDER BY month ASC
                """,
                (str(year),)
            ).fetchall()
        else:
            # Get last 6 or 12 months
            limit = 12 if period == "12months" else 6
            rows = conn.execute(
                """
                SELECT strftime('%Y-%m', sale_date) as month,
                       SUM(total_amount) as total
                FROM sales
                GROUP BY month
                ORDER BY month DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()
            rows = list(reversed(rows))
        
        months = []
        amounts = []
        month_names = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        
        for row in rows:
            if row['total']:  # Only include months with sales
                # Convert YYYY-MM to month name
                month_num = int(row['month'].split('-')[1])
                months.append(month_names[month_num - 1])
                amounts.append(round(row['total'], 2))
        
        return {"labels": months, "data": amounts}


def get_top_products(year: int = None, period: str = "year") -> dict:
    """Get top selling products
    
    Args:
        year: Optional year to filter
        period: 'month' or 'year'
    """
    with get_connection() as conn:
        if year:
            # Get products for specific year
            rows = conn.execute(
                """
                SELECT products_json
                FROM sales
                WHERE strftime('%Y', sale_date) = ? AND status = 'Completada'
                """,
                (str(year),)
            ).fetchall()
        elif period == "month":
            # Get current month
            current_month = datetime.now().strftime('%Y-%m')
            rows = conn.execute(
                """
                SELECT products_json
                FROM sales
                WHERE strftime('%Y-%m', sale_date) = ? AND status = 'Completada'
                """,
                (current_month,)
            ).fetchall()
        else:
            # Get all time
            rows = conn.execute(
                """
                SELECT products_json
                FROM sales
                WHERE status = 'Completada'
                """
            ).fetchall()
        
        # Count products
        product_counts = {}
        for row in rows:
            products = json.loads(row['products_json'])
            for product_str in products:
                # Extract product name (before the quantity in parentheses)
                product_name = product_str.split('(')[0].strip()
                # Extract quantity
                try:
                    quantity = int(product_str.split('(')[1].split(')')[0])
                except:
                    quantity = 1
                
                product_counts[product_name] = product_counts.get(product_name, 0) + quantity
        
        # Get top 5 products
        sorted_products = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        labels = [p[0] for p in sorted_products]
        data = [p[1] for p in sorted_products]
        
        return {"labels": labels, "data": data}

