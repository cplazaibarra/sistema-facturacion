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

@reportes_bp.route('/reporteria/inventario-lotes')
def reportes_inventario_lotes():
    """Reporte oficial de Inventario y Existencias por Lote y Bodega"""
    from db import get_all_lot_stock, get_page_data
    lot_stock_list = get_all_lot_stock()
    
    total_lotes = len(lot_stock_list)
    lotes_activos = sum(1 for l in lot_stock_list if l.get('available_qty', 0) > 0)
    lotes_agotados = total_lotes - lotes_activos
    unidades_disponibles = sum(l.get('available_qty', 0) for l in lot_stock_list)
    valor_total_lotes = sum(l.get('available_qty', 0) * float(l.get('cost') or 0.0) for l in lot_stock_list)
    
    warehouses_set = set(get_page_data("ingreso_warehouses") or ["Almacén Principal", "Almacén Secundario"])
    for lot in lot_stock_list:
        if lot.get("warehouse"):
            warehouses_set.add(lot["warehouse"])
    warehouses_list = sorted(list(warehouses_set))

    return render_template(
        'reporte_inventario_lotes.html',
        lot_stock_list=lot_stock_list,
        warehouses_list=warehouses_list,
        total_lotes=total_lotes,
        lotes_activos=lotes_activos,
        lotes_agotados=lotes_agotados,
        unidades_disponibles=unidades_disponibles,
        valor_total_lotes=valor_total_lotes
    )
