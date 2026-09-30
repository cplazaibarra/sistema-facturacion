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
from core.utils import VALID_PAYMENT_TERMS, DEFAULT_PAYMENT_TERMS


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


def create_purchase_order(supplier_id: int, order_date: str, notes: str, items: list[dict], status: str = "Emitida", created_by: int = None, payment_method: str = "Efectivo", payment_terms: str = "NET_30") -> str:
    """Crea una Orden de Compra completa en la base de datos"""
    terms = str(payment_terms or DEFAULT_PAYMENT_TERMS).strip().upper()
    if terms not in VALID_PAYMENT_TERMS:
        terms = DEFAULT_PAYMENT_TERMS

    oc_num = get_next_oc_number()
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Calcular total
            total_amount = sum(item["quantity"] * item["unit_price"] for item in items)
            
            # Insertar cabecera de la OC
            cur.execute(
                """
                INSERT INTO purchase_orders (oc_number, supplier_id, order_date, status, total_amount, notes, created_by, payment_method, payment_terms, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (oc_num, supplier_id, order_date, status, total_amount, notes, created_by, payment_method or 'Efectivo', terms, datetime.now(timezone.utc).isoformat(timespec='seconds'))
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


def update_purchase_order(po_id: int, supplier_id: int, order_date: str, notes: str, items: list[dict], status: str = "Borrador", payment_method: str = "Efectivo", payment_terms: str = None) -> None:
    """Actualiza una Orden de Compra (borrador) y sus ítems en la base de datos"""
    terms = None
    if payment_terms is not None:
        clean = str(payment_terms).strip().upper()
        terms = clean if clean in VALID_PAYMENT_TERMS else DEFAULT_PAYMENT_TERMS

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Calcular total
            total_amount = sum(item["quantity"] * item["unit_price"] for item in items)
            
            # Actualizar cabecera
            if terms is not None:
                cur.execute(
                    """
                    UPDATE purchase_orders
                    SET supplier_id = %s, order_date = %s, status = %s, total_amount = %s, notes = %s, payment_method = %s, payment_terms = %s
                    WHERE id = %s
                    """,
                    (supplier_id, order_date, status, total_amount, notes, payment_method or 'Efectivo', terms, po_id)
                )
            else:
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
                SELECT po.id, po.oc_number, po.order_date, po.status, po.total_amount, po.notes, po.supplier_id, po.payment_method, po.payment_terms,
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


def get_purchase_orders_paginated(
    page: int = 1,
    per_page: int = 25,
    search: Optional[str] = None,
    oc_status: Optional[str] = None,
    payment_status: Optional[str] = None,
    conn=None
) -> dict:
    """
    Retorna órdenes de compra paginadas server-side (25, 50, 100) con búsqueda
    y filtros server-side. Resuelve facturas y entradas en lote únicamente para las OCs visibles.
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

        if oc_status and oc_status.strip():
            where_clauses.append("po.status = %s")
            params.append(oc_status.strip())

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            where_clauses.append(
                """(
                    LOWER(po.oc_number) LIKE %s OR
                    LOWER(s.name) LIKE %s OR
                    EXISTS (
                        SELECT 1 FROM purchase_invoices pi_s
                        WHERE (pi_s.purchase_order_id = po.id OR pi_s.inventory_entry_id IN (SELECT id FROM inventory_entries WHERE purchase_order_id = po.id))
                          AND LOWER(COALESCE(pi_s.invoice_number, '')) LIKE %s
                    ) OR
                    EXISTS (
                        SELECT 1 FROM inventory_entries ie_s
                        WHERE ie_s.purchase_order_id = po.id
                          AND (LOWER(COALESCE(ie_s.order_number, '')) LIKE %s OR LOWER(COALESCE(ie_s.document_number, '')) LIKE %s)
                    )
                )"""
            )
            params.extend([term, term, term, term, term])

        if payment_status and payment_status.strip():
            ps = payment_status.strip()
            if ps == 'Por Pagar':
                where_clauses.append(
                    """EXISTS (
                        SELECT 1 FROM purchase_invoices pi_f
                        WHERE (pi_f.purchase_order_id = po.id OR pi_f.inventory_entry_id IN (SELECT id FROM inventory_entries WHERE purchase_order_id = po.id))
                          AND (pi_f.payment_status = 'Pendiente' OR pi_f.payment_status = 'Por Pagar')
                    )"""
                )
            elif ps == 'Sin Factura':
                where_clauses.append(
                    """(
                        (po.status IN ('Recibida', 'Parcialmente Recibida') AND NOT EXISTS (
                            SELECT 1 FROM purchase_invoices pi_f
                            WHERE (pi_f.purchase_order_id = po.id OR pi_f.inventory_entry_id IN (SELECT id FROM inventory_entries WHERE purchase_order_id = po.id))
                        ))
                        OR EXISTS (
                            SELECT 1 FROM purchase_invoices pi_f
                            WHERE (pi_f.purchase_order_id = po.id OR pi_f.inventory_entry_id IN (SELECT id FROM inventory_entries WHERE purchase_order_id = po.id))
                              AND pi_f.payment_status = 'Sin Factura'
                        )
                    )"""
                )
            elif ps == 'Pagada':
                where_clauses.append(
                    """EXISTS (
                        SELECT 1 FROM purchase_invoices pi_f
                        WHERE (pi_f.purchase_order_id = po.id OR pi_f.inventory_entry_id IN (SELECT id FROM inventory_entries WHERE purchase_order_id = po.id))
                          AND pi_f.payment_status = 'Pagada'
                    )"""
                )
            elif ps == 'Vencida':
                where_clauses.append(
                    """EXISTS (
                        SELECT 1 FROM purchase_invoices pi_f
                        WHERE (pi_f.purchase_order_id = po.id OR pi_f.inventory_entry_id IN (SELECT id FROM inventory_entries WHERE purchase_order_id = po.id))
                          AND pi_f.payment_status = 'Vencida'
                    )"""
                )
            elif ps == 'Sin Iniciar':
                where_clauses.append(
                    """po.status NOT IN ('Recibida', 'Parcialmente Recibida') AND NOT EXISTS (
                        SELECT 1 FROM purchase_invoices pi_f
                        WHERE (pi_f.purchase_order_id = po.id OR pi_f.inventory_entry_id IN (SELECT id FROM inventory_entries WHERE purchase_order_id = po.id))
                    )"""
                )

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # 1. Conteo total de órdenes de compra
        count_sql = f"""
            SELECT COUNT(*) as total
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
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

        # 2. Órdenes paginadas de la página activa
        select_sql = f"""
            SELECT po.id, po.oc_number, po.order_date, po.status, po.total_amount, po.notes, po.supplier_id, po.payment_method, po.payment_terms,
                   s.name as supplier_name,
                   u1.full_name as creator_name,
                   u2.full_name as approver_name
            FROM purchase_orders po
            JOIN suppliers s ON po.supplier_id = s.id
            LEFT JOIN users u1 ON po.created_by = u1.id
            LEFT JOIN users u2 ON po.approved_by = u2.id
            {where_sql}
            ORDER BY po.id DESC
            LIMIT %s OFFSET %s
        """
        cur.execute(select_sql, list(params) + [per_page, actual_offset])
        po_rows = cur.fetchall()

        if not po_rows:
            return {
                "items": [],
                "total": total_count,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
            }

        po_ids = [r["id"] for r in po_rows]

        # 3. Carga BATCH de Facturas asociadas a las OCs visibles
        cur.execute(
            """
            SELECT pi.id, pi.purchase_order_id, pi.invoice_number, pi.payment_status,
                   pi.invoice_amount, pi.due_date, pi.document_file, pi.payment_date,
                   pi.payment_amount, pi.payment_method,
                   ba.bank_name, ba.account_number,
                   ie.purchase_order_id as ie_po_id
            FROM purchase_invoices pi
            LEFT JOIN bank_accounts ba ON ba.id = pi.bank_account_id
            LEFT JOIN inventory_entries ie ON pi.inventory_entry_id = ie.id
            WHERE pi.purchase_order_id = ANY(%s) OR ie.purchase_order_id = ANY(%s)
            ORDER BY pi.id ASC
            """,
            (po_ids, po_ids)
        )
        invoices_by_po: dict[int, list] = {}
        for inv_row in cur.fetchall():
            target_poid = inv_row["purchase_order_id"] or inv_row["ie_po_id"]
            if target_poid:
                if target_poid not in invoices_by_po:
                    invoices_by_po[target_poid] = []
                # Evitar duplicados si está linkeado por po_id y por entry_id
                inv_dict = dict(inv_row)
                if not any(x["id"] == inv_dict["id"] for x in invoices_by_po[target_poid]):
                    invoices_by_po[target_poid].append(inv_dict)

        # 4. Carga BATCH de Entradas de Bodega asociadas a las OCs visibles
        cur.execute(
            """
            SELECT ie.id, ie.purchase_order_id, ie.order_number, ie.entry_date,
                   ie.warehouse, ie.document_type, ie.document_number, ie.document_file,
                   COALESCE(items_stat.items_count, 0) as items_count
            FROM inventory_entries ie
            LEFT JOIN (
                SELECT inventory_entry_id, COUNT(*) as items_count
                FROM inventory_entry_items
                GROUP BY inventory_entry_id
            ) items_stat ON items_stat.inventory_entry_id = ie.id
            WHERE ie.purchase_order_id = ANY(%s)
            ORDER BY ie.id ASC
            """,
            (po_ids,)
        )
        entries_by_po: dict[int, list] = {}
        for entry_row in cur.fetchall():
            target_poid = entry_row["purchase_order_id"]
            if target_poid not in entries_by_po:
                entries_by_po[target_poid] = []
            entries_by_po[target_poid].append(dict(entry_row))

        # 5. Ensamblar resultado final
        orders_result = []
        for r in po_rows:
            order_dict = dict(r)
            order_id = order_dict["id"]
            order_dict["invoices"] = invoices_by_po.get(order_id, [])
            order_dict["entries"] = entries_by_po.get(order_id, [])
            orders_result.append(order_dict)

        return {
            "items": orders_result,
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


def get_purchase_order(po_id: int) -> dict | None:
    """Obtiene la cabecera e información de una OC, incluyendo facturas asociadas"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT po.id, po.oc_number, po.order_date, po.status, po.total_amount, po.notes, po.supplier_id, po.payment_method, po.payment_terms,
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


def list_receivable_purchase_orders(search_query: str = "") -> list[dict]:
    """Lista todas las OC en estado Emitida o Parcialmente Recibida aptas para recepción de mercadería."""
    query = """
        SELECT po.id, po.oc_number, po.order_date, po.status, po.total_amount, po.notes,
               s.name as supplier_name,
               (
                   SELECT COUNT(*) 
                   FROM purchase_order_items poi 
                   WHERE poi.purchase_order_id = po.id AND poi.quantity_ordered > poi.quantity_received
               ) as pending_items_count
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        WHERE po.status IN ('Emitida', 'Parcialmente Recibida')
    """
    params = []
    if search_query:
        query += " AND (po.oc_number ILIKE %s OR s.name ILIKE %s)"
        clean_search = f"%{search_query.strip()}%"
        params.extend([clean_search, clean_search])
    
    query += " ORDER BY po.id DESC"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = [dict(r) for r in cur.fetchall()]
            # Filtrar las que efectivamente tengan items pendientes de recepción
            return [r for r in rows if r.get("pending_items_count", 0) > 0]


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



def get_purchase_invoices_page(status_filter=None, page=1, search=None):
    """Bounded invoice detail, with existing status/search semantics applied in SQL."""
    from core.pagination import PAGE_SIZE, pagination_meta
    clauses, params = [], []
    if isinstance(status_filter, (list, tuple, set)):
        if status_filter:
            clauses.append('pi.payment_status = ANY(%s)')
            params.append(list(status_filter))
    elif status_filter:
        clauses.append('pi.payment_status = %s')
        params.append(status_filter)
    if search and search.strip():
        term=f'%{search.strip()}%'
        clauses.append("(s.name ILIKE %s OR pi.invoice_number ILIKE %s OR po.oc_number ILIKE %s OR ie.order_number ILIKE %s)")
        params.extend([term]*4)
    where='WHERE '+ ' AND '.join(clauses) if clauses else ''
    joins="""FROM purchase_invoices pi
        LEFT JOIN suppliers s ON s.id=pi.supplier_id
        LEFT JOIN inventory_entries ie ON ie.id=pi.inventory_entry_id
        LEFT JOIN purchase_orders po ON po.id=COALESCE(pi.purchase_order_id,ie.purchase_order_id)
        LEFT JOIN bank_accounts ba ON ba.id=pi.bank_account_id"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) AS n {joins} {where}',params)
            pagination=pagination_meta(cur.fetchone()['n'],page)
            cur.execute(f"""SELECT pi.*,s.name AS supplier_name,ie.order_number AS entry_number,
                ie.entry_date,COALESCE(pi.purchase_order_id,ie.purchase_order_id) AS purchase_order_id,
                po.oc_number,ba.bank_name,ba.account_number,ba.account_type
                {joins} {where}
                ORDER BY CASE pi.payment_status WHEN 'Vencida' THEN 1 WHEN 'Pendiente' THEN 2
                         WHEN 'Pagada' THEN 3 ELSE 4 END,
                         COALESCE(pi.due_date,pi.created_at) ASC,pi.id ASC
                LIMIT %s OFFSET %s""",params+[PAGE_SIZE,pagination['offset']])
            return [dict(r) for r in cur.fetchall()],pagination


def get_purchase_invoice_summary():
    """Global dashboard totals, independent of the visible invoice page/filter."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT
                COUNT(*) FILTER (WHERE payment_status='Vencida') AS n_vencidas,
                COUNT(*) FILTER (WHERE payment_status IN ('Pendiente','Vencida')) AS n_pendientes,
                COALESCE(SUM(invoice_amount) FILTER (WHERE payment_status IN ('Pendiente','Vencida','Sin Factura')),0) AS total_pendiente
                FROM purchase_invoices""")
            return dict(cur.fetchone())


def count_entries_missing_invoice():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT COUNT(*) AS n FROM inventory_entries ie
                LEFT JOIN purchase_invoices pi ON pi.inventory_entry_id=ie.id
                WHERE (ie.document_type='guia_despacho' OR ie.document_type IS NULL OR ie.document_type='')
                  AND pi.id IS NULL""")
            return cur.fetchone()['n']
