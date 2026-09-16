"""
repositories/reporting_repo.py
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
                "SELECT COALESCE(SUM(total_amount), 0) as total FROM sales WHERE sale_date = %s AND status NOT IN ('Cancelada', 'Cotización') AND sale_number LIKE 'VTA-%%'",
                (today_str,)
            )
            row_today = cur.fetchone()
            total_today = float(row_today["total"]) if row_today else 0.0

            cur.execute(
                "SELECT COALESCE(SUM(total_amount), 0) as total FROM sales WHERE sale_date = %s AND status NOT IN ('Cancelada', 'Cotización') AND sale_number LIKE 'VTA-%%'",
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

            # 2. Stock total y productos con bajo stock
            cur.execute("SELECT json FROM page_data WHERE key = 'inventory_items'")
            row_inv = cur.fetchone()
            items = []
            if row_inv and row_inv["json"]:
                try:
                    items = json.loads(row_inv["json"])
                except Exception:
                    items = []
            
            total_stock = sum(int(it.get("stock", 0)) for it in items)
            low_stock_count = sum(1 for it in items if int(it.get("stock", 0)) <= int(it.get("min_stock", 10)))
            
            if low_stock_count > 0:
                stock_trend_text = f"{low_stock_count} bajo stock"
                stock_trend_type = "warning"
            else:
                stock_trend_text = "Stock óptimo"
                stock_trend_type = "positive"

            # 3. Órdenes pendientes vs total
            cur.execute(
                "SELECT COUNT(*) as count FROM sales WHERE status = 'Pendiente' AND sale_number LIKE 'VTA-%%'"
            )
            row_pend = cur.fetchone()
            total_pending = int(row_pend["count"]) if row_pend else 0

            cur.execute(
                "SELECT COUNT(*) as count FROM sales WHERE status NOT IN ('Cancelada', 'Cotización') AND sale_number LIKE 'VTA-%%'"
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

            # 4. Clientes activos y compras recientes (últimos 60 días)
            cur.execute(
                "SELECT COUNT(*) as count FROM clients"
            )
            row_cli = cur.fetchone()
            total_customers = int(row_cli["count"]) if row_cli else 0

            since_60d = (now - timedelta(days=60)).strftime('%Y-%m-%d')
            cur.execute(
                "SELECT COUNT(DISTINCT customer_name) as count FROM sales WHERE sale_number LIKE 'VTA-%%' AND sale_date >= %s",
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
                "ventas_completadas": total_orders - total_pending,
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
                    WHERE TO_CHAR(sale_date::date, 'YYYY') = %s AND status NOT IN ('Cancelada', 'Cotización') AND sale_number LIKE 'VTA-%%'
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
                    WHERE status NOT IN ('Cancelada', 'Cotización') AND sale_number LIKE 'VTA-%%'
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
                    WHERE TO_CHAR(sale_date::date, 'YYYY') = %s AND status NOT IN ('Cancelada', 'Cotización') AND sale_number LIKE 'VTA-%%'
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
                    WHERE TO_CHAR(sale_date::date, 'YYYY-MM') = %s AND status NOT IN ('Cancelada', 'Cotización') AND sale_number LIKE 'VTA-%%'
                    """,
                    (current_month,)
                )
                rows = cur.fetchall()
            else:
                cur.execute(
                    """
                    SELECT products_json
                    FROM sales
                    WHERE status NOT IN ('Cancelada', 'Cotización') AND sale_number LIKE 'VTA-%%'
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


def get_purchased_products_matrix(year: int, category: str = None) -> dict:
    """
    Genera la matriz mensual de productos comprados por SKU para un año determinado.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT 
                    p.id as product_id,
                    COALESCE(NULLIF(p.sku, ''), 'SIN-SKU') as sku,
                    p.name as product_name,
                    COALESCE(NULLIF(p.category, ''), 'Sin Categoría') as category,
                    COALESCE(NULLIF(p.unit_of_measure, ''), 'UN') as unit_of_measure,
                    SUBSTRING(po.order_date, 6, 2)::int as month_num,
                    SUM(poi.quantity_ordered) as total_qty,
                    SUM(COALESCE(poi.total_price, poi.quantity_ordered * poi.unit_price, 0)) as total_amount
                FROM purchase_order_items poi
                JOIN purchase_orders po ON poi.purchase_order_id = po.id
                JOIN products p ON poi.product_id = p.id
                WHERE po.status NOT IN ('Cancelada', 'Borrador')
                  AND SUBSTRING(po.order_date, 1, 4)::int = %s
            """
            params = [year]
            if category and category != 'all':
                query += " AND p.category = %s"
                params.append(category)

            query += """
                GROUP BY p.id, p.sku, p.name, p.category, p.unit_of_measure, month_num
                ORDER BY p.name, month_num
            """
            cur.execute(query, tuple(params))
            rows = cur.fetchall()

            # Obtener todas las categorías para filtros
            cur.execute("""
                SELECT DISTINCT COALESCE(NULLIF(p.category, ''), 'Sin Categoría') as cat
                FROM purchase_order_items poi
                JOIN purchase_orders po ON poi.purchase_order_id = po.id
                JOIN products p ON poi.product_id = p.id
                WHERE po.status NOT IN ('Cancelada', 'Borrador')
                  AND SUBSTRING(po.order_date, 1, 4)::int = %s
                ORDER BY cat
            """, (year,))
            categories = [r['cat'] for r in cur.fetchall() if r['cat']]

    # Estructurar la matriz
    products_map = {}
    monthly_totals = {m: 0 for m in range(1, 13)}
    monthly_amounts = {m: 0.0 for m in range(1, 13)}

    for row in rows:
        pid = row['product_id']
        m = row['month_num']
        qty = int(row['total_qty'] or 0)
        amt = float(row['total_amount'] or 0.0)

        if pid not in products_map:
            products_map[pid] = {
                'product_id': pid,
                'sku': row['sku'],
                'product_name': row['product_name'],
                'category': row['category'],
                'unit_of_measure': row['unit_of_measure'],
                'months': {i: 0 for i in range(1, 13)},
                'total_qty': 0,
                'total_amount': 0.0
            }

        products_map[pid]['months'][m] += qty
        products_map[pid]['total_qty'] += qty
        products_map[pid]['total_amount'] += amt

        if 1 <= m <= 12:
            monthly_totals[m] += qty
            monthly_amounts[m] += amt

    products_list = sorted(products_map.values(), key=lambda x: x['total_qty'], reverse=True)
    grand_total_qty = sum(monthly_totals.values())
    grand_total_amount = sum(monthly_amounts.values())

    month_names = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
        5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
        9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }

    top_month_num = max(monthly_totals, key=monthly_totals.get) if grand_total_qty > 0 else None
    top_month = f"{month_names[top_month_num]} ({monthly_totals[top_month_num]:,} u)" if top_month_num and monthly_totals[top_month_num] > 0 else "—"
    top_product = f"{products_list[0]['sku']} - {products_list[0]['product_name']} ({products_list[0]['total_qty']:,} u)" if products_list else "—"

    return {
        'year': year,
        'products': products_list,
        'monthly_totals': monthly_totals,
        'monthly_amounts': monthly_amounts,
        'grand_total_qty': grand_total_qty,
        'grand_total_amount': grand_total_amount,
        'categories': categories,
        'top_product': top_product,
        'top_month': top_month,
        'total_skus': len(products_list)
    }


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

            # Facturas de proveedores por pagar (futuros compromisos)
            cur.execute("""
                SELECT SUBSTRING(COALESCE(due_date, invoice_date, created_at), 1, 7) AS mes_vence,
                       SUM(invoice_amount) AS total
                FROM purchase_invoices
                WHERE payment_status IN ('Pendiente', 'Vencida')
                GROUP BY mes_vence
            """)
            gastos_por_pagar_mes = {row['mes_vence']: float(row['total'] or 0) for row in cur.fetchall()}

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
            gas  = avg_gas + gas_comp # tendencia + facturas proveedores por pagar
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
            gas      = avg_gas + gas_comp
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
            cur.execute("SELECT json FROM page_data WHERE key = 'inventory_items'")
            row = cur.fetchone()
            if row and row['json']:
                try:
                    items = json.loads(row['json'])
                    for it in items:
                        stk = int(it.get('stock', 0))
                        min_stk = int(it.get('min_stock', 10))
                        if stk <= min_stk:
                            notifications.append({
                                'id': f"stock-{it.get('code')}",
                                'type': 'warning',
                                'icon': 'fa-solid fa-boxes-stacked',
                                'title': f"Stock Bajo: {it.get('name', 'Insumo')}",
                                'desc': f"Quedan {stk} unidades (mínimo requerido: {min_stk})",
                                'link': '/inventario',
                                'time': 'Bodega'
                            })
                except Exception:
                    pass

    # 3. Ventas pendientes por gestionar
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM sales WHERE status = 'Pendiente' AND sale_number LIKE 'VTA-%%'")
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

