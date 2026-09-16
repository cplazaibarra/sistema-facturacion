"""
repositories/inventory_repo.py
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
from repositories.legacy_repo import get_page_data, set_page_data
from repositories.products_repo import get_product_calculated_cost


def get_inventory_entry_detail(entry_id: int) -> dict | None:
    """Obtiene el detalle completo de un ingreso de mercadería con sus productos y OC asociada"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ie.id, ie.entry_date, ie.order_number, ie.warehouse, ie.notes,
                       ie.document_type, ie.document_number, ie.document_file, ie.total_amount,
                       ie.purchase_order_id,
                       po.oc_number, s.name as supplier_name,
                       COALESCE(
                           (
                               SELECT json_agg(json_build_object(
                                   'id', iei.id,
                                   'product_id', iei.product_id,
                                   'product_name', p.name,
                                   'sku', COALESCE(p.sku, 'SIN-SKU'),
                                   'quantity', iei.quantity,
                                   'unit_price', iei.unit_price,
                                   'total', iei.total,
                                   'lot_number', COALESCE(iei.lot_number, '')
                               ))
                               FROM inventory_entry_items iei
                               JOIN products p ON iei.product_id = p.id
                               WHERE iei.inventory_entry_id = ie.id
                           ), '[]'::json
                       ) as items,
                       (
                           SELECT json_build_object(
                               'id', pi.id,
                               'invoice_number', pi.invoice_number,
                               'payment_status', pi.payment_status,
                               'invoice_amount', pi.invoice_amount,
                               'due_date', pi.due_date,
                               'document_file', pi.document_file
                           )
                           FROM purchase_invoices pi
                           WHERE pi.inventory_entry_id = ie.id
                           LIMIT 1
                       ) as invoice
                FROM inventory_entries ie
                LEFT JOIN purchase_orders po ON ie.purchase_order_id = po.id
                LEFT JOIN suppliers s ON ie.supplier_id = s.id
                WHERE ie.id = %s
            """, (entry_id,))
            row = cur.fetchone()
            return dict(row) if row else None


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
            # 0. Bloquear cabecera de la Orden de Compra
            cur.execute("SELECT id, supplier_id, status FROM purchase_orders WHERE id = %s FOR UPDATE", (po_id,))
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

            # 2. Guardar items del ingreso, validar límites y actualizar OC (con orden consistente de productos)
            sorted_items = sorted(items, key=lambda x: x["product_id"])
            for item in sorted_items:
                prod_id    = item["product_id"]
                qty        = item["quantity"]
                price      = item["unit_price"]
                lot_number = (item.get("lot_number") or "").strip()
                line_total = qty * price

                cur.execute(
                    """
                    SELECT id, quantity_ordered, quantity_received
                    FROM purchase_order_items
                    WHERE purchase_order_id = %s AND product_id = %s
                    FOR UPDATE
                    """,
                    (po_id, prod_id)
                )
                po_item = cur.fetchone()
                if not po_item:
                    raise ValueError(f"El producto con ID {prod_id} no está en la Orden de Compra.")

                pending = po_item["quantity_ordered"] - po_item["quantity_received"]
                if qty > pending:
                    raise ValueError(f"No puedes ingresar {qty} unidades. El máximo pendiente en la OC es {pending}.")

                cur.execute("SELECT id, requires_lot, name FROM products WHERE id = %s", (prod_id,))
                prod_row = cur.fetchone()
                if prod_row and prod_row.get("requires_lot") and not lot_number:
                    raise ValueError(f"INV-011: El producto '{prod_row['name']}' requiere número de lote obligatorio.")

                lot_id = None
                if lot_number:
                    cur.execute(
                        "SELECT id FROM lots WHERE product_id = %s AND lot_number = %s ORDER BY id DESC LIMIT 1",
                        (prod_id, lot_number)
                    )
                    ex_lot = cur.fetchone()
                    if ex_lot:
                        lot_id = ex_lot["id"]
                    else:
                        now_iso = datetime.now(timezone.utc).isoformat()
                        cur.execute(
                            """
                            INSERT INTO lots (
                                product_id, lot_number, lot_type, origin_type, origin_id,
                                supplier_id, purchase_order_id, inventory_entry_id,
                                initial_quantity, created_at, status, warehouse
                            ) VALUES (%s, %s, 'RAW_MATERIAL', 'PURCHASE', %s, %s, %s, %s, %s, %s, 'ACTIVE', %s)
                            RETURNING id;
                            """,
                            (prod_id, lot_number, entry_id, supplier_id, po_id, entry_id, qty, now_iso, warehouse)
                        )
                        lot_id = cur.fetchone()["id"]

                cur.execute(
                    """
                    INSERT INTO inventory_entry_items (inventory_entry_id, product_id, quantity, unit_price, total, lot_number, lot_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (entry_id, prod_id, qty, price, line_total, lot_number, lot_id)
                )

                # Si tiene número de lote, registrar o sumar en lot_stock
                if lot_number:
                    cur.execute(
                        """
                        INSERT INTO lot_stock (product_id, lot_number, entry_id, entry_date, initial_qty, available_qty, warehouse, lot_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (product_id, lot_number) DO UPDATE
                        SET initial_qty = lot_stock.initial_qty + EXCLUDED.initial_qty,
                            available_qty = lot_stock.available_qty + EXCLUDED.available_qty,
                            entry_date = EXCLUDED.entry_date,
                            warehouse = EXCLUDED.warehouse,
                            lot_id = COALESCE(lot_stock.lot_id, EXCLUDED.lot_id)
                        """,
                        (prod_id, lot_number, entry_id, entry_date, qty, qty, warehouse, lot_id)
                    )

                # Fase 2: Registrar movimiento relacional en Kardex universal (inventory_movements)
                record_inventory_movement(
                    product_id=prod_id,
                    movement_type="PURCHASE_RECEIPT",
                    quantity=qty,
                    unit_cost=price,
                    lot_number=lot_number if lot_number else None,
                    warehouse=warehouse,
                    reference_type="purchase_order",
                    reference_id=po_id,
                    notes=f"Recepción de compra {order_number} (Entrada #{entry_id})",
                    conn=conn,
                    lot_id=lot_id
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

            # 4. Actualizar stock en page_data.inventory_items dentro de la misma transacción
            try:
                cur.execute("SELECT json FROM page_data WHERE key = 'inventory_items' FOR UPDATE")
                pd_row = cur.fetchone()
                inventory_items = json.loads(pd_row["json"]) if pd_row and pd_row["json"] else []
                inv_map = {item.get("code"): item for item in inventory_items if item.get("code")}

                cur.execute("SELECT id, sku, name, category, description, cost FROM products")
                db_prods = {p["id"]: p for p in cur.fetchall()}

                for item in sorted_items:
                    prod_id = item["product_id"]
                    qty = float(item["quantity"])
                    prod_info = db_prods.get(prod_id)
                    if not prod_info:
                        continue
                    sku = prod_info["sku"]
                    if sku in inv_map:
                        current_st = float(inv_map[sku].get("stock", 0.0) or 0.0)
                        inv_map[sku]["stock"] = current_st + qty
                        min_st = float(inv_map[sku].get("min_stock", 10) or 10)
                        inv_map[sku]["status"] = "Normal" if inv_map[sku]["stock"] >= min_st else "Stock Bajo"
                    else:
                        inventory_items.append({
                            "code": sku,
                            "name": prod_info["name"],
                            "desc": prod_info["description"] or "",
                            "category": prod_info["category"] or "Insumos",
                            "stock": qty,
                            "min_stock": 10,
                            "price": float(prod_info["cost"] or item.get("unit_price") or 0.0),
                            "status": "Normal" if qty >= 10 else "Stock Bajo",
                            "stock_percent": 100
                        })

                cur.execute(
                    """
                    INSERT INTO page_data (key, json) VALUES ('inventory_items', %s)
                    ON CONFLICT (key) DO UPDATE SET json = EXCLUDED.json
                    """,
                    (json.dumps(inventory_items, ensure_ascii=False),)
                )
            except Exception as e:
                print(f"Error al actualizar inventory_items en register_inventory_entry: {e}")

            conn.commit()
            return entry_id


def get_lot_stock_by_product(product_id: int) -> list[dict]:
    """Retorna los lotes con stock disponible para un producto."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ls.id, ls.product_id, ls.lot_number, ls.entry_id, ls.entry_date,
                       ls.initial_qty, ls.available_qty, p.name as product_name, p.sku
                FROM lot_stock ls
                JOIN products p ON p.id = ls.product_id
                WHERE ls.product_id = %s AND ls.available_qty > 0
                ORDER BY ls.entry_date ASC, ls.id ASC
                """,
                (product_id,)
            )
            return [dict(row) for row in cur.fetchall()]


def get_all_lot_stock() -> list[dict]:
    """Retorna todo el stock agrupado por lote para el inventario."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ls.id, ls.product_id, ls.lot_number, ls.entry_id, ls.entry_date,
                       ls.initial_qty, ls.available_qty, p.name as product_name, p.sku,
                       p.category, p.cost,
                       COALESCE(ls.warehouse, ie.warehouse, 'Principal') as warehouse
                FROM lot_stock ls
                JOIN products p ON p.id = ls.product_id
                LEFT JOIN inventory_entries ie ON ie.id = ls.entry_id
                ORDER BY p.name ASC, ls.entry_date DESC
                """
            )
            return [dict(row) for row in cur.fetchall()]


def consume_lots_for_sale(sale_id: int, lot_consumptions: list[dict], conn=None) -> None:
    """
    Descuenta unidades de los lotes utilizados en una venta y registra la trazabilidad.
    lot_consumptions: lista de dicts con keys: product_id, lot_number, quantity
    """
    def _execute(cur):
        now_iso = datetime.now(timezone.utc).isoformat(timespec='seconds')
        for item in lot_consumptions:
            pid = item.get("product_id")
            lot = (item.get("lot_number") or "").strip()
            qty = int(item.get("quantity") or 0)
            if not pid or not lot or qty <= 0:
                continue

            lot_id = item.get("lot_id")
            if not lot_id:
                cur.execute(
                    "SELECT id FROM lots WHERE product_id = %s AND lot_number = %s ORDER BY id DESC LIMIT 1",
                    (pid, lot)
                )
                l_found = cur.fetchone()
                if l_found:
                    lot_id = l_found["id"]

            # Descontar de lot_stock bloqueando la fila
            cur.execute(
                """
                UPDATE lot_stock
                SET available_qty = GREATEST(0, available_qty - %s)
                WHERE product_id = %s AND lot_number = %s
                RETURNING available_qty, lot_id;
                """,
                (qty, pid, lot)
            )
            ls_row = cur.fetchone()
            if ls_row and ls_row["available_qty"] <= 1e-6:
                target_lid = lot_id or ls_row["lot_id"]
                if target_lid:
                    cur.execute("UPDATE lots SET status = 'DEPLETED' WHERE id = %s", (target_lid,))

            # Registrar movimiento
            cur.execute(
                """
                INSERT INTO sale_lot_movements (sale_id, product_id, lot_number, quantity, moved_at, lot_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (sale_id, pid, lot, qty, now_iso, lot_id)
            )

    if conn is not None:
        with conn.cursor() as cur:
            _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                _execute(cur)
            c.commit()


def get_sale_lot_movements(sale_id: int) -> list[dict]:
    """Retorna los lotes utilizados en una venta específica."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT slm.id, slm.sale_id, slm.product_id, slm.lot_number, slm.quantity, slm.moved_at,
                       p.name as product_name, p.sku
                FROM sale_lot_movements slm
                JOIN products p ON p.id = slm.product_id
                WHERE slm.sale_id = %s
                ORDER BY slm.id ASC
                """,
                (sale_id,)
            )
            return [dict(row) for row in cur.fetchall()]


def get_lot_traceability(lot_number: str) -> dict:
    """Retorna la historia de entradas y salidas de un lote específico."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ls.*, p.name as product_name, p.sku
                FROM lot_stock ls
                JOIN products p ON p.id = ls.product_id
                WHERE ls.lot_number = %s
                """,
                (lot_number,)
            )
            stock_info = cur.fetchall()

            cur.execute(
                """
                SELECT iei.quantity, iei.unit_price, iei.total, ie.entry_date, ie.order_number,
                       ie.warehouse, ie.document_type, ie.document_number, p.name as product_name
                FROM inventory_entry_items iei
                JOIN inventory_entries ie ON ie.id = iei.inventory_entry_id
                JOIN products p ON p.id = iei.product_id
                WHERE iei.lot_number = %s
                ORDER BY ie.entry_date ASC
                """,
                (lot_number,)
            )
            entries = [dict(r) for r in cur.fetchall()]

            cur.execute(
                """
                SELECT slm.quantity, slm.moved_at, s.sale_number, s.customer_name, s.sale_date, p.name as product_name
                FROM sale_lot_movements slm
                JOIN sales s ON s.id = slm.sale_id
                JOIN products p ON p.id = slm.product_id
                WHERE slm.lot_number = %s
                ORDER BY slm.moved_at ASC
                """,
                (lot_number,)
            )
            sales = [dict(r) for r in cur.fetchall()]

            return {
                "stock": [dict(r) for r in stock_info],
                "entries": entries,
                "sales": sales
            }


def record_inventory_movement(
    product_id: int,
    movement_type: str,
    quantity: float,
    unit_cost: float = 0.0,
    lot_number: str = None,
    warehouse: str = "Almacén Principal",
    reference_type: str = None,
    reference_id: int = None,
    notes: str = None,
    created_by: str = "Sistema",
    conn=None,
    lot_id: int = None
) -> int:
    """
    Registra un movimiento en inventory_movements cumpliendo los invariantes de inventario:
    - INV-008: Magnitud != 0.0
    - INV-002: Salidas (qty < 0) deben tener origen identificable (reference_type o notes)
    - INV-001: Stock disponible relacional no puede quedar en negativo
    - Fase 5B: Asocia lot_id inmutable si existe lote
    """
    qty = float(quantity)
    if qty == 0.0:
        raise ValueError("INV-008: La cantidad de un movimiento de inventario no puede ser 0.0")

    if qty < 0 and not reference_type and not notes:
        raise ValueError("INV-002: Toda salida de inventario debe tener un documento o referencia de origen identificable")

    def _execute(cursor):
        # Validar existencia del producto y adquirir bloqueo exclusivo sobre el producto
        cursor.execute("SELECT id, sku, name FROM products WHERE id = %s FOR UPDATE", (product_id,))
        prod = cursor.fetchone()
        if not prod:
            raise ValueError(f"Producto con ID {product_id} no encontrado en catálogo")

        # INV-001: No permitir que el stock relacional sea negativo si es salida
        if qty < 0:
            cursor.execute(
                "SELECT COALESCE(SUM(quantity), 0.0) as current_stock FROM inventory_movements WHERE product_id = %s",
                (product_id,)
            )
            row = cursor.fetchone()
            current_stock = float(row["current_stock"] if row else 0.0)
            if current_stock + qty < -1e-6:
                raise ValueError(
                    f"INV-001: Stock insuficiente. Stock relacional actual: {current_stock}, salida solicitada: {abs(qty)}"
                )

        clean_lot = (lot_number or "").strip() or None
        target_lot_id = lot_id
        if not target_lot_id and clean_lot:
            cursor.execute(
                "SELECT id FROM lots WHERE product_id = %s AND lot_number = %s ORDER BY id DESC LIMIT 1",
                (product_id, clean_lot)
            )
            found_l = cursor.fetchone()
            if found_l:
                target_lot_id = found_l["id"]

        now_str = datetime.now(timezone.utc).isoformat(timespec='seconds')
        cursor.execute(
            """
            INSERT INTO inventory_movements (
                product_id, movement_type, quantity, unit_cost, lot_number,
                warehouse, reference_type, reference_id, notes, created_at, created_by, lot_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                product_id, movement_type, qty, float(unit_cost or 0.0),
                clean_lot, warehouse or "Almacén Principal",
                reference_type, reference_id, notes, now_str, created_by, target_lot_id
            )
        )
        mov_id = cursor.fetchone()["id"]
        return mov_id

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as new_conn:
            with new_conn.cursor() as cur:
                res = _execute(cur)
            new_conn.commit()
            return res


def get_relational_stock(product_id: int, conn=None) -> float:
    """Calcula el stock actual disponible de un producto sumando sus movimientos."""
    query = "SELECT COALESCE(SUM(quantity), 0.0) as stock FROM inventory_movements WHERE product_id = %s"
    if conn is not None:
        with conn.cursor() as cur:
            cur.execute(query, (product_id,))
            row = cur.fetchone()
            return float(row["stock"] if row else 0.0)
    else:
        with get_connection() as new_conn:
            with new_conn.cursor() as cur:
                cur.execute(query, (product_id,))
                row = cur.fetchone()
                return float(row["stock"] if row else 0.0)


def get_relational_stock_by_sku(sku: str, conn=None) -> float:
    """Calcula el stock actual disponible de un producto por SKU sumando movimientos."""
    query = """
        SELECT COALESCE(SUM(im.quantity), 0.0) as stock
        FROM inventory_movements im
        JOIN products p ON p.id = im.product_id
        WHERE p.sku = %s;
    """
    if conn is not None:
        with conn.cursor() as cur:
            cur.execute(query, (sku.strip(),))
            row = cur.fetchone()
            return float(row["stock"] if row else 0.0)
    else:
        with get_connection() as new_conn:
            with new_conn.cursor() as cur:
                cur.execute(query, (sku.strip(),))
                row = cur.fetchone()
                return float(row["stock"] if row else 0.0)


def consume_fifo_lots(product_id: int, quantity: float, sale_id: int = None, ot_id: int = None, conn=None) -> list[dict]:
    """
    Consume lotes disponibles utilizando estrategia FIFO (ordenados por entry_date ASC, id ASC).
    Actualiza lot_stock.available_qty y retorna la lista de consumos efectuados:
    [{'lot_number': str, 'quantity': float, 'entry_id': int}]
    """
    qty_to_consume = float(quantity)
    if qty_to_consume <= 0:
        return []

    def _execute(cursor):
        cursor.execute(
            """
            SELECT id, lot_number, available_qty, entry_id, entry_date, lot_id
            FROM lot_stock
            WHERE product_id = %s AND available_qty > 0
            ORDER BY entry_date ASC, id ASC
            FOR UPDATE;
            """,
            (product_id,)
        )
        lots = cursor.fetchall()
        
        total_available = sum(float(l["available_qty"]) for l in lots)
        if total_available < qty_to_consume - 1e-6:
            raise ValueError(
                f"INV-004: Stock insuficiente en lotes FIFO. Disponible: {total_available}, Requerido: {qty_to_consume}"
            )

        consumed = []
        rem = qty_to_consume
        for lot in lots:
            avail = float(lot["available_qty"])
            take = min(avail, rem)
            if take > 0:
                cursor.execute(
                    "UPDATE lot_stock SET available_qty = available_qty - %s WHERE id = %s RETURNING available_qty",
                    (take, lot["id"])
                )
                new_avail = cursor.fetchone()["available_qty"]

                lot_id = lot.get("lot_id")
                if not lot_id:
                    cursor.execute(
                        "SELECT id FROM lots WHERE product_id = %s AND lot_number = %s ORDER BY id DESC LIMIT 1",
                        (product_id, lot["lot_number"])
                    )
                    lrow = cursor.fetchone()
                    if lrow:
                        lot_id = lrow["id"]

                if new_avail <= 1e-6 and lot_id:
                    cursor.execute("UPDATE lots SET status = 'DEPLETED' WHERE id = %s", (lot_id,))

                consumed.append({
                    "lot_id": lot_id,
                    "lot_number": lot["lot_number"],
                    "quantity": take,
                    "entry_id": lot["entry_id"]
                })
                rem -= take
                if rem <= 1e-6:
                    break
        return consumed

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as new_conn:
            with new_conn.cursor() as cur:
                res = _execute(cur)
            new_conn.commit()
            return res


def get_stock_with_dual_read(product_id_or_sku, lot_number: str = None) -> tuple[float, float, float]:
    """
    Dual-Read Helper:
    Compara el stock leído de page_data (legacy) con el stock relacional de inventory_movements.
    Si difieren, emite advertencia en el log de auditoría.
    Retorna: (legacy_stock, relational_stock, delta)
    """
    from security import security_logger

    clean_lot = (lot_number or "").strip()
    product_id = None
    sku = None

    with get_connection() as conn:
        with conn.cursor() as cur:
            if isinstance(product_id_or_sku, int) or (isinstance(product_id_or_sku, str) and str(product_id_or_sku).isdigit()):
                cur.execute("SELECT id, sku FROM products WHERE id = %s", (int(product_id_or_sku),))
            else:
                cur.execute(
                    "SELECT id, sku FROM products WHERE sku = %s OR LOWER(name) = LOWER(%s)",
                    (str(product_id_or_sku).strip(), str(product_id_or_sku).strip())
                )
            prod = cur.fetchone()
            if prod:
                product_id = prod["id"]
                sku = prod["sku"]

    # Stock legacy
    legacy_stock = get_product_available_stock(product_id_or_sku, clean_lot)

    # Stock relacional
    relational_stock = 0.0
    if product_id:
        if clean_lot:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COALESCE(SUM(quantity), 0.0) as stock FROM inventory_movements WHERE product_id = %s AND lot_number = %s",
                        (product_id, clean_lot)
                    )
                    row = cur.fetchone()
                    relational_stock = float(row["stock"] if row else 0.0)
        else:
            relational_stock = get_relational_stock(product_id)

    delta = round(legacy_stock - relational_stock, 4)
    if abs(delta) > 1e-4:
        security_logger.warning(
            f"[INVENTORY DUAL-READ DISCREPANCY] SKU={sku or product_id_or_sku} | Legacy={legacy_stock} | Relational={relational_stock} | Delta={delta}"
        )

    return (legacy_stock, relational_stock, delta)


def get_product_available_stock(product_id_or_sku, lot_number: str = None) -> float:
    """
    Retorna el stock disponible en bodega para un producto (y lote específico si se indica).
    """
    clean_lot = (lot_number or "").strip()

    with get_connection() as conn:
        with conn.cursor() as cur:
            if isinstance(product_id_or_sku, int) or (isinstance(product_id_or_sku, str) and str(product_id_or_sku).isdigit()):
                cur.execute("SELECT id, sku, requires_lot FROM products WHERE id = %s", (int(product_id_or_sku),))
            else:
                cur.execute(
                    "SELECT id, sku, requires_lot FROM products WHERE sku = %s OR LOWER(name) = LOWER(%s)",
                    (str(product_id_or_sku).strip(), str(product_id_or_sku).strip())
                )
            prod = cur.fetchone()
            if not prod:
                return 0.0

            product_id = prod["id"]
            sku = prod["sku"]
            requires_lot = bool(prod.get("requires_lot"))

            # Si se consulta por un lote físico específico:
            if clean_lot:
                cur.execute(
                    "SELECT COALESCE(available_qty, 0) as qty FROM lot_stock WHERE product_id = %s AND lot_number = %s",
                    (product_id, clean_lot)
                )
                row = cur.fetchone()
                return float(row["qty"] or 0) if row else 0.0

            # 1. Total disponible en lotes (lot_stock)
            cur.execute(
                "SELECT COALESCE(SUM(available_qty), 0) as total_lot FROM lot_stock WHERE product_id = %s",
                (product_id,)
            )
            lot_row = cur.fetchone()
            total_lot = float(lot_row["total_lot"] or 0) if lot_row else 0.0

    # 2. Total disponible en inventario general (inventory_items)
    inventory_items = get_page_data("inventory_items") or []
    inv_stock = 0.0
    found_in_inv = False
    for item in inventory_items:
        if item.get("code") == sku:
            inv_stock = float(item.get("stock", 0) or 0)
            found_in_inv = True
            break

    if requires_lot:
        return total_lot

    # Si no tiene lot_stock ni page_data, consultar fuente de verdad relacional (inventory_movements)
    rel_stock = get_relational_stock(product_id)

    if total_lot > 0 and inv_stock > 0:
        return max(total_lot, inv_stock, rel_stock)
    elif total_lot > 0:
        return max(total_lot, rel_stock)
    elif found_in_inv:
        return max(inv_stock, rel_stock)
    else:
        return rel_stock


def validate_stock_for_sale(products_list: list) -> tuple[bool, str, dict]:
    """
    Valida que todos los productos de la venta tengan stock disponible suficiente en bodega.
    Retorna: (is_valid, error_message, stock_details)
    """
    for prod in products_list:
        if not isinstance(prod, dict):
            continue
        pid = prod.get("product_id") or prod.get("id")
        pname = prod.get("product_name") or prod.get("name") or "Producto"
        qty = int(prod.get("quantity", 0) or 0)
        lot_num = (prod.get("lot_number") or "").strip()

        if qty <= 0:
            continue

        avail = get_product_available_stock(pid or pname, lot_num)
        if qty > avail:
            avail_display = int(avail) if avail.is_integer() else avail
            if lot_num:
                err_msg = (
                    f"Stock insuficiente en bodega para el producto '{pname}' (Lote: {lot_num}). "
                    f"Se solicitaron {qty} unidades, pero el máximo disponible en bodega para ese lote es de {avail_display} unidades."
                )
            else:
                err_msg = (
                    f"Stock insuficiente en bodega para el producto '{pname}'. "
                    f"Se solicitaron {qty} unidades, pero el máximo disponible en bodega es de {avail_display} unidades."
                )
            return False, err_msg, {"product_name": pname, "requested": qty, "available": avail_display}

    return True, "", {}


def discount_stock_for_sale(sale_id: int, products_list: list, conn=None) -> None:
    """
    Descuenta las existencias en bodega para los productos de una venta emitida.
    Descuenta tanto en lot_stock (con trazabilidad) como en inventory_items (stock general)
    y registra los movimientos en Kardex relacional (inventory_movements).
    Soporta conn opcional para ejecutarse dentro de la transacción de la venta.
    """
    def _execute(cur, active_conn):
        cur.execute("SELECT id, sku, LOWER(TRIM(name)) as lname FROM products")
        all_prods = cur.fetchall()
        sku_to_id = {p["sku"]: p["id"] for p in all_prods if p.get("sku")}
        id_to_sku = {p["id"]: p["sku"] for p in all_prods if p.get("sku")}
        name_to_id = {p["lname"]: p["id"] for p in all_prods if p.get("lname")}
        name_to_sku = {p["lname"]: p["sku"] for p in all_prods if p.get("lname") and p.get("sku")}

        # 1. Descuento de lotes
        lot_consumptions = []
        for prod in products_list:
            if not isinstance(prod, dict):
                continue
            pid = prod.get("product_id")
            pname = (prod.get("product_name") or prod.get("name") or "").strip().lower()
            sku = prod.get("sku") or (id_to_sku.get(pid) if pid else None)
            if not pid:
                pid = sku_to_id.get(sku) or name_to_id.get(pname)
            if not pid:
                continue

            qty = int(prod.get("quantity", 0) or 0)
            if qty <= 0:
                continue

            cur.execute("SELECT requires_lot, name FROM products WHERE id = %s", (pid,))
            p_req = cur.fetchone()
            req_lot = p_req["requires_lot"] if p_req else False

            cur.execute("SELECT COUNT(*) as c FROM lot_stock WHERE product_id = %s AND available_qty > 0", (pid,))
            has_lots = cur.fetchone()["c"] > 0

            if prod.get("lot_number"):
                lot_consumptions.append({
                    "product_id": pid,
                    "lot_number": prod.get("lot_number"),
                    "quantity": qty
                })
            elif req_lot or has_lots:
                fifo_consumed = consume_fifo_lots(pid, qty, sale_id=sale_id, conn=active_conn)
                for fc in fifo_consumed:
                    lot_consumptions.append({
                        "product_id": pid,
                        "lot_number": fc["lot_number"],
                        "quantity": fc["quantity"],
                        "lot_id": fc.get("lot_id")
                    })

        if lot_consumptions:
            consume_lots_for_sale(sale_id, lot_consumptions, conn=active_conn)

        # 2. Descuento en inventory_items (stock general de inventario) dentro de la misma transacción
        cur.execute("SELECT json FROM page_data WHERE key = 'inventory_items' FOR UPDATE")
        pd_row = cur.fetchone()
        inventory_items = json.loads(pd_row["json"]) if pd_row and pd_row["json"] else []

        if inventory_items:
            inv_map = {item.get("code"): item for item in inventory_items if item.get("code")}
            changed = False
            for prod in products_list:
                if not isinstance(prod, dict):
                    continue
                qty = int(prod.get("quantity", 0) or 0)
                if qty <= 0:
                    continue

                pid = prod.get("product_id")
                pname = (prod.get("product_name") or prod.get("name") or "").strip().lower()
                sku = prod.get("sku") or id_to_sku.get(pid) or name_to_sku.get(pname)

                if sku and sku in inv_map:
                    current_st = float(inv_map[sku].get("stock", 0.0) or 0.0)
                    inv_map[sku]["stock"] = max(0.0, current_st - qty)
                    changed = True

            if changed:
                cur.execute(
                    """
                    INSERT INTO page_data (key, json) VALUES ('inventory_items', %s)
                    ON CONFLICT (key) DO UPDATE SET json = EXCLUDED.json
                    """,
                    (json.dumps(inventory_items, ensure_ascii=False),)
                )

        # 3. Fase 2 & 5B: Registrar movimientos de salida por venta en Kardex universal (inventory_movements)
        # Agrupar lotes consumidos por product_id para Kardex
        prod_lot_map = {}
        for lc in lot_consumptions:
            prod_lot_map.setdefault(lc["product_id"], []).append(lc)

        sorted_prods = sorted(
            [p for p in products_list if isinstance(p, dict)],
            key=lambda x: int(x.get("product_id") or sku_to_id.get(x.get("sku")) or name_to_id.get((x.get("product_name") or x.get("name") or "").strip().lower()) or 0)
        )

        for prod in sorted_prods:
            qty = int(prod.get("quantity", 0) or 0)
            if qty <= 0:
                continue
            pid = prod.get("product_id")
            pname = (prod.get("product_name") or prod.get("name") or "").strip().lower()
            sku = prod.get("sku") or id_to_sku.get(pid)
            if not pid:
                pid = sku_to_id.get(sku) or name_to_id.get(pname)
            if not pid:
                continue

            price = float(prod.get("unit_price") or prod.get("price") or 0.0)
            consumed_lots_for_prod = prod_lot_map.get(pid, [])
            if consumed_lots_for_prod:
                for cl in consumed_lots_for_prod:
                    record_inventory_movement(
                        product_id=pid,
                        movement_type="SALE",
                        quantity=-float(cl["quantity"]),
                        unit_cost=price,
                        lot_number=cl.get("lot_number"),
                        reference_type="sale",
                        reference_id=sale_id,
                        notes=f"Despacho/Venta #{sale_id} (Lote {cl.get('lot_number')})",
                        conn=active_conn,
                        lot_id=cl.get("lot_id")
                    )
            else:
                lot_num = (prod.get("lot_number") or "").strip() or None
                record_inventory_movement(
                    product_id=pid,
                    movement_type="SALE",
                    quantity=-qty,
                    unit_cost=price,
                    lot_number=lot_num,
                    reference_type="sale",
                    reference_id=sale_id,
                    notes=f"Despacho/Venta #{sale_id}",
                    conn=active_conn
                )

    if conn is not None:
        with conn.cursor() as cur:
            _execute(cur, conn)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                _execute(cur, c)
            c.commit()


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

