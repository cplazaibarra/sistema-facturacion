"""
repositories/kardex_repo.py
Repositorio especializado para la Auditoría y Consulta del Kardex Valorizado y PPP (Precio Promedio Ponderado).
Construido estrictamente sobre la fuente de verdad única: inventory_movements.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from core.database import get_connection


# Mapeo de nombres legibles para el usuario de cada tipo de movimiento
MOVEMENT_TYPE_LABELS = {
    "PURCHASE_RECEIPT": "Ingreso Compra",
    "PRODUCTION_OUTPUT": "Ingreso Producción",
    "INITIAL_BALANCE": "Inventario Inicial",
    "IN": "Ingreso / Ajuste (+)",
    "ADJUSTMENT_IN": "Ajuste Entrada",
    "RETURN": "Devolución (+)",
    "SALE_REVERSAL": "Reversa Venta (+)",
    "SALE": "Salida Venta",
    "PRODUCTION_INPUT": "Salida Producción",
    "SALE_PACKAGING": "Salida Embalaje",
    "SALE_PACKAGING_REVERSAL": "Reversa Embalaje",
    "ADJUSTMENT_OUT": "Ajuste Salida",
}


def get_current_ppp(product_id: int, conn=None) -> float:
    """
    Retorna el PPP (Precio Promedio Ponderado) vigente actual para un producto,
    calculado matemáticamente a partir de inventory_movements existentes.

    MOMENTO EXACTO:
    Corresponde al PPP del inventario existente INMEDIATAMENTE ANTES del movimiento.
    Si se proporciona `conn`, reutiliza exactamente esa transacción sin hacer commit/rollback.
    Si el producto no tiene movimientos, utiliza product.cost como fallback o 0.0.
    """
    def _execute(cur):
        cur.execute("SELECT cost FROM products WHERE id = %s", (product_id,))
        p = cur.fetchone()
        default_cost = float(p.get("cost") or 0.0) if p else 0.0

        cur.execute(
            """
            SELECT im.id, im.quantity,
                   COALESCE(r.new_unit_cost, im.unit_cost) AS unit_cost
            FROM inventory_movements im
            LEFT JOIN (
                SELECT DISTINCT ON (movement_id) movement_id, new_unit_cost
                FROM inventory_cost_revaluations
                ORDER BY movement_id, id DESC
            ) r ON r.movement_id = im.id
            WHERE im.product_id = %s
            ORDER BY im.created_at::timestamptz ASC, im.id ASC
            """,
            (product_id,)
        )
        movements = cur.fetchall()

        running_qty = 0.0
        running_value = 0.0
        running_ppp = default_cost

        for mov in movements:
            qty = float(mov["quantity"] or 0.0)
            raw_cost = float(mov["unit_cost"] or 0.0)

            if qty > 0.0:
                in_qty = qty
                unit_price_applied = raw_cost
                movement_cost = in_qty * unit_price_applied

                running_qty += in_qty
                running_value += movement_cost
                if running_qty > 1e-6:
                    running_ppp = running_value / running_qty
                else:
                    running_ppp = unit_price_applied if unit_price_applied > 0 else running_ppp
            elif qty < 0.0:
                out_qty = abs(qty)
                movement_cost = out_qty * running_ppp
                running_qty = max(0.0, running_qty - out_qty)
                running_value = max(0.0, running_value - movement_cost)

        return round(running_ppp, 4)

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


def get_product_kardex_history(
    product_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    movement_type_filter: Optional[str] = None,
    order_asc: bool = False,
    page: Optional[int] = None,
    per_page: Optional[int] = None,
    conn=None
) -> dict:
    """
    Calcula y reconstruye matemáticamente paso a paso el Kardex Valorizado y la evolución del PPP
    para un producto dado, basándose en inventory_movements.
    
    Soporta paginación server-side (page, per_page in (25, 50, 100)) preservando con exactitud
    el PPP y saldos acumulados continuous.
    
    Retorna un diccionario estructurado:
    {
        "product": dict,
        "current_stock": float,
        "current_ppp": float,
        "current_inventory_value": float,
        "total_movements": int,
        "filtered_movements": int,
        "page": int,
        "per_page": int,
        "total_pages": int,
        "rows": list[dict]
    }
    """
    # 1. Sanitizar parámetros de paginación
    is_paginated = (page is not None or per_page is not None)
    target_page = 1
    target_per_page = 25
    if is_paginated:
        try:
            target_page = int(page) if page is not None else 1
            if target_page < 1:
                target_page = 1
        except (ValueError, TypeError):
            target_page = 1

        try:
            target_per_page = int(per_page) if per_page is not None else 25
            if target_per_page not in (25, 50, 100):
                target_per_page = 25
        except (ValueError, TypeError):
            target_per_page = 25

    def _execute(cur):
        nonlocal target_page, target_per_page
        # 1. Obtener producto
        cur.execute(
            """
            SELECT id, sku, name, description, category, product_type, unit_of_measure, cost
            FROM products
            WHERE id = %s
            """,
            (product_id,)
        )
        product = cur.fetchone()
        if not product:
            return {}

        # 2. Cargar TODOS los movimientos del producto en orden cronológico estricto determinístico
        # para reconstruir la matemática exacta del PPP desde el inicio de los tiempos
        cur.execute(
            """
            SELECT im.id, im.product_id, im.movement_type, im.quantity,
                   im.unit_cost AS original_unit_cost,
                   COALESCE(r.new_unit_cost, im.unit_cost) AS unit_cost,
                   (r.new_unit_cost IS NOT NULL) AS is_revalued,
                   r.old_unit_cost AS reval_old_cost,
                   r.new_unit_cost AS reval_new_cost,
                   r.reason AS reval_reason,
                   r.created_by AS reval_created_by,
                   r.created_at AS reval_created_at,
                   im.lot_number, im.warehouse, im.reference_type, im.reference_id,
                   im.notes, im.created_at, im.created_by, im.lot_id
            FROM inventory_movements im
            LEFT JOIN (
                SELECT DISTINCT ON (movement_id) movement_id, old_unit_cost, new_unit_cost, reason, created_by, created_at
                FROM inventory_cost_revaluations
                ORDER BY movement_id, id DESC
            ) r ON r.movement_id = im.id
            WHERE im.product_id = %s
            ORDER BY im.created_at::timestamptz ASC, im.id ASC
            """,
            (product_id,)
        )
        raw_movements = cur.fetchall()

        # 3. Reconstrucción matemática paso a paso del PPP continuo
        running_qty = 0.0
        running_value = 0.0
        running_ppp = float(product.get("cost") or 0.0)

        all_calculated_rows = []

        for mov in raw_movements:
            qty = float(mov["quantity"] or 0.0)
            raw_cost = float(mov["unit_cost"] or 0.0)

            # Snapshot de auditoría ANTES
            before_qty = running_qty
            before_value = running_value
            before_ppp = running_ppp

            is_inflow = qty > 0.0
            is_outflow = qty < 0.0

            if is_inflow:
                # ENTRADA: Aporta unidades y valor monetario real de entrada
                in_qty = qty
                out_qty = 0.0
                unit_price_applied = raw_cost
                movement_cost = in_qty * unit_price_applied

                running_qty += in_qty
                running_value += movement_cost
                # Recalcular PPP ponderado
                if running_qty > 1e-6:
                    running_ppp = running_value / running_qty
                else:
                    running_ppp = unit_price_applied if unit_price_applied > 0 else running_ppp

                in_amount = movement_cost
                out_amount = 0.0

            elif is_outflow:
                # SALIDA: Consume unidades valorizadas al PPP vigente en ese instante
                in_qty = 0.0
                out_qty = abs(qty)
                unit_price_applied = running_ppp
                movement_cost = out_qty * unit_price_applied

                running_qty = max(0.0, running_qty - out_qty)
                running_value = max(0.0, running_value - movement_cost)
                # Las salidas NO alteran el PPP vigente
                running_ppp = running_ppp

                in_amount = 0.0
                out_amount = movement_cost

            else:
                in_qty = 0.0
                out_qty = 0.0
                unit_price_applied = 0.0
                in_amount = 0.0
                out_amount = 0.0

            # Snapshot de auditoría DESPUÉS
            after_qty = running_qty
            after_value = running_value
            after_ppp = running_ppp

            instant = datetime.fromisoformat(str(mov["created_at"]).replace('Z', '+00:00')) if mov.get("created_at") else None
            if instant:
                instant = instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None else instant.astimezone(timezone.utc)
            mov_date = instant.strftime('%Y-%m-%d') if instant else ''
            mov_time = instant.strftime('%H:%M:%S') if instant else '' 
            type_label = MOVEMENT_TYPE_LABELS.get(mov["movement_type"], mov["movement_type"])

            row_dict = {
                "id": mov["id"],
                "created_at": mov["created_at"],
                "date": mov_date,
                "time": mov_time,
                "movement_type": mov["movement_type"],
                "movement_type_label": type_label,
                "reference_type": mov.get("reference_type"),
                "reference_id": mov.get("reference_id"),
                "document_label": "-",
                "document_url": None,
                "lot_number": mov.get("lot_number") or "-",
                "warehouse": mov.get("warehouse") or "Almacén Principal",
                "notes": mov.get("notes") or "",
                # Cantidades
                "in_qty": in_qty,
                "out_qty": out_qty,
                "balance_qty": round(running_qty, 3),
                # Montos
                "unit_cost_applied": round(unit_price_applied, 2),
                "in_amount": round(in_amount, 2),
                "out_amount": round(out_amount, 2),
                "balance_amount": round(running_value, 2),
                "ppp": round(running_ppp, 2),
                "original_unit_cost": float(mov.get("original_unit_cost") or 0.0),
                "is_revalued": bool(mov.get("is_revalued")),
                "revaluation": {
                    "old_unit_cost": float(mov["reval_old_cost"]) if mov.get("reval_old_cost") is not None else None,
                    "new_unit_cost": float(mov["reval_new_cost"]) if mov.get("reval_new_cost") is not None else None,
                    "reason": mov.get("reval_reason"),
                    "created_by": mov.get("reval_created_by"),
                    "created_at": str(mov.get("reval_created_at")) if mov.get("reval_created_at") else None,
                } if mov.get("is_revalued") else None,
                # Auditoría detallada Antes / Movimiento / Después
                "audit": {
                    "before": {
                        "qty": round(before_qty, 3),
                        "value": round(before_value, 2),
                        "ppp": round(before_ppp, 2),
                    },
                    "movement": {
                        "type": type_label,
                        "qty": round(qty, 3),
                        "unit_cost": round(unit_price_applied, 2),
                        "total_cost": round(movement_cost, 2),
                    },
                    "after": {
                        "qty": round(after_qty, 3),
                        "value": round(after_value, 2),
                        "ppp": round(after_ppp, 2),
                    }
                }
            }
            all_calculated_rows.append(row_dict)

        current_stock = running_qty
        current_ppp = running_ppp
        current_inv_value = round(current_stock * current_ppp, 2)

        # 4. Filtrar filas según parámetros si fueron especificados
        filtered_rows = []
        for r in all_calculated_rows:
            r_date = r["date"]
            if start_date and r_date and r_date < start_date:
                continue
            if end_date and r_date and r_date > end_date:
                continue
            if movement_type_filter and r["movement_type"] != movement_type_filter:
                continue
            filtered_rows.append(r)

        # 5. Ordenación determinística: Por defecto más reciente primero (order_asc=False)
        if not order_asc:
            filtered_rows = list(reversed(filtered_rows))

        total_filtered = len(filtered_rows)

        # 6. Aplicar paginación server-side sobre la lista filtrada y ordenada
        if is_paginated:
            total_pages = max(1, (total_filtered + target_per_page - 1) // target_per_page)
            if target_page > total_pages and total_pages > 0:
                target_page = total_pages
            offset = (target_page - 1) * target_per_page
            paged_rows = filtered_rows[offset:offset + target_per_page]
            actual_page = target_page
            actual_per_page = target_per_page
        else:
            total_pages = 1
            actual_page = 1
            actual_per_page = len(filtered_rows)
            paged_rows = filtered_rows

        # 7. Pre-cargar referencias documentales ÚNICAMENTE para las filas paginadas visibles
        ref_docs = {}
        po_ids = [m["reference_id"] for m in paged_rows if m.get("reference_type") == "purchase_order" and m.get("reference_id")]
        if po_ids:
            cur.execute("SELECT id, oc_number FROM purchase_orders WHERE id = ANY(%s)", (list(set(po_ids)),))
            for r in cur.fetchall():
                ref_docs[("purchase_order", r["id"])] = {"label": r["oc_number"], "url": f"/compras/oc?search={r['oc_number']}"}

        ot_ids = [m["reference_id"] for m in paged_rows if m.get("reference_type") in ("production_order", "production_order_item", "production_order_add_item") and m.get("reference_id")]
        if ot_ids:
            cur.execute("SELECT id, ot_number FROM production_orders WHERE id = ANY(%s)", (list(set(ot_ids)),))
            for r in cur.fetchall():
                key = ("production_order", r["id"])
                ref_docs[key] = {"label": r["ot_number"], "url": f"/produccion"}

        sale_ids = [m["reference_id"] for m in paged_rows if m.get("reference_type") == "sale" and m.get("reference_id")]
        if sale_ids:
            cur.execute("SELECT id, sale_number FROM sales WHERE id = ANY(%s)", (list(set(sale_ids)),))
            for r in cur.fetchall():
                ref_docs[("sale", r["id"])] = {"label": r["sale_number"], "url": f"/ventas/detalle/{r['id']}"}

        for row in paged_rows:
            ref_type = row.get("reference_type")
            ref_id = row.get("reference_id")
            doc_info = ref_docs.get((ref_type, ref_id))
            if doc_info:
                row["document_label"] = doc_info["label"]
                row["document_url"] = doc_info["url"]
            elif row.get("notes"):
                notes_str = row["notes"]
                if "OC-" in notes_str:
                    row["document_label"] = "OC"
                elif "OT-" in notes_str:
                    row["document_label"] = "OT"
                elif "VTA-" in notes_str or "P-" in notes_str:
                    row["document_label"] = "Pedido/Venta"
                else:
                    row["document_label"] = notes_str[:25]
            elif ref_type:
                row["document_label"] = ref_type

        return {
            "product": dict(product),
            "current_stock": round(current_stock, 3),
            "current_ppp": round(current_ppp, 2),
            "current_inventory_value": current_inv_value,
            "total_movements": len(all_calculated_rows),
            "filtered_movements": total_filtered,
            "page": actual_page,
            "per_page": actual_per_page,
            "total_pages": total_pages,
            "rows": paged_rows,
            "order_asc": order_asc,
            "start_date": start_date or "",
            "end_date": end_date or "",
            "movement_type_filter": movement_type_filter or "",
        }

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


def get_inventory_valuation_summary() -> dict:
    """
    Calcula la valorización total del inventario consolidando stock y PPP de cada producto.
    Retorna:
    {
        "total_value": float,
        "products_valuation": dict[int, {"stock": float, "ppp": float, "value": float}]
    }
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, sku, cost FROM products WHERE is_deleted = FALSE OR is_deleted IS NULL")
            products = cur.fetchall()

    total_inventory_value = 0.0
    products_valuation = {}

    for prod in products:
        pid = prod["id"]
        # Obtener stock y PPP calculado a partir del kardex
        kh = get_product_kardex_history(pid)
        if kh:
            stock = kh["current_stock"]
            ppp = kh["current_ppp"]
            val = kh["current_inventory_value"]
            products_valuation[pid] = {
                "sku": prod["sku"],
                "stock": stock,
                "ppp": ppp,
                "value": val
            }
            total_inventory_value += val
        else:
            products_valuation[pid] = {
                "sku": prod["sku"],
                "stock": 0.0,
                "ppp": float(prod.get("cost") or 0.0),
                "value": 0.0
            }

    return {
        "total_value": round(total_inventory_value, 2),
        "products_valuation": products_valuation
    }


def get_all_products_kardex_summary() -> dict:
    """
    Retorna la lista completa de todos los productos del catálogo con su stock físico actual,
    PPP vigente y valor de inventario, consolidando los totales globales para la vista principal de Kardex.
    Retorna:
    {
        "total_inventory_value": float,
        "total_units_stock": float,
        "total_products_count": int,
        "products_with_stock_count": int,
        "items": list[dict]
    }
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Traer todos los productos activos
            cur.execute(
                """
                SELECT p.id, p.sku, p.name, p.category, p.product_type, p.unit_of_measure,
                       p.format_capacity, p.line, p.variety, COALESCE(p.cost, 0.0) as cost,
                       COALESCE(p.status, 'Activo') as status
                FROM products p
                WHERE p.is_deleted = FALSE OR p.is_deleted IS NULL
                ORDER BY p.name ASC
                """
            )
            products = cur.fetchall()

            # Traer todos los movimientos de inventario agrupados por producto en orden cronológico
            cur.execute(
                """
                SELECT product_id, quantity, unit_cost
                FROM inventory_movements
                ORDER BY product_id ASC, created_at::timestamptz ASC, id ASC
                """
            )
            all_movements = cur.fetchall()

    # Indexar movimientos por product_id para cálculo lineal en memoria
    movements_by_product: dict[int, list] = {}
    for mov in all_movements:
        pid = mov["product_id"]
        if pid not in movements_by_product:
            movements_by_product[pid] = []
        movements_by_product[pid].append(mov)

    items = []
    total_val = 0.0
    total_units = 0.0
    with_stock_count = 0

    for p in products:
        pid = p["id"]
        default_cost = float(p["cost"] or 0.0)
        p_movs = movements_by_product.get(pid, [])

        running_qty = 0.0
        running_value = 0.0
        running_ppp = default_cost
        movement_count = len(p_movs)

        for m in p_movs:
            qty = float(m["quantity"] or 0.0)
            raw_cost = float(m["unit_cost"] or 0.0)

            if qty > 0.0:
                in_qty = qty
                unit_price = raw_cost
                m_cost = in_qty * unit_price
                running_qty += in_qty
                running_value += m_cost
                if running_qty > 1e-6:
                    running_ppp = running_value / running_qty
                else:
                    running_ppp = unit_price if unit_price > 0 else running_ppp
            elif qty < 0.0:
                out_qty = abs(qty)
                m_cost = out_qty * running_ppp
                running_qty = max(0.0, running_qty - out_qty)
                running_value = max(0.0, running_value - m_cost)

        current_stock = round(running_qty, 3)
        current_ppp = round(running_ppp, 2)
        inv_value = round(current_stock * current_ppp, 2)

        total_val += inv_value
        total_units += current_stock
        if current_stock > 0:
            with_stock_count += 1

        items.append({
            "id": pid,
            "sku": p["sku"],
            "name": p["name"],
            "category": p["category"] or "Sin categoría",
            "product_type": "Producto Terminado" if p["product_type"] == "Final" else (p["product_type"] or "Producto Terminado"),
            "unit_of_measure": p["unit_of_measure"] or "UN",
            "format_capacity": p["format_capacity"] or "-",
            "line": p["line"] or "-",
            "variety": p["variety"] or "-",
            "status": p["status"],
            "current_stock": current_stock,
            "current_ppp": current_ppp,
            "current_inventory_value": inv_value,
            "total_movements": movement_count
        })

    return {
        "total_inventory_value": round(total_val, 2),
        "total_units_stock": round(total_units, 2),
        "total_products_count": len(products),
        "products_with_stock_count": with_stock_count,
        "products": items
    }


def get_all_products_kardex_paginated(
    page: int = 1,
    per_page: int = 25,
    search: Optional[str] = None,
    category: Optional[str] = None,
    product_type: Optional[str] = None,
    conn=None
) -> dict:
    """
    Retorna el catálogo consolidado de productos con paginación server-side (25, 50, 100)
    y búsqueda/filtros server-side, garantizando que los totales de las tarjetas
    representen SIEMPRE el 100% de la empresa (todos los productos).
    
    Retorna:
    {
        "total_inventory_value": float,
        "total_units_stock": float,
        "total_products_count": int,
        "products_with_stock_count": int,
        "page": int,
        "per_page": int,
        "total_pages": int,
        "total_filtered": int,
        "products": list[dict]
    }
    """
    # 1. Sanitizar paginación
    try:
        page = int(page) if page is not None else 1
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = int(per_page) if per_page is not None else 25
        if per_page not in (25, 50, 100):
            per_page = 25
    except (ValueError, TypeError):
        per_page = 25

    def _query(cur):
        # Traer todos los productos activos
        cur.execute(
            """
            SELECT p.id, p.sku, p.name, p.category, p.product_type, p.unit_of_measure,
                   p.format_capacity, p.line, p.variety, COALESCE(p.cost, 0.0) as cost,
                   COALESCE(p.status, 'Activo') as status
            FROM products p
            WHERE p.is_deleted = FALSE OR p.is_deleted IS NULL
            ORDER BY p.name ASC
            """
        )
        prods = cur.fetchall()

        # Traer movimientos en orden cronológico determinístico con costo efectivo revaluado
        cur.execute(
            """
            SELECT im.product_id, im.quantity,
                   COALESCE(r.new_unit_cost, im.unit_cost) AS unit_cost
            FROM inventory_movements im
            LEFT JOIN (
                SELECT DISTINCT ON (movement_id) movement_id, new_unit_cost
                FROM inventory_cost_revaluations
                ORDER BY movement_id, id DESC
            ) r ON r.movement_id = im.id
            ORDER BY im.product_id ASC, im.created_at::timestamptz ASC, im.id ASC
            """
        )
        movs = cur.fetchall()
        return prods, movs

    if conn is not None:
        with conn.cursor() as cur:
            products, all_movements = _query(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                products, all_movements = _query(cur)

    # Indexar movimientos por producto
    movements_by_product: dict[int, list] = {}
    for mov in all_movements:
        pid = mov["product_id"]
        if pid not in movements_by_product:
            movements_by_product[pid] = []
        movements_by_product[pid].append(mov)

    # 2. Calcular agregados de TODOS los productos (Tarjetas globales)
    all_calculated_products = []
    total_val = 0.0
    total_units = 0.0
    with_stock_count = 0

    for p in products:
        pid = p["id"]
        default_cost = float(p["cost"] or 0.0)
        p_movs = movements_by_product.get(pid, [])

        running_qty = 0.0
        running_value = 0.0
        running_ppp = default_cost
        movement_count = len(p_movs)

        for m in p_movs:
            qty = float(m["quantity"] or 0.0)
            raw_cost = float(m["unit_cost"] or 0.0)

            if qty > 0.0:
                in_qty = qty
                unit_price = raw_cost
                m_cost = in_qty * unit_price
                running_qty += in_qty
                running_value += m_cost
                if running_qty > 1e-6:
                    running_ppp = running_value / running_qty
                else:
                    running_ppp = unit_price if unit_price > 0 else running_ppp
            elif qty < 0.0:
                out_qty = abs(qty)
                m_cost = out_qty * running_ppp
                running_qty = max(0.0, running_qty - out_qty)
                running_value = max(0.0, running_value - m_cost)

        current_stock = round(running_qty, 3)
        current_ppp = round(running_ppp, 2)
        inv_value = round(current_stock * current_ppp, 2)

        total_val += inv_value
        total_units += current_stock
        if current_stock > 0:
            with_stock_count += 1

        all_calculated_products.append({
            "id": pid,
            "sku": p["sku"],
            "name": p["name"],
            "category": p["category"] or "Sin categoría",
            "product_type": "Producto Terminado" if p["product_type"] == "Final" else (p["product_type"] or "Producto Terminado"),
            "unit_of_measure": p["unit_of_measure"] or "UN",
            "format_capacity": p["format_capacity"] or "-",
            "line": p["line"] or "-",
            "variety": p["variety"] or "-",
            "status": p["status"],
            "current_stock": current_stock,
            "current_ppp": current_ppp,
            "current_inventory_value": inv_value,
            "total_movements": movement_count
        })

    # 3. Filtrar por término de búsqueda y filtros server-side
    filtered = all_calculated_products
    if search and search.strip():
        term = search.strip().lower()
        filtered = [
            prod for prod in filtered
            if (term in (prod["sku"] or "").lower()
                or term in (prod["name"] or "").lower()
                or term in (prod["category"] or "").lower()
                or term in (prod["product_type"] or "").lower())
        ]

    if category and category.strip():
        cat_term = category.strip().lower()
        filtered = [p for p in filtered if (p["category"] or "").lower() == cat_term]

    if product_type and product_type.strip():
        pt_term = product_type.strip().lower()
        filtered = [p for p in filtered if (p["product_type"] or "").lower() == pt_term]

    total_filtered = len(filtered)
    total_pages = max(1, (total_filtered + per_page - 1) // per_page)
    if page > total_pages and total_pages > 0:
        page = total_pages

    offset = (page - 1) * per_page
    paged_items = filtered[offset:offset + per_page]

    return {
        "total_inventory_value": round(total_val, 2),
        "total_units_stock": round(total_units, 2),
        "total_products_count": len(products),
        "products_with_stock_count": with_stock_count,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "total_filtered": total_filtered,
        "products": paged_items
    }



