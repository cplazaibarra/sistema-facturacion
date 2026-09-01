from flask import Blueprint, render_template, make_response, request
from db import get_income_report_data, get_cash_flow_data, get_cash_flow_data_weekly

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

@reportes_bp.route('/reporteria/flujo-caja')
def reportes_flujo_caja():
    """Flujo de Caja: ingresos, gastos, impagas y proyección — semanal por defecto o mensual"""
    vista = request.args.get('vista', 'semanal')
    if vista == 'mensual':
        cf = get_cash_flow_data()
        vista = 'mensual'
    else:
        cf = get_cash_flow_data_weekly()
        vista = 'semanal'
    response = make_response(render_template(
        'reporte_flujo_caja.html',
        cf=cf,
        vista=vista
    ))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response
