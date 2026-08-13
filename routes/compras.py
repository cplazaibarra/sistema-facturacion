from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash, send_file
from datetime import datetime
import io
from db import (
    list_suppliers,
    list_products_by_supplier,
    create_purchase_order,
    update_purchase_order,
    list_purchase_orders,
    get_purchase_order,
    get_purchase_order_items,
    list_active_purchase_orders_by_supplier
)
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

compras_bp = Blueprint('compras', __name__)

@compras_bp.route('/compras/oc')
def list_oc():
    """Listar órdenes de compra"""
    orders = list_purchase_orders()
    return render_template('compras_oc.html', orders=orders)

@compras_bp.route('/compras/oc/nueva', methods=['GET', 'POST'])
def nueva_oc():
    """Crear una nueva orden de compra"""
    if request.method == 'POST':
        supplier_id = request.form.get('supplier_id', type=int)
        order_date = request.form.get('order_date')
        notes = request.form.get('notes')
        
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        
        items = []
        for pid, qty_raw, price_raw in zip(product_ids, quantities, unit_prices):
            if not pid:
                continue
            try:
                qty = int(qty_raw) if qty_raw else 0
                price = float(price_raw) if price_raw else 0.0
            except ValueError:
                continue
            if qty > 0:
                items.append({
                    "product_id": int(pid),
                    "quantity": qty,
                    "unit_price": price
                })
                
        status = request.form.get('status', 'Emitida').strip()
        if status not in ['Borrador', 'Emitida']:
            status = 'Emitida'

        if not supplier_id or not items:
            flash("Debe seleccionar un proveedor y agregar al menos un producto.", "danger")
            suppliers = list_suppliers()
            return render_template('nueva_oc.html', suppliers=suppliers, default_date=datetime.now().strftime('%Y-%m-%d'))
            
        oc_num = create_purchase_order(supplier_id, order_date, notes, items, status=status)
        flash(f"Orden de Compra {oc_num} guardada como {status} con éxito.", "success")
        return redirect(url_for('compras.list_oc'))

    suppliers = list_suppliers()
    return render_template('nueva_oc.html', suppliers=suppliers, default_date=datetime.now().strftime('%Y-%m-%d'))

@compras_bp.route('/compras/oc/<int:po_id>/editar', methods=['GET', 'POST'])
def editar_oc(po_id):
    """Editar una orden de compra en estado Borrador"""
    po = get_purchase_order(po_id)
    if not po:
        flash("Orden de Compra no encontrada.", "danger")
        return redirect(url_for('compras.list_oc'))
        
    if po['status'] != 'Borrador':
        flash("Solo se pueden editar órdenes de compra en estado Borrador.", "warning")
        return redirect(url_for('compras.list_oc'))

    if request.method == 'POST':
        supplier_id = request.form.get('supplier_id', type=int)
        order_date = request.form.get('order_date')
        notes = request.form.get('notes')
        status = request.form.get('status', 'Borrador').strip()
        
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        
        items = []
        for pid, qty_raw, price_raw in zip(product_ids, quantities, unit_prices):
            if not pid:
                continue
            try:
                qty = int(qty_raw) if qty_raw else 0
                price = float(price_raw) if price_raw else 0.0
            except ValueError:
                continue
            if qty > 0:
                items.append({
                    "product_id": int(pid),
                    "quantity": qty,
                    "unit_price": price
                })
                
        if not supplier_id or not items:
            flash("Debe seleccionar un proveedor y agregar al menos un producto.", "danger")
            suppliers = list_suppliers()
            items_current = get_purchase_order_items(po_id)
            return render_template('editar_oc.html', po=po, items=items_current, suppliers=suppliers)
            
        update_purchase_order(po_id, supplier_id, order_date, notes, items, status=status)
        flash(f"Orden de Compra {po['oc_number']} actualizada como {status} con éxito.", "success")
        return redirect(url_for('compras.list_oc'))

    suppliers = list_suppliers()
    items = get_purchase_order_items(po_id)
    return render_template('editar_oc.html', po=po, items=items, suppliers=suppliers)

@compras_bp.route('/api/compras/proveedores/<int:supplier_id>/productos')
def api_supplier_products(supplier_id):
    """API para obtener todos los productos del sistema (permitiendo elegir cualquiera ya definido)"""
    from db import list_products
    products = list_products()
    return jsonify(products)

@compras_bp.route('/api/compras/proveedores/<int:supplier_id>/oc-activas')
def api_supplier_active_oc(supplier_id):
    """API para obtener OCs activas/pendientes de un proveedor"""
    orders = list_active_purchase_orders_by_supplier(supplier_id)
    return jsonify(orders)

@compras_bp.route('/api/compras/oc/<int:po_id>/items')
def api_oc_items(po_id):
    """API para obtener ítems y cantidades pendientes de una OC"""
    items = get_purchase_order_items(po_id)
    return jsonify(items)

@compras_bp.route('/compras/oc/<int:po_id>/pdf')
def descargar_oc_pdf(po_id):
    """Genera y descarga la Orden de Compra en formato PDF usando ReportLab"""
    po = get_purchase_order(po_id)
    if not po:
        return "Orden de compra no encontrada", 404
        
    items = get_purchase_order_items(po_id)
    
    # Crear buffer en memoria para el PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    
    styles = getSampleStyleSheet()
    
    # Estilos custom
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=colors.HexColor('#1E3A8A'),
        spaceAfter=20
    )
    
    label_style = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=colors.HexColor('#4A5568')
    )
    
    value_style = ParagraphStyle(
        'MetaVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#2D3748')
    )

    # 1. Título e Info de OC
    story.append(Paragraph("ORDEN DE COMPRA", title_style))
    story.append(Spacer(1, 10))
    
    # Grid de Metadatos
    meta_data = [
        [Paragraph("Número de OC:", label_style), Paragraph(po["oc_number"], value_style),
         Paragraph("Fecha de Emisión:", label_style), Paragraph(po["order_date"], value_style)],
        [Paragraph("Proveedor:", label_style), Paragraph(po["supplier_name"], value_style),
         Paragraph("Estado:", label_style), Paragraph(po["status"], value_style)]
    ]
    
    t_meta = Table(meta_data, colWidths=[100, 160, 110, 150])
    t_meta.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 20))
    
    # Notas si existen
    if po["notes"]:
        story.append(Paragraph("Notas / Instrucciones:", label_style))
        story.append(Paragraph(po["notes"], value_style))
        story.append(Spacer(1, 20))
        
    # 2. Tabla de items
    table_headers = [
        Paragraph("<b>SKU</b>", label_style),
        Paragraph("<b>Producto</b>", label_style),
        Paragraph("<b>Solicitado</b>", label_style),
        Paragraph("<b>Recibido</b>", label_style),
        Paragraph("<b>Precio Unit.</b>", label_style),
        Paragraph("<b>Total</b>", label_style)
    ]
    
    table_data = [table_headers]
    for item in items:
        table_data.append([
            Paragraph(item["product_sku"] or "-", value_style),
            Paragraph(item["product_name"], value_style),
            Paragraph(str(item["quantity_ordered"]), value_style),
            Paragraph(str(item["quantity_received"]), value_style),
            Paragraph(f"${item['unit_price']:,.2f}", value_style),
            Paragraph(f"${item['total_price']:,.2f}", value_style)
        ])
        
    # Total fila
    table_data.append([
        "", "", "", "",
        Paragraph("<b>Total General:</b>", label_style),
        Paragraph(f"<b>${po['total_amount']:,.2f}</b>", value_style)
    ])
    
    t_items = Table(table_data, colWidths=[80, 180, 60, 60, 70, 70])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F7FAFC')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#E2E8F0')),
        ('LINEABOVE', (4, -1), (5, -1), 1.5, colors.HexColor('#1E3A8A')),
    ]))
    
    story.append(t_items)
    
    # Construir PDF
    doc.build(story)
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"Orden_Compra_{po['oc_number']}.pdf",
        mimetype="application/pdf"
    )
