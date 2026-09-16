"""
repositories/lot_genealogy_repo.py
Repository for lot genealogy, bidirectional traceability, and recall queries.
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
import psycopg2
import psycopg2.extras
from core.database import get_connection


def create_lot(
    product_id: int,
    lot_number: str,
    lot_type: str = "RAW_MATERIAL",
    origin_type: str = "PURCHASE",
    origin_id: Optional[int] = None,
    supplier_id: Optional[int] = None,
    purchase_order_id: Optional[int] = None,
    inventory_entry_id: Optional[int] = None,
    production_order_id: Optional[int] = None,
    initial_quantity: float = 0.0,
    created_at: Optional[str] = None,
    expiry_date: Optional[str] = None,
    status: str = "ACTIVE",
    warehouse: str = "Principal",
    notes: Optional[str] = None,
    conn=None
) -> int:
    """Crea una entidad de lote inmutable en la tabla lots."""
    clean_lot = (lot_number or "").strip()
    if not clean_lot:
        raise ValueError("INV-010: El número de lote no puede estar vacío.")

    now_iso = created_at or datetime.now(timezone.utc).isoformat()

    def _execute(cur):
        cur.execute(
            """
            INSERT INTO lots (
                product_id, lot_number, lot_type, origin_type, origin_id,
                supplier_id, purchase_order_id, inventory_entry_id, production_order_id,
                initial_quantity, created_at, expiry_date, status, warehouse, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                product_id, clean_lot, lot_type, origin_type, origin_id,
                supplier_id, purchase_order_id, inventory_entry_id, production_order_id,
                float(initial_quantity), now_iso, expiry_date, status, warehouse, notes
            )
        )
        return cur.fetchone()["id"]

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                lot_id = _execute(cur)
            c.commit()
            return lot_id


def get_lot(lot_id: int, conn=None) -> Optional[Dict[str, Any]]:
    """Obtiene un lote por su ID interno primario."""
    def _execute(cur):
        cur.execute(
            """
            SELECT l.*, p.name as product_name, p.sku, p.category, p.product_type,
                   s.name as supplier_name, po.oc_number, ie.order_number as entry_order_number,
                   pro.ot_number as production_ot_number
            FROM lots l
            JOIN products p ON p.id = l.product_id
            LEFT JOIN suppliers s ON s.id = l.supplier_id
            LEFT JOIN purchase_orders po ON po.id = l.purchase_order_id
            LEFT JOIN inventory_entries ie ON ie.id = l.inventory_entry_id
            LEFT JOIN production_orders pro ON pro.id = l.production_order_id
            WHERE l.id = %s;
            """,
            (lot_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


def get_lot_by_product_and_number(product_id: int, lot_number: str, conn=None) -> Optional[Dict[str, Any]]:
    """Obtiene un lote por combinación de product_id y lot_number."""
    clean_lot = (lot_number or "").strip()
    def _execute(cur):
        cur.execute(
            """
            SELECT l.*, p.name as product_name, p.sku
            FROM lots l
            JOIN products p ON p.id = l.product_id
            WHERE l.product_id = %s AND l.lot_number = %s
            ORDER BY l.id DESC
            LIMIT 1;
            """,
            (product_id, clean_lot)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


def record_production_consumption(
    production_order_id: int,
    input_product_id: int,
    input_lot_id: int,
    quantity_consumed: float,
    created_at: Optional[str] = None,
    conn=None
) -> int:
    """Registra el consumo exacto de un lote de insumo en una OT."""
    now_iso = created_at or datetime.now(timezone.utc).isoformat()
    def _execute(cur):
        cur.execute(
            """
            INSERT INTO production_lot_consumptions (
                production_order_id, input_product_id, input_lot_id, quantity_consumed, created_at
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (production_order_id, input_product_id, input_lot_id, float(quantity_consumed), now_iso)
        )
        return cur.fetchone()["id"]

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                cid = _execute(cur)
            c.commit()
            return cid


def record_production_output(
    production_order_id: int,
    output_product_id: int,
    output_lot_id: int,
    quantity_produced: float,
    created_at: Optional[str] = None,
    conn=None
) -> int:
    """Registra el lote de producto terminado generado por una OT."""
    now_iso = created_at or datetime.now(timezone.utc).isoformat()
    def _execute(cur):
        cur.execute(
            """
            INSERT INTO production_lot_outputs (
                production_order_id, output_product_id, output_lot_id, quantity_produced, created_at
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (production_order_id, output_product_id, output_lot_id, float(quantity_produced), now_iso)
        )
        return cur.fetchone()["id"]

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                oid = _execute(cur)
            c.commit()
            return oid


def trace_lot_forward(lot_id: int, conn=None) -> Dict[str, Any]:
    """
    Recorre hacia adelante la genealogía de un lote:
    Lote -> OTs que lo consumieron -> Lotes producidos -> OTs subsecuentes -> Ventas -> Clientes.
    Soporta múltiples niveles mediante recursión protegida.
    """
    def _execute(cur):
        lot = get_lot(lot_id, conn=conn)
        if not lot:
            return {"lot": None, "productions": [], "sales": []}

        # Consulta recursiva de lotes descendientes
        cur.execute(
            """
            WITH RECURSIVE forward_tree AS (
                -- Caso base: el lote consultado
                SELECT l.id as lot_id, l.product_id, l.lot_number, l.lot_type, 0 as depth,
                       ARRAY[l.id] as path
                FROM lots l
                WHERE l.id = %s

                UNION ALL

                -- Paso recursivo: OTs que consumieron los lotes del nivel anterior y generaron nuevos lotes
                SELECT plo.output_lot_id, plo.output_product_id, l_out.lot_number, l_out.lot_type,
                       ft.depth + 1, ft.path || plo.output_lot_id
                FROM forward_tree ft
                JOIN production_lot_consumptions plc ON plc.input_lot_id = ft.lot_id
                JOIN production_lot_outputs plo ON plo.production_order_id = plc.production_order_id
                JOIN lots l_out ON l_out.id = plo.output_lot_id
                WHERE NOT plo.output_lot_id = ANY(ft.path) AND ft.depth < 10
            )
            SELECT ft.*, p.name as product_name, p.sku
            FROM forward_tree ft
            JOIN products p ON p.id = ft.product_id
            ORDER BY ft.depth ASC, ft.lot_id ASC;
            """,
            (lot_id,)
        )
        tree_lots = [dict(r) for r in cur.fetchall()]
        all_lot_ids = [r["lot_id"] for r in tree_lots]

        # Obtener todas las producciones involucradas
        cur.execute(
            """
            SELECT plc.id as consumption_id, plc.production_order_id, plc.input_lot_id, plc.quantity_consumed,
                   po.ot_number, po.status as ot_status,
                   plo.output_lot_id, plo.quantity_produced,
                   l_in.lot_number as input_lot_number, p_in.name as input_product_name,
                   l_out.lot_number as output_lot_number, p_out.name as output_product_name
            FROM production_lot_consumptions plc
            JOIN production_orders po ON po.id = plc.production_order_id
            LEFT JOIN production_lot_outputs plo ON plo.production_order_id = po.id
            JOIN lots l_in ON l_in.id = plc.input_lot_id
            JOIN products p_in ON p_in.id = plc.input_product_id
            LEFT JOIN lots l_out ON l_out.id = plo.output_lot_id
            LEFT JOIN products p_out ON p_out.id = plo.output_product_id
            WHERE plc.input_lot_id = ANY(%s)
            ORDER BY plc.id ASC;
            """,
            (all_lot_ids,)
        )
        productions = [dict(r) for r in cur.fetchall()]

        # Obtener todas las ventas que consumieron cualquiera de los lotes del árbol
        cur.execute(
            """
            SELECT slm.id as movement_id, slm.sale_id, slm.lot_id, slm.lot_number, slm.quantity, slm.moved_at,
                   s.sale_number, s.customer_name, s.customer_email, s.sale_date,
                   p.name as product_name, p.sku
            FROM sale_lot_movements slm
            JOIN sales s ON s.id = slm.sale_id
            JOIN products p ON p.id = slm.product_id
            WHERE slm.lot_id = ANY(%s) OR (slm.product_id = ANY(%s) AND slm.lot_number = ANY(%s))
            ORDER BY slm.id ASC;
            """,
            (all_lot_ids, [r["product_id"] for r in tree_lots], [r["lot_number"] for r in tree_lots])
        )
        sales = [dict(r) for r in cur.fetchall()]

        return {
            "root_lot": lot,
            "tree_lots": tree_lots,
            "productions": productions,
            "sales": sales
        }

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


def trace_lot_backward(lot_id: int, conn=None) -> Dict[str, Any]:
    """
    Recorre hacia atrás la genealogía de un lote:
    Lote -> OT que lo fabricó -> Lotes de insumos utilizados -> OTs anteriores -> Recepciones -> OC -> Proveedor.
    """
    def _execute(cur):
        lot = get_lot(lot_id, conn=conn)
        if not lot:
            return {"root_lot": None, "ancestor_lots": [], "origins": []}

        # Consulta recursiva de ancestros
        cur.execute(
            """
            WITH RECURSIVE backward_tree AS (
                -- Caso base: el lote consultado
                SELECT l.id as lot_id, l.product_id, l.lot_number, l.origin_type, l.origin_id,
                       l.supplier_id, l.purchase_order_id, l.inventory_entry_id, l.production_order_id,
                       0 as depth, ARRAY[l.id] as path
                FROM lots l
                WHERE l.id = %s

                UNION ALL

                -- Paso recursivo: lotes de insumos que alimentaron a la OT que fabricó el lote actual
                SELECT l_in.id, l_in.product_id, l_in.lot_number, l_in.origin_type, l_in.origin_id,
                       l_in.supplier_id, l_in.purchase_order_id, l_in.inventory_entry_id, l_in.production_order_id,
                       bt.depth + 1, bt.path || l_in.id
                FROM backward_tree bt
                JOIN production_lot_outputs plo ON plo.output_lot_id = bt.lot_id
                JOIN production_lot_consumptions plc ON plc.production_order_id = plo.production_order_id
                JOIN lots l_in ON l_in.id = plc.input_lot_id
                WHERE NOT l_in.id = ANY(bt.path) AND bt.depth < 10
            )
            SELECT bt.*, p.name as product_name, p.sku, s.name as supplier_name, po.oc_number,
                   ie.order_number as entry_order_number
            FROM backward_tree bt
            JOIN products p ON p.id = bt.product_id
            LEFT JOIN suppliers s ON s.id = bt.supplier_id
            LEFT JOIN purchase_orders po ON po.id = bt.purchase_order_id
            LEFT JOIN inventory_entries ie ON ie.id = bt.inventory_entry_id
            ORDER BY bt.depth DESC, bt.lot_id ASC;
            """,
            (lot_id,)
        )
        ancestors = [dict(r) for r in cur.fetchall()]

        # Buscar las OTs de transformación
        all_lot_ids = [r["lot_id"] for r in ancestors]
        cur.execute(
            """
            SELECT po.id as production_order_id, po.ot_number, po.status,
                   plc.input_lot_id, plc.quantity_consumed, l_in.lot_number as input_lot_number,
                   p_in.name as input_product_name,
                   plo.output_lot_id, plo.quantity_produced, l_out.lot_number as output_lot_number,
                   p_out.name as output_product_name
            FROM production_orders po
            JOIN production_lot_outputs plo ON plo.production_order_id = po.id
            JOIN production_lot_consumptions plc ON plc.production_order_id = po.id
            JOIN lots l_in ON l_in.id = plc.input_lot_id
            JOIN products p_in ON p_in.id = plc.input_product_id
            JOIN lots l_out ON l_out.id = plo.output_lot_id
            JOIN products p_out ON p_out.id = plo.output_product_id
            WHERE plo.output_lot_id = ANY(%s) OR plc.input_lot_id = ANY(%s)
            ORDER BY po.id ASC;
            """,
            (all_lot_ids, all_lot_ids)
        )
        transformations = [dict(r) for r in cur.fetchall()]

        return {
            "root_lot": lot,
            "ancestors": ancestors,
            "transformations": transformations
        }

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


def get_lot_recall_impact(lot_id: int, conn=None) -> Dict[str, Any]:
    """
    Calcula el impacto 360° para un recall o retiro de producto:
    - OTs afectadas
    - Lotes derivados afectados
    - Ventas afectadas
    - Clientes afectados
    - Cantidades totales impactadas
    - Stock actual remanente en bodega
    """
    forward = trace_lot_forward(lot_id, conn=conn)
    root = forward["root_lot"]
    if not root:
        return {"error": "Lote no encontrado", "affected_clients": [], "affected_sales": [], "affected_lots": []}

    tree_lots = forward["tree_lots"]
    sales = forward["sales"]
    productions = forward["productions"]

    # Clientes únicos afectados
    clients_map = {}
    for s in sales:
        cname = s["customer_name"]
        if cname not in clients_map:
            clients_map[cname] = {
                "customer_name": cname,
                "customer_email": s["customer_email"],
                "total_units_bought": 0.0,
                "sales": []
            }
        clients_map[cname]["total_units_bought"] += float(s["quantity"])
        clients_map[cname]["sales"].append(s["sale_number"])

    # Stock remanente en bodega de todos los lotes involucrados
    all_lot_ids = [l["lot_id"] for l in tree_lots]
    remaining_stock = []
    with (conn if conn else get_connection()) as c:
        with c.cursor() as cur:
            cur.execute(
                """
                SELECT ls.product_id, ls.lot_number, ls.available_qty, ls.warehouse,
                       p.name as product_name, p.sku
                FROM lot_stock ls
                JOIN products p ON p.id = ls.product_id
                WHERE ls.lot_id = ANY(%s) AND ls.available_qty > 0;
                """,
                (all_lot_ids,)
            )
            remaining_stock = [dict(r) for r in cur.fetchall()]

    return {
        "target_lot": root,
        "affected_lots_count": len(tree_lots),
        "affected_lots": tree_lots,
        "affected_productions_count": len(productions),
        "affected_productions": productions,
        "affected_sales_count": len(sales),
        "affected_sales": sales,
        "affected_clients_count": len(clients_map),
        "affected_clients": list(clients_map.values()),
        "remaining_warehouse_stock": remaining_stock,
        "total_units_sold": sum(float(s["quantity"]) for s in sales),
    }


def search_lots(query_str: str = "", limit: int = 50, conn=None) -> List[Dict[str, Any]]:
    """Busca lotes por número de lote, SKU de producto, nombre, OT, OC, venta, proveedor o cliente."""
    q = f"%{(query_str or '').strip()}%"
    def _execute(cur):
        cur.execute(
            """
            SELECT DISTINCT l.id, l.product_id, l.lot_number, l.lot_type, l.origin_type,
                   l.origin_id, l.supplier_id, l.purchase_order_id, l.inventory_entry_id,
                   l.production_order_id, l.initial_quantity, l.created_at, l.expiry_date,
                   l.status, l.warehouse, l.notes,
                   p.name as product_name, p.sku, p.category,
                   ls.available_qty, s.name as supplier_name,
                   po.oc_number, pord.ot_number
            FROM lots l
            JOIN products p ON p.id = l.product_id
            LEFT JOIN lot_stock ls ON ls.lot_id = l.id
            LEFT JOIN suppliers s ON s.id = l.supplier_id
            LEFT JOIN purchase_orders po ON po.id = l.purchase_order_id
            LEFT JOIN production_orders pord ON pord.id = l.production_order_id
            LEFT JOIN production_lot_consumptions plc ON plc.input_lot_id = l.id
            LEFT JOIN production_orders pord_cons ON pord_cons.id = plc.production_order_id
            LEFT JOIN sale_lot_movements slm ON slm.lot_id = l.id
            LEFT JOIN sales sale ON sale.id = slm.sale_id
            WHERE l.lot_number ILIKE %s
               OR p.name ILIKE %s
               OR p.sku ILIKE %s
               OR s.name ILIKE %s
               OR po.oc_number ILIKE %s
               OR pord.ot_number ILIKE %s
               OR pord_cons.ot_number ILIKE %s
               OR sale.sale_number ILIKE %s
               OR sale.customer_name ILIKE %s
            ORDER BY l.id DESC
            LIMIT %s;
            """,
            (q, q, q, q, q, q, q, q, q, limit)
        )
        return [dict(r) for r in cur.fetchall()]

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)
