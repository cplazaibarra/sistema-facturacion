"""Proyección de ventas con ventanas móviles y precisión medida por backtesting."""
import calendar
import json
import statistics
from datetime import date, datetime

from db import get_connection


def _parse_date(date_str):
    if not date_str:
        return None
    value = str(date_str).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt).date()
        except ValueError:
            try:
                return datetime.strptime(value[:10], fmt).date()
            except ValueError:
                continue
    return None


def _days_in_month(year, month):
    return calendar.monthrange(year, month)[1]


def _shift_month(month_key, offset):
    year, month = map(int, month_key.split('-'))
    index = year * 12 + month - 1 + offset
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def _month_range(start_month, end_month):
    if not start_month or start_month > end_month:
        return []
    months = []
    current = start_month
    while current <= end_month:
        months.append(current)
        current = _shift_month(current, 1)
    return months


def _month_label(month_str):
    names = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
             'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    try:
        year, month = month_str.split('-')
        return names[int(month) - 1] + f" '{year[2:]}"
    except (ValueError, IndexError):
        return month_str


def _weighted_moving_average(values):
    """Promedio de ventana con peso lineal mayor para el dato más reciente."""
    if not values:
        return 0.0
    weights = range(1, len(values) + 1)
    return sum(value * weight for value, weight in zip(values, weights)) / sum(weights)


def _forecast_month(monthly_values, target_month):
    """Combina ventanas móviles de 3 y 6 meses; suma estacionalidad con 2 años."""
    available = [month for month in monthly_values if month < target_month]
    if not available:
        return 0.0
    first_month = min(available)

    def window_average(size):
        months = [m for m in (_shift_month(target_month, -offset) for offset in range(size, 0, -1))
                  if m >= first_month]
        return _weighted_moving_average([monthly_values.get(m, 0.0) for m in months])

    short_window = window_average(3)
    long_window = window_average(6)
    months = [m for m in (_shift_month(target_month, -offset) for offset in range(6, 0, -1))
              if m >= first_month]
    recent_values = [monthly_values.get(m, 0.0) for m in months]
    robust_center = statistics.median(recent_values) if recent_values else 0.0
    forecast = short_window * 0.55 + long_window * 0.30 + robust_center * 0.15

    seasonal_months = [_shift_month(target_month, -12 * year) for year in (1, 2)]
    seasonal_values = [monthly_values[m] for m in seasonal_months if m in monthly_values]
    if len(seasonal_values) == 2:
        seasonal_average = sum(seasonal_values) / 2
        forecast = forecast * 0.8 + seasonal_average * 0.2
    return max(forecast, 0.0)


def _backtest(monthly_values):
    """Evalúa pronósticos de un mes usando sólo meses anteriores (WAPE)."""
    months = sorted(monthly_values)
    errors = []
    actual_total = 0.0
    first_test_index = max(3, len(months) - 12)
    for index in range(first_test_index, len(months)):
        target = months[index]
        history = {month: monthly_values[month] for month in months[:index]}
        actual = monthly_values[target]
        predicted = _forecast_month(history, target)
        errors.append(abs(actual - predicted))
        actual_total += abs(actual)

    if not errors or actual_total == 0:
        return {"wape": None, "periods": len(errors)}
    return {"wape": sum(errors) / actual_total * 100, "periods": len(errors)}


def _precision_label(metrics):
    wape = metrics["wape"]
    periods = metrics["periods"]
    if wape is None or periods < 3:
        return "Datos insuficientes", "low"
    if periods >= 6 and wape <= 15:
        level = "high"
        label = "Alta"
    elif periods >= 3 and wape <= 30:
        level = "medium"
        label = "Media"
    else:
        level = "low"
        label = "Baja"
    return f"{label} · WAPE {wape:.1f}% · {periods} períodos", level


def _blend_current_month(base_forecast, month_actual, day_of_month, days_in_month):
    if month_actual <= 0:
        return base_forecast
    run_rate = month_actual / max(day_of_month, 1) * days_in_month
    elapsed_share = day_of_month / max(days_in_month, 1)
    pace_weight = min(0.75, 0.15 + elapsed_share * 0.60)
    blended = base_forecast * (1 - pace_weight) + run_rate * pace_weight
    return max(blended, month_actual)


def get_sales_by_month():
    """Ventas efectivas por mes; excluye cotizaciones, borradores y anulaciones."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT SUBSTRING(sale_date, 1, 7) AS mes, SUM(total_amount) AS total
                FROM sales
                WHERE total_amount IS NOT NULL
                  AND sale_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
                  AND status NOT IN ('Cancelada', 'Cancelado', 'Anulada', 'Anulado', 'Cotización', 'Borrador')
                  AND (sale_number LIKE 'VTA-%' OR sale_number LIKE 'P-%')
                GROUP BY mes
                ORDER BY mes
            """)
            return {row['mes']: float(row['total'] or 0) for row in cur.fetchall() if row['mes']}


def get_all_sales_with_products():
    """Detalle de productos sólo de ventas efectivas, con la misma definición del total."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT sale_number, sale_date, total_amount, products_json
                FROM sales
                WHERE status NOT IN ('Cancelada', 'Cancelado', 'Anulada', 'Anulado', 'Cotización', 'Borrador')
                  AND (sale_number LIKE 'VTA-%' OR sale_number LIKE 'P-%')
                  AND sale_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
                ORDER BY sale_date
            """)
            rows = [dict(row) for row in cur.fetchall()]

    result = []
    for row in rows:
        sale_date = _parse_date(row['sale_date'])
        if sale_date is None:
            continue
        try:
            raw = json.loads(row['products_json']) if row['products_json'] else []
            items = [item for item in raw if isinstance(item, dict)]
        except (TypeError, ValueError):
            items = []
        result.append({"date": sale_date, "items": items})
    return result


def compute_proyeccion():
    today = date.today()
    current_month = today.strftime('%Y-%m')
    previous_month = _shift_month(current_month, -1)
    days_in_month = _days_in_month(today.year, today.month)

    raw_sales = get_sales_by_month()
    if raw_sales:
        first_month = min(raw_sales)
        closed_months = _month_range(first_month, previous_month)
        closed_sales = {month: raw_sales.get(month, 0.0) for month in closed_months}
    else:
        closed_sales = {}

    current_actual = raw_sales.get(current_month, 0.0)
    current_baseline = _forecast_month(closed_sales, current_month)
    current_projection = _blend_current_month(
        current_baseline, current_actual, today.day, days_in_month
    )

    # Produce meses futuros iterativamente, alimentando cada paso con la proyección previa.
    forecast_history = dict(closed_sales)
    forecast_history[current_month] = current_projection
    future_months = [_shift_month(current_month, offset) for offset in (1, 2)]
    future_values = {}
    for month in future_months:
        future_values[month] = _forecast_month(forecast_history, month)
        forecast_history[month] = future_values[month]

    # Validación retrospectiva: cada mes de prueba se predice sin usar sus datos reales.
    quality = _backtest(closed_sales)

    prev_actual = raw_sales.get(previous_month, 0.0)
    if prev_actual > 0:
        change = (current_projection - prev_actual) / prev_actual * 100
        change_label = f"{'+' if change >= 0 else ''}{change:.1f}% vs. mes anterior"
    else:
        change = None
        change_label = "Sin ventas en el mes anterior"

    last_three_closed = [_shift_month(current_month, -offset) for offset in (3, 2, 1)]
    recent_three_total = sum(raw_sales.get(month, 0.0) for month in last_three_closed)
    prior_three_total = sum(raw_sales.get(_shift_month(current_month, -offset), 0.0)
                            for offset in range(6, 3, -1))
    quarter_change = ((recent_three_total - prior_three_total) / prior_three_total * 100
                      if prior_three_total > 0 else None)

    # Proyección anual: real de meses cerrados + proyección actual y meses restantes.
    annual_actual = sum(value for month, value in raw_sales.items()
                        if month.startswith(f"{today.year:04d}-") and month < current_month)
    annual_projection = annual_actual + current_projection
    annual_history = dict(closed_sales)
    annual_history[current_month] = current_projection
    for month_number in range(today.month + 1, 13):
        month = f"{today.year:04d}-{month_number:02d}"
        forecast = _forecast_month(annual_history, month)
        annual_projection += forecast
        annual_history[month] = forecast
    year_actual_to_date = annual_actual + current_actual
    annual_progress = (year_actual_to_date / annual_projection * 100) if annual_projection > 0 else 0.0

    # Serie para el gráfico: reales hasta hoy y pronósticos desde el mes actual.
    chart_start = _shift_month(current_month, -5)
    chart_months = _month_range(chart_start, current_month) + future_months
    real_values = [round(raw_sales.get(month, 0.0), 2) if month <= current_month else None
                   for month in chart_months]
    projected_values = [None if month < current_month else round(
        current_projection if month == current_month else future_values.get(month, 0.0), 2
    ) for month in chart_months]

    # Series de ventas por producto, usando el subtotal persistido de cada línea.
    all_sales = get_all_sales_with_products()
    product_values = {}
    for sale in all_sales:
        month = sale['date'].strftime('%Y-%m')
        if month < _shift_month(current_month, -23):
            continue
        for item in sale['items']:
            product_name = item.get('product_name') or item.get('name') or 'Desconocido'
            try:
                amount = float(item.get('subtotal'))
            except (TypeError, ValueError):
                try:
                    amount = float(item.get('quantity', 1)) * float(item.get('price', 0))
                    amount *= 1 - float(item.get('discount', 0) or 0) / 100
                except (TypeError, ValueError):
                    amount = 0.0
            product_month = product_values.setdefault(product_name, {})
            product_month[month] = product_month.get(month, 0.0) + max(amount, 0.0)

    product_table = []
    for product_name, raw_values in product_values.items():
        product_months = _month_range(min(raw_values), current_month)
        product_series = {month: raw_values.get(month, 0.0) for month in product_months
                          if month <= previous_month}
        current_product_actual = raw_values.get(current_month, 0.0)
        product_base = _forecast_month(product_series, current_month)
        product_projection = _blend_current_month(
            product_base, current_product_actual, today.day, days_in_month
        )
        comparison_actual = raw_values.get(previous_month, 0.0)
        comparison_change = ((product_projection - comparison_actual) / comparison_actual * 100
                             if comparison_actual > 0 else None)
        product_quality = _backtest(product_series)
        product_precision, product_level = _precision_label(product_quality)
        product_table.append({
            "product": product_name,
            "current": f"${current_product_actual:,.0f}",
            "projection": f"${product_projection:,.0f}",
            "variation": (f"{'+' if comparison_change >= 0 else ''}{comparison_change:.1f}%"
                          if comparison_change is not None else "Sin base comparable"),
            "confidence": product_precision,
            "level": product_level,
        })
    product_table.sort(key=lambda row: float(row['projection'].replace('$', '').replace(',', '')), reverse=True)

    stats = [
        {"icon": "fas fa-chart-bar", "label": "Proyección del mes actual",
         "value": f"${current_projection:,.0f}", "change": change_label, "color": "blue"},
        {"icon": "fas fa-chart-line", "label": "Ventas de los últimos 3 meses cerrados",
         "value": f"${recent_three_total:,.0f}",
         "change": (f"{'+' if quarter_change >= 0 else ''}{quarter_change:.1f}% vs. los 3 meses previos"
                    if quarter_change is not None else "Sin base de comparación de 3 meses"), "color": "cyan"},
        {"icon": "fas fa-flag-checkered", "label": "Proyección anual móvil",
         "value": f"${annual_projection:,.0f}",
         "change": f"Real acumulado: ${year_actual_to_date:,.0f} ({annual_progress:.0f}%)", "color": "purple"},
        {"icon": "fas fa-bullseye", "label": "Precisión histórica del modelo",
         "value": (f"WAPE {quality['wape']:.1f}%" if quality['wape'] is not None else "Sin datos suficientes"),
         "change": f"Backtesting · {quality['periods']} períodos evaluados", "color": "blue"},
    ]

    insights = [{
        "icon": "fas fa-chart-line",
        "title": "Método de proyección",
        "desc": "Combina promedios móviles ponderados de 3 y 6 meses con una mediana móvil para moderar meses atípicos. Incorpora estacionalidad sólo con dos años comparables; el mes actual combina esa base con el ritmo observado.",
    }]
    if change is not None:
        insights.append({
            "icon": "fas fa-arrow-trend-up" if change >= 0 else "fas fa-arrow-trend-down",
            "title": "Comparación mensual",
            "desc": f"El cierre proyectado está {change:+.1f}% frente al último mes cerrado.",
        })
    if quality['wape'] is None or quality['periods'] < 3:
        insights.append({
            "icon": "fas fa-circle-info",
            "title": "Historial limitado",
            "desc": "Aún no hay al menos tres períodos de backtesting para estimar la precisión del pronóstico.",
        })
    else:
        insights.append({
            "icon": "fas fa-bullseye",
            "title": "Error de pronóstico",
            "desc": f"El WAPE histórico es {quality['wape']:.1f}% en {quality['periods']} períodos. Un valor menor indica pronósticos más cercanos a las ventas observadas.",
        })

    return {
        "proyeccion_stats": stats,
        "proyeccion_chart": {
            "labels": [_month_label(month) for month in chart_months],
            "projected": projected_values,
            "real": real_values,
        },
        "proyeccion_table": product_table,
        "proyeccion_insights": insights,
    }
