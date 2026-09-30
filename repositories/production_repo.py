"""
repositories/production_repo.py
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


def get_next_ot_number(conn=None) -> str:
    """Genera el siguiente número correlativo único para una Orden de Trabajo (ej: OT-00001)"""
    def _execute(cursor):
        cursor.execute("SELECT nextval('production_order_number_seq') as val")
        val = cursor.fetchone()["val"]
        return f"OT-{val:05d}"

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                val_str = _execute(cur)
            c.commit()
            return val_str


def list_production_orders(conn=None) -> list[dict]:
    """
    Retorna el listado completo de Órdenes de Trabajo con sus insumos planificados,
    insumos adicionales y lote de salida resultante resuelto en lote (evitando N+1 queries).
    """
    def _execute(cur):
        cur.execute(
            """
            SELECT po.id, po.ot_number, po.quantity, po.status, po.notes, po.created_at, po.approved_at, po.completed_at, po.unit_cost,
                   po.scheduled_date, po.schedule_order,
                   po.final_product_id, p.sku as final_product_sku, p.name as final_product_name,
                   plo.output_lot_id, l.lot_number as output_lot_number
            FROM production_orders po
            JOIN products p ON po.final_product_id = p.id
            LEFT JOIN production_lot_outputs plo ON plo.production_order_id = po.id
            LEFT JOIN lots l ON l.id = plo.output_lot_id
            ORDER BY po.id DESC
            """
        )
        rows = cur.fetchall()
        if not rows:
            return []

        ot_ids = [r["id"] for r in rows]

        # 1. Cargar insumos planificados de todas las OTs en un solo query
        cur.execute(
            """
            SELECT poi.production_order_id, poi.input_product_id, poi.quantity_required, poi.unit_cost,
                   p.sku as input_sku, p.name as input_name, p.cost as input_cost
            FROM production_order_items poi
            JOIN products p ON poi.input_product_id = p.id
            WHERE poi.production_order_id = ANY(%s)
            ORDER BY poi.id ASC
            """,
            (ot_ids,)
        )
        items_by_ot = {}
        for item_row in cur.fetchall():
            item_dict = dict(item_row)
            if item_dict.get("unit_cost") is None:
                item_dict["unit_cost"] = float(item_dict.get("input_cost") or 0.0)
            po_id = item_dict["production_order_id"]
            if po_id not in items_by_ot:
                items_by_ot[po_id] = []
            items_by_ot[po_id].append(item_dict)

        # 2. Cargar insumos adicionales de todas las OTs en un solo query
        cur.execute(
            """
            SELECT poai.production_order_id, poai.input_product_id, poai.quantity, poai.unit_cost, poai.reason,
                   p.sku as input_sku, p.name as input_name, p.cost as input_cost
            FROM production_order_additional_items poai
            JOIN products p ON poai.input_product_id = p.id
            WHERE poai.production_order_id = ANY(%s)
            ORDER BY poai.id ASC
            """,
            (ot_ids,)
        )
        add_items_by_ot = {}
        for add_row in cur.fetchall():
            add_dict = dict(add_row)
            if add_dict.get("unit_cost") is None:
                add_dict["unit_cost"] = float(add_dict.get("input_cost") or 0.0)
            po_id = add_dict["production_order_id"]
            if po_id not in add_items_by_ot:
                add_items_by_ot[po_id] = []
            add_items_by_ot[po_id].append(add_dict)

        # 3. Ensamblar lista final
        ots = []
        for r in rows:
            ot_dict = dict(r)
            ot_id = ot_dict["id"]
            ot_dict["items"] = items_by_ot.get(ot_id, [])
            ot_dict["additional_items"] = add_items_by_ot.get(ot_id, [])
            ots.append(ot_dict)

        return ots

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


def get_production_orders_paginated(
    page: int = 1,
    per_page: int = 25,
    search: str = None,
    status: str = None,
    conn=None
) -> dict:
    """
    Retorna órdenes de trabajo paginadas server-side con filtros opcionales de búsqueda y estado.
    - page: int >= 1 (default 1)
    - per_page: int in (25, 50, 100) (default 25)
    - search: búsqueda por número de OT, nombre de producto o SKU
    - status: 'Borrador' | 'Solicitada' | 'Aprobada' | 'Finalizada' | 'Cancelada' | 'all'
    """
    # 1. Sanitizar y validar parámetros
    try:
        page = int(page)
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = int(per_page)
        if per_page not in (25, 50, 100):
            per_page = 25
    except (ValueError, TypeError):
        per_page = 25

    offset = (page - 1) * per_page

    def _execute(cur):
        # 2. Construir condiciones WHERE dinámicas con parámetros seguros
        where_clauses = []
        params = []

        if status and status != 'all':
            where_clauses.append("po.status = %s")
            params.append(status.strip())

        if search and search.strip():
            search_pattern = f"%{search.strip()}%"
            where_clauses.append("(po.ot_number ILIKE %s OR p.name ILIKE %s OR p.sku ILIKE %s)")
            params.extend([search_pattern, search_pattern, search_pattern])

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        # 3. COUNT(*) total server-side
        count_query = f"""
            SELECT COUNT(*) as total
            FROM production_orders po
            JOIN products p ON po.final_product_id = p.id
            {where_sql}
        """
        cur.execute(count_query, params)
        total_row = cur.fetchone()
        total_count = int(total_row["total"] if total_row else 0)

        total_pages = max(1, (total_count + per_page - 1) // per_page)
        if total_count == 0:
            return {
                "items": [],
                "total": 0,
                "page": page,
                "per_page": per_page,
                "total_pages": 1
            }

        # 4. SELECT paginado con LIMIT y OFFSET
        select_query = f"""
            SELECT po.id, po.ot_number, po.quantity, po.status, po.notes, po.created_at, po.approved_at, po.completed_at, po.unit_cost,
                   po.scheduled_date, po.schedule_order,
                   po.final_product_id, p.sku as final_product_sku, p.name as final_product_name,
                   plo.output_lot_id, l.lot_number as output_lot_number
            FROM production_orders po
            JOIN products p ON po.final_product_id = p.id
            LEFT JOIN production_lot_outputs plo ON plo.production_order_id = po.id
            LEFT JOIN lots l ON l.id = plo.output_lot_id
            {where_sql}
            ORDER BY po.id DESC
            LIMIT %s OFFSET %s
        """
        data_params = list(params) + [per_page, offset]
        cur.execute(select_query, data_params)
        rows = cur.fetchall()

        if not rows:
            return {
                "items": [],
                "total": total_count,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages
            }

        ot_ids = [r["id"] for r in rows]

        # 5. Cargar insumos planificados de las OTs de la página
        cur.execute(
            """
            SELECT poi.production_order_id, poi.input_product_id, poi.quantity_required, poi.unit_cost,
                   p.sku as input_sku, p.name as input_name, p.cost as input_cost
            FROM production_order_items poi
            JOIN products p ON poi.input_product_id = p.id
            WHERE poi.production_order_id = ANY(%s)
            ORDER BY poi.id ASC
            """,
            (ot_ids,)
        )
        items_by_ot = {}
        for item_row in cur.fetchall():
            item_dict = dict(item_row)
            if item_dict.get("unit_cost") is None:
                item_dict["unit_cost"] = float(item_dict.get("input_cost") or 0.0)
            po_id = item_dict["production_order_id"]
            if po_id not in items_by_ot:
                items_by_ot[po_id] = []
            items_by_ot[po_id].append(item_dict)

        # 6. Cargar insumos adicionales de las OTs de la página
        cur.execute(
            """
            SELECT poai.production_order_id, poai.input_product_id, poai.quantity, poai.unit_cost, poai.reason,
                   p.sku as input_sku, p.name as input_name, p.cost as input_cost
            FROM production_order_additional_items poai
            JOIN products p ON poai.input_product_id = p.id
            WHERE poai.production_order_id = ANY(%s)
            ORDER BY poai.id ASC
            """,
            (ot_ids,)
        )
        add_items_by_ot = {}
        for add_row in cur.fetchall():
            add_dict = dict(add_row)
            if add_dict.get("unit_cost") is None:
                add_dict["unit_cost"] = float(add_dict.get("input_cost") or 0.0)
            po_id = add_dict["production_order_id"]
            if po_id not in add_items_by_ot:
                add_items_by_ot[po_id] = []
            add_items_by_ot[po_id].append(add_dict)

        # 7. Ensamblar lista de OTs de la página
        items = []
        for r in rows:
            ot_dict = dict(r)
            ot_id = ot_dict["id"]
            ot_dict["items"] = items_by_ot.get(ot_id, [])
            ot_dict["additional_items"] = add_items_by_ot.get(ot_id, [])
            items.append(ot_dict)

        return {
            "items": items,
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages
        }

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)



def list_active_production_orders(conn=None) -> list[dict]:
    """Retorna las Órdenes de Trabajo activas para operarios (Solicitada, Aprobada, En Proceso)."""
    all_ots = list_production_orders(conn=conn)
    return [ot for ot in all_ots if ot.get("status") in ("Solicitada", "Aprobada", "En Proceso")]


def get_production_order_by_id(ot_id: int, conn=None) -> dict | None:
    """Retorna el detalle completo de una OT específica, con insumos y consumos ya realizados."""
    def _execute(cur):
        cur.execute(
            """
            SELECT po.id, po.ot_number, po.quantity, po.status, po.notes, po.created_at, po.approved_at, po.completed_at, po.unit_cost,
                   po.scheduled_date, po.schedule_order,
                   po.final_product_id, p.sku as final_product_sku, p.name as final_product_name,
                   COALESCE(p.requires_lot, FALSE) as requires_lot,
                   plo.output_lot_id, l.lot_number as output_lot_number
            FROM production_orders po
            JOIN products p ON po.final_product_id = p.id
            LEFT JOIN production_lot_outputs plo ON plo.production_order_id = po.id
            LEFT JOIN lots l ON l.id = plo.output_lot_id
            WHERE po.id = %s
            """,
            (ot_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        
        ot = dict(row)

        # Insumos planificados
        cur.execute(
            """
            SELECT poi.id, poi.input_product_id, poi.quantity_required, poi.unit_cost,
                   p.sku as input_sku, p.name as input_name, p.cost as input_cost,
                   COALESCE(p.requires_lot, FALSE) as requires_lot
            FROM production_order_items poi
            JOIN products p ON poi.input_product_id = p.id
            WHERE poi.production_order_id = %s
            ORDER BY poi.id ASC
            """,
            (ot_id,)
        )
        ot["plan_items"] = [dict(r) for r in cur.fetchall()]
        ot["items_list"] = ot["plan_items"]

        # Insumos consumidos hasta el momento
        cur.execute(
            """
            SELECT plc.id, plc.input_product_id, plc.input_lot_id, plc.quantity_consumed, plc.created_at,
                   p.name as product_name, p.sku as product_sku,
                   l.lot_number
            FROM production_lot_consumptions plc
            JOIN products p ON plc.input_product_id = p.id
            JOIN lots l ON plc.input_lot_id = l.id
            WHERE plc.production_order_id = %s
            ORDER BY plc.id ASC
            """,
            (ot_id,)
        )
        ot["consumptions"] = [dict(r) for r in cur.fetchall()]
        return ot

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


def get_ot_material_availability(ot_id: int, conn=None) -> dict:
    """
    Calcula dinámicamente la disponibilidad de materiales para una OT consultando
    el inventario oficial en tiempo real (inventory_movements).
    Retorna un diccionario con:
    - ot_id: int
    - is_complete: bool (True si todos los insumos tienen missing_stock == 0)
    - status_label: 'Stock disponible' | 'Faltan materiales'
    - materials: list[dict] de cada insumo con required, available, missing.
    """
    from repositories.inventory_repo import get_relational_stock

    def _execute(cur):
        cur.execute(
            """
            SELECT poi.input_product_id, poi.quantity_required,
                   p.sku, p.name, p.cost
            FROM production_order_items poi
            JOIN products p ON poi.input_product_id = p.id
            WHERE poi.production_order_id = %s
            ORDER BY poi.id ASC
            """,
            (ot_id,)
        )
        rows = cur.fetchall()
        materials = []
        is_complete = True
        for r in rows:
            pid = r["input_product_id"]
            req = float(r["quantity_required"] or 0.0)
            avail = get_relational_stock(pid, conn=cur.connection)
            missing = max(0.0, req - avail)
            if missing > 1e-6:
                is_complete = False
            materials.append({
                "product_id": pid,
                "sku": r["sku"],
                "name": r["name"],
                "quantity_required": req,
                "available_stock": avail,
                "missing_stock": missing
            })

        return {
            "ot_id": ot_id,
            "is_complete": is_complete,
            "status_label": "Stock disponible" if is_complete else "Faltan materiales",
            "materials": materials
        }

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


def get_material_availability_for_orders(ot_ids: list[int], conn=None) -> dict[int, dict]:
    """
    Calcula en BATCH la disponibilidad de materiales para un lote de OTs (ej. las de la página activa),
    eliminando el problema N+1.
    Ejecuta exactamente 2 consultas SQL independientes del número de OTs:
      1. Carga todos los items de insumo de las OTs recibidas.
      2. Carga la suma de stock en inventory_movements agrupada por los insumos únicos.
    Retorna un diccionario { ot_id: { 'ot_id', 'is_complete', 'status_label', 'materials', 'missing_materials' } }
    """
    if not ot_ids:
        return {}

    def _execute(cur):
        # 1. Obtener todos los items de las OTs dadas
        cur.execute(
            """
            SELECT poi.production_order_id, poi.input_product_id, poi.quantity_required,
                   p.sku, p.name, p.cost
            FROM production_order_items poi
            JOIN products p ON poi.input_product_id = p.id
            WHERE poi.production_order_id = ANY(%s)
            ORDER BY poi.production_order_id, poi.id ASC
            """,
            (ot_ids,)
        )
        item_rows = cur.fetchall()

        # Insumos únicos necesarios
        product_ids = list({r["input_product_id"] for r in item_rows})
        stock_map = {}
        if product_ids:
            cur.execute(
                """
                SELECT product_id, COALESCE(SUM(quantity), 0.0) as stock
                FROM inventory_movements
                WHERE product_id = ANY(%s)
                GROUP BY product_id
                """,
                (product_ids,)
            )
            for s_row in cur.fetchall():
                stock_map[s_row["product_id"]] = float(s_row["stock"] or 0.0)

        # Agrupar por OT
        results = {}
        # Inicializar todas las OTs con lista vacía
        for ot_id in ot_ids:
            results[ot_id] = {
                "ot_id": ot_id,
                "is_complete": True,
                "status_label": "Stock disponible",
                "materials": [],
                "missing_materials": []
            }

        for r in item_rows:
            ot_id = r["production_order_id"]
            pid = r["input_product_id"]
            req = float(r["quantity_required"] or 0.0)
            avail = stock_map.get(pid, 0.0)
            missing = max(0.0, req - avail)

            mat_info = {
                "product_id": pid,
                "sku": r["sku"],
                "name": r["name"],
                "quantity_required": req,
                "available_stock": avail,
                "missing_stock": missing
            }
            results[ot_id]["materials"].append(mat_info)
            if missing > 1e-6:
                results[ot_id]["is_complete"] = False
                results[ot_id]["missing_materials"].append(mat_info)

        # Actualizar labels finales
        for ot_id, data in results.items():
            data["status_label"] = "Stock disponible" if data["is_complete"] else "Faltan materiales"

        return results

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)



def create_production_order(
    final_product_id: int,
    quantity: int,
    notes: str = "",
    status: str = "Borrador",
    items: list[dict] = None,
    scheduled_date: str = None,
    schedule_order: int = None,
    conn=None
) -> tuple[int, str]:
    """
    Crea una Orden de Trabajo con su correlativo oficial de secuencia.
    No valida ni consume stock si status == 'Borrador'.
    Permite opcionalmente asignar scheduled_date y schedule_order.
    Retorna (ot_id, ot_number).
    """
    clean_status = status.strip() if status else "Borrador"
    if clean_status not in ('Borrador', 'Solicitada', 'Aprobada', 'En Proceso', 'Finalizada', 'Cancelada'):
        clean_status = "Borrador"

    clean_scheduled_date = scheduled_date.strip() if scheduled_date and str(scheduled_date).strip() else None

    def _execute(cur):
        ot_num = get_next_ot_number(conn=cur.connection)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Si viene scheduled_date pero no schedule_order, calcular el siguiente orden del día
        actual_order = schedule_order
        if clean_scheduled_date and actual_order is None:
            cur.execute(
                "SELECT COALESCE(MAX(schedule_order), 0) + 1 as next_order FROM production_orders WHERE scheduled_date = %s",
                (clean_scheduled_date,)
            )
            actual_order = cur.fetchone()["next_order"]

        cur.execute(
            """
            INSERT INTO production_orders (ot_number, final_product_id, quantity, status, notes, created_at, scheduled_date, schedule_order)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (ot_num, final_product_id, int(quantity), clean_status, notes, now_str, clean_scheduled_date, actual_order)
        )
        ot_id = cur.fetchone()["id"]

        # Si no vienen ítems explícitos, cargar componentes de la receta del producto final
        plan_items = items
        if plan_items is None:
            cur.execute(
                """
                SELECT pri.input_product_id, pri.quantity_required
                FROM product_recipe_items pri
                JOIN product_recipes pr ON pri.recipe_id = pr.id
                WHERE pr.final_product_id = %s
                ORDER BY pri.id ASC
                """,
                (final_product_id,)
            )
            plan_items = cur.fetchall()

        for it in (plan_items or []):
            inp_id = it.get("input_product_id") or it["input_product_id"]
            unit_q = float(it.get("quantity_required") or it["quantity_required"])
            tot_q = float(it.get("total_quantity", unit_q * int(quantity)))
            cur.execute(
                """
                INSERT INTO production_order_items (production_order_id, input_product_id, quantity_required)
                VALUES (%s, %s, %s)
                """,
                (ot_id, inp_id, tot_q)
            )

        return ot_id, ot_num

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                res = _execute(cur)
            c.commit()
            return res


def update_draft_production_order(
    ot_id: int,
    final_product_id: int,
    quantity: int,
    notes: str = "",
    items: list[dict] = None,
    scheduled_date: str = None,
    schedule_order: int = None,
    update_schedule: bool = False,
    conn=None
) -> tuple[bool, str]:
    """
    Permite modificar una OT siempre y cuando esté en estado 'Borrador'.
    Recalcula o reemplaza los ítems planificados de acuerdo con la receta/BOM.
    Si update_schedule es True, actualiza scheduled_date y schedule_order.
    """
    if quantity <= 0:
        return False, "La cantidad a producir debe ser mayor a 0."

    clean_scheduled_date = scheduled_date.strip() if scheduled_date and str(scheduled_date).strip() else None

    def _execute(cur):
        cur.execute(
            "SELECT id, ot_number, status, final_product_id, scheduled_date, schedule_order FROM production_orders WHERE id = %s FOR UPDATE",
            (ot_id,)
        )
        ot = cur.fetchone()
        if not ot:
            return False, "Orden de Trabajo no encontrada."
        if ot["status"] != "Borrador":
            return False, f"Solo se pueden editar Órdenes de Trabajo en estado Borrador (Estado actual: {ot['status']})."

        if update_schedule:
            cur.execute(
                """
                UPDATE production_orders
                SET final_product_id = %s, quantity = %s, notes = %s, scheduled_date = %s, schedule_order = %s
                WHERE id = %s
                """,
                (final_product_id, int(quantity), notes, clean_scheduled_date, schedule_order, ot_id)
            )
        else:
            cur.execute(
                """
                UPDATE production_orders
                SET final_product_id = %s, quantity = %s, notes = %s
                WHERE id = %s
                """,
                (final_product_id, int(quantity), notes, ot_id)
            )

        # Actualizar insumos
        cur.execute("DELETE FROM production_order_items WHERE production_order_id = %s", (ot_id,))

        plan_items = items
        if plan_items is None:
            cur.execute(
                """
                SELECT pri.input_product_id, pri.quantity_required
                FROM product_recipe_items pri
                JOIN product_recipes pr ON pri.recipe_id = pr.id
                WHERE pr.final_product_id = %s
                ORDER BY pri.id ASC
                """,
                (final_product_id,)
            )
            plan_items = cur.fetchall()

        for it in (plan_items or []):
            inp_id = it.get("input_product_id") or it["input_product_id"]
            unit_q = float(it.get("quantity_required") or it["quantity_required"])
            tot_q = float(it.get("total_quantity", unit_q * int(quantity)))
            cur.execute(
                """
                INSERT INTO production_order_items (production_order_id, input_product_id, quantity_required)
                VALUES (%s, %s, %s)
                """,
                (ot_id, inp_id, tot_q)
            )

        return True, "Orden de Trabajo actualizada con éxito."

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                ok, msg = _execute(cur)
            if ok:
                c.commit()
            return ok, msg


def activate_draft_production_order(ot_id: int, conn=None) -> tuple[bool, str, dict]:
    """
    Valida atómicamente si existe stock disponible real en inventory_movements para todos
    los insumos requeridos por la OT.
    - Si falta stock: no activa la OT, permanece en 'Borrador' y retorna los faltantes.
    - Si hay stock suficiente: actualiza status a 'Solicitada' SIN reservar ni consumir inventario.
    Retorna (success, message, detail_dict).
    """
    from repositories.inventory_repo import get_relational_stock

    def _execute(cur):
        # Bloquear la OT
        cur.execute(
            "SELECT id, ot_number, status, final_product_id, quantity FROM production_orders WHERE id = %s FOR UPDATE",
            (ot_id,)
        )
        ot = cur.fetchone()
        if not ot:
            return False, "Orden de Trabajo no encontrada.", {}
        if ot["status"] != "Borrador":
            return False, f"Solo se pueden activar OTs en estado Borrador (Estado actual: {ot['status']}).", {}

        # Cargar insumos requeridos
        cur.execute(
            """
            SELECT poi.input_product_id, poi.quantity_required, p.sku, p.name
            FROM production_order_items poi
            JOIN products p ON poi.input_product_id = p.id
            WHERE poi.production_order_id = %s
            ORDER BY poi.input_product_id ASC
            """,
            (ot_id,)
        )
        items = cur.fetchall()
        if not items:
            return False, "La Orden de Trabajo no tiene insumos configurados.", {}

        # Bloquear productos involucrados en orden consistente id ASC
        pids = sorted(list(set([it["input_product_id"] for it in items])))
        cur.execute("SELECT id FROM products WHERE id = ANY(%s) ORDER BY id ASC FOR UPDATE", (pids,))

        # Validar stock disponible en tiempo real desde inventory_movements
        insufficient = []
        materials = []
        for it in items:
            pid = it["input_product_id"]
            req = float(it["quantity_required"])
            avail = get_relational_stock(pid, conn=cur.connection)
            missing = max(0.0, req - avail)
            materials.append({
                "product_id": pid,
                "sku": it["sku"],
                "name": it["name"],
                "quantity_required": req,
                "available_stock": avail,
                "missing_stock": missing
            })
            if missing > 1e-6:
                insufficient.append(f"{it['name']} (Necesario: {req:g}, Disponible: {avail:g}, Faltante: {missing:g})")

        if insufficient:
            return False, f"No se puede activar la OT porque falta stock: {'; '.join(insufficient)}", {
                "is_complete": False,
                "materials": materials
            }

        # Cambiar estado a 'Solicitada'
        cur.execute(
            "UPDATE production_orders SET status = 'Solicitada' WHERE id = %s",
            (ot_id,)
        )

        return True, f"Orden de Trabajo {ot['ot_number']} activada exitosamente.", {
            "is_complete": True,
            "materials": materials
        }

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                ok, msg, det = _execute(cur)
            if ok:
                c.commit()
            return ok, msg, det


def cancel_draft_production_order(ot_id: int, conn=None) -> tuple[bool, str]:
    """
    Cancela o elimina una OT en estado Borrador que no posee movimientos ni consumos históricos.
    """
    def _execute(cur):
        cur.execute("SELECT id, ot_number, status FROM production_orders WHERE id = %s FOR UPDATE", (ot_id,))
        ot = cur.fetchone()
        if not ot:
            return False, "Orden de Trabajo no encontrada."
        if ot["status"] != "Borrador":
            return False, f"Solo se pueden eliminar o cancelar OTs en estado Borrador (Estado actual: {ot['status']})."

        # Verificar que no tenga consumos ni lotes
        cur.execute("SELECT COUNT(*) as c FROM production_lot_consumptions WHERE production_order_id = %s", (ot_id,))
        if cur.fetchone()["c"] > 0:
            return False, "No se puede eliminar la OT porque tiene consumos de lotes registrados."

        cur.execute("SELECT COUNT(*) as c FROM production_lot_outputs WHERE production_order_id = %s", (ot_id,))
        if cur.fetchone()["c"] > 0:
            return False, "No se puede eliminar la OT porque tiene productos fabricados registrados."

        # Eliminar ítems y orden físicamente ya que es un borrador sin movimientos
        cur.execute("DELETE FROM production_order_items WHERE production_order_id = %s", (ot_id,))
        cur.execute("DELETE FROM production_orders WHERE id = %s", (ot_id,))
        return True, f"Orden de Trabajo {ot['ot_number']} eliminada correctamente."

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                ok, msg = _execute(cur)
            if ok:
                c.commit()
            return ok, msg






# ==============================================================================
# CALENDARIO Y PROGRAMACIÓN SEMANAL DE PRODUCCIÓN
# ==============================================================================

def set_production_order_schedule(
    ot_id: int,
    scheduled_date: Optional[str] = None,
    schedule_order: Optional[int] = None,
    conn=None
) -> tuple[bool, str, dict]:
    """
    Asigna o modifica la fecha programada y el orden diario de una Orden de Trabajo.
    - No cambia el estado (status) de la OT.
    - No reserva ni consume inventario ni genera lotes/movimientos.
    - Si scheduled_date es None o vacía, desprograma la OT (NULL).
    - Normaliza automáticamente los órdenes del día de origen y destino (1, 2, 3...).
    Retorna (success, message, detail_dict).
    """
    clean_date = scheduled_date.strip() if scheduled_date and str(scheduled_date).strip() else None

    def _normalize_day(cur, day_str):
        if not day_str:
            return
        cur.execute(
            """
            SELECT id FROM production_orders
            WHERE scheduled_date = %s
            ORDER BY schedule_order ASC NULLS LAST, id ASC
            FOR UPDATE
            """,
            (day_str,)
        )
        day_rows = cur.fetchall()
        for idx, row in enumerate(day_rows, start=1):
            cur.execute(
                "UPDATE production_orders SET schedule_order = %s WHERE id = %s",
                (idx, row["id"])
            )

    def _execute(cur):
        cur.execute(
            "SELECT id, ot_number, status, scheduled_date, schedule_order FROM production_orders WHERE id = %s FOR UPDATE",
            (ot_id,)
        )
        ot = cur.fetchone()
        if not ot:
            return False, "Orden de Trabajo no encontrada.", {}

        prev_date = str(ot["scheduled_date"]) if ot["scheduled_date"] else None
        target_date = clean_date

        # Determinar nuevo orden
        if target_date is None:
            # Desprogramar
            cur.execute(
                "UPDATE production_orders SET scheduled_date = NULL, schedule_order = NULL WHERE id = %s",
                (ot_id,)
            )
            # Re-normalizar el día anterior si tenía fecha
            if prev_date:
                _normalize_day(cur, prev_date)
            return True, f"OT {ot['ot_number']} desprogramada exitosamente.", {
                "ot_id": ot_id,
                "ot_number": ot["ot_number"],
                "scheduled_date": None,
                "schedule_order": None,
                "status": ot["status"]
            }

        # Programar para target_date
        # Obtener OTs existentes en target_date excepto esta OT
        cur.execute(
            """
            SELECT id FROM production_orders
            WHERE scheduled_date = %s AND id != %s
            ORDER BY schedule_order ASC NULLS LAST, id ASC
            FOR UPDATE
            """,
            (target_date, ot_id)
        )
        other_ids = [r["id"] for r in cur.fetchall()]

        # Insertar ot_id en la posición deseada
        if schedule_order is None or schedule_order > len(other_ids) + 1:
            pos = len(other_ids)  # al final
        else:
            pos = max(0, int(schedule_order) - 1)

        new_order_list = other_ids[:pos] + [ot_id] + other_ids[pos:]

        # Asignar fecha y órdenes normalizados
        for idx, oid in enumerate(new_order_list, start=1):
            cur.execute(
                "UPDATE production_orders SET scheduled_date = %s, schedule_order = %s WHERE id = %s",
                (target_date, idx, oid)
            )

        # Si cambió de día respecto al anterior, normalizar el día anterior
        if prev_date and prev_date != target_date:
            _normalize_day(cur, prev_date)

        return True, f"OT {ot['ot_number']} programada para {target_date}.", {
            "ot_id": ot_id,
            "ot_number": ot["ot_number"],
            "scheduled_date": target_date,
            "schedule_order": pos + 1,
            "status": ot["status"]
        }

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                ok, msg, det = _execute(cur)
            if ok:
                c.commit()
            return ok, msg, det


def list_scheduled_production_orders(start_date: str, end_date: str, conn=None) -> list[dict]:
    """
    Retorna las Órdenes de Trabajo programadas dentro del rango [start_date, end_date]
    ordenadas por scheduled_date ASC, schedule_order ASC, id ASC.
    Calcula dinámicamente la disponibilidad de stock para cada OT.
    """
    def _execute(cur):
        cur.execute(
            """
            SELECT po.id, po.ot_number, po.quantity, po.status, po.notes, po.created_at, po.approved_at, po.completed_at, po.unit_cost,
                   po.scheduled_date, po.schedule_order,
                   po.final_product_id, p.sku as final_product_sku, p.name as final_product_name,
                   plo.output_lot_id, l.lot_number as output_lot_number
            FROM production_orders po
            JOIN products p ON po.final_product_id = p.id
            LEFT JOIN production_lot_outputs plo ON plo.production_order_id = po.id
            LEFT JOIN lots l ON l.id = plo.output_lot_id
            WHERE po.scheduled_date >= %s AND po.scheduled_date <= %s
            ORDER BY po.scheduled_date ASC, po.schedule_order ASC NULLS LAST, po.id ASC
            """,
            (start_date, end_date)
        )
        rows = cur.fetchall()
        if not rows:
            return []

        ot_ids = [r["id"] for r in rows]

        # Insumos requeridos
        cur.execute(
            """
            SELECT poi.production_order_id, poi.input_product_id, poi.quantity_required, poi.unit_cost,
                   p.sku as input_sku, p.name as input_name, p.cost as input_cost
            FROM production_order_items poi
            JOIN products p ON poi.input_product_id = p.id
            WHERE poi.production_order_id = ANY(%s)
            ORDER BY poi.id ASC
            """,
            (ot_ids,)
        )
        items_by_ot = {}
        for item_row in cur.fetchall():
            it = dict(item_row)
            p_id = it["production_order_id"]
            if p_id not in items_by_ot:
                items_by_ot[p_id] = []
            items_by_ot[p_id].append(it)

        # Insumos adicionales
        cur.execute(
            """
            SELECT poai.production_order_id, poai.input_product_id, poai.quantity, poai.unit_cost, poai.reason,
                   p.sku as input_sku, p.name as input_name
            FROM production_order_additional_items poai
            JOIN products p ON poai.input_product_id = p.id
            WHERE poai.production_order_id = ANY(%s)
            ORDER BY poai.id ASC
            """,
            (ot_ids,)
        )
        add_by_ot = {}
        for add_row in cur.fetchall():
            it = dict(add_row)
            p_id = it["production_order_id"]
            if p_id not in add_by_ot:
                add_by_ot[p_id] = []
            add_by_ot[p_id].append(it)

        result = []
        for r in rows:
            ot_dict = dict(r)
            ot_id = ot_dict["id"]
            ot_dict["items"] = items_by_ot.get(ot_id, [])
            ot_dict["additional_items"] = add_by_ot.get(ot_id, [])
            
            # Disponibilidad dinámica
            avail = get_ot_material_availability(ot_id, conn=cur.connection)
            ot_dict["is_complete"] = avail["is_complete"]
            ot_dict["status_label"] = avail["status_label"]
            ot_dict["materials_availability"] = avail["materials"]
            ot_dict["missing_materials"] = [m for m in avail["materials"] if m["missing_stock"] > 1e-6]
            
            result.append(ot_dict)
        return result

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


def list_unscheduled_production_orders(conn=None) -> list[dict]:
    """
    Retorna las Órdenes de Trabajo no programadas (scheduled_date IS NULL)
    excluyendo las finalizadas y canceladas para la planificación activa,
    ordenadas por id DESC. Calcula dinámicamente la disponibilidad de stock.
    """
    def _execute(cur):
        cur.execute(
            """
            SELECT po.id, po.ot_number, po.quantity, po.status, po.notes, po.created_at, po.approved_at, po.completed_at, po.unit_cost,
                   po.scheduled_date, po.schedule_order,
                   po.final_product_id, p.sku as final_product_sku, p.name as final_product_name
            FROM production_orders po
            JOIN products p ON po.final_product_id = p.id
            WHERE po.scheduled_date IS NULL
              AND po.status NOT IN ('Finalizada', 'Cancelada')
            ORDER BY po.id DESC
            """
        )
        rows = cur.fetchall()
        if not rows:
            return []

        ot_ids = [r["id"] for r in rows]

        cur.execute(
            """
            SELECT poi.production_order_id, poi.input_product_id, poi.quantity_required, poi.unit_cost,
                   p.sku as input_sku, p.name as input_name, p.cost as input_cost
            FROM production_order_items poi
            JOIN products p ON poi.input_product_id = p.id
            WHERE poi.production_order_id = ANY(%s)
            ORDER BY poi.id ASC
            """,
            (ot_ids,)
        )
        items_by_ot = {}
        for item_row in cur.fetchall():
            it = dict(item_row)
            p_id = it["production_order_id"]
            if p_id not in items_by_ot:
                items_by_ot[p_id] = []
            items_by_ot[p_id].append(it)

        result = []
        for r in rows:
            ot_dict = dict(r)
            ot_id = ot_dict["id"]
            ot_dict["items"] = items_by_ot.get(ot_id, [])
            ot_dict["additional_items"] = []

            avail = get_ot_material_availability(ot_id, conn=cur.connection)
            ot_dict["is_complete"] = avail["is_complete"]
            ot_dict["status_label"] = avail["status_label"]
            ot_dict["materials_availability"] = avail["materials"]
            ot_dict["missing_materials"] = [m for m in avail["materials"] if m["missing_stock"] > 1e-6]

            result.append(ot_dict)
        return result

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


def get_recipes_paginated(
    page: int = 1,
    per_page: int = 25,
    search: Optional[str] = None,
    conn=None
) -> dict:
    """
    Retorna recetas de producción paginadas server-side con sus componentes (BOM)
    cargados en BATCH mediante ANY(%s) en exactamente 2 consultas SQL (0 N+1).
    """
    try:
        page = int(page)
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = int(per_page)
        if per_page not in (25, 50, 100):
            per_page = 25
    except (ValueError, TypeError):
        per_page = 25

    offset = (page - 1) * per_page

    def _execute(cur):
        where_clauses = []
        params = []

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            # Búsqueda por código de receta, producto final (SKU, nombre) o insumo componente
            where_clauses.append(
                """(
                    LOWER(COALESCE(pr.recipe_code, '')) LIKE %s OR
                    LOWER(p.sku) LIKE %s OR
                    LOWER(p.name) LIKE %s OR
                    EXISTS (
                        SELECT 1 FROM product_recipe_items pri_s
                        JOIN products p_in ON pri_s.input_product_id = p_in.id
                        WHERE pri_s.recipe_id = pr.id AND (
                            LOWER(p_in.sku) LIKE %s OR
                            LOWER(p_in.name) LIKE %s
                        )
                    )
                )"""
            )
            params.extend([term, term, term, term, term])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # 1. Conteo total de recetas coincidentes
        count_sql = f"""
            SELECT COUNT(*) as total
            FROM product_recipes pr
            JOIN products p ON pr.final_product_id = p.id
            {where_sql}
        """
        cur.execute(count_sql, params)
        total_count = int(cur.fetchone()["total"])

        total_pages = max(1, (total_count + per_page - 1) // per_page)
        nonlocal page
        if page > total_pages and total_pages > 0:
            page = total_pages
            actual_offset = (page - 1) * per_page
        else:
            actual_offset = offset

        # 2. Recetas paginadas de la página activa
        select_sql = f"""
            SELECT pr.id, pr.created_at, pr.recipe_code, p.sku as final_sku, p.name as final_name,
                   p.line, p.variety, p.format_capacity
            FROM product_recipes pr
            JOIN products p ON pr.final_product_id = p.id
            {where_sql}
            ORDER BY pr.id ASC
            LIMIT %s OFFSET %s
        """
        cur.execute(select_sql, list(params) + [per_page, actual_offset])
        recipe_rows = cur.fetchall()

        if not recipe_rows:
            return {
                "items": [],
                "total": total_count,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
            }

        # 3. Carga BATCH de todos los componentes de las recetas visibles en 1 sola consulta (ANY)
        recipe_ids = [r["id"] for r in recipe_rows]
        cur.execute(
            """
            SELECT pri.recipe_id, pri.quantity_required, pri.unit, pri.notes,
                   p.sku as input_sku, p.name as input_name
            FROM product_recipe_items pri
            JOIN products p ON pri.input_product_id = p.id
            WHERE pri.recipe_id = ANY(%s)
            ORDER BY pri.id ASC
            """,
            (recipe_ids,)
        )
        items_by_recipe: dict[int, list] = {}
        for item_row in cur.fetchall():
            rid = item_row["recipe_id"]
            if rid not in items_by_recipe:
                items_by_recipe[rid] = []
            items_by_recipe[rid].append(dict(item_row))

        recipes_result = []
        for r in recipe_rows:
            r_dict = dict(r)
            r_dict["items"] = items_by_recipe.get(r["id"], [])
            recipes_result.append(r_dict)

        return {
            "items": recipes_result,
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        }

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)
