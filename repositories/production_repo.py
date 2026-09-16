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
                   p.sku as final_product_sku, p.name as final_product_name,
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
            SELECT poi.production_order_id, poi.quantity_required, poi.unit_cost,
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
            SELECT poai.production_order_id, poai.quantity, poai.unit_cost, poai.reason,
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


