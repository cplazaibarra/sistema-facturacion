from flask import Blueprint, render_template, make_response
from db import get_income_report_data

reportes_bp = Blueprint('reportes', __name__)

@reportes_bp.route('/reporteria/ventas')
def reportes_ventas():
    """Reporte de Ventas"""
    return render_template('reporte_ventas.html')

@reportes_bp.route('/reporteria/compras')
def reportes_compras():
    """Reporte de Compras"""
    return render_template('reporte_compras.html')

@reportes_bp.route('/reporteria/gastos')
def reportes_gastos():
    """Reporte de Gastos"""
    return render_template('reporte_gastos.html')

@reportes_bp.route('/reporteria/ingresos')
def reportes_ingresos():
    """Reporte de Ingresos ($) - Histórico y Flujo Futuro por compromisos"""
    income_data = get_income_report_data()
    response = make_response(render_template(
        'reporte_ingresos.html',
        income_data=income_data
    ))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response
