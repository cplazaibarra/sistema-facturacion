"""
repositories/reporting_repo.py
Domain repository extracted from db.py.
Preserves exact implementation, parameters, locks, and return types.
"""

import os
import json
import re
import math
import calendar
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import psycopg2
import psycopg2.extras
from werkzeug.security import generate_password_hash

from core.database import get_connection
from repositories.legacy_repo import get_page_data
from repositories.purchases_repo import list_purchase_invoices


def get_sales_metrics() -> dict:
    """Calcula las métricas principales del dashboard y sus tendencias reales calculadas."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            now = datetime.now()
            today_str = now.strftime('%Y-%m-%d')
            yesterday_str = (now - timedelta(days=1)).strftime('%Y-%m-%d')
            cur_month_str = now.strftime('%Y-%m')
            prev_month_date = (now.replace(day=1) - timedelta(days=1))
            prev_month_str = prev_month_date.strftime('%Y-%m')

            # 1. Ventas hoy vs ayer
            cur.execute(
                "SELECT COALESCE(SUM(total_amount), 0) as total FROM sales WHERE sale_date = %s AND status NOT IN ('Cancelada', 'Cotización') AND (sale_number LIKE 'VTA-%%' OR sale_number LIKE 'P-%%')",
                (today_str,)
            )
            row_today = cur.fetchone()
            total_today = float(row_today["total"]) if row_today else 0.0

            cur.execute(
                "SELECT COALESCE(SUM(total_amount), 0) as total FROM sales WHERE sale_date = %s AND status NOT IN ('Cancelada', 'Cotización') AND (sale_number LIKE 'VTA-%%' OR sale_number LIKE 'P-%%')",
                (yesterday_str,)
            )
            row_yesterday = cur.fetchone()
            total_yesterday = float(row_yesterday["total"]) if row_yesterday else 0.0

            if total_yesterday > 0:
                diff_pct = round(((total_today - total_yesterday) / total_yesterday) * 100, 1)
                ventas_trend_text = f"{'+' if diff_pct > 0 else ''}{diff_pct:.1f}% vs ayer"
                ventas_trend_type = "positive" if diff_pct >= 0 else "negative"
            elif total_today > 0:
                ventas_trend_text = "+100% vs ayer"
                ventas_trend_type = "positive"
            else:
                ventas_trend_text = "0% vs ayer"
                ventas_trend_type = "neutral"

            # 2. Stock total y productos con bajo stock (fuente oficial: inventory_movements)
            cur.execute("""
                SELECT COALESCE(SUM(CASE WHEN COALESCE(p.requires_lot,FALSE)
                                         THEN COALESCE(ls.stock,0)
                                         ELSE COALESCE(ms.stock,0) END),0) AS total_units
                FROM products p
                LEFT JOIN (SELECT product_id, SUM(quantity) AS stock
                           FROM inventory_movements GROUP BY product_id) ms ON ms.product_id=p.id
                LEFT JOIN (SELECT product_id, SUM(available_qty) AS stock
                           FROM lot_stock GROUP BY product_id) ls ON ls.product_id=p.id
                WHERE p.is_deleted IS NOT TRUE
            """)
            row_stk = cur.fetchone()
            total_stock = int(row_stk["total_units"]) if row_stk and row_stk["total_units"] is not None else 0

            cur.execute("""
                SELECT COUNT(*) as low_count
                FROM (
                    SELECT p.id
                    FROM products p
                    LEFT JOIN (SELECT product_id, SUM(quantity) AS stock
                               FROM inventory_movements GROUP BY product_id) ms ON ms.product_id=p.id
                    LEFT JOIN (SELECT product_id, SUM(available_qty) AS stock
                               FROM lot_stock GROUP BY product_id) ls ON ls.product_id=p.id
                    WHERE p.is_deleted IS NOT TRUE
                    AND CASE WHEN COALESCE(p.requires_lot,FALSE)
                             THEN COALESCE(ls.stock,0) ELSE COALESCE(ms.stock,0) END <= COALESCE(p.min_stock,10)
                ) sub
            """)
            row_low = cur.fetchone()
            low_stock_count = int(row_low["low_count"]) if row_low else 0

            if low_stock_count > 0:
                stock_trend_text = f"{low_stock_count} bajo stock"
                stock_trend_type = "warning"
            else:
                stock_trend_text = "Stock óptimo"
                stock_trend_type = "positive"

            # 3. Órdenes pendientes vs total
            cur.execute(
                """SELECT COUNT(*) as count FROM sales
                   WHERE status = 'Pendiente'
                     AND (sale_number LIKE 'VTA-%%' OR sale_number LIKE 'P-%%')"""
            )
            row_pend = cur.fetchone()
            total_pending = int(row_pend["count"]) if row_pend else 0

            cur.execute(
                """SELECT COUNT(*) as count FROM sales
                   WHERE status NOT IN ('Cancelada', 'Cotización')
                     AND (sale_number LIKE 'VTA-%%' OR sale_number LIKE 'P-%%')"""
            )
            row_tot_ord = cur.fetchone()
            total_orders = int(row_tot_ord["count"]) if row_tot_ord else 0

            if total_orders > 0 and total_pending > 0:
                pct_pend = round((total_pending / total_orders) * 100, 1)
                pend_trend_text = f"{pct_pend:.0f}% del total"
                pend_trend_type = "negative" if pct_pend > 50 else "warning"
            elif total_pending == 0:
                pend_trend_text = "Al día (0)"
                pend_trend_type = "positive"
            else:
                pend_trend_text = f"{total_pending} activas"
                pend_trend_type = "warning"

            # La tarjeta de ventas debe cubrir el mismo universo que el
            # listado: todas las VTA activas. Los estados intermedios
            # (En Preparación/Para Despacho) también son ventas gestionadas,
            # por lo que se agrupan junto a completadas para que las métricas
            # no omitan registros visibles en /ventas.
            total_completed = max(total_orders - total_pending, 0)

            # 4. Clientes activos y compras recientes (últimos 60 días)
            cur.execute(
                "SELECT COUNT(*) as count FROM clients"
            )
            row_cli = cur.fetchone()
            total_customers = int(row_cli["count"]) if row_cli else 0

            since_60d = (now - timedelta(days=60)).strftime('%Y-%m-%d')
            cur.execute(
                "SELECT COUNT(DISTINCT customer_name) as count FROM sales WHERE (sale_number LIKE 'VTA-%%' OR sale_number LIKE 'P-%%') AND sale_date >= %s",
                (since_60d,)
            )
            row_rec = cur.fetchone()
            recent_active = int(row_rec["count"]) if row_rec else 0

            if total_customers > 0:
                cli_trend_text = f"100% activos"
                cli_trend_type = "positive"
            else:
                cli_trend_text = "0 registrados"
                cli_trend_type = "neutral"

            return {
                "ventas_hoy": round(float(total_today), 2),
                "ventas_hoy_trend": {"text": ventas_trend_text, "type": ventas_trend_type},
                "productos_stock": total_stock,
                "productos_stock_trend": {"text": stock_trend_text, "type": stock_trend_type},
                "ordenes_pendientes": total_pending,
                "ordenes_pendientes_trend": {"text": pend_trend_text, "type": pend_trend_type},
                "ventas_pendientes": total_pending,
                "clientes_activos": total_customers,
                "clientes_activos_trend": {"text": cli_trend_text, "type": cli_trend_type},
                "ventas_completadas": total_completed,
            }


def get_sales_chart_data(year: int = None, period: str = "6months") -> dict:
    """Obtiene los datos mensuales de ventas para el gráfico de barras del Dashboard."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if year:
                cur.execute(
                    """
                    SELECT TO_CHAR(sale_date::date, 'YYYY-MM') as month,
                           COALESCE(SUM(total_amount), 0) as total
                    FROM sales
                    WHERE TO_CHAR(sale_date::date, 'YYYY') = %s AND status NOT IN ('Cancelada', 'Cotización') AND (sale_number LIKE 'VTA-%%' OR sale_number LIKE 'P-%%')
                    GROUP BY month
                    ORDER BY month ASC
                    """,
                    (str(year),)
                )
                rows = cur.fetchall()
            else:
                limit = 12 if period == "12months" else 6
                cur.execute(
                    """
                    SELECT TO_CHAR(sale_date::date, 'YYYY-MM') as month,
                           COALESCE(SUM(total_amount), 0) as total
                    FROM sales
                    WHERE status NOT IN ('Cancelada', 'Cotización') AND (sale_number LIKE 'VTA-%%' OR sale_number LIKE 'P-%%')
                    GROUP BY month
                    ORDER BY month DESC
                    LIMIT %s
                    """,
                    (limit,)
                )
                rows = cur.fetchall()
                rows = list(reversed(rows))
            
            months = []
            amounts = []
            month_names = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
            
            for row in rows:
                if row.get('month'):
                    try:
                        parts = row['month'].split('-')
                        month_num = int(parts[1])
                        months.append(f"{month_names[month_num - 1]} {parts[0]}")
                        amounts.append(round(float(row['total'] or 0), 2))
                    except Exception:
                        pass
            
            return {"labels": months, "data": amounts}


def get_top_products(year: int = None, period: str = "year") -> dict:
    """Calcula los 5 productos más vendidos agrupados por cantidad (soporta formato JSON dict y string)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if year:
                cur.execute(
                    """
                    SELECT products_json
                    FROM sales
                    WHERE TO_CHAR(sale_date::date, 'YYYY') = %s AND status NOT IN ('Cancelada', 'Cotización') AND (sale_number LIKE 'VTA-%%' OR sale_number LIKE 'P-%%')
                    """,
                    (str(year),)
                )
                rows = cur.fetchall()
            elif period == "month":
                current_month = datetime.now().strftime('%Y-%m')
                cur.execute(
                    """
                    SELECT products_json
                    FROM sales
                    WHERE TO_CHAR(sale_date::date, 'YYYY-MM') = %s AND status NOT IN ('Cancelada', 'Cotización') AND (sale_number LIKE 'VTA-%%' OR sale_number LIKE 'P-%%')
                    """,
                    (current_month,)
                )
                rows = cur.fetchall()
            else:
                cur.execute(
                    """
                    SELECT products_json
                    FROM sales
                    WHERE status NOT IN ('Cancelada', 'Cotización') AND (sale_number LIKE 'VTA-%%' OR sale_number LIKE 'P-%%')
                    """
                )
                rows = cur.fetchall()
            
            product_counts = {}
            for row in rows:
                p_raw = row.get('products_json')
                if not p_raw:
                    continue
                if isinstance(p_raw, str):
                    try:
                        products = json.loads(p_raw)
                    except Exception:
                        products = []
                elif isinstance(p_raw, list):
                    products = p_raw
                else:
                    products = []

                if isinstance(products, dict):
                    products = [products]

                for item in products:
                    if isinstance(item, dict):
                        name = item.get('product_name') or item.get('name') or item.get('sku') or 'Producto'
                        try:
                            qty = int(item.get('quantity', 1))
                        except Exception:
                            qty = 1
                    elif isinstance(item, str):
                        name = item.split('(')[0].strip()
                        try:
                            qty = int(item.split('(')[1].split(')')[0])
                        except Exception:
                            qty = 1
                    else:
                        continue
                    
                    if name:
                        product_counts[name] = product_counts.get(name, 0) + qty
            
            sorted_products = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            
            labels = [p[0] for p in sorted_products]
            data = [p[1] for p in sorted_products]
            
            return {"labels": labels, "data": data}


def get_purchase_years() -> list[int]:
    """Obtiene los años disponibles con órdenes de compra registradas."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT SUBSTRING(order_date, 1, 4)::int as yr
                FROM purchase_orders
                WHERE order_date IS NOT NULL AND status != 'Cancelada'
                ORDER BY yr DESC
            """)
            years = [r['yr'] for r in cur.fetchall() if r['yr']]
            current_yr = datetime.now().year
            if current_yr not in years:
                years.insert(0, current_yr)
            return sorted(list(set(years)), reverse=True)


def get_purchased_products_matrix(year: int, category: str = None, search: str = None, page: int = None, per_page: int = None) -> dict:
    """Monthly product groups paged in SQL; aggregates and CSV cover all matches."""
    from core.pagination import PAGE_SIZE, pagination_meta
    paginated = page is not None or per_page is not None
    clauses = ["po.status NOT IN ('Cancelada', 'Borrador')",
               "SUBSTRING(po.order_date, 1, 4)::int = %s"]
    params = [year]
    if category and category != 'all':
        clauses.append("p.category = %s")
        params.append(category)
    if search and search.strip():
        clauses.append("(p.sku ILIKE %s OR p.name ILIKE %s)")
        params.extend([f"%{search.strip()}%"] * 2)
    cte = f"""WITH monthly AS (
        SELECT p.id AS product_id, COALESCE(NULLIF(p.sku,''),'SIN-SKU') AS sku,
               p.name AS product_name, COALESCE(NULLIF(p.category,''),'Sin Categoría') AS category,
               COALESCE(NULLIF(p.unit_of_measure,''),'UN') AS unit_of_measure,
               SUBSTRING(po.order_date,6,2)::int AS month_num,
               TRUNC(SUM(poi.quantity_ordered)::numeric) AS qty,
               SUM(COALESCE(poi.total_price,poi.quantity_ordered*poi.unit_price,0)) AS amount
        FROM purchase_order_items poi
        JOIN purchase_orders po ON po.id=poi.purchase_order_id
        JOIN products p ON p.id=poi.product_id
        WHERE {' AND '.join(clauses)}
        GROUP BY p.id,p.sku,p.name,p.category,p.unit_of_measure,month_num
    ), grouped AS (
        SELECT product_id,sku,product_name,category,unit_of_measure,
               jsonb_object_agg(month_num,qty) AS months,
               SUM(qty) AS total_qty,SUM(amount) AS total_amount
        FROM monthly GROUP BY product_id,sku,product_name,category,unit_of_measure
    ) """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(cte + "SELECT COUNT(*) AS n FROM grouped", params)
            total_skus = cur.fetchone()['n']
            pagination = pagination_meta(total_skus, page)
            cur.execute(cte + "SELECT month_num,SUM(qty) AS qty,SUM(amount) AS amount FROM monthly GROUP BY month_num", params)
            totals = {r['month_num']: r for r in cur.fetchall()}
            monthly_totals = {m: int(totals.get(m, {}).get('qty') or 0) for m in range(1,13)}
            monthly_amounts = {m: float(totals.get(m, {}).get('amount') or 0) for m in range(1,13)}
            order = " ORDER BY total_qty DESC, product_name ASC, product_id ASC"
            cur.execute(cte + "SELECT sku,product_name,total_qty FROM grouped" + order + " LIMIT 1", params)
            top = cur.fetchone()
            detail = cte + "SELECT * FROM grouped" + order
            detail_params = list(params)
            if paginated:
                detail += " LIMIT %s OFFSET %s"
                detail_params.extend([PAGE_SIZE, pagination['offset']])
            cur.execute(detail, detail_params)
            products = []
            for row in cur.fetchall():
                row = dict(row)
                row['months'] = {m: int(row['months'].get(str(m),0)) for m in range(1,13)}
                row['total_qty'] = int(row['total_qty'] or 0)
                row['total_amount'] = float(row['total_amount'] or 0)
                products.append(row)
            cur.execute("""SELECT DISTINCT COALESCE(NULLIF(p.category,''),'Sin Categoría') AS cat
                FROM purchase_order_items poi JOIN purchase_orders po ON po.id=poi.purchase_order_id
                JOIN products p ON p.id=poi.product_id
                WHERE po.status NOT IN ('Cancelada','Borrador')
                AND SUBSTRING(po.order_date,1,4)::int=%s ORDER BY cat""", (year,))
            categories = [r['cat'] for r in cur.fetchall()]
    grand_total_qty = sum(monthly_totals.values())
    names = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
    top_m = max(monthly_totals,key=monthly_totals.get) if grand_total_qty > 0 else None
    return dict(year=year,products=products,monthly_totals=monthly_totals,
                monthly_amounts=monthly_amounts,grand_total_qty=grand_total_qty,
                grand_total_amount=sum(monthly_amounts.values()),categories=categories,
                top_product=f"{top['sku']} - {top['product_name']} ({int(top['total_qty']):,} u)" if top else '—',
                top_month=f"{names[top_m-1]} ({monthly_totals[top_m]:,} u)" if top_m else '—',
                total_skus=total_skus,page=pagination['page'] if paginated else 1,
                per_page=PAGE_SIZE if paginated else total_skus,
                total_pages=pagination['total_pages'] if paginated else 1,
                pagination=pagination)


def get_income_report_data() -> dict:
    """Calcula datos financieros de Ingresos: pagos históricos realizados y compromisos de cobros futuros."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT s.id, s.sale_number, s.customer_name, s.sale_date, s.total_amount, s.status, s.payment_status,
                       sp.invoice_due_date, sp.payment_date, sp.payment_amount
                FROM sales s
                LEFT JOIN sale_payments sp ON sp.sale_id = s.id
                WHERE s.status NOT IN ('Cancelada', 'Cancelado', 'Cotización')
                ORDER BY s.sale_date ASC
            """
            cur.execute(query)
            sales = cur.fetchall()

    today_str = datetime.now().strftime('%Y-%m-%d')
    
    month_names = {
        "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
        "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
        "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
    }

    monthly_summary = {}
    
    total_historico = 0.0
    total_futuro = 0.0
    monto_retrasado = 0.0
    count_retrasados = 0
    
    futuros_detalles = []
    historicos_detalles = []

    for sale in sales:
        total = float(sale.get("total_amount") or 0.0)
        p_status = sale.get("payment_status") or "Pendiente"
        sale_date = str(sale.get("sale_date") or "")[:10]
        due_date = str(sale.get("invoice_due_date") or "")[:10]
        payment_date = str(sale.get("payment_date") or "")[:10]
        
        if p_status == "Pagado":
            monto_pago = float(sale.get("payment_amount") or total)
            target_month = payment_date[:7] if len(payment_date) >= 7 else (sale_date[:7] if len(sale_date) >= 7 else today_str[:7])
            
            total_historico += monto_pago
            
            if target_month not in monthly_summary:
                y, m = target_month.split("-") if "-" in target_month else (today_str[:4], today_str[5:7])
                monthly_summary[target_month] = {
                    "month_key": target_month,
                    "label": f"{month_names.get(m, m)} {y}",
                    "realizado": 0.0,
                    "comprometido": 0.0,
                }
            monthly_summary[target_month]["realizado"] += monto_pago
            
            historicos_detalles.append({
                "sale_number": sale["sale_number"],
                "customer_name": sale["customer_name"],
                "sale_date": sale_date,
                "payment_date": payment_date or sale_date,
                "monto": monto_pago,
                "status": "Pagado"
            })
        else:
            target_due = due_date if (due_date and due_date != "-") else sale_date
            target_month = target_due[:7] if len(target_due) >= 7 else today_str[:7]
            
            total_futuro += total
            
            is_overdue = False
            if target_due and target_due != "-" and target_due < today_str:
                is_overdue = True
                monto_retrasado += total
                count_retrasados += 1

            if target_month not in monthly_summary:
                y, m = target_month.split("-") if "-" in target_month else (today_str[:4], today_str[5:7])
                monthly_summary[target_month] = {
                    "month_key": target_month,
                    "label": f"{month_names.get(m, m)} {y}",
                    "realizado": 0.0,
                    "comprometido": 0.0,
                }
            monthly_summary[target_month]["comprometido"] += total

            futuros_detalles.append({
                "sale_number": sale["sale_number"],
                "customer_name": sale["customer_name"],
                "sale_date": sale_date,
                "due_date": target_due,
                "monto": total,
                "status": "Retrasada" if is_overdue else "Pendiente",
                "is_overdue": is_overdue
            })

    sorted_months_keys = sorted(monthly_summary.keys())
    chart_labels = [monthly_summary[k]["label"] for k in sorted_months_keys]
    chart_realizados = [round(monthly_summary[k]["realizado"], 2) for k in sorted_months_keys]
    chart_comprometidos = [round(monthly_summary[k]["comprometido"], 2) for k in sorted_months_keys]
    
    table_months = [monthly_summary[k] for k in sorted_months_keys]

    return {
        "total_historico": round(total_historico, 2),
        "total_futuro": round(total_futuro, 2),
        "total_proyectado": round(total_historico + total_futuro, 2),
        "monto_retrasado": round(monto_retrasado, 2),
        "count_retrasados": count_retrasados,
        "chart_labels": chart_labels,
        "chart_realizados": chart_realizados,
        "chart_comprometidos": chart_comprometidos,
        "table_months": table_months,
        "futuros_detalles": futuros_detalles,
        "historicos_detalles": historicos_detalles
    }


def get_cash_flow_data() -> dict:
    """
    Calcula el Flujo de Caja mensual real + proyección 6 meses futuros.
    - Ingresos: pagos cobrados reales (sale_payments con payment_date confirmado).
    - Gastos: recepciones de mercadería (inventory_entries).
    - Impagas: facturas de ventas pendientes de cobro, agrupadas por fecha de vencimiento.
    - Proyección: promedio de los últimos 3 meses con datos + compromisos ya registrados.
    """
    from datetime import date, timedelta

    with get_connection() as conn:
        with conn.cursor() as cur:

            # ── Ingresos cobrados reales por mes ─────────────────────────────
            cur.execute("""
                SELECT SUBSTRING(sp.payment_date, 1, 7) AS mes,
                       SUM(sp.payment_amount) AS total
                FROM sale_payments sp
                WHERE sp.payment_date IS NOT NULL
                  AND sp.payment_amount IS NOT NULL
                  AND sp.payment_amount > 0
                GROUP BY mes
                ORDER BY mes
            """)
            ingresos_reales = {row['mes']: float(row['total'] or 0) for row in cur.fetchall()}

            # ── Gastos reales por mes ─────────────────────────────────────────
            cur.execute("""
                SELECT SUBSTRING(COALESCE(payment_date, created_at), 1, 7) AS mes,
                       SUM(COALESCE(payment_amount, invoice_amount, 0)) AS total
                FROM purchase_invoices
                WHERE payment_status = 'Pagada' AND payment_date IS NOT NULL
                GROUP BY mes
            """)
            pagos_facturas = {row['mes']: float(row['total'] or 0) for row in cur.fetchall()}

            cur.execute("""
                SELECT SUBSTRING(entry_date, 1, 7) AS mes,
                       SUM(total_amount) AS total
                FROM inventory_entries
                WHERE entry_date IS NOT NULL AND total_amount IS NOT NULL
                  AND id NOT IN (SELECT inventory_entry_id FROM purchase_invoices WHERE inventory_entry_id IS NOT NULL)
                GROUP BY mes
            """)
            gastos_entradas = {row['mes']: float(row['total'] or 0) for row in cur.fetchall()}

            gastos_reales = {}
            for mes, val in list(pagos_facturas.items()) + list(gastos_entradas.items()):
                gastos_reales[mes] = gastos_reales.get(mes, 0.0) + val

            cur.execute("""
                SELECT TO_CHAR(paid_date, 'YYYY-MM') AS mes,
                       SUM(COALESCE(payment_amount, amount, 0)) AS total
                FROM operational_expense_occurrences
                WHERE status = 'Pagado' AND paid_date IS NOT NULL
                GROUP BY mes
            """)
            for row in cur.fetchall():
                gastos_reales[row['mes']] = gastos_reales.get(row['mes'], 0.0) + float(row['total'] or 0)

            # Pagos reales de cuotas de deudas financieras
            cur.execute("""
                SELECT TO_CHAR(payment_date, 'YYYY-MM') AS mes,
                       SUM(payment_amount) AS total
                FROM debt_payments
                WHERE payment_date IS NOT NULL AND payment_amount > 0
                GROUP BY mes
            """)
            for row in cur.fetchall():
                gastos_reales[row['mes']] = gastos_reales.get(row['mes'], 0.0) + float(row['total'] or 0)

            # Facturas de proveedores por pagar (futuros compromisos)
            cur.execute("""
                SELECT SUBSTRING(COALESCE(due_date, invoice_date, created_at), 1, 7) AS mes_vence,
                       SUM(invoice_amount) AS total
                FROM purchase_invoices
                WHERE payment_status IN ('Pendiente', 'Vencida')
                GROUP BY mes_vence
            """)
            gastos_por_pagar_mes = {row['mes_vence']: float(row['total'] or 0) for row in cur.fetchall()}

            # Cuotas de deudas financieras por pagar (futuros compromisos proyectados)
            cur.execute("""
                SELECT TO_CHAR(due_date, 'YYYY-MM') AS mes_vence,
                       SUM(balance) AS total
                FROM debt_installments
                WHERE status IN ('PENDIENTE', 'PAGO_PARCIAL', 'VENCIDA') AND balance > 0
                GROUP BY mes_vence
            """)
            for row in cur.fetchall():
                gastos_por_pagar_mes[row['mes_vence']] = gastos_por_pagar_mes.get(row['mes_vence'], 0.0) + float(row['total'] or 0)

            # ── Facturas impagas por mes de vencimiento ──────────────────────
            cur.execute("""
                SELECT
                    COALESCE(SUBSTRING(sp.invoice_due_date, 1, 7), SUBSTRING(s.sale_date, 1, 7)) AS mes_vence,
                    SUM(s.total_amount) AS total
                FROM sales s
                LEFT JOIN sale_payments sp ON sp.sale_id = s.id
                WHERE s.payment_status != 'Pagado'
                  AND s.status NOT IN ('Cancelada', 'Cancelado', 'Cotización')
                GROUP BY mes_vence
                ORDER BY mes_vence
            """)
            impagas_por_mes = {row['mes_vence']: float(row['total'] or 0) for row in cur.fetchall()}

    # ── KPIs del mes actual ───────────────────────────────────────────────
    today = date.today()
    cur_month = today.strftime('%Y-%m')

    ingreso_mes    = ingresos_reales.get(cur_month, 0.0)
    gasto_mes      = gastos_reales.get(cur_month, 0.0)
    impagas_total  = sum(impagas_por_mes.values())
    flujo_neto_mes = ingreso_mes - gasto_mes

    # ── Helpers de fecha ──────────────────────────────────────────────────
    def last_n_months(ref, n):
        months = []
        d = ref.replace(day=1)
        for _ in range(n):
            months.append(d.strftime('%Y-%m'))
            d = (d - timedelta(days=1)).replace(day=1)
        return list(reversed(months))

    def next_n_months(ref, n):
        months = []
        d = ref.replace(day=1)
        for _ in range(n):
            d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
            months.append(d.strftime('%Y-%m'))
        return months

    MONTHS_ES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
    def month_label(m):
        try:
            y, mo = m.split('-')
            return MONTHS_ES[int(mo)-1] + f" '{y[2:]}"
        except Exception:
            return m

    # ── Serie de 6 históricos + 6 proyectados ────────────────────────────
    hist_months = last_n_months(today, 6)
    fut_months  = next_n_months(today, 6)
    all_months  = hist_months + fut_months

    recent_ing = [ingresos_reales.get(m, 0) for m in hist_months[-3:] if ingresos_reales.get(m, 0) > 0]
    recent_gas = [gastos_reales.get(m, 0)   for m in hist_months[-3:] if gastos_reales.get(m, 0) > 0]
    avg_ing = sum(recent_ing) / len(recent_ing) if recent_ing else 0
    avg_gas = sum(recent_gas) / len(recent_gas) if recent_gas else 0

    from repositories.operational_expenses_repo import project_operational_expenses
    projection_start = today.replace(day=1)
    last_projection_month = date.fromisoformat(fut_months[-1] + '-01')
    projection_end = last_projection_month.replace(day=calendar.monthrange(last_projection_month.year, last_projection_month.month)[1])
    operational_projection = {}
    for occurrence in project_operational_expenses(projection_start, projection_end):
        key = occurrence['due_date'].strftime('%Y-%m')
        operational_projection[key] = operational_projection.get(key, 0.0) + occurrence['amount']

    rows = []
    acumulado = 0.0
    for m in all_months:
        es_futuro = m > cur_month
        if not es_futuro:
            ing  = ingresos_reales.get(m, 0.0)
            gas  = gastos_reales.get(m, 0.0)
            imp  = impagas_por_mes.get(m, 0.0)
            tipo = 'real'
        else:
            imp  = impagas_por_mes.get(m, 0.0)
            gas_comp = gastos_por_pagar_mes.get(m, 0.0)
            ing  = avg_ing + imp   # tendencia + facturas clientes por cobrar
            gas  = avg_gas + gas_comp + operational_projection.get(m, 0.0)
            tipo = 'proyectado'

        neto = ing - gas
        acumulado += neto

        rows.append({
            'mes':       m,
            'label':     month_label(m),
            'ingresos':  round(ing, 2),
            'gastos':    round(gas, 2),
            'impagas':   round(imp, 2),
            'neto':      round(neto, 2),
            'acumulado': round(acumulado, 2),
            'tipo':      tipo,
        })

    idx_proyeccion = next((i for i, r in enumerate(rows) if r['tipo'] == 'proyectado'), len(rows))

    return {
        'ingreso_mes':     round(ingreso_mes, 2),
        'gasto_mes':       round(gasto_mes, 2),
        'impagas_total':   round(impagas_total, 2),
        'flujo_neto_mes':  round(flujo_neto_mes, 2),
        'rows':            rows,
        'chart_labels':    [r['label']     for r in rows],
        'chart_ingresos':  [r['ingresos']  for r in rows],
        'chart_gastos':    [r['gastos']    for r in rows],
        'chart_impagas':   [r['impagas']   for r in rows],
        'chart_neto':      [r['neto']      for r in rows],
        'chart_acumulado': [r['acumulado'] for r in rows],
        'idx_proyeccion':  idx_proyeccion,
    }


def get_cash_flow_data_weekly() -> dict:
    """
    Flujo de Caja SEMANAL: 8 semanas históricas + 6 semanas proyectadas.
    Agrupa por semana ISO (lunes–domingo).
    """
    from datetime import date, timedelta

    def week_key(d: date) -> str:
        iso = d.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"

    def week_label(wk: str) -> str:
        try:
            y, w = wk.split('-W')
            monday = date.fromisocalendar(int(y), int(w), 1)
            MONTHS_ES = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic']
            return f"S{int(w)} ({monday.day} {MONTHS_ES[monday.month-1]})"
        except Exception:
            return wk

    def weeks_range(ref: date, back: int, fwd: int):
        monday_ref = ref - timedelta(days=ref.weekday())
        start = monday_ref - timedelta(weeks=back - 1)
        out = []
        d = start
        for _ in range(back + fwd):
            out.append(week_key(d))
            d += timedelta(weeks=1)
        return out

    today = date.today()
    cur_week = week_key(today)

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute("""
                SELECT payment_date, payment_amount FROM sale_payments
                WHERE payment_date IS NOT NULL AND payment_amount IS NOT NULL AND payment_amount > 0
            """)
            ingresos_reales: dict = {}
            for row in cur.fetchall():
                try:
                    d = date.fromisoformat(str(row['payment_date'])[:10])
                    wk = week_key(d)
                    ingresos_reales[wk] = ingresos_reales.get(wk, 0.0) + float(row['payment_amount'])
                except Exception:
                    pass

            # Gastos pagados de facturas
            cur.execute("""
                SELECT COALESCE(payment_date, created_at) AS p_date,
                       COALESCE(payment_amount, invoice_amount, 0) AS total
                FROM purchase_invoices
                WHERE payment_status = 'Pagada' AND payment_date IS NOT NULL
            """)
            gastos_reales: dict = {}
            for row in cur.fetchall():
                try:
                    d = date.fromisoformat(str(row['p_date'])[:10])
                    wk = week_key(d)
                    gastos_reales[wk] = gastos_reales.get(wk, 0.0) + float(row['total'])
                except Exception:
                    pass

            # Entradas sin factura vinculada
            cur.execute("""
                SELECT entry_date, total_amount FROM inventory_entries
                WHERE entry_date IS NOT NULL AND total_amount IS NOT NULL
                  AND id NOT IN (SELECT inventory_entry_id FROM purchase_invoices WHERE inventory_entry_id IS NOT NULL)
            """)
            for row in cur.fetchall():
                try:
                    d = date.fromisoformat(str(row['entry_date'])[:10])
                    wk = week_key(d)
                    gastos_reales[wk] = gastos_reales.get(wk, 0.0) + float(row['total_amount'])
                except Exception:
                    pass

            cur.execute("""
                SELECT paid_date, COALESCE(payment_amount, amount, 0) AS total
                FROM operational_expense_occurrences
                WHERE status = 'Pagado' AND paid_date IS NOT NULL
            """)
            for row in cur.fetchall():
                try:
                    d = date.fromisoformat(str(row['paid_date'])[:10])
                    wk = week_key(d)
                    gastos_reales[wk] = gastos_reales.get(wk, 0.0) + float(row['total'] or 0)
                except Exception:
                    pass

            # Pagos reales de cuotas de deudas
            cur.execute("""
                SELECT payment_date, payment_amount
                FROM debt_payments
                WHERE payment_date IS NOT NULL AND payment_amount > 0
            """)
            for row in cur.fetchall():
                try:
                    d = date.fromisoformat(str(row['payment_date'])[:10])
                    wk = week_key(d)
                    gastos_reales[wk] = gastos_reales.get(wk, 0.0) + float(row['payment_amount'])
                except Exception:
                    pass

            # Facturas de proveedores por pagar (futuros compromisos)
            cur.execute("""
                SELECT COALESCE(due_date, invoice_date, created_at) AS due_d, invoice_amount
                FROM purchase_invoices
                WHERE payment_status IN ('Pendiente', 'Vencida')
            """)
            gastos_por_pagar_sem: dict = {}
            for row in cur.fetchall():
                try:
                    d = date.fromisoformat(str(row['due_d'])[:10])
                    wk = week_key(d)
                    gastos_por_pagar_sem[wk] = gastos_por_pagar_sem.get(wk, 0.0) + float(row['invoice_amount'])
                except Exception:
                    pass

            # Cuotas de deudas financieras pendientes (futuros compromisos)
            cur.execute("""
                SELECT due_date, balance
                FROM debt_installments
                WHERE status IN ('PENDIENTE', 'PAGO_PARCIAL', 'VENCIDA') AND balance > 0
            """)
            for row in cur.fetchall():
                try:
                    d = date.fromisoformat(str(row['due_date'])[:10])
                    wk = week_key(d)
                    gastos_por_pagar_sem[wk] = gastos_por_pagar_sem.get(wk, 0.0) + float(row['balance'])
                except Exception:
                    pass

            # Facturas clientes impagas
            cur.execute("""
                SELECT s.total_amount,
                       COALESCE(sp.invoice_due_date, s.sale_date) AS fecha_vence
                FROM sales s
                LEFT JOIN sale_payments sp ON sp.sale_id = s.id
                WHERE s.payment_status != 'Pagado'
                  AND s.status NOT IN ('Cancelada', 'Cancelado', 'Cotización')
            """)
            impagas_por_semana: dict = {}
            for row in cur.fetchall():
                try:
                    d = date.fromisoformat(str(row['fecha_vence'])[:10])
                    wk = week_key(d)
                    impagas_por_semana[wk] = impagas_por_semana.get(wk, 0.0) + float(row['total_amount'])
                except Exception:
                    pass

    ingreso_sem    = ingresos_reales.get(cur_week, 0.0)
    gasto_sem      = gastos_reales.get(cur_week, 0.0)
    impagas_total  = sum(impagas_por_semana.values())
    flujo_neto_sem = ingreso_sem - gasto_sem

    all_weeks  = weeks_range(today, back=8, fwd=6)
    hist_weeks = [w for w in all_weeks if w <= cur_week]
    recent_ing = [ingresos_reales.get(w, 0) for w in hist_weeks[-4:] if ingresos_reales.get(w, 0) > 0]
    recent_gas = [gastos_reales.get(w, 0)   for w in hist_weeks[-4:] if gastos_reales.get(w, 0) > 0]
    avg_ing = sum(recent_ing) / len(recent_ing) if recent_ing else 0
    avg_gas = sum(recent_gas) / len(recent_gas) if recent_gas else 0

    from repositories.operational_expenses_repo import project_operational_expenses
    monday_start = today - timedelta(days=today.weekday())
    projection_end = monday_start + timedelta(weeks=6)
    operational_projection = {}
    for occurrence in project_operational_expenses(monday_start, projection_end):
        key = week_key(occurrence['due_date'])
        operational_projection[key] = operational_projection.get(key, 0.0) + occurrence['amount']

    rows = []
    acumulado = 0.0
    for wk in all_weeks:
        es_futuro = wk > cur_week
        if not es_futuro:
            ing  = ingresos_reales.get(wk, 0.0)
            gas  = gastos_reales.get(wk, 0.0)
            imp  = impagas_por_semana.get(wk, 0.0)
            tipo = 'real'
        else:
            imp      = impagas_por_semana.get(wk, 0.0)
            gas_comp = gastos_por_pagar_sem.get(wk, 0.0)
            ing      = avg_ing + imp
            gas      = avg_gas + gas_comp + operational_projection.get(wk, 0.0)
            tipo     = 'proyectado'

        neto = ing - gas
        acumulado += neto
        rows.append({
            'mes':       wk,
            'label':     week_label(wk),
            'ingresos':  round(ing, 2),
            'gastos':    round(gas, 2),
            'impagas':   round(imp, 2),
            'neto':      round(neto, 2),
            'acumulado': round(acumulado, 2),
            'tipo':      tipo,
        })

    idx_proyeccion = next((i for i, r in enumerate(rows) if r['tipo'] == 'proyectado'), len(rows))

    return {
        'ingreso_mes':     round(ingreso_sem, 2),
        'gasto_mes':       round(gasto_sem, 2),
        'impagas_total':   round(impagas_total, 2),
        'flujo_neto_mes':  round(flujo_neto_sem, 2),
        'rows':            rows,
        'chart_labels':    [r['label']     for r in rows],
        'chart_ingresos':  [r['ingresos']  for r in rows],
        'chart_gastos':    [r['gastos']    for r in rows],
        'chart_impagas':   [r['impagas']   for r in rows],
        'chart_neto':      [r['neto']      for r in rows],
        'chart_acumulado': [r['acumulado'] for r in rows],
        'idx_proyeccion':  idx_proyeccion,
    }


def get_system_notifications() -> list[dict]:
    """Genera las notificaciones y alertas activas del sistema (facturas vencidas/por vencer, stock bajo, ventas pendientes)."""
    notifications = []
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    next_7d_str = (now + timedelta(days=7)).strftime('%Y-%m-%d')

    # 1. Facturas de compra vencidas o por vencer (Cuentas por Pagar)
    invoices = list_purchase_invoices()
    for inv in invoices:
        p_status = inv.get('payment_status', 'Pendiente')
        due = inv.get('due_date') or ''
        num = inv.get('invoice_number') or f"ID #{inv.get('id')}"
        supp = inv.get('supplier_name') or 'Proveedor'
        amt = float(inv.get('invoice_amount') or 0)
        
        if p_status != 'Pagada' and due:
            if due < today_str:
                notifications.append({
                    'id': f"inv-{inv['id']}",
                    'type': 'danger',
                    'icon': 'fa-solid fa-file-circle-xmark',
                    'title': f'Factura Vencida: {num}',
                    'desc': f'{supp} · ${amt:,.0f} · Venció el {due}',
                    'link': '/compras/cuentas-por-pagar',
                    'time': 'Cuentas por Pagar'
                })
            elif due <= next_7d_str:
                notifications.append({
                    'id': f"inv-{inv['id']}",
                    'type': 'warning',
                    'icon': 'fa-solid fa-file-invoice-dollar',
                    'title': f'Factura por Vencer: {num}',
                    'desc': f'{supp} · ${amt:,.0f} · Vence el {due}',
                    'link': '/compras/cuentas-por-pagar',
                    'time': 'Cuentas por Pagar'
                })

    # 2. Stock crítico en Bodega
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.id, p.name, p.sku, COALESCE(p.min_stock, 10) as min_stock,
                       CASE WHEN COALESCE(p.requires_lot,FALSE)
                            THEN COALESCE(ls.stock,0) ELSE COALESCE(ms.stock,0) END AS current_stock
                FROM products p
                LEFT JOIN (SELECT product_id, SUM(quantity) AS stock
                           FROM inventory_movements GROUP BY product_id) ms ON ms.product_id=p.id
                LEFT JOIN (SELECT product_id, SUM(available_qty) AS stock
                           FROM lot_stock GROUP BY product_id) ls ON ls.product_id=p.id
                WHERE p.is_deleted IS NOT TRUE
                  AND CASE WHEN COALESCE(p.requires_lot,FALSE)
                           THEN COALESCE(ls.stock,0) ELSE COALESCE(ms.stock,0) END <= COALESCE(p.min_stock,10)
                ORDER BY current_stock ASC, p.id ASC
                LIMIT 5
            """)
            low_rows = cur.fetchall()
            for p_low in low_rows:
                stk = int(p_low['current_stock'])
                min_stk = int(p_low['min_stock'])
                notifications.append({
                    'id': f"stock-{p_low['sku'] or p_low['id']}",
                    'type': 'warning',
                    'icon': 'fa-solid fa-boxes-stacked',
                    'title': f"Stock Bajo: {p_low['name']}",
                    'desc': f"Quedan {stk} unidades (mínimo requerido: {min_stk})",
                    'link': '/inventario',
                    'time': 'Bodega'
                })

    # 3. Ventas pendientes por gestionar
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM sales WHERE status = 'Pendiente' AND (sale_number LIKE 'VTA-%%' OR sale_number LIKE 'P-%%')")
            row_pend = cur.fetchone()
            pend = int(row_pend['count']) if row_pend else 0
            if pend > 0:
                notifications.append({
                    'id': 'sales-pending',
                    'type': 'info',
                    'icon': 'fa-solid fa-clock',
                    'title': f'{pend} Ventas Pendientes',
                    'desc': 'Pedidos pendientes de pago o despacho',
                    'link': '/ventas',
                    'time': 'Ventas'
                })

    return notifications


def get_sales_report_data(year: Optional[int] = None) -> dict:
    """
    Calcula los datos reales consolidados para el reporte de ventas:
    - Ingresos totales reales
    - Cantidad total de ventas no canceladas
    - Ticket promedio
    - Desglose y distribución por producto
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT id, sale_number, total_amount, sale_date, products_json
                FROM sales
                WHERE status NOT IN ('Cancelada', 'Cotización')
                  AND (sale_number LIKE 'VTA-%%' OR sale_number LIKE 'P-%%')
            """
            params = []
            if year:
                query += " AND SUBSTRING(sale_date, 1, 4) = %s"
                params.append(str(year))
            query += " ORDER BY sale_date DESC"

            cur.execute(query, tuple(params))
            sales = cur.fetchall()

    total_sales_count = len(sales)
    total_income = sum(float(s["total_amount"] or 0.0) for s in sales)
    avg_ticket = (total_income / total_sales_count) if total_sales_count > 0 else 0.0

    product_stats = {}
    for s in sales:
        raw = s.get("products_json")
        if not raw:
            continue
        try:
            prods = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            prods = []

        if isinstance(prods, dict):
            prods = [prods]

        for p in prods:
            if isinstance(p, dict):
                p_name = p.get("product_name") or p.get("name") or p.get("sku") or "Producto"
                qty = float(p.get("quantity") or 1)
                rev = float(p.get("subtotal") or (qty * float(p.get("price") or 0.0)))
            elif isinstance(p, str):
                import re
                m = re.match(r'^(.*?)\s*\((\d+(?:\.\d+)?)\)$', p)
                if m:
                    p_name = m.group(1).strip()
                    qty = float(m.group(2))
                else:
                    p_name = p.strip()
                    qty = 1.0
                rev = 0.0
            else:
                continue

            if p_name not in product_stats:
                product_stats[p_name] = {"units": 0.0, "revenue": 0.0}
            product_stats[p_name]["units"] += qty
            product_stats[p_name]["revenue"] += rev

    # Distribución porcentual
    items_list = []
    for name, stats in sorted(product_stats.items(), key=lambda x: (x[1]["revenue"], x[1]["units"]), reverse=True):
        pct = round((stats["revenue"] / total_income * 100), 1) if total_income > 0 else 0.0
        items_list.append({
            "name": name,
            "units": int(stats["units"]) if stats["units"].is_integer() else round(stats["units"], 2),
            "revenue": round(stats["revenue"], 2),
            "percentage": pct,
        })

    return {
        "total_income": round(total_income, 2),
        "total_sales_count": total_sales_count,
        "avg_ticket": round(avg_ticket, 2),
        "products": items_list,
        "has_data": total_sales_count > 0,
    }


def get_purchases_report_data(year: Optional[int] = None) -> dict:
    """
    Calcula los datos reales consolidados para el reporte de compras:
    - Total acumulado comprado
    - Proveedores activos con órdenes
    - Total de órdenes de compra válidas
    - Desglose por proveedor con total y estado de pago
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT 
                    s.name as supplier_name,
                    MAX(po.order_date) as last_purchase_date,
                    COUNT(po.id) as total_pos,
                    COALESCE(SUM(po.total_amount), 0) as total_amount
                FROM purchase_orders po
                JOIN suppliers s ON po.supplier_id = s.id
                WHERE po.status != 'Anulada'
            """
            params = []
            if year:
                query += " AND SUBSTRING(po.order_date, 1, 4) = %s"
                params.append(str(year))
            query += " GROUP BY s.id, s.name ORDER BY total_amount DESC"

            cur.execute(query, tuple(params))
            supplier_rows = [dict(r) for r in cur.fetchall()]

            # Obtener estado de pago agregado por proveedor desde facturas
            cur.execute("""
                SELECT supplier_id, payment_status, COUNT(*) as cnt
                FROM purchase_invoices
                GROUP BY supplier_id, payment_status
            """)
            inv_statuses = cur.fetchall()

    total_amount = sum(float(r["total_amount"]) for r in supplier_rows)
    total_suppliers = len(supplier_rows)
    total_pos = sum(int(r["total_pos"]) for r in supplier_rows)

    return {
        "total_amount": round(total_amount, 2),
        "total_suppliers": total_suppliers,
        "total_pos": total_pos,
        "suppliers": supplier_rows,
        "has_data": total_pos > 0,
    }


def get_expenses_report_data(month: Optional[str] = None) -> dict:
    """
    Calcula los datos reales consolidados para el reporte de gastos operacionales:
    - Total de facturas/gastos registrados en el mes o período
    - Servicios y gastos directos
    - Margen de gastos sobre ingresos del período
    - Desglose por proveedor / tipo de gasto
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Facturas de compra registradas
            cur.execute("""
                SELECT 
                    COALESCE(s.name, 'Proveedor General') as category,
                    COALESCE(SUM(pi.invoice_amount), 0) as total_amount,
                    COUNT(pi.id) as count_invoices
                FROM purchase_invoices pi
                LEFT JOIN suppliers s ON pi.supplier_id = s.id
                GROUP BY s.name
                ORDER BY total_amount DESC
            """)
            breakdown_rows = [dict(r) for r in cur.fetchall()]

            # Total gastos acumulados
            total_expenses = sum(float(r["total_amount"]) for r in breakdown_rows)

            # Total ingresos acumulados para calcular margen
            cur.execute("""
                SELECT COALESCE(SUM(total_amount), 0) as total_sales
                FROM sales
                WHERE status NOT IN ('Cancelada', 'Cotización') AND (sale_number LIKE 'VTA-%%' OR sale_number LIKE 'P-%%')
            """)
            row_sales = cur.fetchone()
            total_sales = float(row_sales["total_sales"]) if row_sales else 0.0

    margin_pct = round((total_expenses / total_sales * 100), 1) if total_sales > 0 else 0.0

    # Agregar porcentajes a cada categoría
    for r in breakdown_rows:
        amt = float(r["total_amount"])
        r["percentage"] = round((amt / total_expenses * 100), 1) if total_expenses > 0 else 0.0

    return {
        "total_expenses": round(total_expenses, 2),
        "margin_pct": margin_pct,
        "breakdown": breakdown_rows,
        "has_data": len(breakdown_rows) > 0,
    }


def get_purchases_and_expenses_report_data(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    doc_type: Optional[str] = "all",
    supplier_beneficiary: Optional[str] = None,
    category: Optional[str] = None,
    payment_status: Optional[str] = "all",
    search: Optional[str] = None,
    page: Optional[int] = 1,
    per_page: Optional[int] = 25,
    sort_by: Optional[str] = "date",
    sort_order: Optional[str] = "desc",
) -> dict:
    """
    Reporte Consolidado: Facturas de Compra y Gastos (Histórico / Documental).
    Unifica:
    1. Facturas de compra (purchase_invoices con proveedor, OC y recepción).
    2. Gastos operacionales registrados (operational_expense_occurrences con categoría).
    """
    records = []

    # Validar y normalizar parámetros
    try:
        page = int(page) if page is not None else 1
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    if per_page is not None:
        try:
            per_page = int(per_page)
            if per_page not in (25, 50, 100):
                per_page = 25
        except (ValueError, TypeError):
            per_page = 25

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Facturas de Compra (si doc_type in ('all', 'factura'))
            if doc_type in ("all", "factura", "", None):
                query_invoices = """
                    SELECT
                        pi.id AS id,
                        'Factura de Compra' AS doc_type,
                        'factura' AS doc_type_code,
                        COALESCE(NULLIF(pi.invoice_date, ''), SUBSTRING(pi.created_at, 1, 10)) AS doc_date,
                        COALESCE(NULLIF(pi.due_date, ''), '') AS due_date,
                        COALESCE(NULLIF(pi.invoice_number, ''), 'Sin Factura') AS doc_number,
                        COALESCE(s.name, 'Proveedor no especificado') AS party_name,
                        COALESCE(s.rut, '') || CASE WHEN s.dv IS NOT NULL AND s.dv <> '' THEN '-' || s.dv ELSE '' END AS party_rut,
                        'Compras / Insumos' AS category_name,
                        COALESCE(NULLIF(pi.notes, ''), 'Factura de compra / recepción de mercadería') AS description,
                        COALESCE(po.oc_number, '') AS oc_number,
                        COALESCE(po.id, ie.purchase_order_id) AS purchase_order_id,
                        ie.id AS inventory_entry_id,
                        ie.order_number AS entry_order_number,
                        COALESCE(pi.invoice_amount, 0.0) AS total_amount,
                        ie.total_amount AS entry_net_amount,
                        COALESCE(pi.payment_amount, 0.0) AS payment_amount,
                        pi.payment_status AS payment_status,
                        COALESCE(pi.payment_date, '') AS payment_date,
                        COALESCE(pi.payment_method, '') AS payment_method,
                        COALESCE(ba.bank_name, '') AS bank_name,
                        COALESCE(ba.account_number, '') AS bank_account_number,
                        pi.document_file AS doc_file,
                        pi.payment_proof_file AS payment_proof_file
                    FROM purchase_invoices pi
                    LEFT JOIN suppliers s ON s.id = pi.supplier_id
                    LEFT JOIN inventory_entries ie ON ie.id = pi.inventory_entry_id
                    LEFT JOIN purchase_orders po ON po.id = COALESCE(pi.purchase_order_id, ie.purchase_order_id)
                    LEFT JOIN bank_accounts ba ON ba.id = pi.bank_account_id
                """
                cur.execute(query_invoices)
                for row in cur.fetchall():
                    total = float(row["total_amount"] or 0.0)
                    entry_net = row["entry_net_amount"]

                    # Cálculo exacto Neto / IVA
                    if entry_net is not None and float(entry_net) > 0 and float(entry_net) <= total:
                        neto = round(float(entry_net), 2)
                        iva = round(total - neto, 2)
                    elif total > 0:
                        neto = round(total / 1.19, 2)
                        iva = round(total - neto, 2)
                    else:
                        neto = 0.0
                        iva = 0.0

                    pay_status = row["payment_status"] or "Pendiente"
                    paid_amt = float(row["payment_amount"] or 0.0)
                    if pay_status == "Pagada" and paid_amt == 0.0:
                        paid_amt = total
                    pending_amt = 0.0 if pay_status == "Pagada" else max(0.0, total - paid_amt)

                    records.append({
                        "id": row["id"],
                        "origin_type": "Factura de Compra",
                        "origin_code": "factura",
                        "doc_date": row["doc_date"] or "",
                        "due_date": row["due_date"] or "",
                        "doc_number": row["doc_number"] or "Sin N°",
                        "party_name": row["party_name"] or "",
                        "party_rut": row["party_rut"] or "",
                        "category_name": row["category_name"] or "Compras",
                        "description": row["description"] or "",
                        "oc_number": row["oc_number"] or "",
                        "purchase_order_id": row["purchase_order_id"],
                        "inventory_entry_id": row["inventory_entry_id"],
                        "entry_order_number": row["entry_order_number"] or "",
                        "neto": neto,
                        "iva": iva,
                        "total": total,
                        "paid_amount": paid_amt,
                        "pending_amount": pending_amt,
                        "payment_status": pay_status,
                        "payment_date": row["payment_date"] or "",
                        "payment_method": row["payment_method"] or "",
                        "bank_name": row["bank_name"] or "",
                        "bank_account_number": row["bank_account_number"] or "",
                        "doc_file": row["doc_file"] or "",
                        "payment_proof_file": row["payment_proof_file"] or "",
                        "expense_id": None,
                    })

            # 2. Gastos Operacionales (si doc_type in ('all', 'gasto'))
            if doc_type in ("all", "gasto", "", None):
                query_expenses = """
                    SELECT
                        o.id AS occurrence_id,
                        e.id AS expense_id,
                        'Gasto Operacional' AS doc_type,
                        'gasto' AS doc_type_code,
                        TO_CHAR(COALESCE(o.invoice_date, o.due_date, e.start_date), 'YYYY-MM-DD') AS doc_date,
                        TO_CHAR(COALESCE(o.due_date, e.start_date), 'YYYY-MM-DD') AS due_date,
                        COALESCE(NULLIF(o.invoice_number, ''), 'GOP-' || LPAD(o.id::text, 5, '0')) AS doc_number,
                        o.invoice_number,
                        e.name AS expense_name,
                        COALESCE(NULLIF(e.beneficiary, ''), e.name) AS party_name,
                        '' AS party_rut,
                        COALESCE(c.name, e.category, 'Operacional') AS category_name,
                        COALESCE(NULLIF(o.notes, ''), NULLIF(e.description, ''), e.name) AS description,
                        '' AS oc_number,
                        NULL::integer AS purchase_order_id,
                        NULL::integer AS inventory_entry_id,
                        '' AS entry_order_number,
                        COALESCE(o.amount, e.amount, 0.0) AS total_amount,
                        COALESCE(o.payment_amount, o.amount, 0.0) AS payment_amount,
                        o.status AS status,
                        TO_CHAR(o.paid_date, 'YYYY-MM-DD') AS payment_date,
                        'Transferencia' AS payment_method,
                        COALESCE(ba.bank_name, '') AS bank_name,
                        COALESCE(ba.account_number, '') AS bank_account_number,
                        COALESCE(o.document_file, '') AS doc_file,
                        '' AS payment_proof_file
                    FROM operational_expense_occurrences o
                    JOIN operational_expenses e ON e.id = o.expense_id
                    LEFT JOIN expense_categories c ON c.id = e.category_id
                    LEFT JOIN bank_accounts ba ON ba.id = COALESCE(o.bank_account_id, e.bank_account_id)
                    WHERE o.status <> 'Anulado'
                """
                cur.execute(query_expenses)
                for row in cur.fetchall():
                    total = float(row["total_amount"] or 0.0)
                    st = row["status"] or "Proyectado"
                    pay_status = "Pagada" if st == "Pagado" else ("Pendiente" if st in ("Proyectado", "Pendiente") else st)
                    paid_amt = float(row["payment_amount"] or total) if pay_status == "Pagada" else 0.0
                    pending_amt = max(0.0, total - paid_amt) if pay_status != "Pagada" else 0.0

                    records.append({
                        "id": row["occurrence_id"],
                        "origin_type": "Gasto Operacional",
                        "origin_code": "gasto",
                        "doc_date": row["doc_date"] or "",
                        "due_date": row["due_date"] or "",
                        "doc_number": row["doc_number"] or "",
                        "invoice_number": row["invoice_number"] or "",
                        "doc_file": row["doc_file"] or "",
                        "party_name": row["party_name"] or "",
                        "party_rut": "",
                        "category_name": row["category_name"] or "Operacional",
                        "description": row["description"] or "",
                        "oc_number": "",
                        "purchase_order_id": None,
                        "inventory_entry_id": None,
                        "entry_order_number": "",
                        "neto": total,
                        "iva": 0.0,
                        "total": total,
                        "paid_amount": paid_amt,
                        "pending_amount": pending_amt,
                        "payment_status": pay_status,
                        "payment_date": row["payment_date"] or "",
                        "payment_method": row["payment_method"] or "",
                        "bank_name": row["bank_name"] or "",
                        "bank_account_number": row["bank_account_number"] or "",
                        "expense_name": row.get("expense_name") or "",
                        "expense_id": row["expense_id"],
                    })

            # 3. Cuotas de Deudas Financieras (si doc_type in ('all', 'deuda'))
            if doc_type in ("all", "deuda", "", None):
                query_debts = """
                    SELECT
                        di.id AS installment_id,
                        d.id AS debt_id,
                        'Cuota Financiera' AS doc_type,
                        'deuda' AS doc_type_code,
                        TO_CHAR(d.start_date, 'YYYY-MM-DD') AS doc_date,
                        TO_CHAR(di.due_date, 'YYYY-MM-DD') AS due_date,
                        'DEU-' || LPAD(d.id::text, 4, '0') || ' C' || di.installment_number::text AS doc_number,
                        d.name AS debt_name,
                        d.creditor_name AS party_name,
                        COALESCE(d.creditor_rut, '') AS party_rut,
                        dt.name AS category_name,
                        COALESCE(di.notes, d.name) AS description,
                        COALESCE(d.contract_number, '') AS oc_number,
                        NULL::integer AS purchase_order_id,
                        NULL::integer AS inventory_entry_id,
                        '' AS entry_order_number,
                        di.total_amount,
                        di.paid_amount,
                        di.balance,
                        di.status AS status,
                        TO_CHAR(di.paid_date, 'YYYY-MM-DD') AS payment_date,
                        'Transferencia' AS payment_method,
                        COALESCE(ba.bank_name, '') AS bank_name,
                        COALESCE(ba.account_number, '') AS bank_account_number
                    FROM debt_installments di
                    JOIN debts d ON di.debt_id = d.id
                    JOIN debt_types dt ON d.debt_type_id = dt.id
                    LEFT JOIN bank_accounts ba ON d.bank_account_id = ba.id
                    WHERE di.status <> 'ANULADA'
                """
                cur.execute(query_debts)
                for row in cur.fetchall():
                    tot = float(row["total_amount"] or 0.0)
                    paid = float(row["paid_amount"] or 0.0)
                    bal = float(row["balance"] or 0.0)
                    st = row["status"]
                    # Mapear estados a convención Cuentas por Pagar
                    if st == "PAGADA":
                        pay_st = "Pagada"
                    elif st == "VENCIDA":
                        pay_st = "Vencida"
                    else:
                        pay_st = "Pendiente"

                    records.append({
                        "id": row["installment_id"],
                        "origin_type": "Cuota Financiera",
                        "origin_code": "deuda",
                        "doc_date": row["doc_date"] or "",
                        "due_date": row["due_date"] or "",
                        "doc_number": row["doc_number"] or "",
                        "party_name": row["party_name"] or "",
                        "party_rut": row["party_rut"] or "",
                        "category_name": row["category_name"] or "Deuda Financiera",
                        "description": row["description"] or "",
                        "oc_number": row["oc_number"] or "",
                        "purchase_order_id": None,
                        "inventory_entry_id": None,
                        "entry_order_number": "",
                        "neto": tot,
                        "iva": 0.0,
                        "total": tot,
                        "paid_amount": paid,
                        "pending_amount": bal,
                        "payment_status": pay_st,
                        "payment_date": row["payment_date"] or "",
                        "payment_method": row["payment_method"] or "",
                        "bank_name": row["bank_name"] or "",
                        "bank_account_number": row["bank_account_number"] or "",
                        "debt_name": row["debt_name"],
                        "debt_id": row["debt_id"],
                    })

    # Filtrado en memoria estructurado y consistente
    filtered = []
    for r in records:
        # Filtro de Fechas (por doc_date)
        if date_from and r["doc_date"] and r["doc_date"] < date_from:
            continue
        if date_to and r["doc_date"] and r["doc_date"] > date_to:
            continue

        # Filtro Tipo de Documento
        if doc_type and doc_type not in ("all", ""):
            if doc_type == "factura" and r["origin_code"] != "factura":
                continue
            if doc_type == "gasto" and r["origin_code"] != "gasto":
                continue

        # Filtro Proveedor / Beneficiario
        if supplier_beneficiary and supplier_beneficiary.strip():
            sb_clean = supplier_beneficiary.strip().lower()
            if sb_clean not in r["party_name"].lower() and sb_clean not in r["party_rut"].lower() and sb_clean not in r.get("expense_name", "").lower():
                continue

        # Filtro Categoría
        if category and category.strip() and category != "all":
            if category.strip().lower() != r["category_name"].lower():
                continue

        # Filtro Estado de Pago
        if payment_status and payment_status not in ("all", ""):
            ps_clean = payment_status.strip().lower()
            if ps_clean == "pendiente" and r["payment_status"].lower() not in ("pendiente", "proyectado"):
                continue
            elif ps_clean == "pagada" and r["payment_status"].lower() not in ("pagada", "pagado"):
                continue
            elif ps_clean == "vencida" and r["payment_status"].lower() != "vencida":
                continue
            elif ps_clean not in ("pendiente", "pagada", "vencida") and ps_clean != r["payment_status"].lower():
                continue

        # Búsqueda general: doc_number, party_name, party_rut, description, oc_number, expense_name
        if search and search.strip():
            q = search.strip().lower()
            match = (
                q in r["doc_number"].lower() or
                q in r["party_name"].lower() or
                q in r["party_rut"].lower() or
                q in r["description"].lower() or
                q in r["oc_number"].lower() or
                q in r.get("expense_name", "").lower()
            )
            if not match:
                continue

        filtered.append(r)

    # Ordenamiento seguro (Whitelist)
    sort_key_map = {
        "date": lambda x: (x["doc_date"] or "", x["id"]),
        "due_date": lambda x: (x["due_date"] or "", x["id"]),
        "doc_number": lambda x: (x["doc_number"] or "", x["id"]),
        "origin": lambda x: (x["origin_type"], x["id"]),
        "supplier": lambda x: (x["party_name"].lower(), x["id"]),
        "category": lambda x: (x["category_name"].lower(), x["id"]),
        "neto": lambda x: (x["neto"], x["id"]),
        "iva": lambda x: (x["iva"], x["id"]),
        "total": lambda x: (x["total"], x["id"]),
        "payment_status": lambda x: (x["payment_status"], x["id"]),
    }
    sort_fn = sort_key_map.get(sort_by, sort_key_map["date"])
    reverse = (sort_order or "desc").lower() == "desc"
    filtered.sort(key=sort_fn, reverse=reverse)

    # KPIs sobre el conjunto filtrado completo
    total_docs = len(filtered)
    total_neto = round(sum(r["neto"] for r in filtered), 2)
    total_iva = round(sum(r["iva"] for r in filtered), 2)
    total_general = round(sum(r["total"] for r in filtered), 2)
    total_pendiente = round(sum(r["pending_amount"] for r in filtered), 2)
    total_pagado = round(sum(r["paid_amount"] for r in filtered), 2)

    # Paginación server-side
    if per_page is not None:
        total_pages = max(1, math.ceil(total_docs / per_page)) if total_docs > 0 else 1
        if page > total_pages:
            page = total_pages
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paged_items = filtered[start_idx:end_idx]
    else:
        page = 1
        per_page = total_docs
        total_pages = 1
        paged_items = filtered

    return {
        "items": paged_items,
        "all_filtered_items": filtered,
        "metrics": {
            "total_documentos": total_docs,
            "total_neto": total_neto,
            "total_iva": total_iva,
            "total_general": total_general,
            "total_pendiente": total_pendiente,
            "total_pagado": total_pagado,
        },
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "total": total_docs,
        "filters": {
            "date_from": date_from or "",
            "date_to": date_to or "",
            "doc_type": doc_type or "all",
            "supplier_beneficiary": supplier_beneficiary or "",
            "category": category or "",
            "payment_status": payment_status or "all",
            "search": search or "",
            "sort_by": sort_by or "date",
            "sort_order": sort_order or "desc",
        },
    }


def get_accounts_payable_report_data(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    due_date_from: Optional[str] = None,
    due_date_to: Optional[str] = None,
    doc_type: Optional[str] = "all",
    supplier_beneficiary: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = "all",
    search: Optional[str] = None,
    page: Optional[int] = 1,
    per_page: Optional[int] = 25,
    sort_by: Optional[str] = "due_date",
    sort_order: Optional[str] = "asc",
) -> dict:
    """
    Reporte Operacional Financiero: CUENTAS POR PAGAR.
    Muestra exclusivamente obligaciones vigentes con SALDO PENDIENTE > 0.
    Orden por defecto: Fecha Vencimiento ASC (las más urgentes primero).
    KPIs calculados sobre SALDO PENDIENTE:
    - Total Por Pagar (saldo total pendiente)
    - Total Vencido (saldo con due_date < hoy)
    - Vence en próximos 7 días (0 <= dias_vencimiento <= 7)
    - Vence en próximos 30 días (0 <= dias_vencimiento <= 30)
    """
    today_date = datetime.now().date()
    today_str = today_date.isoformat()

    # Primero traer todos los registros mediante la fuente consolidada sin paginar
    base_report = get_purchases_and_expenses_report_data(
        date_from=date_from,
        date_to=date_to,
        doc_type=doc_type,
        supplier_beneficiary=supplier_beneficiary,
        category=category,
        payment_status="all",
        search=search,
        page=1,
        per_page=None,
        sort_by="due_date",
        sort_order="asc",
    )

    all_items = base_report["all_filtered_items"]
    payable_items = []

    for it in all_items:
        # REGLA FUNDAMENTAL: Saldo pendiente > 0
        pending_amount = round(it["pending_amount"], 2)
        if pending_amount <= 0:
            continue

        # Si ya está marcada como Pagada en el sistema, no es cuenta por pagar activa
        if it["payment_status"].lower() in ("pagada", "pagado"):
            continue

        due_date_str = it["due_date"]
        dias_vencimiento = None
        due_badge_type = "normal"  # normal, proxima, vence_hoy, vencida

        if due_date_str:
            try:
                due_d = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                dias_vencimiento = (due_d - today_date).days
                if dias_vencimiento < 0:
                    due_badge_type = "vencida"
                elif dias_vencimiento == 0:
                    due_badge_type = "vence_hoy"
                elif 0 < dias_vencimiento <= 7:
                    due_badge_type = "proxima_7"
                elif 7 < dias_vencimiento <= 30:
                    due_badge_type = "proxima_30"
            except Exception:
                dias_vencimiento = None

        # Clasificación de Estado Operacional Dinámico
        paid_amt = round(it["paid_amount"], 2)
        total_amt = round(it["total"], 2)

        if dias_vencimiento is not None and dias_vencimiento < 0:
            computed_status = "Vencida"
        elif paid_amt > 0 and pending_amount > 0:
            computed_status = "Parcial"
        else:
            computed_status = "Pendiente"

        # Filtro de fecha de vencimiento específica
        if due_date_from and due_date_str and due_date_str < due_date_from:
            continue
        if due_date_to and due_date_str and due_date_str > due_date_to:
            continue

        # Filtro de Estado Cuentas por Pagar ('Pendiente', 'Parcial', 'Vencida')
        if status and status not in ("all", ""):
            st_clean = status.strip().lower()
            if st_clean != computed_status.lower():
                continue

        payable_record = dict(it)
        payable_record.update({
            "computed_status": computed_status,
            "dias_vencimiento": dias_vencimiento,
            "due_badge_type": due_badge_type,
        })
        payable_items.append(payable_record)

    # Ordenamiento
    sort_key_map = {
        "due_date": lambda x: (x["due_date"] == "", x["due_date"] or "9999-99-99", x["id"]),
        "date": lambda x: (x["doc_date"] or "", x["id"]),
        "doc_number": lambda x: (x["doc_number"] or "", x["id"]),
        "supplier": lambda x: (x["party_name"].lower(), x["id"]),
        "total": lambda x: (x["total"], x["id"]),
        "paid": lambda x: (x["paid_amount"], x["id"]),
        "pending": lambda x: (x["pending_amount"], x["id"]),
        "days": lambda x: (x["dias_vencimiento"] if x["dias_vencimiento"] is not None else 9999, x["id"]),
        "status": lambda x: (x["computed_status"], x["id"]),
    }
    sort_fn = sort_key_map.get(sort_by, sort_key_map["due_date"])
    reverse = (sort_order or "asc").lower() == "desc"
    payable_items.sort(key=sort_fn, reverse=reverse)

    # KPIs calculados ESTRICTAMENTE sobre SALDO PENDIENTE
    total_por_pagar = round(sum(p["pending_amount"] for p in payable_items), 2)
    total_vencido = round(
        sum(p["pending_amount"] for p in payable_items if p["dias_vencimiento"] is not None and p["dias_vencimiento"] < 0),
        2
    )
    vence_7_dias = round(
        sum(p["pending_amount"] for p in payable_items if p["dias_vencimiento"] is not None and 0 <= p["dias_vencimiento"] <= 7),
        2
    )
    vence_30_dias = round(
        sum(p["pending_amount"] for p in payable_items if p["dias_vencimiento"] is not None and 0 <= p["dias_vencimiento"] <= 30),
        2
    )

    total_records = len(payable_items)

    # Paginación
    try:
        page = int(page) if page is not None else 1
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    if per_page is not None:
        try:
            per_page = int(per_page)
            if per_page not in (25, 50, 100):
                per_page = 25
        except (ValueError, TypeError):
            per_page = 25
        total_pages = max(1, math.ceil(total_records / per_page)) if total_records > 0 else 1
        if page > total_pages:
            page = total_pages
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paged_items = payable_items[start_idx:end_idx]
    else:
        page = 1
        per_page = total_records
        total_pages = 1
        paged_items = payable_items

    return {
        "items": paged_items,
        "all_filtered_items": payable_items,
        "metrics": {
            "total_por_pagar": total_por_pagar,
            "total_vencido": total_vencido,
            "vence_7_dias": vence_7_dias,
            "vence_30_dias": vence_30_dias,
            "count_obligaciones": total_records,
        },
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "total": total_records,
        "filters": {
            "date_from": date_from or "",
            "date_to": date_to or "",
            "due_date_from": due_date_from or "",
            "due_date_to": due_date_to or "",
            "doc_type": doc_type or "all",
            "supplier_beneficiary": supplier_beneficiary or "",
            "category": category or "",
            "status": status or "all",
            "search": search or "",
            "sort_by": sort_by or "due_date",
            "sort_order": sort_order or "asc",
        },
    }


def get_accounts_receivable_report_data(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    due_date_from: Optional[str] = None,
    due_date_to: Optional[str] = None,
    customer: Optional[str] = None,
    payment_status: Optional[str] = "all",
    sale_status: Optional[str] = "all",
    quick_filter: Optional[str] = "all",
    filter_gestion: Optional[str] = "all",
    filter_antiguedad_gestion: Optional[str] = "all",
    filter_tipo_gestion: Optional[str] = "all",
    search: Optional[str] = None,
    page: Optional[int] = 1,
    per_page: Optional[int] = 25,
    sort_by: Optional[str] = "due_date",
    sort_order: Optional[str] = "asc",
) -> dict:
    """
    Reporte Operacional Financiero: CUENTAS POR COBRAR.
    Muestra exclusivamente ventas no canceladas con SALDO PENDIENTE > 0.
    
    Criterios fundamentales:
    - Saldo Pendiente = max(0.0, total_amount - pagos_aplicados).
    - Excluye ventas canceladas ('Cancelada', 'Cancelado') y cotizaciones ('Cotización', 'COT-%').
    - Si payment_status == 'Pagado' o Saldo == 0, se excluye del listado activo.
    - Soporta múltiples pagos parciales por venta agrupando atómicamente (sin duplicar filas).
    - Orden por defecto: Fecha Vencimiento ASC (más urgentes primero).
    - KPIs calculados ESTRICTAMENTE sobre SALDO PENDIENTE.
    """
    today_date = datetime.now().date()
    today_str = today_date.isoformat()

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Obtenemos las ventas con sus pagos asociados agrupados
            query = """
                SELECT 
                    s.id,
                    s.sale_number,
                    s.customer_name,
                    s.customer_email,
                    s.customer_initials,
                    s.sale_date,
                    s.sale_time,
                    s.total_amount,
                    s.status AS sale_status,
                    s.seller_name,
                    s.payment_method,
                    s.payment_status,
                    s.delivery_status,
                    s.notes,
                    sp.invoice_number,
                    sp.invoice_due_date,
                    sp.payment_date AS header_payment_date,
                    sp.payment_amount AS header_payment_amount,
                    sp.payment_proof_file AS header_payment_proof,
                    COALESCE(spi_agg.total_paid_items, 0.0) AS items_paid_amount,
                    spi_agg.last_payment_date,
                    spi_agg.payment_items_count,
                    ca_last.last_action_type,
                    ca_last.last_action_date,
                    ca_last.last_action_time,
                    ca_last.last_action_contact,
                    ca_last.last_action_result,
                    ca_last.last_next_action,
                    ca_last.last_next_action_date,
                    ca_last.last_commitment_date,
                    ca_last.last_commitment_amount,
                    ca_last.last_action_user,
                    COALESCE(ca_last.total_actions_count, 0) AS collection_actions_count
                FROM sales s
                LEFT JOIN sale_payments sp ON sp.sale_id = s.id
                LEFT JOIN (
                    SELECT 
                        sale_id,
                        SUM(payment_amount) AS total_paid_items,
                        MAX(payment_date) AS last_payment_date,
                        COUNT(id) AS payment_items_count
                    FROM sale_payment_items
                    WHERE COALESCE(accounting_approved, 1) = 1
                    GROUP BY sale_id
                ) spi_agg ON spi_agg.sale_id = s.id
                LEFT JOIN (
                    SELECT DISTINCT ON (sale_id)
                        sale_id,
                        action_type AS last_action_type,
                        action_date AS last_action_date,
                        action_time AS last_action_time,
                        contact_name AS last_action_contact,
                        result AS last_action_result,
                        next_action AS last_next_action,
                        next_action_date AS last_next_action_date,
                        payment_commitment_date AS last_commitment_date,
                        payment_commitment_amount AS last_commitment_amount,
                        user_name AS last_action_user,
                        COUNT(id) OVER (PARTITION BY sale_id) AS total_actions_count
                    FROM collection_actions
                    ORDER BY sale_id, action_date DESC, action_time DESC, id DESC
                ) ca_last ON ca_last.sale_id = s.id
                WHERE s.status NOT IN ('Cancelada', 'Cancelado', 'Cotización')
                  AND s.sale_number NOT LIKE 'COT-%%'
            """
            cur.execute(query)
            rows = cur.fetchall()

            # 2. Cargar mapa de clientes para enriquecimiento de RUT, teléfono y dirección
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

            # 3. Procesar y clasificar cada venta
            receivable_items = []

            for r in rows:
                raw_p_status = (r.get("payment_status") or "").strip()
                if raw_p_status.lower() in ("pagado", "pagada"):
                    continue

                total_amount = round(float(r.get("total_amount") or 0.0), 2)
                
                # Monto pagado: si hay items individuales se prioriza la suma de items, de lo contrario el header
                items_paid = round(float(r.get("items_paid_amount") or 0.0), 2)
                header_paid = round(float(r.get("header_payment_amount") or 0.0), 2)
                paid_amount = items_paid if items_paid > 0 else header_paid
                paid_amount = round(min(paid_amount, total_amount), 2)

                pending_amount = round(max(0.0, total_amount - paid_amount), 2)

                # REGLA FUNDAMENTAL: Saldo por cobrar > 0
                if pending_amount <= 0:
                    continue

                # Fecha de vencimiento: invoice_due_date si es válida, o sale_date en su defecto
                due_date_str = r.get("invoice_due_date")
                if not due_date_str or due_date_str in ("-", ""):
                    due_date_str = r.get("sale_date") or ""

                dias_vencimiento = None
                due_badge_type = "normal"

                if due_date_str:
                    try:
                        due_d = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                        dias_vencimiento = (due_d - today_date).days
                        if dias_vencimiento < 0:
                            due_badge_type = "vencida"
                        elif dias_vencimiento == 0:
                            due_badge_type = "vence_hoy"
                        elif 0 < dias_vencimiento <= 7:
                            due_badge_type = "proxima_7"
                        elif 7 < dias_vencimiento <= 30:
                            due_badge_type = "proxima_30"
                    except Exception:
                        dias_vencimiento = None

                # Clasificación de Estado Financiero Computado
                if dias_vencimiento is not None and dias_vencimiento < 0:
                    computed_status = "Vencida"
                elif paid_amount > 0 and pending_amount > 0:
                    computed_status = "Parcial"
                else:
                    computed_status = "Pendiente"

                # Enriquecimiento de datos del cliente
                c_email = (r.get("customer_email") or "").lower().strip()
                c_name = (r.get("customer_name") or "").lower().strip()
                c_data = clients_map.get(c_email) or clients_map.get(c_name) or {}

                notes_str = r.get("notes") or ""
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
                rut_formatted = f"{rut_val}-{dv_val}" if rut_val and dv_val else rut_val

                # Documento asignado
                doc_number = r.get("invoice_number") or ""
                if not doc_number:
                    if "Doc: Factura" in notes_str:
                        doc_number = f"FACT-{r['id']:05d}"
                    elif "Doc: Boleta" in notes_str:
                        doc_number = f"BOL-{r['id']:05d}"
                    else:
                        doc_number = f"DOC-{r['id']:05d}"

                last_payment_date = r.get("last_payment_date") or r.get("header_payment_date") or ""

                # --- Gestión y Seguimiento de Cobranza ---
                last_action_type = r.get("last_action_type") or ""
                last_action_date = r.get("last_action_date") or ""
                last_action_time = r.get("last_action_time") or ""
                last_action_contact = r.get("last_action_contact") or ""
                last_action_result = r.get("last_action_result") or ""
                last_next_action = r.get("last_next_action") or ""
                last_next_action_date = r.get("last_next_action_date") or ""
                last_commitment_date = r.get("last_commitment_date") or ""
                last_commitment_amount = float(r.get("last_commitment_amount") or 0.0) if r.get("last_commitment_amount") is not None else None
                last_action_user = r.get("last_action_user") or ""
                total_actions_count = int(r.get("collection_actions_count") or 0)

                dias_sin_gestion = None
                gestion_badge_type = "sin_gestion"

                if last_action_date:
                    try:
                        act_d = datetime.strptime(last_action_date, "%Y-%m-%d").date()
                        dias_sin_gestion = (today_date - act_d).days
                        if dias_sin_gestion <= 3:
                            gestion_badge_type = "reciente"
                        elif dias_sin_gestion <= 7:
                            gestion_badge_type = "normal"
                        elif dias_sin_gestion <= 15:
                            gestion_badge_type = "atencion"
                        else:
                            gestion_badge_type = "critico"
                    except Exception:
                        dias_sin_gestion = None
                        gestion_badge_type = "normal"
                else:
                    gestion_badge_type = "sin_gestion"

                proxima_gestion_atrasada = False
                if last_next_action_date:
                    try:
                        nxt_d = datetime.strptime(last_next_action_date, "%Y-%m-%d").date()
                        if nxt_d < today_date:
                            proxima_gestion_atrasada = True
                    except Exception:
                        pass

                item = {
                    "id": r["id"],
                    "sale_number": r["sale_number"],
                    "customer_name": r["customer_name"],
                    "customer_rut": rut_formatted,
                    "customer_email": r.get("customer_email") or "",
                    "customer_phone": c_data.get("phone") or "",
                    "sale_date": r["sale_date"] or "",
                    "due_date": due_date_str,
                    "dias_vencimiento": dias_vencimiento,
                    "due_badge_type": due_badge_type,
                    "doc_number": doc_number,
                    "payment_method": r.get("payment_method") or "Efectivo",
                    "sale_status": r["sale_status"],
                    "delivery_status": r.get("delivery_status") or "Pendiente",
                    "computed_status": computed_status,
                    "total_amount": total_amount,
                    "paid_amount": paid_amount,
                    "pending_amount": pending_amount,
                    "last_payment_date": last_payment_date,
                    "payment_items_count": r.get("payment_items_count") or (1 if paid_amount > 0 else 0),
                    "notes": notes_str,
                    # Campos de Gestión de Cobranza
                    "last_action_type": last_action_type,
                    "last_action_date": last_action_date,
                    "last_action_time": last_action_time,
                    "last_action_contact": last_action_contact,
                    "last_action_result": last_action_result,
                    "last_next_action": last_next_action,
                    "last_next_action_date": last_next_action_date,
                    "last_commitment_date": last_commitment_date,
                    "last_commitment_amount": last_commitment_amount,
                    "last_action_user": last_action_user,
                    "total_actions_count": total_actions_count,
                    "dias_sin_gestion": dias_sin_gestion,
                    "gestion_badge_type": gestion_badge_type,
                    "proxima_gestion_atrasada": proxima_gestion_atrasada,
                }

                # 4. APLICACIÓN DE FILTROS

                # Filtro Fecha Venta Desde / Hasta
                if date_from and item["sale_date"] and item["sale_date"] < date_from:
                    continue
                if date_to and item["sale_date"] and item["sale_date"] > date_to:
                    continue

                # Filtro Fecha Vencimiento Desde / Hasta
                if due_date_from and item["due_date"] and item["due_date"] < due_date_from:
                    continue
                if due_date_to and item["due_date"] and item["due_date"] > due_date_to:
                    continue

                # Filtro Cliente
                if customer and customer.strip():
                    c_filter = customer.strip().lower()
                    if c_filter not in item["customer_name"].lower() and c_filter not in item["customer_rut"].lower():
                        continue

                # Filtro Estado de Pago ('Pendiente', 'Parcial', 'Vencida')
                if payment_status and payment_status not in ("all", ""):
                    if payment_status.strip().lower() != item["computed_status"].lower():
                        continue

                # Filtro Estado de Venta / Logístico
                if sale_status and sale_status not in ("all", ""):
                    if sale_status.strip().lower() != item["sale_status"].lower():
                        continue

                # Filtro Rápido de Cobranza ('vencidas', 'hoy', 'proximas_7', 'proximas_30')
                if quick_filter and quick_filter not in ("all", ""):
                    qf = quick_filter.strip().lower()
                    if qf == "vencidas":
                        if item["dias_vencimiento"] is None or item["dias_vencimiento"] >= 0:
                            continue
                    elif qf == "hoy":
                        if item["dias_vencimiento"] != 0:
                            continue
                    elif qf == "proximas_7":
                        if item["dias_vencimiento"] is None or not (0 <= item["dias_vencimiento"] <= 7):
                            continue
                    elif qf == "proximas_30":
                        if item["dias_vencimiento"] is None or not (0 <= item["dias_vencimiento"] <= 30):
                            continue

                # Filtro Por Gestión ('con_gestion', 'sin_gestion')
                if filter_gestion and filter_gestion not in ("all", ""):
                    fg = filter_gestion.strip().lower()
                    if fg == "con_gestion" and not item["last_action_date"]:
                        continue
                    elif fg == "sin_gestion" and item["last_action_date"]:
                        continue

                # Filtro Antigüedad de Gestión ('hoy', 'ultimos_7', 'mas_7', 'mas_15', 'mas_30')
                if filter_antiguedad_gestion and filter_antiguedad_gestion not in ("all", ""):
                    fag = filter_antiguedad_gestion.strip().lower()
                    dsg = item["dias_sin_gestion"]
                    if dsg is None:
                        # Si no tiene gestión, se excluye de estos filtros específicos de antigüedad
                        continue
                    if fag == "hoy" and dsg != 0:
                        continue
                    elif fag == "ultimos_7" and not (0 <= dsg <= 7):
                        continue
                    elif fag == "mas_7" and dsg <= 7:
                        continue
                    elif fag == "mas_15" and dsg <= 15:
                        continue
                    elif fag == "mas_30" and dsg <= 30:
                        continue

                # Filtro Tipo de Última Gestión
                if filter_tipo_gestion and filter_tipo_gestion not in ("all", ""):
                    if filter_tipo_gestion.strip().lower() != (item["last_action_type"] or "").strip().lower():
                        continue

                # Búsqueda por texto (número de venta, documento, cliente, RUT, notas)
                if search and search.strip():
                    term = search.strip().lower()
                    matches = (
                        term in item["sale_number"].lower()
                        or term in item["doc_number"].lower()
                        or term in item["customer_name"].lower()
                        or term in item["customer_rut"].lower()
                        or term in item["notes"].lower()
                        or term in (item["last_action_contact"] or "").lower()
                        or term in (item["last_action_result"] or "").lower()
                    )
                    if not matches:
                        continue

                receivable_items.append(item)

    # 5. ORDENAMIENTO (Predeterminado: Fecha Vencimiento ASC)
    sort_key_map = {
        "due_date": lambda x: (x["due_date"] == "", x["due_date"] or "9999-99-99", x["id"]),
        "date": lambda x: (x["sale_date"] or "", x["id"]),
        "sale_number": lambda x: (x["sale_number"] or "", x["id"]),
        "doc_number": lambda x: (x["doc_number"] or "", x["id"]),
        "customer": lambda x: (x["customer_name"].lower(), x["id"]),
        "total": lambda x: (x["total_amount"], x["id"]),
        "paid": lambda x: (x["paid_amount"], x["id"]),
        "pending": lambda x: (x["pending_amount"], x["id"]),
        "days": lambda x: (x["dias_vencimiento"] if x["dias_vencimiento"] is not None else 9999, x["id"]),
        "payment_status": lambda x: (x["computed_status"], x["id"]),
        "sale_status": lambda x: (x["sale_status"], x["id"]),
        "last_action": lambda x: (x["last_action_date"] == "", x["last_action_date"] or "0000-00-00", x["id"]),
        "days_without_action": lambda x: (x["dias_sin_gestion"] is None, x["dias_sin_gestion"] if x["dias_sin_gestion"] is not None else -1, x["id"]),
        "next_action": lambda x: (x["last_next_action_date"] == "", x["last_next_action_date"] or "9999-99-99", x["id"]),
    }
    sort_fn = sort_key_map.get(sort_by, sort_key_map["due_date"])
    reverse = (sort_order or "asc").lower() == "desc"
    receivable_items.sort(key=sort_fn, reverse=reverse)

    # 6. KPIS CALCULADOS ESTRICTAMENTE SOBRE SALDO POR COBRAR
    total_por_cobrar = round(sum(p["pending_amount"] for p in receivable_items), 2)
    total_vencido = round(
        sum(p["pending_amount"] for p in receivable_items if p["dias_vencimiento"] is not None and p["dias_vencimiento"] < 0),
        2
    )
    vence_7_dias = round(
        sum(p["pending_amount"] for p in receivable_items if p["dias_vencimiento"] is not None and 0 <= p["dias_vencimiento"] <= 7),
        2
    )
    vence_30_dias = round(
        sum(p["pending_amount"] for p in receivable_items if p["dias_vencimiento"] is not None and 0 <= p["dias_vencimiento"] <= 30),
        2
    )
    clientes_con_deuda = len({p["customer_name"].strip().lower() for p in receivable_items if p["customer_name"]})
    cuentas_parciales = sum(1 for p in receivable_items if p["paid_amount"] > 0)
    total_records = len(receivable_items)

    # 7. PAGINACIÓN SERVER-SIDE
    try:
        page = int(page) if page is not None else 1
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    if per_page is not None:
        try:
            per_page = int(per_page)
            if per_page <= 0:
                per_page = 25
        except (ValueError, TypeError):
            per_page = 25
        total_pages = max(1, math.ceil(total_records / per_page)) if total_records > 0 else 1
        if page > total_pages:
            page = total_pages
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paged_items = receivable_items[start_idx:end_idx]
    else:
        page = 1
        per_page = total_records
        total_pages = 1
        paged_items = receivable_items

    return {
        "items": paged_items,
        "all_filtered_items": receivable_items,
        "metrics": {
            "total_por_cobrar": total_por_cobrar,
            "total_vencido": total_vencido,
            "vence_7_dias": vence_7_dias,
            "vence_30_dias": vence_30_dias,
            "clientes_con_deuda": clientes_con_deuda,
            "cuentas_parciales": cuentas_parciales,
            "count_cuentas": total_records,
        },
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "total": total_records,
        "filters": {
            "date_from": date_from or "",
            "date_to": date_to or "",
            "due_date_from": due_date_from or "",
            "due_date_to": due_date_to or "",
            "customer": customer or "",
            "payment_status": payment_status or "all",
            "sale_status": sale_status or "all",
            "quick_filter": quick_filter or "all",
            "filter_gestion": filter_gestion or "all",
            "filter_antiguedad_gestion": filter_antiguedad_gestion or "all",
            "filter_tipo_gestion": filter_tipo_gestion or "all",
            "search": search or "",
            "sort_by": sort_by or "due_date",
            "sort_order": sort_order or "asc",
        },
    }
