"""
repositories/sales_repo.py
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


def list_sales(filters: dict = None, *, limit: Optional[int] = None) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT s.id, s.sale_number, s.customer_name, s.customer_email, s.customer_initials,
                       s.sale_date, s.sale_time, s.products_json, s.total_amount, s.status,
                       s.seller_name, s.seller_initials, s.payment_method, s.payment_status,
                       s.delivery_status, s.notes, s.quotation_status, s.win_probability, s.created_at,
                       sp.invoice_due_date, sp.payment_date, sp.payment_proof_file, sp.invoice_file, sp.invoice_number
                FROM sales s
                LEFT JOIN LATERAL (
                    SELECT invoice_due_date, payment_date, payment_proof_file, invoice_file, invoice_number
                    FROM sale_payments
                    WHERE sale_id = s.id
                    ORDER BY id DESC
                    LIMIT 1
                ) sp ON TRUE
                WHERE 1=1
            """
            params = []
            
            if filters:
                if filters.get('status'):
                    query += " AND s.status = %s"
                    params.append(filters['status'])
                if filters.get('exclude_status'):
                    query += " AND s.status != %s"
                    params.append(filters['exclude_status'])
                if filters.get('prefix'):
                    pfx = filters['prefix']
                    if isinstance(pfx, (list, tuple)):
                        sub_or = " OR ".join(["s.sale_number LIKE %s" for _ in pfx])
                        query += f" AND ({sub_or})"
                        params.extend([f"{p}%" for p in pfx])
                    else:
                        query += " AND s.sale_number LIKE %s"
                        params.append(f"{pfx}%")
                if filters.get('customer_name'):
                    query += " AND s.customer_name ILIKE %s"
                    params.append(f"%{filters['customer_name']}%")
                if filters.get('date_from'):
                    query += " AND s.sale_date >= %s"
                    params.append(filters['date_from'])
                if filters.get('date_to'):
                    query += " AND s.sale_date <= %s"
                    params.append(filters['date_to'])
            
            query += " ORDER BY (COALESCE(NULLIF(s.sale_date, ''), '1970-01-01') || ' ' || COALESCE(NULLIF(s.sale_time, ''), '00:00:00'))::timestamp DESC, s.id DESC"
            
            if limit is not None:
                query += " LIMIT %s"
                params.append(max(1, int(limit)))
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            sales = []
            for row in rows:
                sale = dict(row)
                sale['products'] = json.loads(sale['products_json'])
                del sale['products_json']
                sales.append(sale)
            return sales


def count_sales(filters: dict = None) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            query = "SELECT COUNT(*) as count FROM sales WHERE 1=1"
            params = []
            if filters:
                if filters.get('status'):
                    query += " AND status = %s"
                    params.append(filters['status'])
                if filters.get('customer_name'):
                    query += " AND customer_name ILIKE %s"
                    params.append(f"%{filters['customer_name']}%")
                if filters.get('date_from'):
                    query += " AND sale_date >= %s"
                    params.append(filters['date_from'])
                if filters.get('date_to'):
                    query += " AND sale_date <= %s"
                    params.append(filters['date_to'])
            cur.execute(query, tuple(params))
            return cur.fetchone()["count"]


def list_sales_page(limit: int, offset: int, filters: dict = None) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
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
                    query += " AND status = %s"
                    params.append(filters['status'])
                if filters.get('customer_name'):
                    query += " AND customer_name ILIKE %s"
                    params.append(f"%{filters['customer_name']}%")
                if filters.get('date_from'):
                    query += " AND sale_date >= %s"
                    params.append(filters['date_from'])
                if filters.get('date_to'):
                    query += " AND sale_date <= %s"
                    params.append(filters['date_to'])
            query += " ORDER BY (COALESCE(NULLIF(sale_date, ''), '1970-01-01') || ' ' || COALESCE(NULLIF(sale_time, ''), '00:00:00'))::timestamp DESC, id DESC"
            query += " LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            sales = []
            for row in rows:
                sale = dict(row)
                sale['products'] = json.loads(sale['products_json'])
                del sale['products_json']
                sales.append(sale)
            return sales


def list_sales_page_light(limit: int, offset: int, filters: dict = None) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT id, sale_number, customer_name, customer_email, customer_initials,
                       sale_date, sale_time, total_amount, status,
                       seller_name, seller_initials, payment_method, payment_status,
                       delivery_status, notes, created_at
                FROM sales
                WHERE 1=1
            """
            params = []
            if filters:
                if filters.get('status'):
                    query += " AND status = %s"
                    params.append(filters['status'])
                if filters.get('customer_name'):
                    query += " AND customer_name ILIKE %s"
                    params.append(f"%{filters['customer_name']}%")
                if filters.get('date_from'):
                    query += " AND sale_date >= %s"
                    params.append(filters['date_from'])
                if filters.get('date_to'):
                    query += " AND sale_date <= %s"
                    params.append(filters['date_to'])
            query += " ORDER BY (COALESCE(NULLIF(sale_date, ''), '1970-01-01') || ' ' || COALESCE(NULLIF(sale_time, ''), '00:00:00'))::timestamp DESC, id DESC"
            query += " LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return [dict(row) for row in rows]


def get_sales_paginated(
    page: int = 1,
    per_page: int = 25,
    search: str = None,
    client_filter: str = None,
    status_filter: str = None,
    product_filter: str = None,
    card_filter: str = None,
    conn=None,
    sort_by: str = None,
    sort_direction: str = "desc",
) -> dict:
    """
    Retorna ventas paginadas server-side con carga en lote (eliminación de N+1) y filtros.
    - Excluye cotizaciones de manera consistente.
    - Soporta filtros por tarjeta (Ventas Pendientes, Ventas Completadas, Pago Retrasado, Ventas Hoy).
    - Soporta búsqueda server-side y filtros por cliente, estado y producto.
    - Batch loading para sales_status_history, sales_payment_history, sale_payment_items.
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
    sort_columns = {
        'number': 's.sale_number', 'customer': 's.customer_name',
        'date': "(COALESCE(NULLIF(s.sale_date, ''), '1970-01-01') || ' ' || COALESCE(NULLIF(s.sale_time, ''), '00:00:00'))::timestamp",
        'products': 's.products_json', 'total': 's.total_amount',
        'status': 's.status', 'payment': 's.payment_status',
        'due': "NULLIF(NULLIF(sp.invoice_due_date, '-'), '')::date",
        'seller': 's.seller_name',
    }
    sort_column = sort_columns.get(sort_by, sort_columns['date'])
    direction = 'ASC' if sort_direction == 'asc' else 'DESC'
    today_str = datetime.today().strftime('%Y-%m-%d')

    def _execute(cur):
        where_clauses = [
            "s.status != 'Cotización'",
            "s.sale_number NOT LIKE 'COT-%%'"
        ]
        params = []

        # Filtro de Tarjetas Métricas
        if card_filter:
            cf = card_filter.strip()
            if cf == 'Ventas Pendientes':
                where_clauses.append("s.status = 'Pendiente'")
            elif cf == 'Ventas Completadas':
                where_clauses.append("s.status = 'Completada'")
            elif cf in ['Pago Retrasado', 'Pagos Retrasados', 'Retrasada']:
                where_clauses.append(
                    """(
                        (s.payment_status != 'Pagado' OR s.payment_status IS NULL)
                        AND sp.invoice_due_date IS NOT NULL
                        AND sp.invoice_due_date != '-'
                        AND sp.invoice_due_date != ''
                        AND sp.invoice_due_date < %s
                    )"""
                )
                params.append(today_str)
            elif cf == 'Ventas Hoy':
                where_clauses.append("s.sale_date = %s")
                params.append(today_str)

        # Filtro por Estado explícito
        if status_filter and status_filter.strip():
            where_clauses.append("s.status = %s")
            params.append(status_filter.strip())

        # Filtro por Cliente
        if client_filter and client_filter.strip():
            where_clauses.append("LOWER(s.customer_name) = LOWER(%s)")
            params.append(client_filter.strip())

        # Filtro por Producto
        if product_filter and product_filter.strip():
            where_clauses.append("s.products_json ILIKE %s")
            params.append(f"%{product_filter.strip()}%")

        # Búsqueda por texto (N° Venta, Cliente, Email, Factura, Rut en notas)
        if search and search.strip():
            term = f"%{search.strip()}%"
            where_clauses.append(
                """(
                    s.sale_number ILIKE %s OR
                    s.customer_name ILIKE %s OR
                    s.customer_email ILIKE %s OR
                    sp.invoice_number ILIKE %s OR
                    s.notes ILIKE %s OR
                    s.products_json ILIKE %s
                )"""
            )
            params.extend([term] * 6)

        where_sql = "WHERE " + " AND ".join(where_clauses)

        # 2. Contar total de registros
        count_sql = f"""
            SELECT COUNT(*) as total
            FROM sales s
            LEFT JOIN sale_payments sp ON sp.sale_id = s.id
            {where_sql}
        """
        cur.execute(count_sql, tuple(params))
        total_row = cur.fetchone()
        total_count = int(total_row["total"] if total_row else 0)

        total_pages = max(1, (total_count + per_page - 1) // per_page)
        nonlocal page
        if page > total_pages and total_pages > 0:
            page = total_pages
            actual_offset = (page - 1) * per_page
        else:
            actual_offset = offset

        # 3. Consulta paginada de ventas
        select_sql = f"""
            SELECT s.id, s.sale_number, s.customer_name, s.customer_email, s.customer_initials,
                   s.sale_date, s.sale_time, s.products_json, s.total_amount, s.status,
                   s.seller_name, s.seller_initials, s.payment_method, s.payment_status,
                   s.delivery_status, s.notes, s.quotation_status, s.win_probability, s.created_at,
                   sp.invoice_due_date, sp.payment_date, sp.payment_proof_file, sp.invoice_file, sp.invoice_number
            FROM sales s
            LEFT JOIN sale_payments sp ON sp.sale_id = s.id
            {where_sql}
            ORDER BY {sort_column} {direction} NULLS LAST, s.id {direction}
            LIMIT %s OFFSET %s
        """
        data_params = list(params) + [per_page, actual_offset]
        cur.execute(select_sql, tuple(data_params))
        raw_rows = cur.fetchall()

        if not raw_rows:
            return {
                "items": [],
                "total": total_count,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
            }

        sales_list = []
        sale_ids = []
        for r in raw_rows:
            row_dict = dict(r)
            try:
                row_dict["products"] = json.loads(row_dict["products_json"])
            except Exception:
                row_dict["products"] = []
            del row_dict["products_json"]
            sales_list.append(row_dict)
            sale_ids.append(row_dict["id"])

        # 4. CARGA BATCH (Eliminación de N+1 Queries)
        # Query 1: sales_status_history en lote
        cur.execute(
            """
            SELECT sale_id, status, user_name, changed_at, comment
            FROM sales_status_history
            WHERE sale_id = ANY(%s)
            ORDER BY id DESC
            """,
            (sale_ids,)
        )
        status_history_map = {}
        for sh in cur.fetchall():
            sid = sh["sale_id"]
            if sid not in status_history_map:
                status_history_map[sid] = []
            status_history_map[sid].append(dict(sh))

        # Query 2: sales_payment_history en lote
        cur.execute(
            """
            SELECT sale_id, action, user_name, changed_at, details
            FROM sales_payment_history
            WHERE sale_id = ANY(%s)
            ORDER BY id DESC
            """,
            (sale_ids,)
        )
        payment_history_map = {}
        for ph in cur.fetchall():
            sid = ph["sale_id"]
            if sid not in payment_history_map:
                payment_history_map[sid] = []
            payment_history_map[sid].append(dict(ph))

        # Query 3: último pago formal en lote
        cur.execute(
            """
            SELECT DISTINCT ON (sale_id) sale_id, id, bank_account_id,
                   payment_amount, payment_date, payment_proof_file,
                   payment_method, registered_by, registered_at,
                   bank_name_snapshot, account_number_snapshot, payment_notes
            FROM sale_payment_items
            WHERE sale_id = ANY(%s)
            ORDER BY sale_id, id DESC
            """,
            (sale_ids,)
        )
        payment_items_map = {row["sale_id"]: dict(row) for row in cur.fetchall()}
        cur.execute(
            """SELECT sale_id, COALESCE(SUM(payment_amount), 0) AS total_paid
               FROM sale_payment_items WHERE sale_id = ANY(%s)
               GROUP BY sale_id""",
            (sale_ids,)
        )
        payment_totals_map = {row["sale_id"]: float(row["total_paid"] or 0) for row in cur.fetchall()}

        # 5. Cargar mapa de clientes para enriquecer datos
        clients_map = {}
        cur.execute("SELECT * FROM clients")
        for c in cur.fetchall():
            c_dict = dict(c)
            if c_dict.get("email"):
                clients_map[c_dict["email"].lower().strip()] = c_dict
            if c_dict.get("razon_social"):
                clients_map[c_dict["razon_social"].lower().strip()] = c_dict
            if c_dict.get("rut"):
                clients_map[c_dict["rut"].strip()] = c_dict

        # 6. Formatear cada venta
        formatted_items = []
        for sale in sales_list:
            raw_p_status = sale.get("payment_status") or "Pendiente"
            due_date = sale.get("invoice_due_date") or ""

            calculated_payment_status = raw_p_status
            if raw_p_status != "Pagado" and due_date and due_date != "-":
                if due_date < today_str:
                    calculated_payment_status = "Retrasada"

            sid = sale["id"]
            history = status_history_map.get(sid, [])
            payment_history = payment_history_map.get(sid, [])
            payment_item = payment_items_map.get(sid, {})
            bank_account_id = payment_item.get("bank_account_id")

            c_email = (sale.get("customer_email") or "").lower().strip()
            c_name = (sale.get("customer_name") or "").lower().strip()
            c_data = clients_map.get(c_email) or clients_map.get(c_name) or {}

            notes_str = sale.get("notes") or ""
            rut_val = c_data.get("rut") or ""
            dv_val = c_data.get("dv") or ""
            if not rut_val and "RUT:" in notes_str:
                try:
                    rut_part = notes_str.split("RUT:")[1].split("|")[0].strip()
                    if "-" in rut_part:
                        rut_val, dv_val = rut_part.split("-", 1)
                    else:
                        rut_val = rut_part
                except Exception:
                    pass

            formatted_items.append({
                "id": sale["id"],
                "sale_number": sale["sale_number"],
                "customer": {
                    "id": c_data.get("id"),
                    "rut": rut_val,
                    "dv": dv_val,
                    "name": sale["customer_name"],
                    "email": sale.get("customer_email", ""),
                    "phone": c_data.get("phone", ""),
                    "direccion": c_data.get("direccion", ""),
                    "comuna": c_data.get("comuna", ""),
                    "ciudad": c_data.get("ciudad", ""),
                    "giro": c_data.get("giro", ""),
                    "tipo_compra": c_data.get("tipo_compra", "Del Giro"),
                    "category_id": c_data.get("category_id", ""),
                    "initials": sale.get("customer_initials", ""),
                },
                "date": sale["sale_date"],
                "time": sale["sale_time"],
                "products": sale["products"],
                "total": f"${sale['total_amount']:.2f}",
                "total_raw": sale['total_amount'],
                "payment_method": sale.get("payment_method") or "Efectivo",
                "payment_status": calculated_payment_status,
                "invoice_due_date": sale.get("invoice_due_date") or "-",
                "payment_date": sale.get("payment_date") or "-",
                "payment_proof_file": sale.get("payment_proof_file") or "",
                "invoice_number": sale.get("invoice_number") or "",
                "invoice_file": sale.get("invoice_file") or "",
                "notes": sale.get("notes") or "",
                "bank_account_id": bank_account_id,
                "payment_detail": payment_item,
                "payment_paid": payment_totals_map.get(sid, 0.0),
                "payment_pending": max(0.0, float(sale.get("total_amount") or 0) - payment_totals_map.get(sid, 0.0)),
                "status": {
                    "label": sale["status"],
                    "level": "success" if sale["status"] == "Completada" else "warning" if sale["status"] == "Pendiente" else "info" if sale["status"] == "Cotización" else "danger"
                },
                "quotation_status": sale.get("quotation_status") or ("Ganada" if "Venta Generada:" in (sale.get("notes") or "") else "Activa"),
                "win_probability": int(sale.get("win_probability") if sale.get("win_probability") is not None else (100 if "Venta Generada:" in (sale.get("notes") or "") else 50)),
                "seller": {
                    "name": sale["seller_name"],
                    "initials": sale.get("seller_initials", "")
                },
                "history": history,
                "payment_history": payment_history
            })

        return {
            "items": formatted_items,
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


def get_sale_payments_for_sales(sale_ids: list[int]) -> dict[int, dict]:
    if not sale_ids:
        return {}
    placeholders = ",".join(["%s"] * len(sale_ids))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT sale_id, invoice_number, invoice_amount, invoice_due_date, invoice_file, payment_proof_file, payment_amount, payment_date,
                       seller_uploaded_at, payment_uploaded_at, accounting_approved, accounting_approved_by,
                       accounting_approved_at, accounting_comment, status, created_at, updated_at
                FROM sale_payments
                WHERE sale_id IN ({placeholders})
                """,
                tuple(sale_ids),
            )
            rows = cur.fetchall()
            return {row["sale_id"]: dict(row) for row in rows}


def get_sale(sale_id: int) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, sale_number, customer_name, customer_email, customer_initials,
                       sale_date, sale_time, products_json, total_amount, status,
                       seller_name, seller_initials, payment_method, payment_status,
                       delivery_status, notes, quotation_status, win_probability, created_at
                       , customer_delivery_address, customer_category_snapshot
                FROM sales
                WHERE id = %s
                """,
                (sale_id,),
            )
            row = cur.fetchone()
            if row:
                sale = dict(row)
                sale['products'] = json.loads(sale['products_json'])
                del sale['products_json']
                return sale
            return None


def insert_sale(sale: dict, conn=None) -> int:
    quotation_status = sale.get("quotation_status", "Activa")
    win_probability = sale.get("win_probability", 50)
    if quotation_status == "Perdida":
        win_probability = 0

    def _execute(cursor):
        cursor.execute(
            """
            INSERT INTO sales (
                sale_number, customer_name, customer_email, customer_initials,
                sale_date, sale_time, products_json, total_amount, status,
                seller_name, seller_initials, payment_method, payment_status,
                delivery_status, notes, quotation_status, win_probability, created_at
                , customer_delivery_address, customer_category_snapshot
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
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
                sale.get("seller_name", "Vendedor"),
                sale.get("seller_initials", ""),
                sale.get("payment_method", ""),
                sale.get("payment_status", "Pendiente"),
                sale.get("delivery_status", "Pendiente"),
                sale.get("notes", ""),
                quotation_status,
                win_probability,
                sale["created_at"],
                sale.get("customer_delivery_address"),
                sale.get("customer_category_snapshot"),
            ),
        )
        return cursor.fetchone()["id"]

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                ins_id = _execute(cur)
            c.commit()
            return ins_id


class CancelledSaleError(ValueError):
    """A cancelled document is terminal and must remain historical evidence."""


def lock_sale_for_change(cur, sale_id: int, *, allow_cancelled=False):
    """Lock before any mutation; the caller must retain this transaction to commit."""
    cur.execute("SELECT id, status FROM sales WHERE id = %s FOR UPDATE", (sale_id,))
    sale = cur.fetchone()
    if sale and sale['status'] == 'Cancelada' and not allow_cancelled:
        raise CancelledSaleError(
            'Una venta cancelada no se reactiva ni se modifica. Para recuperar la operación, cree una nueva venta.'
        )
    return sale


def update_sale(sale_id: int, sale: dict) -> None:
    quot_status = sale.get("quotation_status")
    win_prob = sale.get("win_probability")
    if quot_status == "Perdida":
        win_prob = 0

    with get_connection() as conn:
        with conn.cursor() as cur:
            lock_sale_for_change(cur, sale_id)
            cur.execute(
                """
                UPDATE sales SET
                    customer_name = %s, customer_email = %s, customer_initials = %s,
                    sale_date = %s, sale_time = %s, products_json = %s, total_amount = %s,
                    status = %s, seller_name = %s, seller_initials = %s,
                    payment_method = %s, payment_status = %s, delivery_status = %s, notes = %s,
                    quotation_status = COALESCE(%s, quotation_status),
                    win_probability = CASE
                        WHEN COALESCE(%s, quotation_status) = 'Perdida' THEN 0
                        ELSE COALESCE(%s, win_probability)
                    END,
                    customer_delivery_address = %s,
                    customer_category_snapshot = %s
                WHERE id = %s
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
                    quot_status,
                    quot_status,
                    win_prob,
                    sale.get("customer_delivery_address"),
                    sale.get("customer_category_snapshot"),
                    sale_id,
                ),
            )
        conn.commit()


def update_quotation_status(sale_id: int, status: str, probability: int = None) -> None:
    """Actualiza el estado (Activa, Ganada, Perdida) y la probabilidad de una cotización."""
    # REGLA DE NEGOCIO: Si el estado es 'Perdida', la probabilidad SIEMPRE es 0%
    if status == 'Perdida':
        probability = 0

    with get_connection() as conn:
        with conn.cursor() as cur:
            lock_sale_for_change(cur, sale_id)
            if probability is not None:
                cur.execute(
                    "UPDATE sales SET quotation_status = %s, win_probability = %s WHERE id = %s",
                    (status, probability, sale_id)
                )
            else:
                cur.execute(
                    "UPDATE sales SET quotation_status = %s WHERE id = %s",
                    (status, sale_id)
                )
        conn.commit()


def delete_sale(sale_id: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            lock_sale_for_change(cur, sale_id)
            cur.execute("DELETE FROM sales WHERE id = %s", (sale_id,))
        conn.commit()


def get_next_sale_number(prefix: str = "P", conn=None) -> str:
    """Genera el siguiente número correlativo único para un pedido de venta o cotización (ej: P-00001, COT-00001)"""
    def _execute(cursor):
        cursor.execute("SELECT nextval('sales_number_seq') as val")
        val = cursor.fetchone()["val"]
        return f"{prefix}-{val:05d}"

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                val_str = _execute(cur)
            c.commit()
            return val_str


def list_packaging_products(conn=None) -> list[dict]:
    """
    Retorna los productos clasificados como material de embalaje (product_type = 'PACKAGING')
    con su físico asignable al embalaje y costo estimado actual.
    """
    from repositories.inventory_repo import get_product_physical_stock
    from repositories.kardex_repo import get_current_ppp

    def _execute(cur):
        cur.execute(
            """
            SELECT id, sku, name, description, cost, product_type
            FROM products
            WHERE (is_deleted = FALSE OR is_deleted IS NULL)
              AND (product_type = 'PACKAGING' OR category = 'Packaging' OR category = 'Embalaje')
            ORDER BY name ASC
            """
        )
        prods = [dict(r) for r in cur.fetchall()]
        for p in prods:
            pid = p["id"]
            physical = get_product_physical_stock(pid, conn=cur.connection)
            calc_cost = get_current_ppp(pid, conn=cur.connection)
            effective_cost = float(calc_cost if calc_cost is not None and calc_cost > 0 else (p.get("cost") or 0.0))
            p["available_stock"] = max(0.0, physical)
            p["calculated_cost"] = effective_cost
        return prods

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


def get_sale_packaging_items(sale_id: int, conn=None) -> list[dict]:
    """
    Retorna los ítems de cajas/embalaje asignados a una venta específica,
    incluyendo el costo unitario congelado como snapshot histórico.
    """
    query = """
        SELECT spi.id, spi.sale_id, spi.product_id, spi.quantity,
               spi.unit_cost, spi.total_cost, spi.inventory_movement_id,
               spi.created_at, spi.created_by,
               p.name as product_name, p.sku as product_sku
        FROM sale_packaging_items spi
        JOIN products p ON p.id = spi.product_id
        WHERE spi.sale_id = %s
        ORDER BY spi.id ASC
    """
    if conn is not None:
        with conn.cursor() as cur:
            cur.execute(query, (sale_id,))
            return [dict(r) for r in cur.fetchall()]
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                cur.execute(query, (sale_id,))
                return [dict(r) for r in cur.fetchall()]


def sale_has_packaging(sale_id: int, conn=None) -> bool:
    """
    Verifica si una venta ya tiene embalaje de despacho formalmente registrado en sale_packaging_items.
    IMPORTANTE: Los productos comerciales vendidos (aunque sean cajas en sales.products_json)
    NO constituyen embalaje de despacho, manteniendo una separación inequívoca entre
    COMMERCIAL SALE ITEM y PACKAGING CONSUMPTION.
    """
    def _execute(cur):
        cur.execute("SELECT 1 FROM sale_packaging_items WHERE sale_id = %s LIMIT 1", (sale_id,))
        return cur.fetchone() is not None

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


def record_sale_packaging(sale_id: int, packaging_items: list[dict], user_name: str = "Sistema", conn=None) -> list[dict]:
    """
    Asigna y descuenta físicamente material de embalaje para una venta:
    - Adquiere locks FOR UPDATE sobre los productos de packaging.
    - Valida que cantidad > 0 y cantidad <= físico remanente bajo lock.
    - Captura el snapshot histórico de costo unitario mediante get_product_calculated_cost().
    - Genera el movimiento de salida en inventory_movements (movement_type='SALE_PACKAGING').
    - Inserta en sale_packaging_items vinculando el movimiento de inventario.
    - Ejecución atómica en PostgreSQL.
    """
    from repositories.inventory_repo import record_inventory_movement, get_product_physical_stock
    from repositories.kardex_repo import get_current_ppp

    if not packaging_items:
        return []

    # Filtrar items válidos
    valid_items = []
    for item in packaging_items:
        try:
            pid = int(item.get("product_id"))
            qty = int(item.get("quantity", 0))
            if qty > 0:
                valid_items.append({"product_id": pid, "quantity": qty})
        except (ValueError, TypeError):
            continue

    if not valid_items:
        return []

    def _execute(cur, active_conn):
        # Bloquear productos en orden ascendente para evitar deadlocks
        sorted_pids = sorted(list(set(i["product_id"] for i in valid_items)))
        cur.execute("SELECT id, name, sku, cost FROM products WHERE id = ANY(%s) ORDER BY id ASC FOR UPDATE", (sorted_pids,))
        locked_prods = {p["id"]: dict(p) for p in cur.fetchall()}

        now_str = datetime.now(timezone.utc).isoformat(timespec='seconds')
        created_records = []

        for it in valid_items:
            pid = it["product_id"]
            qty = it["quantity"]
            prod = locked_prods.get(pid)
            if not prod:
                raise ValueError(f"Producto de embalaje ID {pid} no existe.")

            physical = get_product_physical_stock(pid, conn=active_conn)
            available = max(0.0, physical)
            if available < qty - 1e-6:
                raise ValueError(
                    f"Stock insuficiente para '{prod['name']}'. Disponible: {int(available)}, solicitado: {qty}."
                )

            # Obtener costo unitario congelado al PPP vigente antes de la salida
            calc_cost = get_current_ppp(pid, conn=active_conn)
            unit_cost = float(calc_cost if calc_cost is not None and calc_cost > 0 else (prod.get("cost") or 0.0))
            total_cost = round(qty * unit_cost, 2)

            # Registrar salida en Kardex (inventory_movements)
            mov_id = record_inventory_movement(
                product_id=pid,
                movement_type="SALE_PACKAGING",
                quantity=-float(qty),
                unit_cost=unit_cost,
                warehouse="Almacén Principal",
                reference_type="sale",
                reference_id=sale_id,
                notes=f"Consumo de embalaje para Venta #{sale_id}",
                created_by=user_name,
                conn=active_conn
            )

            # Insertar en sale_packaging_items
            cur.execute(
                """
                INSERT INTO sale_packaging_items (
                    sale_id, product_id, quantity, unit_cost, total_cost,
                    inventory_movement_id, created_at, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    sale_id, pid, qty, unit_cost, total_cost,
                    mov_id, now_str, user_name
                )
            )
            item_id = cur.fetchone()["id"]
            created_records.append({
                "id": item_id,
                "product_id": pid,
                "product_name": prod["name"],
                "quantity": qty,
                "unit_cost": unit_cost,
                "total_cost": total_cost,
                "inventory_movement_id": mov_id
            })

        return created_records

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur, conn)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                res = _execute(cur, c)
            c.commit()
            return res


def get_sale_financial_summary(sale_id: int, conn=None) -> dict:
    """
    Calcula el resumen financiero real de una venta:
    - Neto (Venta sin IVA = total_amount / 1.19)
    - Costo Productos (congelado a partir de sale_items.total_cost_at_sale; fallback seguro a products_json solo para legacy)
    - Costo Embalaje (suma congelada de sale_packaging_items.total_cost)
    - Costo Total Real = Costo Productos + Costo Embalaje
    - Margen Real ($) = Neto - Costo Total Real
    - Margen Real (%) = (Margen Real / Neto) * 100
    """
    def _execute(cur):
        cur.execute("SELECT total_amount, products_json FROM sales WHERE id = %s", (sale_id,))
        srow = cur.fetchone()
        if not srow:
            return {}

        total_amount = float(srow["total_amount"] or 0.0)
        neto = round(total_amount / 1.19, 2)
        iva = round(total_amount - neto, 2)

        # 1. Costo de productos vendidos: Prioridad absoluta al snapshot congelado en sale_items
        cur.execute(
            """
            SELECT COUNT(*) as cnt, COALESCE(SUM(total_cost_at_sale), 0.0) as frozen_cost
            FROM sale_items
            WHERE sale_id = %s
            """,
            (sale_id,)
        )
        items_summary = cur.fetchone()
        if items_summary and items_summary["cnt"] > 0:
            products_cost = float(items_summary["frozen_cost"])
        else:
            # Fallback legacy para ventas antiguas anteriores a la migración
            from repositories.products_repo import get_product_calculated_cost
            products_cost = 0.0
            try:
                products_list = json.loads(srow["products_json"] or "[]")
                for p in products_list:
                    qty = float(p.get("quantity", 0) or 0)
                    pid = p.get("product_id")
                    p_unit_cost = None
                    if pid:
                        p_unit_cost = get_product_calculated_cost(pid)
                        if p_unit_cost is None:
                            cur.execute("SELECT cost FROM products WHERE id = %s", (pid,))
                            prow = cur.fetchone()
                            if prow and prow.get("cost"):
                                p_unit_cost = float(prow["cost"])
                    if p_unit_cost is None:
                        p_unit_cost = 0.0
                    products_cost += round(qty * p_unit_cost, 2)
            except Exception:
                pass

        # 2. Costo de embalaje (sale_packaging_items)
        cur.execute(
            """
            SELECT COALESCE(SUM(total_cost), 0.0) as packaging_cost
            FROM sale_packaging_items
            WHERE sale_id = %s
            """,
            (sale_id,)
        )
        prow = cur.fetchone()
        packaging_cost = float(prow["packaging_cost"] if prow else 0.0)

        # 3. Costo total real y margen
        real_total_cost = round(products_cost + packaging_cost, 2)
        real_margin = round(neto - real_total_cost, 2)
        real_margin_pct = round((real_margin / neto * 100.0), 2) if neto > 0 else 0.0

        return {
            "total_amount": total_amount,
            "neto": neto,
            "iva": iva,
            "products_cost": products_cost,
            "packaging_cost": packaging_cost,
            "real_total_cost": real_total_cost,
            "real_margin": real_margin,
            "real_margin_pct": real_margin_pct
        }

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


def reverse_sale_packaging(sale_id: int, user_name: str = "Sistema", conn=None) -> list[dict]:
    """
    En caso de cancelación de una venta, genera movimientos compensatorios
    en inventory_movements para reingresar las cajas al stock disponible sin borrar registros históricos.
    Utiliza estrictamente el unit_cost original congelado en sale_packaging_items.
    """
    from repositories.inventory_repo import record_inventory_movement

    def _execute(cur, active_conn):
        cur.execute(
            """
            SELECT id, product_id, quantity, unit_cost
            FROM sale_packaging_items
            WHERE sale_id = %s
            """,
            (sale_id,)
        )
        items = [dict(r) for r in cur.fetchall()]
        reversal_movements = []
        for it in items:
            mov_id = record_inventory_movement(
                product_id=it["product_id"],
                movement_type="SALE_PACKAGING_REVERSAL",
                quantity=float(it["quantity"]),  # Reingreso positivo
                unit_cost=float(it["unit_cost"]),
                warehouse="Almacén Principal",
                reference_type="sale_cancellation",
                reference_id=sale_id,
                notes=f"Reversión de embalaje por cancelación de Venta #{sale_id}",
                created_by=user_name,
                conn=active_conn
            )
            reversal_movements.append({"item_id": it["id"], "reversal_movement_id": mov_id})
        return reversal_movements

    if conn is not None:
        return _execute(conn.cursor(), conn)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                res = _execute(cur, c)
            c.commit()
            return res


def reverse_sale_inventory(sale_id: int, user_name: str = "Sistema", conn=None) -> list[dict]:
    """
    Reversa transaccional e idempotente de productos vendidos al cancelar una venta:
    - IDEMPOTENCIA: Verifica que la venta no haya sido revertida previamente (sales.reversal_applied).
    - RESTAURACIÓN DE LOTES: Consulta sale_lot_movements para restaurar exactamente las cantidades
      de los lotes originales en lot_stock. Si un lote quedó DEPLETED, se reactiva a ACTIVE.
    - COSTO HISTÓRICO ORIGINAL: Cada movimiento SALE_REVERSAL ingresa con el unit_cost_at_sale
      congelado en sale_items (nunca el PPP actual).
    - TRAZABILIDAD: No borra movimientos de venta; genera movimientos compensatorios explícitos SALE_REVERSAL.
    """
    from repositories.inventory_repo import record_inventory_movement

    def _execute(cur, active_conn):
        # 1. Bloquear la venta para evitar cancelaciones concurrentes
        cur.execute("SELECT id, status, reversal_applied FROM sales WHERE id = %s FOR UPDATE", (sale_id,))
        sale = cur.fetchone()
        if not sale:
            raise ValueError(f"Venta ID {sale_id} no encontrada.")

        # Idempotencia estricta: Si ya fue revertida, retornar lista vacía sin duplicar
        if sale.get("reversal_applied"):
            return []

        # Marcar la venta como revertida
        cur.execute("UPDATE sales SET reversal_applied = TRUE WHERE id = %s", (sale_id,))

        # 2. Cargar items vendidos y costos unitarios congelados
        cur.execute(
            """
            SELECT product_id, quantity, unit_price, unit_cost_at_sale
            FROM sale_items
            WHERE sale_id = %s
            ORDER BY product_id ASC
            """,
            (sale_id,)
        )
        sale_items = [dict(r) for r in cur.fetchall()]

        # Mapa de costo unitario por producto
        prod_cost_map = {item["product_id"]: float(item["unit_cost_at_sale"] or 0.0) for item in sale_items}

        # 3. Cargar movimientos de lotes originales de esta venta
        cur.execute(
            """
            SELECT id, product_id, lot_number, quantity, lot_id
            FROM sale_lot_movements
            WHERE sale_id = %s
            ORDER BY id ASC
            """,
            (sale_id,)
        )
        lot_movs = [dict(r) for r in cur.fetchall()]

        reversal_results = []

        if lot_movs:
            # Restaurar por cada lote registrado en la venta original
            for lm in lot_movs:
                pid = lm["product_id"]
                lot_num = lm["lot_number"]
                qty = float(lm["quantity"])
                lot_id = lm.get("lot_id")
                unit_cost = prod_cost_map.get(pid, 0.0)

                # Restaurar en lot_stock
                cur.execute(
                    """
                    UPDATE lot_stock
                    SET available_qty = available_qty + %s
                    WHERE product_id = %s AND lot_number = %s
                    RETURNING available_qty, lot_id
                    """,
                    (qty, pid, lot_num)
                )
                ls_res = cur.fetchone()
                target_lot_id = lot_id or (ls_res["lot_id"] if ls_res else None)

                # Si el lote estaba agotado, reactivarlo
                if target_lot_id:
                    cur.execute(
                        "UPDATE lots SET status = 'ACTIVE' WHERE id = %s AND status = 'DEPLETED'",
                        (target_lot_id,)
                    )

                # Registrar movimiento compensatorio en Kardex (inventory_movements)
                mov_id = record_inventory_movement(
                    product_id=pid,
                    movement_type="SALE_REVERSAL",
                    quantity=qty,
                    unit_cost=unit_cost,
                    lot_number=lot_num,
                    warehouse="Almacén Principal",
                    reference_type="sale_cancellation",
                    reference_id=sale_id,
                    notes=f"Reversión de venta #{sale_id} (Lote {lot_num})",
                    created_by=user_name,
                    conn=active_conn,
                    lot_id=target_lot_id
                )
                reversal_results.append({"product_id": pid, "lot_number": lot_num, "quantity": qty, "movement_id": mov_id})
        else:
            # Venta sin lotes detallados (o productos que no requieren lote)
            for it in sale_items:
                pid = it["product_id"]
                qty = float(it["quantity"])
                unit_cost = float(it["unit_cost_at_sale"] or 0.0)

                mov_id = record_inventory_movement(
                    product_id=pid,
                    movement_type="SALE_REVERSAL",
                    quantity=qty,
                    unit_cost=unit_cost,
                    warehouse="Almacén Principal",
                    reference_type="sale_cancellation",
                    reference_id=sale_id,
                    notes=f"Reversión de venta #{sale_id}",
                    created_by=user_name,
                    conn=active_conn
                )
                reversal_results.append({"product_id": pid, "quantity": qty, "movement_id": mov_id})

        # 4. Restaurar existencias en page_data.inventory_items
        try:
            cur.execute("SELECT json FROM page_data WHERE key = 'inventory_items' FOR UPDATE")
            pd_row = cur.fetchone()
            if pd_row and pd_row["json"]:
                inv_items = json.loads(pd_row["json"])
                inv_map = {item.get("code"): item for item in inv_items if item.get("code")}

                cur.execute("SELECT id, sku FROM products WHERE id = ANY(%s)", (list(set(it["product_id"] for it in sale_items)),))
                sku_map = {r["id"]: r["sku"] for r in cur.fetchall()}

                for it in sale_items:
                    sku = sku_map.get(it["product_id"])
                    if sku and sku in inv_map:
                        inv_map[sku]["stock"] = float(inv_map[sku].get("stock", 0.0) or 0.0) + float(it["quantity"])

                cur.execute(
                    """
                    INSERT INTO page_data (key, json) VALUES ('inventory_items', %s)
                    ON CONFLICT (key) DO UPDATE SET json = EXCLUDED.json
                    """,
                    (json.dumps(inv_items, ensure_ascii=False),)
                )
        except Exception:
            pass

        return reversal_results

    if conn is not None:
        return _execute(conn.cursor(), conn)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                res = _execute(cur, c)
            c.commit()
            return res


def check_sale_stock_availability(sale_id: int, conn=None) -> dict:
    """
    Verifica la disponibilidad de stock en tiempo real para todos los productos de una venta.
    Calcula:
      - requested: cantidad solicitada en la línea de la venta.
      - available: físico remanente asignable a la venta seleccionada, sin
                   prioridad automática por fecha o ID de otras pendientes.
      - deficit: max(0, requested - available).
    Si la venta ya fue descontada físicamente previamente (registros en sale_items),
    se marca is_discounted=True y no se considera en déficit.
    Retorna un diccionario estructurado:
      {
         "sale_id": int,
         "has_deficit": bool,
         "is_discounted": bool,
         "items": [
             {
                 "product_id": int,
                 "sku": str,
                 "product_name": str,
                 "requested": float,
                 "available": float,
                 "deficit": float,
                 "has_deficit": bool
             }
         ],
         "total_deficit_lines": int
      }
    """
    from repositories.inventory_repo import get_product_physical_stock

    def _execute(cur, active_conn):
        # 1. Obtener la venta y sus productos
        cur.execute("SELECT id, status, products_json FROM sales WHERE id = %s FOR UPDATE", (sale_id,))
        sale_row = cur.fetchone()
        if not sale_row:
            return {
                "sale_id": sale_id,
                "has_deficit": False,
                "is_discounted": False,
                "items": [],
                "total_deficit_lines": 0,
                "error": "Venta no encontrada"
            }

        # 2. Verificar si ya fue descontada físicamente (sale_items)
        cur.execute("SELECT COUNT(*) as count FROM sale_items WHERE sale_id = %s", (sale_id,))
        is_discounted = (cur.fetchone()["count"] or 0) > 0

        # Si ya fue descontada, sus productos ya consumieron inventario y no presentan déficit
        if is_discounted:
            return {
                "sale_id": sale_id,
                "has_deficit": False,
                "is_discounted": True,
                "items": [],
                "total_deficit_lines": 0
            }

        products_json = sale_row["products_json"]
        products_list = json.loads(products_json) if products_json else []

        items_result = []
        has_deficit = False
        deficit_count = 0

        # Agrupar cantidades solicitadas por producto dentro de la venta
        sale_demand = {}
        for p in products_list:
            if not isinstance(p, dict):
                continue
            pid = p.get("product_id")
            pname = p.get("product_name") or p.get("name") or "Producto"
            sku = p.get("sku") or ""
            qty = float(p.get("quantity", 0) or 0)
            lot_num = (p.get("lot_number") or "").strip()
            if qty <= 0:
                continue

            # Clave de agrupación (pid si existe, sino sku/nombre)
            key = pid if pid else (sku or pname)
            if key not in sale_demand:
                sale_demand[key] = {
                    "product_id": pid,
                    "sku": sku,
                    "product_name": pname,
                    "requested": 0.0,
                    "lot_number": lot_num
                }
            sale_demand[key]["requested"] += qty

        # Resolver también líneas legacy por SKU/nombre antes de adquirir locks.
        # Todas las transiciones que compiten por el mismo producto deben esperar
        # el mismo lock, incluso si sus documentos usan identidades distintas.
        resolved_demand = []
        for demand_info in sale_demand.values():
            pid = demand_info["product_id"]
            pname = demand_info["product_name"]
            sku = demand_info["sku"]
            prod_row = None
            if pid:
                cur.execute("SELECT id, sku, name, requires_lot FROM products WHERE id = %s", (pid,))
                prod_row = cur.fetchone()
            elif sku:
                cur.execute("SELECT id, sku, name, requires_lot FROM products WHERE sku = %s", (sku,))
                prod_row = cur.fetchone()
            elif pname:
                cur.execute("SELECT id, sku, name, requires_lot FROM products WHERE LOWER(TRIM(name)) = LOWER(TRIM(%s))", (pname,))
                prod_row = cur.fetchone()
            resolved_demand.append((demand_info, prod_row))

        product_ids = sorted({product["id"] for _, product in resolved_demand if product})
        if product_ids:
            cur.execute('SELECT id FROM products WHERE id = ANY(%s) ORDER BY id FOR UPDATE', (product_ids,))

        remaining_by_product = {}
        for demand_info, prod_row in resolved_demand:
            pid = demand_info["product_id"]
            pname = demand_info["product_name"]
            sku = demand_info["sku"]
            requested = demand_info["requested"]
            lot_num = demand_info["lot_number"]

            if not prod_row:
                # Si el producto no existe en la base de datos (e.g. mock test product 9999 o servicio no inventariable),
                # no se bloquea por inventario físico inexistente.
                items_result.append({
                    "product_id": pid,
                    "sku": sku,
                    "product_name": pname,
                    "requested": requested,
                    "available": requested,
                    "deficit": 0.0,
                    "has_deficit": False
                })
                continue

            actual_pid = prod_row["id"]
            actual_sku = prod_row["sku"]
            actual_name = prod_row["name"]

            if actual_pid not in remaining_by_product:
                physical_stock = float(get_product_physical_stock(actual_pid, conn=active_conn))
                remaining_by_product[actual_pid] = max(0.0, physical_stock)

            effective_available = remaining_by_product[actual_pid]
            if lot_num:
                lot_physical = float(get_product_physical_stock(actual_pid, lot_num, conn=active_conn))
                effective_available = min(effective_available, lot_physical)

            deficit = max(0.0, requested - effective_available)
            line_has_deficit = (deficit > 0.0001)

            if line_has_deficit:
                has_deficit = True
                deficit_count += 1

            items_result.append({
                "product_id": actual_pid,
                "sku": actual_sku,
                "product_name": actual_name,
                "requested": requested,
                "available": effective_available,
                "deficit": deficit,
                "has_deficit": line_has_deficit
            })
            if not line_has_deficit:
                remaining_by_product[actual_pid] -= requested

        return {
            "sale_id": sale_id,
            "has_deficit": has_deficit,
            "is_discounted": is_discounted,
            "items": items_result,
            "total_deficit_lines": deficit_count
        }

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur, conn)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur, c)


def ensure_sale_stock_discounted(sale_id: int, conn=None) -> bool:
    """
    Garantiza de forma idempotente que las existencias físicas de una venta hayan sido descontadas.
    Si ya existen registros en sale_items para sale_id, no realiza ninguna acción.
    Si aún no ha sido descontada, bloquea venta/productos, revalida físico
    remanente y ejecuta discount_stock_for_sale en la misma transacción.
    Retorna True si realizó el descuento, o False si ya estaba descontada previamente.
    """
    from repositories.inventory_repo import discount_stock_for_sale

    def _execute(cur, active_conn):
        stock_check = check_sale_stock_availability(sale_id, conn=active_conn)
        if stock_check.get("error"):
            raise ValueError(stock_check["error"])
        if stock_check["is_discounted"]:
            return False
        if stock_check["has_deficit"]:
            raise ValueError("Stock físico insuficiente para iniciar la ejecución de esta venta.")

        cur.execute("SELECT products_json FROM sales WHERE id = %s", (sale_id,))
        row = cur.fetchone()
        if not row or not row["products_json"]:
            return False

        products_list = json.loads(row["products_json"])
        discount_stock_for_sale(sale_id, products_list, conn=active_conn)
        return True

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur, conn)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                res = _execute(cur, c)
            c.commit()
            return res


def insert_collection_action(action: dict, conn=None) -> int:
    """
    Inserta una nueva acción de cobranza para una venta en collection_actions.
    Los registros son inmutables.
    """
    def _execute(cur):
        cur.execute(
            """
            INSERT INTO collection_actions (
                sale_id, action_type, action_date, action_time, contact_name,
                result, next_action, next_action_date, payment_commitment_date,
                payment_commitment_amount, notes, user_name
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                action["sale_id"],
                action["action_type"],
                action["action_date"],
                action.get("action_time", "00:00"),
                action.get("contact_name") or None,
                action["result"],
                action.get("next_action") or None,
                action.get("next_action_date") or None,
                action.get("payment_commitment_date") or None,
                action.get("payment_commitment_amount") or None,
                action.get("notes") or None,
                action["user_name"],
            ),
        )
        return cur.fetchone()["id"]

    if conn is not None:
        return _execute(conn.cursor())
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                res = _execute(cur)
            c.commit()
            return res


def list_collection_actions(sale_id: int) -> list[dict]:
    """Retorna el historial completo de gestiones de cobranza para una venta ordenado cronológicamente (más recientes primero)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, sale_id, action_type, action_date, action_time, contact_name,
                       result, next_action, next_action_date, payment_commitment_date,
                       payment_commitment_amount, notes, user_name, created_at
                FROM collection_actions
                WHERE sale_id = %s
                ORDER BY action_date DESC, action_time DESC, id DESC
                """,
                (sale_id,)
            )
            return [dict(row) for row in cur.fetchall()]



def get_quotation_page(cur, *, page=1, status='Activa', search='', client='', product=''):
    """Filter/count in PostgreSQL before fetching the detail and its child batches."""
    from core.pagination import PAGE_SIZE, pagination_meta
    status_expr = "COALESCE(NULLIF(s.quotation_status,''), CASE WHEN POSITION('Venta Generada:' IN COALESCE(s.notes,'')) > 0 THEN 'Ganada' ELSE 'Activa' END)"
    clauses = ["(s.status = 'Cotización' OR s.sale_number LIKE 'COT-%%')"]
    params = []
    if status and status.lower() not in ('all', 'todas'):
        clauses.append(status_expr + " = %s")
        params.append(status)
    if client:
        clauses.append("POSITION(LOWER(%s) IN LOWER(CONCAT_WS(' ',s.customer_name,s.customer_email))) > 0")
        params.append(client.strip())
    if product:
        clauses.append("EXISTS (SELECT 1 FROM jsonb_array_elements(COALESCE(NULLIF(s.products_json,''),'[]')::jsonb) line WHERE POSITION(LOWER(%s) IN LOWER(COALESCE(line->>'product_name',line->>'name',line #>> '{}'))) > 0)")
        params.append(product.strip())
    if search:
        clauses.append("POSITION(LOWER(%s) IN LOWER(CONCAT_WS(' ',s.sale_number,s.customer_name,s.customer_email,s.sale_date,s.sale_time,s.products_json,s.seller_name,s.total_amount,s.payment_method,s.payment_status," + status_expr + "))) > 0")
        params.append(search.strip())
    where = ' AND '.join(clauses)
    cur.execute(f"""SELECT COUNT(*) AS total,
        COUNT(*) FILTER (WHERE {status_expr}='Activa') AS active,
        COUNT(*) FILTER (WHERE {status_expr}='Ganada') AS won,
        COUNT(*) FILTER (WHERE {status_expr}='Perdida') AS lost
        FROM sales s WHERE {where}""", params)
    metrics = dict(cur.fetchone())
    pagination = pagination_meta(metrics['total'], page)
    cur.execute(f"""
                SELECT s.id, s.sale_number, s.customer_name, s.customer_email, s.customer_initials,
                       s.sale_date, s.sale_time, s.products_json, s.total_amount, s.status,
                       s.seller_name, s.seller_initials, s.payment_method, s.payment_status,
                       s.delivery_status, s.notes, s.quotation_status, s.win_probability, s.created_at,
                       s.customer_delivery_address, s.customer_category_snapshot,
                       sp.invoice_due_date, sp.payment_date, sp.payment_proof_file, sp.invoice_file, sp.invoice_number
                FROM sales s
                LEFT JOIN sale_payments sp ON sp.sale_id = s.id
                WHERE {where}
                ORDER BY (COALESCE(NULLIF(s.sale_date, ''), '1970-01-01') || ' ' || COALESCE(NULLIF(s.sale_time, ''), '00:00:00'))::timestamp DESC, s.id DESC
                LIMIT %s OFFSET %s
    """, params + [PAGE_SIZE, pagination['offset']])
    rows = cur.fetchall()
    # Options are distinct labels, never full quotation objects or histories.
    cur.execute("SELECT DISTINCT customer_name FROM sales WHERE status=%s OR sale_number LIKE %s ORDER BY customer_name", ('Cotización','COT-%'))
    clients = [r['customer_name'] for r in cur.fetchall() if r['customer_name']]
    cur.execute("""SELECT DISTINCT COALESCE(line->>'product_name',line->>'name',line #>> '{}') AS name
        FROM sales CROSS JOIN LATERAL jsonb_array_elements(COALESCE(NULLIF(products_json,''),'[]')::jsonb) line
        WHERE status=%s OR sale_number LIKE %s ORDER BY name""", ('Cotización','COT-%'))
    products = [r['name'] for r in cur.fetchall() if r['name']]
    return rows, pagination, metrics, clients, products
