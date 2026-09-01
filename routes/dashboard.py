from flask import Blueprint, render_template, request, jsonify, make_response, redirect, url_for
from db import (
    list_sales,
    get_sales_chart_data,
    get_top_products,
    get_sales_metrics,
    get_page_data,
    get_system_notifications
)

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
def dashboard():
    """Página principal - Dashboard con gráficos y estadísticas"""
    # Obtener solo ventas reales (prefijo VTA-), excluyendo cotizaciones (COT-)
    sales_list = list_sales({"prefix": "VTA-", "exclude_status": "Cotización"})
    recent_sales = []
    for sale in sales_list[:5]:
        products_names = []
        for p in sale.get("products", []):
            if isinstance(p, dict):
                p_name = p.get("product_name") or p.get("name") or p.get("sku", "")
                if p_name:
                    products_names.append(p_name)
            elif isinstance(p, str):
                p_name = p.split('(')[0].strip()
                if p_name:
                    products_names.append(p_name)
        
        prod_display = ", ".join(products_names[:2]) if products_names else "Varios"
        if len(products_names) > 2:
            prod_display += f" (+{len(products_names) - 2})"

        recent_sales.append({
            "id": sale["sale_number"],
            "cliente": sale.get("customer_name") or "Sin cliente",
            "producto": prod_display,
            "cantidad": len(sale.get("products", [])),
            "total": sale.get("total_amount", 0),
            "estado": sale.get("status", "Pendiente"),
        })
    return render_template('dashboard.html', recent_sales=recent_sales)

@dashboard_bp.route('/api/dashboard-data')
def dashboard_data():
    """Datos para el dashboard"""
    # Get query parameters
    sales_year = request.args.get('sales_year', type=int)
    products_year = request.args.get('products_year', type=int)
    sales_period = request.args.get('sales_period', '6months')
    products_period = request.args.get('products_period', 'year')

    # Get sales data
    ventas_mensuales = get_sales_chart_data(year=sales_year, period=sales_period)

    # Get products data
    productos_top = get_top_products(year=products_year, period=products_period)

    # Get stats from database
    metrics = get_sales_metrics()
    estadisticas = {
        "ventas_hoy": metrics['ventas_hoy'],
        "ventas_hoy_trend": metrics.get('ventas_hoy_trend', {'text': '0%', 'type': 'neutral'}),
        "productos_stock": metrics.get('productos_stock', 0),
        "productos_stock_trend": metrics.get('productos_stock_trend', {'text': 'Óptimo', 'type': 'positive'}),
        "ordenes_pendientes": metrics.get('ordenes_pendientes', 0),
        "ordenes_pendientes_trend": metrics.get('ordenes_pendientes_trend', {'text': '0%', 'type': 'neutral'}),
        "clientes_activos": metrics['clientes_activos'],
        "clientes_activos_trend": metrics.get('clientes_activos_trend', {'text': 'Activos', 'type': 'positive'}),
    }

    return jsonify(
        {
            "ventas_mensuales": ventas_mensuales,
            "productos_top": productos_top,
            "estadisticas": estadisticas,
        }
    )


@dashboard_bp.route('/api/notificaciones')
def api_notificaciones():
    """Retorna las notificaciones y alertas activas del sistema"""
    notifs = get_system_notifications()
    return jsonify({
        "count": len(notifs),
        "notifications": notifs
    })
