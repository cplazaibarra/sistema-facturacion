"""
repositories/purchases_repo.py
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


def get_next_oc_number(conn=None) -> str:
    """Genera el siguiente número correlativo único para una OC usando secuencias de PostgreSQL"""
    def _execute(cursor):
        cursor.execute("SELECT nextval('purchase_order_number_seq') as val")
        val = cursor.fetchone()["val"]
        return f"OC-{val:05d}"

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                val_str = _execute(cur)
            c.commit()
            return val_str


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
                       ) AS invoices,
                       COALESCE(
                           (
                               SELECT json_agg(json_build_object(
                                   'id', ie.id,
                                   'order_number', ie.order_number,
                                   'entry_date', ie.entry_date,
                                   'warehouse', ie.warehouse,
                                   'document_type', ie.document_type,
                                   'document_number', ie.document_number,
                                   'document_file', ie.document_file,
                                   'items_count', (SELECT COUNT(*) FROM inventory_entry_items WHERE inventory_entry_id = ie.id)
                               ) ORDER BY ie.id ASC)
                               FROM inventory_entries ie
                               WHERE ie.purchase_order_id = po.id
                           ), '[]'::json
                       ) AS entries
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


def anular_purchase_order(po_id: int, reason: str = "") -> bool:
    """Anula una Orden de Compra en estado 'Emitida' si no registra recepciones de mercadería"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Validar que exista la OC y esté en estado 'Emitida'
            cur.execute("SELECT id, oc_number, status, notes FROM purchase_orders WHERE id = %s", (po_id,))
            po = cur.fetchone()
            if not po or po["status"] != "Emitida":
                return False

            # Validar que no tenga recepciones registradas ni cantidades recibidas
            cur.execute("SELECT COUNT(*) as count FROM inventory_entries WHERE purchase_order_id = %s", (po_id,))
            entries_count = cur.fetchone()["count"]
            if entries_count > 0:
                return False

            cur.execute("SELECT COALESCE(SUM(quantity_received), 0) as total_rec FROM purchase_order_items WHERE purchase_order_id = %s", (po_id,))
            total_rec = cur.fetchone()["total_rec"]
            if total_rec > 0:
                return False

            new_notes = po.get("notes") or ""
            if reason:
                new_notes = f"{new_notes}\n[ANULADA]: {reason}".strip()

            cur.execute(
                """
                UPDATE purchase_orders
                SET status = 'Anulada', notes = %s
                WHERE id = %s
                """,
                (new_notes, po_id)
            )
        conn.commit()
    return True


def get_purchase_order_items(po_id: int) -> list[dict]:
    """Obtiene los productos asociados a una OC"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT poi.id, poi.product_id, poi.quantity_ordered, poi.quantity_received, poi.unit_price, poi.total_price,
                       p.name as product_name, p.sku as product_sku, COALESCE(p.requires_lot, FALSE) as requires_lot
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


def get_purchase_order_entries(po_id: int) -> list[dict]:
    """Obtiene todas las recepciones / entradas de bodega de una OC con sus productos e información de factura"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ie.id, ie.entry_date, ie.order_number, ie.warehouse, ie.notes,
                       ie.document_type, ie.document_number, ie.document_file, ie.total_amount,
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
                WHERE ie.purchase_order_id = %s
                ORDER BY ie.id ASC
            """, (po_id,))
            return [dict(r) for r in cur.fetchall()]


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


def get_purchase_invoice_products_detail(invoice_id: int) -> dict | None:
    """Obtiene el detalle completo de una factura de compra y los productos ingresados en bodega."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT pi.*, s.name AS supplier_name,
                       COALESCE(pi.purchase_order_id, ie.purchase_order_id) AS purchase_order_id,
                       po.oc_number,
                       ie.id AS entry_id, ie.order_number AS entry_number, ie.entry_date,
                       ie.warehouse, ie.document_type AS entry_doc_type,
                       ie.document_number AS entry_doc_number, ie.document_file AS entry_doc_file,
                       ba.bank_name, ba.account_number, ba.account_type
                FROM purchase_invoices pi
                LEFT JOIN suppliers s ON s.id = pi.supplier_id
                LEFT JOIN inventory_entries ie ON ie.id = pi.inventory_entry_id
                LEFT JOIN purchase_orders po ON po.id = COALESCE(pi.purchase_order_id, ie.purchase_order_id)
                LEFT JOIN bank_accounts ba ON ba.id = pi.bank_account_id
                WHERE pi.id = %s
            """, (invoice_id,))
            inv_row = cur.fetchone()
            if not inv_row:
                return None
            inv = dict(inv_row)

            items = []
            # 1. Si la factura tiene entrada directa de inventario
            if inv.get("inventory_entry_id"):
                cur.execute("""
                    SELECT iei.id, iei.product_id, iei.quantity, iei.unit_price, iei.total, iei.lot_number,
                           p.sku, p.name AS product_name, ie.warehouse, ie.entry_date, ie.order_number AS entry_number
                    FROM inventory_entry_items iei
                    JOIN products p ON iei.product_id = p.id
                    JOIN inventory_entries ie ON iei.inventory_entry_id = ie.id
                    WHERE iei.inventory_entry_id = %s
                    ORDER BY iei.id ASC
                """, (inv["inventory_entry_id"],))
                items = [dict(r) for r in cur.fetchall()]

            # 2. Si no tiene entrada directa pero tiene OC asociada, buscar todas las entradas de esa OC
            if not items and inv.get("purchase_order_id"):
                cur.execute("""
                    SELECT iei.id, iei.product_id, iei.quantity, iei.unit_price, iei.total, iei.lot_number,
                           p.sku, p.name AS product_name, ie.warehouse, ie.entry_date, ie.order_number AS entry_number
                    FROM inventory_entry_items iei
                    JOIN products p ON iei.product_id = p.id
                    JOIN inventory_entries ie ON iei.inventory_entry_id = ie.id
                    WHERE ie.purchase_order_id = %s
                    ORDER BY ie.id ASC, iei.id ASC
                """, (inv["purchase_order_id"],))
                items = [dict(r) for r in cur.fetchall()]

            # 3. Si aún no hay recepción registrada, traer los ítems de la OC
            if not items and inv.get("purchase_order_id"):
                cur.execute("""
                    SELECT poi.id, poi.product_id, poi.quantity_ordered AS quantity, poi.unit_price, poi.total_price AS total,
                           '' AS lot_number, p.sku, p.name AS product_name, 'Sin recepción aún' AS warehouse, '' AS entry_date, '' AS entry_number
                    FROM purchase_order_items poi
                    JOIN products p ON poi.product_id = p.id
                    WHERE poi.purchase_order_id = %s
                    ORDER BY poi.id ASC
                """, (inv["purchase_order_id"],))
                items = [dict(r) for r in cur.fetchall()]

            total_qty = sum(float(it.get("quantity") or 0) for it in items)
            total_amount = sum(float(it.get("total") or (float(it.get("quantity") or 0) * float(it.get("unit_price") or 0))) for it in items)

            return {
                "invoice": inv,
                "items": items,
                "total_quantity": total_qty,
                "total_amount": total_amount
            }


def list_purchase_invoices(status_filter: str | list | tuple = None) -> list:
    """Lista facturas de proveedor con datos del proveedor, entrada de bodega y cuenta bancaria."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if isinstance(status_filter, (list, tuple, set)):
                where = "WHERE pi.payment_status = ANY(%s)"
                params = (list(status_filter),)
            elif status_filter:
                where = "WHERE pi.payment_status = %s"
                params = (status_filter,)
            else:
                where = ""
                params = ()
            cur.execute(f"""
                SELECT pi.*, s.name AS supplier_name,
                       ie.order_number AS entry_number, ie.entry_date,
                       COALESCE(pi.purchase_order_id, ie.purchase_order_id) AS purchase_order_id,
                       po.oc_number,
                       ba.bank_name, ba.account_number, ba.account_type
                FROM purchase_invoices pi
                LEFT JOIN suppliers s ON s.id = pi.supplier_id
                LEFT JOIN inventory_entries ie ON ie.id = pi.inventory_entry_id
                LEFT JOIN purchase_orders po ON po.id = COALESCE(pi.purchase_order_id, ie.purchase_order_id)
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

