from flask import Blueprint, render_template, request, jsonify, make_response, redirect, url_for
from db import (
    list_sales,
    get_sales_chart_data,
    get_top_products,
    get_sales_metrics,
    get_page_data
)

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
def dashboard():
    """Página principal - Dashboard con gráficos y estadísticas"""
    # Get recent sales from database (last 3)
    sales_list = list_sales()
    recent_sales = []
    for sale in sales_list[:3]:
        recent_sales.append({
            "id": sale["sale_number"],
            "cliente": sale["customer_name"],
            "producto": ", ".join(sale["products"][:2]),
            "cantidad": len(sale["products"]),
            "total": sale["total_amount"],
            "estado": sale["status"],
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
        "productos_stock": 1250,  # This should come from inventory
        "ordenes_pendientes": metrics['ventas_pendientes'],
        "clientes_activos": metrics['clientes_activos'],
    }

    return jsonify(
        {
            "ventas_mensuales": ventas_mensuales,
            "productos_top": productos_top,
            "estadisticas": estadisticas,
        }
    )
