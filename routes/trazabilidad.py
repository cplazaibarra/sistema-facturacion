"""
routes/trazabilidad.py
Blueprint for 360° Lot Traceability, Genealogy exploration, and Recall analysis.
"""

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from datetime import datetime, timezone
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


@trazabilidad_bp.route('/trazabilidad/<int:lot_id>/export/csv')
def export_recall_csv(lot_id):
    """Exporta el reporte de impacto de Recall de un lote en formato CSV."""
    import csv
    import io
    from flask import Response

    data = LotTraceabilityService.get_lot_recall_impact(lot_id)
    if "error" in data:
        flash("Lote no encontrado para exportar Recall.", "danger")
        return redirect(url_for('trazabilidad.view_trazabilidad'))

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    target = data.get("target_lot", {})
    writer.writerow(["REPORTE DE RETIRO DE PRODUCTO (RECALL) - ERP BODEGA MIEL"])
    writer.writerow(["Fecha Emision", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")])
    writer.writerow(["Lote Investigado", target.get("lot_number", "")])
    writer.writerow(["ID Sistema", target.get("id", "")])
    writer.writerow(["Producto", target.get("product_name", "")])
    writer.writerow(["SKU", target.get("sku", "")])
    writer.writerow([])

    writer.writerow(["RESUMEN DE ALCANCE OPERACIONAL"])
    writer.writerow(["Lotes Afectados", data.get("affected_lots_count", 0)])
    writer.writerow(["OT Afectadas", data.get("affected_productions_count", 0)])
    writer.writerow(["Ventas Afectadas", data.get("affected_sales_count", 0)])
    writer.writerow(["Clientes Afectados", data.get("affected_clients_count", 0)])
    writer.writerow(["Total Unidades Vendidas", data.get("total_units_sold", 0.0)])
    writer.writerow([])

    writer.writerow(["1. STOCK REMANENTE EN BODEGAS (INTERNO)"])
    writer.writerow(["Bodega", "Producto", "SKU", "Lote", "Cantidad Disponible"])
    for st in data.get("remaining_warehouse_stock", []):
        writer.writerow([
            st.get("warehouse", "Principal"),
            st.get("product_name", ""),
            st.get("sku", ""),
            st.get("lot_number", ""),
            st.get("available_qty", 0.0)
        ])
    writer.writerow([])

    writer.writerow(["2. VENTAS Y CLIENTES IMPACTADOS (EXTERNO)"])
    writer.writerow(["Numero Venta", "Fecha", "Cliente", "Email", "Lote Vendido", "Cantidad Despachada"])
    for s in data.get("affected_sales", []):
        writer.writerow([
            s.get("sale_number", ""),
            s.get("sale_date", ""),
            s.get("customer_name", ""),
            s.get("customer_email", ""),
            s.get("lot_number", ""),
            s.get("quantity", 0.0)
        ])
    writer.writerow([])

    writer.writerow(["3. ARBOL DE LOTES Y TRANSFORMACIONES (OT)"])
    writer.writerow(["Lote", "Producto", "SKU", "Tipo Lote", "Nivel Profundidad"])
    for l in data.get("affected_lots", []):
        writer.writerow([
            l.get("lot_number", ""),
            l.get("product_name", ""),
            l.get("sku", ""),
            l.get("lot_type", ""),
            l.get("depth", 0)
        ])

    csv_data = output.getvalue()
    lot_num_clean = target.get("lot_number", f"lote_{lot_id}").replace(" ", "_")
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=recall_impact_{lot_num_clean}.csv"}
    )


@trazabilidad_bp.route('/trazabilidad/<int:lot_id>/export/pdf')
def export_recall_pdf(lot_id):
    """Exporta el informe de Recall oficial en formato PDF usando ReportLab."""
    import io
    from flask import Response
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    data = LotTraceabilityService.get_lot_recall_impact(lot_id)
    if "error" in data:
        flash("Lote no encontrado para exportar Recall.", "danger")
        return redirect(url_for('trazabilidad.view_trazabilidad'))

    target = data.get("target_lot", {})
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'RecallTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#991B1B')
    )
    h2_style = ParagraphStyle(
        'RecallH2',
        parent=styles['Heading2'],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=12,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'RecallBody',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1E293B')
    )

    elements.append(Paragraph("REPORTE OFICIAL DE RECALL / RETIRO DE PRODUCTO", title_style))
    elements.append(Paragraph(f"Generado el: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | Sistema ERP Bodega Miel", body_style))
    elements.append(Spacer(1, 12))

    # Info Lote
    info_data = [
        [Paragraph("<b>Lote Origen:</b>", body_style), Paragraph(str(target.get("lot_number", "")), body_style),
         Paragraph("<b>ID Sistema:</b>", body_style), Paragraph(f"#{target.get('id', '')}", body_style)],
        [Paragraph("<b>Producto:</b>", body_style), Paragraph(str(target.get("product_name", "")), body_style),
         Paragraph("<b>SKU:</b>", body_style), Paragraph(str(target.get("sku", "")), body_style)],
        [Paragraph("<b>Fecha Creación:</b>", body_style), Paragraph(str(target.get("created_at", "")), body_style),
         Paragraph("<b>Estado:</b>", body_style), Paragraph(str(target.get("status", "")), body_style)],
    ]
    t_info = Table(info_data, colWidths=[90, 180, 80, 190])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(t_info)
    elements.append(Spacer(1, 10))

    # Métricas de Alcance
    metrics_data = [
        ["Lotes Afectados", "OT Involucradas", "Ventas Despachadas", "Clientes Impactados", "Unidades Vendidas"],
        [str(data.get("affected_lots_count", 0)),
         str(data.get("affected_productions_count", 0)),
         str(data.get("affected_sales_count", 0)),
         str(data.get("affected_clients_count", 0)),
         f"{data.get('total_units_sold', 0.0):,.1f} un"]
    ]
    t_metrics = Table(metrics_data, colWidths=[108, 108, 108, 108, 108])
    t_metrics.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#FEF2F2')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#991B1B')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,1), (-1,1), 11),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#FCA5A5')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_metrics)
    elements.append(Spacer(1, 10))

    # Ventas Afectadas
    elements.append(Paragraph("1. Clientes y Ventas Impactadas (Acción Externa Urgente)", h2_style))
    sales_rows = [["Nº Venta", "Fecha", "Cliente", "Email", "Lote", "Cantidad"]]
    for s in data.get("affected_sales", []):
        sales_rows.append([
            str(s.get("sale_number", "")),
            str(s.get("sale_date", "")),
            str(s.get("customer_name", "")),
            str(s.get("customer_email", "") or "Sin email"),
            str(s.get("lot_number", "")),
            f"{float(s.get('quantity', 0)):,.1f} un"
        ])
    if len(sales_rows) == 1:
        sales_rows.append(["Sin ventas registradas para este lote o sus derivados.", "", "", "", "", ""])

    t_sales = Table(sales_rows, colWidths=[70, 65, 140, 135, 70, 60])
    t_sales.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    elements.append(t_sales)

    # Stock Remanente en Bodega
    elements.append(Paragraph("2. Stock Remanente en Bodegas (Cuarentena Interna Inmediata)", h2_style))
    stock_rows = [["Bodega", "Producto", "SKU", "Lote", "Saldo Disponible"]]
    for st in data.get("remaining_warehouse_stock", []):
        stock_rows.append([
            str(st.get("warehouse", "Principal")),
            str(st.get("product_name", "")),
            str(st.get("sku", "")),
            str(st.get("lot_number", "")),
            f"{float(st.get('available_qty', 0)):,.1f} un"
        ])
    if len(stock_rows) == 1:
        stock_rows.append(["No hay saldo remanente en bodegas (Stock agotado).", "", "", "", ""])

    t_stock = Table(stock_rows, colWidths=[90, 180, 80, 100, 90])
    t_stock.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    elements.append(t_stock)

    doc.build(elements)
    pdf_val = buffer.getvalue()
    buffer.close()

    lot_num_clean = target.get("lot_number", f"lote_{lot_id}").replace(" ", "_")
    return Response(
        pdf_val,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment;filename=recall_impact_{lot_num_clean}.pdf"}
    )

