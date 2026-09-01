from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash, send_file, session
from datetime import datetime, date
import io, os
from db import (
    list_suppliers,
    list_products_by_supplier,
    create_purchase_order,
    update_purchase_order,
    list_purchase_orders,
    get_purchase_order,
    get_purchase_order_items,
    list_active_purchase_orders_by_supplier,
    approve_purchase_order,
    # Cuentas por Pagar y Bancos
    list_bank_accounts,
    create_purchase_invoice,
    list_purchase_invoices,
    get_purchase_invoice,
    register_purchase_payment,
    count_pending_invoices,
    update_invoice_payment_status,
    list_entries_missing_invoice,
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
        
        payment_method = request.form.get('payment_method', 'Efectivo').strip()
        status = request.form.get('status', 'Pendiente Aprobación').strip()
        if status not in ['Borrador', 'Pendiente Aprobación', 'Emitida']:
            status = 'Pendiente Aprobación'

        if not supplier_id or not items:
            flash("Debe seleccionar un proveedor y agregar al menos un producto.", "danger")
            suppliers = list_suppliers()
            return render_template('nueva_oc.html', suppliers=suppliers, default_date=datetime.now().strftime('%Y-%m-%d'))
            
        created_by = session.get('user_id')
        oc_num = create_purchase_order(supplier_id, order_date, notes, items, status=status, created_by=created_by, payment_method=payment_method)
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
        payment_method = request.form.get('payment_method', 'Efectivo').strip()
        
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
        
        status = request.form.get('status', 'Borrador').strip()
        if status not in ['Borrador', 'Pendiente Aprobación', 'Emitida']:
            status = 'Borrador'
                
        if not supplier_id or not items:
            flash("Debe seleccionar un proveedor y agregar al menos un producto.", "danger")
            suppliers = list_suppliers()
            items_current = get_purchase_order_items(po_id)
            return render_template('editar_oc.html', po=po, items=items_current, suppliers=suppliers)
            
        update_purchase_order(po_id, supplier_id, order_date, notes, items, status=status, payment_method=payment_method)
        flash(f"Orden de Compra {po['oc_number']} actualizada como {status} con éxito.", "success")
        return redirect(url_for('compras.list_oc'))

    suppliers = list_suppliers()
    items = get_purchase_order_items(po_id)
    return render_template('editar_oc.html', po=po, items=items, suppliers=suppliers)

@compras_bp.route('/compras/oc/<int:po_id>/aprobar', methods=['POST'])
def aprobar_oc(po_id):
    """Aprobar una orden de compra pendiente de aprobación"""
    user_role = session.get('role_name')
    user_id = session.get('user_id')
    
    if user_role not in ['Aprobador', 'Gerente', 'Administrativo']:
        flash("No tienes permisos para aprobar órdenes de compra.", "danger")
        return redirect(url_for('compras.list_oc'))
        
    po = get_purchase_order(po_id)
    if not po:
        flash("Orden de Compra no encontrada.", "danger")
        return redirect(url_for('compras.list_oc'))
        
    if po['status'] != 'Pendiente Aprobación':
        flash("Solo se pueden aprobar órdenes de compra en estado 'Pendiente Aprobación'.", "warning")
        return redirect(url_for('compras.list_oc'))
        
    approve_purchase_order(po_id, user_id)
    flash(f"Orden de Compra {po['oc_number']} aprobada con éxito.", "success")
    return redirect(url_for('compras.list_oc'))

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

@compras_bp.route('/api/compras/oc/<int:po_id>/detalle')
def api_oc_detalle(po_id):
    """API para obtener el detalle completo de una Orden de Compra"""
    po = get_purchase_order(po_id)
    if not po:
        return jsonify({"error": "Orden de compra no encontrada"}), 404
    items = get_purchase_order_items(po_id)
    return jsonify({
        "order": po,
        "items": items
    })

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
         Paragraph("Forma de Pago:", label_style), Paragraph(po.get("payment_method") or "Efectivo", value_style)],
        [Paragraph("Estado:", label_style), Paragraph(po["status"], value_style),
         Paragraph("Creado por:", label_style), Paragraph(po.get("creator_name") or "-", value_style)],
        [Paragraph("Aprobado por:", label_style), Paragraph(po.get("approver_name") or "-", value_style),
         Paragraph("", label_style), Paragraph("", value_style)]
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
        as_attachment=False,
        download_name=f"Orden_Compra_{po['oc_number']}.pdf",
        mimetype="application/pdf"
    )


# ─── CUENTAS POR PAGAR ────────────────────────────────────────────────────────

@compras_bp.route('/compras/cuentas-por-pagar')
def cuentas_por_pagar():
    """Listado de facturas de proveedores: pendientes, vencidas, sin factura y pagadas."""
    # Actualizar estados vencidos automáticamente
    update_invoice_payment_status()

    filtro = request.args.get('filtro', 'todas')
    filtro_map = {
        'pendiente':   'Pendiente',
        'vencida':     'Vencida',
        'sin_factura': 'Sin Factura',
        'pagada':      'Pagada',
    }
    status_filter = filtro_map.get(filtro)  # None = todas

    invoices          = list_purchase_invoices(status_filter)
    guias_sin_factura = list_entries_missing_invoice()
    all_invoices      = list_purchase_invoices()
    suppliers         = list_suppliers()
    pos               = list_purchase_orders()
    bank_accounts     = list_bank_accounts()

    n_vencidas       = sum(1 for i in all_invoices if i['payment_status'] == 'Vencida')
    n_pendientes     = sum(1 for i in all_invoices if i['payment_status'] == 'Pendiente')
    n_sin_factura    = len(guias_sin_factura)
    total_pendiente  = sum(
        (i['invoice_amount'] or 0) for i in all_invoices
        if i['payment_status'] in ('Pendiente', 'Vencida', 'Sin Factura')
    )

    stats = {
        'n_vencidas':    n_vencidas,
        'n_pendientes':  n_pendientes,
        'n_sin_factura': n_sin_factura,
        'total_pendiente': total_pendiente,
    }

    return render_template(
        'compras_cuentas_pagar.html',
        invoices=invoices,
        guias_sin_factura=guias_sin_factura,
        suppliers=suppliers,
        purchase_orders=pos,
        bank_accounts=bank_accounts,
        stats=stats,
        filtro_activo=filtro,
    )


@compras_bp.route('/compras/facturas/nueva', methods=['POST'])
def nueva_factura_proveedor():
    """Registra y sube una factura de proveedor vinculada a una guía/recepción, OC o directa."""
    supplier_id        = request.form.get('supplier_id', type=int)
    inventory_entry_id = request.form.get('inventory_entry_id', type=int) or None
    purchase_order_id  = request.form.get('purchase_order_id', type=int) or None
    invoice_number     = (request.form.get('invoice_number') or '').strip()
    invoice_amount     = request.form.get('invoice_amount', type=float) or 0.0
    invoice_date       = request.form.get('invoice_date', date.today().isoformat())
    due_date           = (request.form.get('due_date') or '').strip()
    notes              = request.form.get('notes', '')
    payment_status     = request.form.get('payment_status', 'Pendiente')  # 'Pendiente' o 'Pagada'
    bank_account_id    = request.form.get('bank_account_id', type=int) or None

    # Upload de factura
    doc_file_path = None
    doc_file = request.files.get('document_file')
    if doc_file and doc_file.filename:
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'documentos_compra')
        os.makedirs(upload_dir, exist_ok=True)
        from werkzeug.utils import secure_filename
        ext = os.path.splitext(doc_file.filename)[1].lower()
        filename = secure_filename(f"factura_{invoice_number or 'doc'}_{date.today().isoformat()}{ext}")
        doc_file.save(os.path.join(upload_dir, filename))
        doc_file_path = f"documentos_compra/{filename}"

    # Si se marca como pagada al momento de cargar
    payment_date       = None
    payment_amount     = None
    payment_method     = None
    payment_proof_path = None
    if payment_status == 'Pagada':
        if not bank_account_id:
            flash("Debes seleccionar la cuenta bancaria de la empresa con la que se pagó la factura para poder registrarla como pagada.", "danger")
            return redirect(url_for('compras.cuentas_por_pagar'))
        payment_date   = request.form.get('payment_date', date.today().isoformat())
        payment_amount = invoice_amount
        payment_method = request.form.get('payment_method', 'Transferencia bancaria')
        proof_file     = request.files.get('payment_proof_file')
        if proof_file and proof_file.filename:
            upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'comprobantes_pago')
            os.makedirs(upload_dir, exist_ok=True)
            from werkzeug.utils import secure_filename
            ext = os.path.splitext(proof_file.filename)[1].lower()
            filename = secure_filename(f"comprobante_{invoice_number}_{payment_date}{ext}")
            proof_file.save(os.path.join(upload_dir, filename))
            payment_proof_path = f"comprobantes_pago/{filename}"

    inv_id = create_purchase_invoice({
        'inventory_entry_id': inventory_entry_id,
        'purchase_order_id':  purchase_order_id,
        'supplier_id':        supplier_id,
        'invoice_number':     invoice_number,
        'invoice_amount':     invoice_amount,
        'invoice_date':       invoice_date,
        'due_date':           due_date,
        'document_file':      doc_file_path,
        'payment_status':     payment_status,
        'bank_account_id':    bank_account_id,
        'notes':              notes,
    })

    if payment_status == 'Pagada':
        register_purchase_payment(inv_id, {
            'payment_date':       payment_date,
            'payment_amount':     payment_amount,
            'payment_method':     payment_method,
            'bank_account_id':    bank_account_id,
            'payment_proof_file': payment_proof_path,
            'payment_notes':      'Registrado pagado al cargar factura',
        })

    flash(f"Factura #{invoice_number} cargada y registrada con éxito.", "success")
    return redirect(url_for('compras.cuentas_por_pagar'))


@compras_bp.route('/compras/facturas/<int:invoice_id>/registrar-pago', methods=['POST'])
def registrar_pago_factura(invoice_id):
    """Registra el pago de una factura de proveedor con cuenta bancaria y comprobante."""
    inv = get_purchase_invoice(invoice_id)
    if not inv:
        flash("Factura no encontrada.", "danger")
        return redirect(url_for('compras.cuentas_por_pagar'))

    bank_account_id = request.form.get('bank_account_id', type=int) or None
    if not bank_account_id:
        flash("Debes seleccionar la cuenta bancaria de la empresa con la que se realizó el pago para poder cerrar la transacción.", "danger")
        return redirect(url_for('compras.cuentas_por_pagar'))

    payment_date    = request.form.get('payment_date', date.today().isoformat())
    payment_amount  = request.form.get('payment_amount', type=float) or inv['invoice_amount'] or 0
    payment_method  = request.form.get('payment_method', 'Transferencia bancaria')
    payment_notes   = request.form.get('payment_notes', '')
    invoice_number  = request.form.get('invoice_number', inv.get('invoice_number', ''))

    # Upload del comprobante
    proof_path = inv.get('payment_proof_file')
    proof_file = request.files.get('payment_proof_file')
    if proof_file and proof_file.filename:
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'comprobantes_pago')
        os.makedirs(upload_dir, exist_ok=True)
        from werkzeug.utils import secure_filename
        ext      = os.path.splitext(proof_file.filename)[1].lower()
        filename = secure_filename(f"comprobante_{invoice_id}_{payment_date}{ext}")
        proof_file.save(os.path.join(upload_dir, filename))
        proof_path = f"comprobantes_pago/{filename}"

    ok = register_purchase_payment(invoice_id, {
        'payment_date':       payment_date,
        'payment_amount':     payment_amount,
        'payment_method':     payment_method,
        'bank_account_id':    bank_account_id,
        'payment_proof_file': proof_path,
        'payment_notes':      payment_notes,
    })

    # Si el N° de factura cambió (era guía de despacho y ahora llega la factura), actualizarlo
    if invoice_number and invoice_number != (inv.get('invoice_number') or ''):
        from db import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE purchase_invoices SET invoice_number = %s WHERE id = %s",
                    (invoice_number, invoice_id)
                )
                conn.commit()

    if ok:
        flash(f"Pago registrado correctamente para la factura #{invoice_number or invoice_id}.", "success")
    else:
        flash("No se pudo registrar el pago. Intenta nuevamente.", "danger")

    return redirect(url_for('compras.cuentas_por_pagar'))



@compras_bp.route('/api/compras/facturas/pendientes/count')
def api_pending_invoices_count():
    """API: devuelve la cantidad de facturas pendientes/vencidas (para badge del menú)."""
    n = count_pending_invoices()
    return jsonify({'count': n})

