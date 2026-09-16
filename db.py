import json
import os
import re
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from typing import Any, Dict
from werkzeug.security import generate_password_hash

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


from core.database import get_connection


def init_db() -> None:
    """
    Initialize database schema using ordered transactional migrations and seed required baseline catalogs.
    """
    import tools.migrate as mig
    import tools.seed_required as seed_req

    with get_connection() as conn:
        mig.apply_all_migrations(conn)
        seed_req.seed_required_catalogs(conn)

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

# ==============================================================================

# ==============================================================================
# FASE 5: MODULAR BACKEND REPOSITORIES & FACADE RE-EXPORTS
# ==============================================================================

from core.utils import EMAIL_REGEX

from core.database import (
    get_connection,
)

from core.utils import (
    is_valid_email,
    normalize_rut_str,
)

from repositories.auth_repo import (
    delete_role,
    delete_user,
    get_role,
    get_user,
    insert_role,
    insert_user,
    list_roles,
    list_users,
    update_role,
    update_user,
)

from repositories.products_repo import (
    add_product_supplier,
    delete_category,
    delete_product,
    get_product,
    get_product_calculated_cost,
    insert_product,
    list_product_suppliers,
    list_products,
    list_products_by_supplier,
    remove_product_supplier,
    rename_category,
    update_product,
)

from repositories.suppliers_repo import (
    delete_supplier,
    delete_supplier_contact,
    get_supplier,
    get_supplier_contact,
    insert_supplier,
    insert_supplier_contact,
    list_supplier_contacts,
    list_suppliers,
    update_supplier,
    update_supplier_contact,
)

from repositories.clients_repo import (
    delete_client,
    get_client_by_id,
    get_client_by_rut,
    insert_client,
    list_clients,
    search_clients,
    update_client,
    upsert_client_by_rut,
)

from repositories.legacy_repo import (
    get_page_data,
    insert_sales_entry,
    list_sales_entries,
    set_page_data,
)

from repositories.reporting_repo import (
    get_cash_flow_data,
    get_cash_flow_data_weekly,
    get_income_report_data,
    get_purchase_years,
    get_purchased_products_matrix,
    get_sales_chart_data,
    get_sales_metrics,
    get_system_notifications,
    get_top_products,
)

from repositories.purchases_repo import (
    anular_purchase_order,
    approve_purchase_order,
    create_purchase_invoice,
    create_purchase_order,
    get_next_oc_number,
    get_purchase_invoice,
    get_purchase_invoice_products_detail,
    get_purchase_order,
    get_purchase_order_entries,
    get_purchase_order_items,
    list_active_purchase_orders_by_supplier,
    list_entries_missing_invoice,
    list_purchase_invoices,
    list_purchase_orders,
    update_purchase_order,
)

from repositories.finance_repo import (
    count_pending_invoices,
    delete_bank_account,
    delete_sale_payment_item,
    get_bank_account,
    get_sale_payment,
    get_sale_payment_items_totals,
    get_sale_payments_map,
    insert_bank_account,
    insert_sale_payment_item,
    link_invoice_to_entry,
    list_bank_accounts,
    list_pending_invoice_alerts,
    list_sale_payment_items,
    register_purchase_payment,
    update_bank_account,
    update_invoice_payment_status,
    update_sale_payment_item_amount_date,
    update_sale_payment_item_approval,
    update_sale_payment_item_proof,
    upsert_sale_payment,
)

from repositories.inventory_repo import (
    consume_fifo_lots,
    consume_lots_for_sale,
    discount_stock_for_sale,
    get_all_lot_stock,
    get_inventory_entry_detail,
    get_lot_stock_by_product,
    get_lot_traceability,
    get_product_available_stock,
    get_relational_stock,
    get_relational_stock_by_sku,
    get_sale_lot_movements,
    get_stock_with_dual_read,
    list_inventory_entries,
    record_inventory_movement,
    register_inventory_entry,
    validate_stock_for_sale,
)

from repositories.sales_repo import (
    count_sales,
    delete_sale,
    get_next_sale_number,
    get_sale,
    get_sale_payments_for_sales,
    insert_sale,
    list_sales,
    list_sales_page,
    list_sales_page_light,
    update_quotation_status,
    update_sale,
)

from repositories.production_repo import (
    get_next_ot_number,
)
