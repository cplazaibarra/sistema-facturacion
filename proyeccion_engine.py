"""
Motor de Proyección de Ventas.
Calcula estadísticas reales y proyecciones basadas en datos históricos de la BD.
"""
import json
import calendar
from datetime import datetime, timedelta, date
from db import get_connection


def _parse_date(date_str):
    if not date_str:
        return None
    s = str(date_str).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt).date()
        except ValueError:
            pass
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            pass
    return None


def _days_in_month(year, month):
    return calendar.monthrange(year, month)[1]


def _last_n_months(ref_date, n):
    months = []
    d = ref_date.replace(day=1)
    for _ in range(n):
        months.append(d.strftime('%Y-%m'))
        d = (d - timedelta(days=1)).replace(day=1)
    return list(reversed(months))


def _next_n_months(ref_date, n):
    months = []
    d = ref_date.replace(day=1)
    for _ in range(n):
        if d.month == 12:
            d = d.replace(year=d.year + 1, month=1)
        else:
            d = d.replace(month=d.month + 1)
        months.append(d.strftime('%Y-%m'))
    return months


def _month_label(month_str):
    MONTHS_ES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    try:
        y, m = month_str.split('-')
        return MONTHS_ES[int(m) - 1] + f" '{y[2:]}"
    except Exception:
        return month_str


def get_sales_by_month():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT SUBSTRING(sale_date, 1, 7) AS mes, SUM(total_amount) AS total
                FROM sales
                WHERE total_amount IS NOT NULL
                GROUP BY mes
                ORDER BY mes
            """)
            return {row['mes']: float(row['total'] or 0) for row in cur.fetchall()}


def get_all_sales_with_products():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT sale_date, total_amount, products_json FROM sales ORDER BY sale_date")
            rows = [dict(r) for r in cur.fetchall()]

    result = []
    for row in rows:
        d = _parse_date(row['sale_date'])
        if d is None:
            continue
        try:
            raw = json.loads(row['products_json']) if row['products_json'] else []
            # Filtrar solo elementos que sean dicts (ignorar strings sueltos)
            items = [it for it in raw if isinstance(it, dict)]
        except Exception:
            items = []
        result.append({'date': d, 'total': float(row['total_amount'] or 0), 'items': items})
    return result


def compute_proyeccion():
    today = date.today()
    current_month_str = today.strftime('%Y-%m')
    prev_month_date = (today.replace(day=1) - timedelta(days=1))
    prev_month_str = prev_month_date.strftime('%Y-%m')

    sales_by_month = get_sales_by_month()
    all_sales = get_all_sales_with_products()

    # ── Mes actual vs anterior ────────────────────────────────────────────────
    current_month_real = sales_by_month.get(current_month_str, 0.0)
    prev_month_real = sales_by_month.get(prev_month_str, 0.0)

    days_in_month = _days_in_month(today.year, today.month)
    days_elapsed = today.day
    daily_rate = (current_month_real / days_elapsed) if days_elapsed > 0 and current_month_real > 0 else 0
    projected_current_month = daily_rate * days_in_month if daily_rate > 0 else current_month_real

    if prev_month_real > 0:
        change_vs_prev = ((projected_current_month - prev_month_real) / prev_month_real) * 100
        change_label = f"{'+' if change_vs_prev >= 0 else ''}{change_vs_prev:.1f}% vs mes anterior"
    else:
        change_vs_prev = None
        change_label = "Sin datos mes anterior"

    # ── Tendencia trimestral ──────────────────────────────────────────────────
    months_history = _last_n_months(today, 4)[:-1]  # 3 meses previos
    q3_total = sum(sales_by_month.get(m, 0) for m in months_history)
    prev_q_months = _last_n_months(today, 7)[:-4] if today.month > 3 else []
    prev_q_total = sum(sales_by_month.get(m, 0) for m in prev_q_months)
    if prev_q_total > 0:
        q_growth = ((q3_total - prev_q_total) / prev_q_total) * 100
        q_label = f"{'+' if q_growth >= 0 else ''}{q_growth:.1f}% crecimiento"
    else:
        q_label = "Primer trimestre con datos"

    # ── Proyección anual ──────────────────────────────────────────────────────
    year_str = str(today.year)
    year_so_far = sum(v for k, v in sales_by_month.items() if k.startswith(year_str))
    annual_projection = (year_so_far / today.month) * 12 if today.month > 0 else year_so_far
    progress_pct = (year_so_far / annual_projection * 100) if annual_projection > 0 else 0

    # ── Tasa de crecimiento mensual promedio ─────────────────────────────────
    chart_months = _last_n_months(today, 6)
    monthly_rates = []
    for i in range(1, len(chart_months)):
        prev_v = sales_by_month.get(chart_months[i - 1], 0)
        curr_v = sales_by_month.get(chart_months[i], 0)
        if prev_v > 0 and curr_v > 0:
            monthly_rates.append(curr_v / prev_v)
    avg_growth_rate = sum(monthly_rates) / len(monthly_rates) if monthly_rates else 1.05

    # ── Gráfico ───────────────────────────────────────────────────────────────
    future_months = _next_n_months(today, 2)
    all_chart_months = chart_months + future_months

    real_values = []
    for m in all_chart_months:
        if m < current_month_str:
            real_values.append(round(sales_by_month.get(m, 0), 2))
        elif m == current_month_str:
            real_values.append(round(current_month_real, 2))
        else:
            real_values.append(None)

    projected_values = []
    for i, m in enumerate(all_chart_months):
        if i == 0:
            base = sales_by_month.get(m, 0)
            projected_values.append(round(base, 2))
        elif m <= current_month_str:
            base = projected_values[-1] or sales_by_month.get(m, 0)
            projected_values.append(round(base * avg_growth_rate, 2))
        else:
            base = projected_values[-1] or projected_current_month
            projected_values.append(round(base * avg_growth_rate, 2))

    proyeccion_chart = {
        "labels": [_month_label(m) for m in all_chart_months],
        "projected": projected_values,
        "real": real_values,
    }

    # Incluir todos los meses con datos para la comparación
    # Si no hay mes anterior, buscar datos en el mes con más historia
    months_with_data = [m for m in _last_n_months(today, 6) if m in sales_by_month and sales_by_month[m] > 0]
    comparison_month = prev_month_str
    # Si el mes anterior no tiene datos, usar el último mes disponible con datos (excluyendo el actual)
    if prev_month_real == 0 and months_with_data:
        candidates = [m for m in months_with_data if m != current_month_str]
        if candidates:
            comparison_month = candidates[-1]

    product_current = {}
    product_compare = {}
    for sale in all_sales:
        sale_month = sale['date'].strftime('%Y-%m')
        for item in sale['items']:
            pname = item.get('product_name', 'Desconocido')
            try:
                subtotal = float(item.get('quantity', 1)) * float(item.get('price', 0))
            except Exception:
                subtotal = 0.0
            if sale_month == current_month_str:
                product_current[pname] = product_current.get(pname, 0) + subtotal
            elif sale_month == comparison_month:
                product_compare[pname] = product_compare.get(pname, 0) + subtotal

    proyeccion_table = []
    all_products = sorted(
        set(list(product_current.keys()) + list(product_compare.keys())),
        key=lambda p: -product_current.get(p, 0)
    )
    compare_label = _month_label(comparison_month) if comparison_month else "período anterior"
    for pname in all_products:
        curr = product_current.get(pname, 0)
        prev_val = product_compare.get(pname, 0)
        # Extrapolación al mes completo basada en ritmo diario
        if days_elapsed > 0 and curr > 0:
            proj = (curr / days_elapsed) * days_in_month
        elif prev_val > 0:
            proj = prev_val * avg_growth_rate
        else:
            proj = 0

        if prev_val > 0:
            variation = ((proj - prev_val) / prev_val) * 100
            variation_label = f"{'+' if variation >= 0 else ''}{variation:.1f}%"
            if days_elapsed >= 15:
                confidence, level = "Alta (92%)", "high"
            elif days_elapsed >= 7:
                confidence, level = "Media (75%)", "medium"
            else:
                confidence, level = "Baja (55%)", "low"
        elif curr > 0:
            variation_label = "Sin histórico"
            confidence, level = "Baja (55%)", "low"
        else:
            variation_label = "-"
            confidence, level = "-", "low"

        proyeccion_table.append({
            "product": pname,
            "current": f"${curr:,.0f}",
            "projection": f"${proj:,.0f}",
            "variation": variation_label,
            "confidence": confidence,
            "level": level,
        })

    # ── Insights automáticos ──────────────────────────────────────────────────
    proyeccion_insights = []

    if change_vs_prev is not None:
        if change_vs_prev >= 10:
            proyeccion_insights.append({
                "icon": "fas fa-chart-line",
                "title": "Tendencia Positiva",
                "desc": f"Las ventas proyectadas crecen {change_vs_prev:.1f}% respecto al mes anterior.",
            })
        elif change_vs_prev < 0:
            proyeccion_insights.append({
                "icon": "fas fa-exclamation-triangle",
                "title": "Alerta de Caída",
                "desc": f"La proyección actual está {abs(change_vs_prev):.1f}% por debajo del mes anterior.",
            })
        else:
            proyeccion_insights.append({
                "icon": "fas fa-equals",
                "title": "Ventas Estables",
                "desc": f"Las ventas se mantienen estables ({change_label}).",
            })

    if product_current:
        top_product = max(product_current, key=product_current.get)
        proyeccion_insights.append({
            "icon": "fas fa-star",
            "title": "Producto Líder",
            "desc": f'"{top_product}" lidera con ${product_current[top_product]:,.0f} vendidos este mes.',
        })

    proyeccion_insights.append({
        "icon": "fas fa-bullseye",
        "title": "Proyección Anual",
        "desc": f"A la tasa actual, se proyectan ${annual_projection:,.0f} en ventas para {today.year}. Avance: {progress_pct:.0f}%.",
    })

    if daily_rate > 0:
        proyeccion_insights.append({
            "icon": "fas fa-tachometer-alt",
            "title": "Ritmo Diario",
            "desc": f"Promedio diario este mes: ${daily_rate:,.0f}/día ({days_elapsed} días transcurridos).",
        })

    if not proyeccion_insights:
        proyeccion_insights.append({
            "icon": "fas fa-info-circle",
            "title": "Sin suficientes datos",
            "desc": "Registra más ventas para generar insights automáticos.",
        })

    # ── Stats tarjetas ────────────────────────────────────────────────────────
    proyeccion_stats = [
        {
            "icon": "fas fa-chart-bar",
            "label": "Proyección Mes Actual",
            "value": f"${projected_current_month:,.0f}",
            "change": change_label,
            "color": "blue",
        },
        {
            "icon": "fas fa-chart-line",
            "label": "Ventas Último Trimestre",
            "value": f"${q3_total:,.0f}",
            "change": q_label,
            "color": "cyan",
        },
        {
            "icon": "fas fa-flag-checkered",
            "label": "Proyección Anual",
            "value": f"${annual_projection:,.0f}",
            "change": f"Avance real: ${year_so_far:,.0f} ({progress_pct:.0f}%)",
            "color": "purple",
        },
    ]

    return {
        "proyeccion_stats": proyeccion_stats,
        "proyeccion_chart": proyeccion_chart,
        "proyeccion_table": proyeccion_table,
        "proyeccion_insights": proyeccion_insights,
    }
