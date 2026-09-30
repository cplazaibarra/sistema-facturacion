#!/usr/bin/env python3
import sys
import os
import time
import re
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import core.database
import db
from app import app

class ProfiledCursor:
    def __init__(self, real_cursor, profiler):
        self._real_cursor = real_cursor
        self._profiler = profiler

    def execute(self, query, vars=None):
        t0 = time.perf_counter()
        try:
            return self._real_cursor.execute(query, vars)
        finally:
            t1 = time.perf_counter()
            elapsed = t1 - t0
            self._profiler.total_time += elapsed
            self._profiler.queries.append({
                "query": str(query)[:300],
                "time": elapsed
            })

    def executemany(self, query, vars):
        t0 = time.perf_counter()
        try:
            return self._real_cursor.executemany(query, vars)
        finally:
            t1 = time.perf_counter()
            elapsed = t1 - t0
            self._profiler.total_time += elapsed
            self._profiler.queries.append({
                "query": str(query)[:300],
                "time": elapsed
            })

    def __getattr__(self, attr):
        return getattr(self._real_cursor, attr)

    def __iter__(self):
        return iter(self._real_cursor)

class ProfiledConnection:
    def __init__(self, real_conn, profiler):
        self._real_conn = real_conn
        self._profiler = profiler

    def cursor(self, *args, **kwargs):
        real_cur = self._real_conn.cursor(*args, **kwargs)
        return ProfiledCursor(real_cur, self._profiler)

    def __enter__(self):
        self._real_conn.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._real_conn.__exit__(exc_type, exc_val, exc_tb)

    def __getattr__(self, attr):
        return getattr(self._real_conn, attr)

class SQLQueryProfiler:
    def __init__(self):
        self.queries: List[Dict[str, Any]] = []
        self.total_time: float = 0.0
        self._orig_core_get_conn = None
        self._orig_db_get_conn = None

    def start(self):
        self.queries = []
        self.total_time = 0.0
        self._orig_core_get_conn = core.database.get_connection
        self._orig_db_get_conn = db.get_connection

        profiler_self = self
        def profiled_get_conn():
            real_conn = profiler_self._orig_core_get_conn()
            return ProfiledConnection(real_conn, profiler_self)

        core.database.get_connection = profiled_get_conn
        db.get_connection = profiled_get_conn

    def stop(self):
        if self._orig_core_get_conn:
            core.database.get_connection = self._orig_core_get_conn
            self._orig_core_get_conn = None
        if self._orig_db_get_conn:
            db.get_connection = self._orig_db_get_conn
            self._orig_db_get_conn = None

WEB_PAGES = [
    {"module": "Dashboard", "route": "/", "label": "Dashboard Principal"},
    {"module": "Productos", "route": "/productos", "label": "Catálogo de Productos"},
    {"module": "Kardex", "route": "/kardex", "label": "Kardex Valorizado / PPP"},
    {"module": "Inventario", "route": "/inventario", "label": "Stock e Inventario"},
    {"module": "Inventario", "route": "/ingreso-mercaderia", "label": "Ingreso Mercadería / Recepciones"},
    {"module": "Producción", "route": "/produccion", "label": "Órdenes de Trabajo (OT)"},
    {"module": "Producción", "route": "/produccion/calendario", "label": "Calendario de Producción"},
    {"module": "Producción", "route": "/produccion/recetas", "label": "Recetas de Fabricación (BOM)"},
    {"module": "Producción", "route": "/produccion/nueva", "label": "Nueva Orden de Trabajo"},
    {"module": "Ventas", "route": "/ventas", "label": "Listado de Ventas"},
    {"module": "Ventas", "route": "/ventas/cotizaciones", "label": "Cotizaciones"},
    {"module": "Ventas", "route": "/ventas/clientes", "label": "Clientes"},
    {"module": "Ventas", "route": "/ventas/reportes", "label": "Reportes de Ventas"},
    {"module": "Ventas", "route": "/proyeccion-ventas", "label": "Proyección de Ventas"},
    {"module": "Ventas", "route": "/ingreso-ventas", "label": "Ingreso Manual de Ventas"},
    {"module": "Compras", "route": "/compras/oc", "label": "Órdenes de Compra (OC)"},
    {"module": "Compras", "route": "/compras/oc/nueva", "label": "Nueva Orden de Compra"},
    {"module": "Compras", "route": "/compras/cuentas-por-pagar", "label": "Cuentas por Pagar (CxP)"},
    {"module": "Compras", "route": "/compras/productos-comprados", "label": "Historial Productos Comprados"},
    {"module": "Proveedores", "route": "/proveedores", "label": "Directorio de Proveedores"},
    {"module": "Trazabilidad", "route": "/trazabilidad", "label": "Trazabilidad y Lotes"},
    {"module": "Reportes", "route": "/reporteria/ventas", "label": "Reporte BI Ventas"},
    {"module": "Reportes", "route": "/reporteria/compras", "label": "Reporte BI Compras"},
    {"module": "Reportes", "route": "/reporteria/gastos", "label": "Reporte BI Gastos"},
    {"module": "Reportes", "route": "/reporteria/ingresos", "label": "Reporte BI Ingresos"},
    {"module": "Reportes", "route": "/reporteria/flujo-caja", "label": "Reporte Flujo de Caja"},
    {"module": "Reportes", "route": "/reporteria/inventario-lotes", "label": "Reporte Lotes y Vencimientos"},
    {"module": "Usuarios", "route": "/usuarios", "label": "Gestión de Usuarios"},
    {"module": "Usuarios", "route": "/roles", "label": "Roles y Permisos"},
    {"module": "Administración", "route": "/administracion", "label": "Panel de Administración"},
    {"module": "Administración", "route": "/administracion/cuentas-bancarias", "label": "Cuentas Bancarias"},
    {"module": "Administración", "route": "/administracion/listas-precios", "label": "Listas de Precios"},
    {"module": "Operario", "route": "/operario/", "label": "Portal Operario PWA"},
    {"module": "Operario", "route": "/operario/ot", "label": "Operario OT List"},
    {"module": "Operario", "route": "/operario/recepcion", "label": "Operario Recepción List"},
    {"module": "Operario", "route": "/operario/historial", "label": "Operario Historial"},
]

def count_rendered_rows(html: str) -> int:
    tbody_matches = re.findall(r'<tbody[^>]*>(.*?)</tbody>', html, re.DOTALL | re.IGNORECASE)
    if tbody_matches:
        tr_count = len(re.findall(r'<tr[^>]*>', tbody_matches[0], re.IGNORECASE))
        return tr_count
    return 0

def run():
    profiler = SQLQueryProfiler()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['full_name'] = 'Administrador Sistema'
            sess['role'] = 'Administrador'
            sess['permissions'] = {
                'dashboard': True,
                'usuarios': True,
                'ventas': True,
                'inventario': True,
                'productos': True,
                'administracion': True,
                'reportes': True,
                'configuracion': True,
                'crear_registros': True,
                'aprobar_registros': True,
                'solo_ver': False,
            }

        print("=" * 125)
        print(f"{'MÓDULO':<14} | {'RUTA':<32} | {'STATUS':<6} | {'QUERIES':<8} | {'SQL (ms)':<9} | {'TOTAL (ms)':<10} | {'KB':<8} | {'FILAS':<6} | {'CLASE'}")
        print("=" * 125)
        sys.stdout.flush()

        results = []
        for page in WEB_PAGES:
            route = page['route']
            profiler.start()
            t0 = time.perf_counter()
            try:
                res = client.get(route, follow_redirects=True)
                t1 = time.perf_counter()
                endpoint_time_ms = (t1 - t0) * 1000.0
                status_code = res.status_code
                payload_size_kb = len(res.data) / 1024.0
                html = res.get_data(as_text=True) if status_code == 200 else ""
                row_count = count_rendered_rows(html)
            except Exception as e:
                t1 = time.perf_counter()
                endpoint_time_ms = (t1 - t0) * 1000.0
                status_code = 500
                payload_size_kb = 0.0
                row_count = 0
                html = str(e)
            finally:
                profiler.stop()

            sql_count = len(profiler.queries)
            sql_time_ms = profiler.total_time * 1000.0

            if endpoint_time_ms > 1000.0 or sql_count >= 40 or payload_size_kb > 1500.0:
                classification = "RED"
            elif endpoint_time_ms > 300.0 or sql_count >= 15 or payload_size_kb > 400.0:
                classification = "YELLOW"
            else:
                classification = "GREEN"

            r = {
                "module": page["module"],
                "label": page["label"],
                "route": route,
                "status": status_code,
                "sql_queries": sql_count,
                "sql_time_ms": round(sql_time_ms, 1),
                "endpoint_time_ms": round(endpoint_time_ms, 1),
                "payload_kb": round(payload_size_kb, 1),
                "rendered_rows": row_count,
                "classification": classification
            }
            results.append(r)
            print(f"{r['module']:<14} | {r['route']:<32} | {r['status']:<6} | {r['sql_queries']:<8} | {r['sql_time_ms']:<9.1f} | {r['endpoint_time_ms']:<10.1f} | {r['payload_kb']:<8.1f} | {r['rendered_rows']:<6} | {r['classification']}")
            sys.stdout.flush()

        print("=" * 125)
        total_red = sum(1 for r in results if r['classification'] == 'RED')
        total_yellow = sum(1 for r in results if r['classification'] == 'YELLOW')
        total_green = sum(1 for r in results if r['classification'] == 'GREEN')
        print(f"\nResumen: Total Rutas Auditadas: {len(results)} | RED: {total_red} | YELLOW: {total_yellow} | GREEN: {total_green}\n")

if __name__ == '__main__':
    run()
