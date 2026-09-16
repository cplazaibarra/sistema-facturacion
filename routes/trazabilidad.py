"""
routes/trazabilidad.py
Blueprint for 360° Lot Traceability, Genealogy exploration, and Recall analysis.
"""

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from services.lot_traceability_service import LotTraceabilityService
from db import get_connection

trazabilidad_bp = Blueprint('trazabilidad', __name__)


@trazabilidad_bp.route('/trazabilidad')
def view_trazabilidad():
    """Vista principal interactiva de trazabilidad de lotes y recall."""
    query = request.args.get('q', '').strip()
    selected_lot_id = request.args.get('lot_id', type=int)

    lots_list = LotTraceabilityService.search_lots(query, limit=50) if query else []
    
    selected_lot_360 = None
    if selected_lot_id:
        selected_lot_360 = LotTraceabilityService.get_lot_traceability(selected_lot_id)
    elif lots_list:
        selected_lot_id = lots_list[0]["id"]
        selected_lot_360 = LotTraceabilityService.get_lot_traceability(selected_lot_id)

    return render_template(
        'trazabilidad.html',
        query=query,
        lots_list=lots_list,
        selected_lot=selected_lot_360,
        selected_lot_id=selected_lot_id
    )


@trazabilidad_bp.route('/api/lots/search')
def api_search_lots():
    """Búsqueda de lotes por texto."""
    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', default=50, type=int)
    results = LotTraceabilityService.search_lots(query, limit=limit)
    return jsonify({"status": "success", "count": len(results), "lots": results})


@trazabilidad_bp.route('/api/lots/<int:lot_id>/traceability')
def api_lot_traceability(lot_id):
    """Consulta 360° del ciclo de vida del lote."""
    data = LotTraceabilityService.get_lot_traceability(lot_id)
    if not data:
        return jsonify({"status": "error", "message": "Lote no encontrado"}), 404
    return jsonify({"status": "success", "traceability": data})


@trazabilidad_bp.route('/api/lots/<int:lot_id>/forward')
def api_lot_forward(lot_id):
    """Trazabilidad hacia adelante (Forward Trace)."""
    data = LotTraceabilityService.trace_lot_forward(lot_id)
    if not data.get("root_lot"):
        return jsonify({"status": "error", "message": "Lote no encontrado"}), 404
    return jsonify({"status": "success", "forward": data})


@trazabilidad_bp.route('/api/lots/<int:lot_id>/backward')
def api_lot_backward(lot_id):
    """Trazabilidad hacia atrás (Backward Trace)."""
    data = LotTraceabilityService.trace_lot_backward(lot_id)
    if not data.get("root_lot"):
        return jsonify({"status": "error", "message": "Lote no encontrado"}), 404
    return jsonify({"status": "success", "backward": data})


@trazabilidad_bp.route('/api/lots/<int:lot_id>/recall-impact')
def api_lot_recall_impact(lot_id):
    """Análisis de impacto y alcance de retiro de producto (Recall)."""
    data = LotTraceabilityService.get_lot_recall_impact(lot_id)
    if "error" in data:
        return jsonify({"status": "error", "message": data["error"]}), 404
    return jsonify({"status": "success", "recall_impact": data})


@trazabilidad_bp.route('/api/lots/sale/<int:sale_id>')
def api_sale_origin_trace(sale_id):
    """Trazabilidad desde una venta hacia sus proveedores y lotes de origen."""
    data = LotTraceabilityService.trace_sale_to_origin(sale_id)
    if data.get("error"):
        return jsonify({"status": "error", "message": data["error"]}), 404
    return jsonify({"status": "success", "sale_trace": data})
