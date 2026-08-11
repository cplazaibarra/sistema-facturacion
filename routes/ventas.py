from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from datetime import datetime
from db import (
    get_page_data,
    list_sales,
    get_sales_metrics,
    insert_sales_entry,
    list_sales_entries,
    list_roles,
    upsert_sale_payment
)

ventas_bp = Blueprint('ventas', __name__)

@ventas_bp.route('/proyeccion-ventas')
def proyeccion_ventas():
    """Módulo de Proyección de Ventas"""
    proyeccion_stats = get_page_data("proyeccion_stats")
    proyeccion_table = get_page_data("proyeccion_table")
    proyeccion_insights = get_page_data("proyeccion_insights")
    proyeccion_chart = get_page_data("proyeccion_chart")
    return render_template(
        'proyeccion_ventas.html',
        proyeccion_stats=proyeccion_stats,
        proyeccion_table=proyeccion_table,
        proyeccion_insights=proyeccion_insights,
        proyeccion_chart=proyeccion_chart,
    )

@ventas_bp.route('/ventas')
def ventas():
    """Módulo de Ventas"""
    # Get filter parameters
    filters = {}
    if request.args.get('status'):
        filters['status'] = request.args.get('status')
    if request.args.get('customer_name'):
        filters['customer_name'] = request.args.get('customer_name')
    if request.args.get('date_from'):
        filters['date_from'] = request.args.get('date_from')
    if request.args.get('date_to'):
        filters['date_to'] = request.args.get('date_to')

    # Get sales from database
    sales_list = list_sales(filters if filters else None)
    today_str = datetime.today().strftime('%Y-%m-%d')
    # Format sales for template
    ventas_records = []
    for sale in sales_list:
        raw_p_status = sale.get("payment_status") or "Pendiente"
        due_date = sale.get("invoice_due_date") or ""
        
        # Calcular si está retrasada
        calculated_payment_status = raw_p_status
        if raw_p_status != "Pagado" and due_date and due_date != "-":
            if due_date < today_str:
                calculated_payment_status = "Retrasada"

        ventas_records.append({
            "id": sale["id"],
            "sale_number": sale["sale_number"],
            "customer": {
                "name": sale["customer_name"],
                "email": sale.get("customer_email", ""),
                "initials": sale.get("customer_initials", ""),
            },
            "date": sale["sale_date"],
            "time": sale["sale_time"],
            "products": sale["products"],
            "total": f"${sale['total_amount']:.2f}",
            "payment_status": calculated_payment_status,
            "invoice_due_date": sale.get("invoice_due_date") or "-",
            "payment_date": sale.get("payment_date") or "-",
            "status": {
                "label": sale["status"],
                "level": "success" if sale["status"] == "Completada" else "warning" if sale["status"] == "Pendiente" else "danger"
            },
            "seller": {
                "name": sale["seller_name"],
                "initials": sale.get("seller_initials", "")
            },
        })

    # Get metrics from database
    metrics = get_sales_metrics()
    ventas_metrics = [
        {
            "icon": "<i class=\"fa-solid fa-money-bill-trend-up\"></i>",
            "value": f"${metrics['ventas_hoy']:.0f}",
            "label": "Ventas Hoy",
            "secondary": f"{metrics['ventas_completadas']} ventas totales",
            "color": "blue",
        },
        {
            "icon": "<i class=\"fa-solid fa-circle-check\"></i>",
            "value": str(metrics['ventas_completadas']),
            "label": "Ventas Completadas",
            "secondary": f"{metrics['ventas_pendientes']} pendientes",
            "color": "purple",
        },
        {
            "icon": "<i class=\"fa-solid fa-hourglass-half\"></i>",
            "value": str(metrics['ventas_pendientes']),
            "label": "Ventas Pendientes",
            "secondary": "por procesar",
            "color": "orange",
        },
        {
            "icon": "<i class=\"fa-solid fa-users\"></i>",
            "value": str(metrics['clientes_activos']),
            "label": "Clientes Activos",
            "secondary": "clientes únicos",
            "color": "green",
        },
    ]

    roles = list_roles()
    return render_template(
        'ventas.html',
        ventas_metrics=ventas_metrics,
        ventas_records=ventas_records,
        roles=roles,
    )

@ventas_bp.route('/ventas/registrar-pago', methods=['POST'])
def registrar_pago_venta():
    """Registrar o actualizar el pago de una factura de venta"""
    import os
    from werkzeug.utils import secure_filename
    from flask import current_app, flash
    from db import get_connection

    sale_id = request.form.get('sale_id', type=int)
    payment_status = request.form.get('payment_status')  # 'Pendiente' o 'Pagado'
    invoice_due_date = request.form.get('invoice_due_date')
    payment_date = request.form.get('payment_date') if payment_status == 'Pagado' else None

    if not sale_id:
        flash('No se especificó un ID de venta válido.', 'danger')
        return redirect(url_for('ventas.ventas'))

    # Subir comprobante si existe y el estado es Pagado
    payment_proof_file = None
    file = request.files.get('payment_file')
    if payment_status == 'Pagado' and file and file.filename:
        safe_name = secure_filename(file.filename)
        ext = os.path.splitext(safe_name)[1]
        filename = f"comprobante_venta_{sale_id}_{int(datetime.utcnow().timestamp())}{ext}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        payment_proof_file = f"/uploads/{filename}"

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Obtener la venta
            cur.execute("SELECT total_amount, sale_date FROM sales WHERE id = %s", (sale_id,))
            sale_row = cur.fetchone()
            if not sale_row:
                flash('Venta no encontrada.', 'danger')
                return redirect(url_for('ventas.ventas'))
            
            total_amount = sale_row["total_amount"]
            sale_date = sale_row["sale_date"]

            # 2. Actualizar el estado de pago principal en la tabla sales
            cur.execute(
                "UPDATE sales SET payment_status = %s WHERE id = %s",
                (payment_status, sale_id)
            )

            # 3. Guardar en la tabla sale_payments (upsert)
            payment_data = {
                "invoice_number": f"FACT-{sale_id:05d}",
                "invoice_amount": total_amount,
                "invoice_due_date": invoice_due_date or sale_date,
                "invoice_file": None,
                "payment_proof_file": payment_proof_file,
                "payment_amount": total_amount if payment_status == 'Pagado' else 0.0,
                "payment_date": payment_date,
                "seller_uploaded_at": datetime.utcnow().isoformat(),
                "payment_uploaded_at": datetime.utcnow().isoformat() if payment_status == 'Pagado' else None,
                "accounting_approved": 1 if payment_status == 'Pagado' else 0,
                "accounting_approved_by": "Sistema",
                "accounting_approved_at": datetime.utcnow().isoformat() if payment_status == 'Pagado' else None,
                "accounting_comment": "Pago registrado desde panel rápido de Ventas",
                "status": payment_status,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Utilizar upsert_sale_payment para guardar los datos de pago
            upsert_sale_payment(sale_id, payment_data)

        conn.commit()

    flash(f'Estado de pago actualizado correctamente para la venta.', 'success')
    return redirect(url_for('ventas.ventas'))

@ventas_bp.route('/ventas/reportes')
def ventas_reportes():
    """Reportes de ventas"""
    return render_template('ventas_reportes.html')

@ventas_bp.route('/ingreso-ventas', methods=['GET', 'POST'])
def ingreso_ventas():
    """Ingreso manual de ventas"""
    payment_status_options = get_page_data("sales_payment_status_options")
    payment_method_options = get_page_data("sales_payment_method_options")
    delivery_status_options = get_page_data("sales_delivery_status_options")

    if request.method == 'POST':
        quantity = int(request.form.get('quantity', 0) or 0)
        unit_price = float(request.form.get('unit_price', 0) or 0)
        total_price = round(quantity * unit_price, 2)

        entry = {
            "sku": request.form.get('sku', '').strip(),
            "product_name": request.form.get('product_name', '').strip(),
            "quantity": quantity,
            "unit_price": unit_price,
            "total_price": total_price,
            "sale_date": request.form.get('sale_date', '').strip(),
            "delivery_date": request.form.get('delivery_date', '').strip(),
            "payment_status": request.form.get('payment_status', '').strip(),
            "delivery_status": request.form.get('delivery_status', '').strip(),
            "payment_method": request.form.get('payment_method', '').strip(),
            "customer_name": request.form.get('customer_name', '').strip(),
            "seller_name": request.form.get('seller_name', '').strip(),
            "notes": request.form.get('notes', '').strip(),
            "created_at": datetime.utcnow().isoformat(timespec='seconds'),
        }

        if entry["sku"] and entry["product_name"] and entry["sale_date"]:
            insert_sales_entry(entry)

        return redirect(url_for('ventas.ingreso_ventas'))

    entries = list_sales_entries()
    return render_template(
        'ingreso_ventas.html',
        payment_status_options=payment_status_options,
        payment_method_options=payment_method_options,
        delivery_status_options=delivery_status_options,
        entries=entries,
    )
