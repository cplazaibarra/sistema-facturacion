from flask import Blueprint, render_template

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
