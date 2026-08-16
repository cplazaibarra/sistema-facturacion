from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, flash
from datetime import datetime
from db import (
    get_page_data,
    list_sales,
    get_sales_metrics,
    insert_sales_entry,
    list_sales_entries,
    list_roles,
    upsert_sale_payment,
    list_products,
    insert_sale,
    get_sale,
    update_sale
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
    from db import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            for sale in sales_list:
                raw_p_status = sale.get("payment_status") or "Pendiente"
                due_date = sale.get("invoice_due_date") or ""
                
                # Calcular si está retrasada
                calculated_payment_status = raw_p_status
                if raw_p_status != "Pagado" and due_date and due_date != "-":
                    if due_date < today_str:
                        calculated_payment_status = "Retrasada"

                # Obtener historial de estado
                cur.execute(
                    "SELECT status, user_name, changed_at, comment FROM sales_status_history WHERE sale_id = %s ORDER BY id DESC",
                    (sale["id"],)
                )
                history = [dict(row) for row in cur.fetchall()]

                # Obtener historial de cobros/pagos
                cur.execute(
                    "SELECT action, user_name, changed_at, details FROM sales_payment_history WHERE sale_id = %s ORDER BY id DESC",
                    (sale["id"],)
                )
                payment_history = [dict(row) for row in cur.fetchall()]

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
                    "payment_proof_file": sale.get("payment_proof_file") or "",
                    "invoice_number": sale.get("invoice_number") or "",
                    "invoice_file": sale.get("invoice_file") or "",
                    "status": {
                        "label": sale["status"],
                        "level": "success" if sale["status"] == "Completada" else "warning" if sale["status"] == "Pendiente" else "info" if sale["status"] == "Cotización" else "danger"
                    },
                    "seller": {
                        "name": sale["seller_name"],
                        "initials": sale.get("seller_initials", "")
                    },
                    "history": history,
                    "payment_history": payment_history
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
            "icon": "<i class=\"fa-solid fa-clock\"></i>",
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
    from flask import current_app, flash, session
    from db import get_connection, upsert_sale_payment

    sale_id = request.form.get('sale_id', type=int)
    payment_status = request.form.get('payment_status')  # 'Pendiente' o 'Pagado'
    
    # Validación de rol: si es digitador/vendedor y pone "Pagado", pasa a "Pendiente Aprobación Pago"
    user_role = session.get('role_name')
    if payment_status == 'Pagado' and user_role not in ['Aprobador', 'Gerente', 'Administrativo']:
        payment_status = 'Pendiente Aprobación Pago'
        
    invoice_due_date = request.form.get('invoice_due_date')
    payment_date = request.form.get('payment_date') if payment_status in ['Pagado', 'Pendiente Aprobación Pago'] else None

    if not sale_id:
        flash('No se especificó un ID de venta válido.', 'danger')
        return redirect(url_for('ventas.ventas'))

    user_responsible = session.get('full_name', 'Administrador')

    # Subir comprobante si existe y el estado es Pagado o Pendiente Aprobación
    payment_proof_file = None
    file = request.files.get('payment_file')
    file_uploaded = False
    if payment_status in ['Pagado', 'Pendiente Aprobación Pago'] and file and file.filename:
        safe_name = secure_filename(file.filename)
        ext = os.path.splitext(safe_name)[1]
        filename = f"comprobante_venta_{sale_id}_{int(datetime.utcnow().timestamp())}{ext}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        payment_proof_file = f"/uploads/{filename}"
        file_uploaded = True

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Obtener la venta, su estado anterior y el pago anterior para auditar diferencias
            cur.execute("SELECT total_amount, sale_date, status, payment_status FROM sales WHERE id = %s", (sale_id,))
            sale_row = cur.fetchone()
            if not sale_row:
                flash('Venta no encontrada.', 'danger')
                return redirect(url_for('ventas.ventas'))
            
            total_amount = sale_row["total_amount"]
            sale_date = sale_row["sale_date"]
            old_sale_status = sale_row["status"]
            old_payment_status = sale_row["payment_status"]

            # Obtener datos de pago anteriores
            cur.execute("SELECT invoice_due_date, payment_date, payment_proof_file FROM sale_payments WHERE sale_id = %s", (sale_id,))
            old_payment_row = cur.fetchone()
            old_due_date = old_payment_row["invoice_due_date"] if old_payment_row else None
            old_payment_date = old_payment_row["payment_date"] if old_payment_row else None
            old_proof_file = old_payment_row["payment_proof_file"] if old_payment_row else None

            # Si el estado de pago cambia a Pendiente
            if payment_status == 'Pendiente' and old_payment_status in ['Pagado', 'Pendiente Aprobación Pago']:
                # Registrar historial de borrado de comprobante
                cur.execute(
                    """
                    INSERT INTO sales_payment_history (sale_id, action, user_name, changed_at, details)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        sale_id,
                        'Pago Revertido / Comprobante Eliminado',
                        user_responsible,
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'Se cambió el estado a Pendiente y se eliminó la vinculación del comprobante.'
                    )
                )
            elif payment_status in ['Pagado', 'Pendiente Aprobación Pago']:
                if old_payment_status not in ['Pagado', 'Pendiente Aprobación Pago'] or file_uploaded:
                    # Registrar historial de subida o actualización del comprobante de pago
                    action_lbl = 'Comprobante Subido' if old_payment_status not in ['Pagado', 'Pendiente Aprobación Pago'] else 'Comprobante Actualizado'
                    cur.execute(
                        """
                        INSERT INTO sales_payment_history (sale_id, action, user_name, changed_at, details)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            sale_id,
                            action_lbl,
                            user_responsible,
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            f'Se subió un nuevo comprobante de pago. Estado: {payment_status}. Fecha real de pago: {payment_date}'
                        )
                    )
                elif old_payment_date != payment_date:
                    # Registrar historial de modificación de fecha de pago
                    cur.execute(
                        """
                        INSERT INTO sales_payment_history (sale_id, action, user_name, changed_at, details)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            sale_id,
                            'Fecha Pago Modificada',
                            user_responsible,
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            f'Se modificó la fecha de pago de {old_payment_date} a {payment_date}.'
                        )
                    )

            # Auditar si cambió la fecha de vencimiento
            if old_due_date != invoice_due_date:
                cur.execute(
                    """
                    INSERT INTO sales_payment_history (sale_id, action, user_name, changed_at, details)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        sale_id,
                        'Fecha Vencimiento Modificada',
                        user_responsible,
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        f'Se modificó la fecha de vencimiento (cobro) de {old_due_date} a {invoice_due_date}.'
                    )
                )

            # 2. Actualizar el estado de pago principal en la tabla sales
            cur.execute(
                "UPDATE sales SET payment_status = %s WHERE id = %s",
                (payment_status, sale_id)
            )

            # Automatización: Si el pago se registró como "Pagado" y la venta no estaba Completada
            auto_completed = False
            if payment_status == 'Pagado' and old_sale_status != 'Completada':
                cur.execute(
                    "UPDATE sales SET status = 'Completada' WHERE id = %s",
                    (sale_id,)
                )
                auto_completed = True
                
                # Registrar historial de estado por cambio automático del sistema
                cur.execute(
                    """
                    INSERT INTO sales_status_history (sale_id, status, user_name, changed_at, comment)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        sale_id,
                        'Completada',
                        f'Sistema (Auto por {user_responsible})',
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'Estado cambiado automáticamente a Completada tras subida de comprobante'
                    )
                )

            # Si es reversión a Pendiente, mantener el archivo anterior a menos que explícitamente se borre. 
            final_proof_file = payment_proof_file if payment_proof_file else (old_proof_file if payment_status in ['Pagado', 'Pendiente Aprobación Pago'] else None)

            # 3. Guardar en la tabla sale_payments (upsert)
            payment_data = {
                "invoice_number": f"FACT-{sale_id:05d}",
                "invoice_amount": total_amount,
                "invoice_due_date": invoice_due_date or sale_date,
                "invoice_file": None,
                "payment_proof_file": final_proof_file,
                "payment_amount": total_amount if payment_status in ['Pagado', 'Pendiente Aprobación Pago'] else 0.0,
                "payment_date": payment_date,
                "seller_uploaded_at": datetime.utcnow().isoformat(),
                "payment_uploaded_at": datetime.utcnow().isoformat() if payment_status in ['Pagado', 'Pendiente Aprobación Pago'] else None,
                "accounting_approved": 1 if payment_status == 'Pagado' else 0,
                "accounting_approved_by": user_responsible if payment_status == 'Pagado' else None,
                "accounting_approved_at": datetime.utcnow().isoformat() if payment_status == 'Pagado' else None,
                "accounting_comment": "Pago registrado y aprobado automáticamente" if payment_status == 'Pagado' else "Pago registrado por Digitador, pendiente de validación por Aprobador",
                "status": payment_status,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Utilizar upsert_sale_payment para guardar los datos de pago
            upsert_sale_payment(sale_id, payment_data)

        conn.commit()

    if auto_completed:
        flash('El pago fue registrado y la venta se marcó automáticamente como Completada.', 'success')
    elif payment_status == 'Pendiente Aprobación Pago':
        flash('El pago ha sido registrado y enviado a aprobación.', 'warning')
    else:
        flash('Estado de pago actualizado correctamente para la venta.', 'success')
    return redirect(url_for('ventas.ventas'))

@ventas_bp.route('/ventas/pago/<int:sale_id>/aprobar', methods=['POST'])
def aprobar_pago_venta(sale_id):
    """Aprobar un pago pendiente de validación por parte del Aprobador"""
    user_role = session.get('role_name')
    user_responsible = session.get('full_name', 'Administrador')
    
    if user_role not in ['Aprobador', 'Gerente', 'Administrativo']:
        flash("No tienes permisos para aprobar pagos.", "danger")
        return redirect(url_for('ventas.ventas'))
        
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Obtener la venta
            cur.execute("SELECT payment_status, total_amount FROM sales WHERE id = %s", (sale_id,))
            sale_row = cur.fetchone()
            if not sale_row:
                flash("Venta no encontrada.", "danger")
                return redirect(url_for('ventas.ventas'))
                
            if sale_row['payment_status'] != 'Pendiente Aprobación Pago':
                flash("El pago de esta venta no está pendiente de aprobación.", "warning")
                return redirect(url_for('ventas.ventas'))
                
            # 2. Actualizar el estado de pago principal a 'Pagado' y el estado de la venta a 'Completada'
            cur.execute("UPDATE sales SET payment_status = 'Pagado', status = 'Completada' WHERE id = %s", (sale_id,))
            
            # 3. Actualizar la tabla sale_payments
            cur.execute(
                """
                UPDATE sale_payments
                SET status = 'Pagado',
                    accounting_approved = 1,
                    accounting_approved_by = %s,
                    accounting_approved_at = %s,
                    payment_amount = %s,
                    updated_at = %s
                WHERE sale_id = %s
                """,
                (user_responsible, datetime.utcnow().isoformat(), sale_row['total_amount'], datetime.utcnow().isoformat(), sale_id)
            )
            
            # 4. Registrar en historial de estado
            cur.execute(
                """
                INSERT INTO sales_status_history (sale_id, status, user_name, changed_at, comment)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    sale_id,
                    'Completada',
                    f'Sistema (Aprobación por {user_responsible})',
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'Estado cambiado a Completada tras aprobación de pago'
                )
            )
            
            # 5. Registrar en historial de pagos
            cur.execute(
                """
                INSERT INTO sales_payment_history (sale_id, action, user_name, changed_at, details)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    sale_id,
                    'Pago Aprobado',
                    user_responsible,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'El pago fue validado y aprobado formalmente.'
                )
            )
        conn.commit()
        
    flash("Pago aprobado y verificado correctamente.", "success")
    return redirect(url_for('ventas.ventas'))

@ventas_bp.route('/ventas/actualizar-estado', methods=['POST'])
def actualizar_estado_venta():
    """Actualizar el estado general de la venta (Completada, Pendiente, Cancelada)"""
    import os
    from werkzeug.utils import secure_filename
    from flask import current_app, flash, session
    from db import get_connection

    sale_id = request.form.get('sale_id', type=int)
    new_status = request.form.get('status')
    invoice_number = request.form.get('invoice_number')

    if not sale_id or not new_status:
        flash('Datos inválidos para actualizar el estado.', 'danger')
        return redirect(url_for('ventas.ventas'))

    user_responsible = session.get('full_name', 'Administrador')

    # Subir factura física si existe
    invoice_file_path = None
    file = request.files.get('invoice_file')
    if file and file.filename:
        safe_name = secure_filename(file.filename)
        ext = os.path.splitext(safe_name)[1]
        filename = f"factura_venta_{sale_id}_{int(datetime.utcnow().timestamp())}{ext}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        invoice_file_path = f"/uploads/{filename}"

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Registrar el historial de cambio de estado
            cur.execute(
                """
                INSERT INTO sales_status_history (sale_id, status, user_name, changed_at, comment)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    sale_id,
                    new_status,
                    user_responsible,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    f'Estado cambiado manualmente a {new_status}' + (f' (Nº Factura: {invoice_number})' if invoice_number else '')
                )
            )

            # 2. Actualizar el estado en la tabla de ventas
            cur.execute(
                "UPDATE sales SET status = %s WHERE id = %s",
                (new_status, sale_id)
            )

            # 3. Guardar el número de factura y el archivo adjunto de la factura en sale_payments
            # Primero verificar si existe un registro de pago para esa venta
            cur.execute("SELECT id FROM sale_payments WHERE sale_id = %s", (sale_id,))
            payment_row = cur.fetchone()

            if payment_row:
                # Si existe, actualizamos
                update_fields = []
                params = []
                if invoice_number is not None:
                    update_fields.append("invoice_number = %s")
                    params.append(invoice_number)
                if invoice_file_path:
                    update_fields.append("invoice_file = %s")
                    params.append(invoice_file_path)

                if update_fields:
                    params.append(sale_id)
                    cur.execute(
                        f"UPDATE sale_payments SET {', '.join(update_fields)} WHERE sale_id = %s",
                        tuple(params)
                    )
            else:
                # Si no existe, creamos un registro inicial de pagos
                cur.execute(
                    """
                    INSERT INTO sale_payments (sale_id, invoice_number, invoice_file, status)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (sale_id, invoice_number, invoice_file_path, 'Factura pendiente')
                )

            # 4. Registrar en el historial de cobros y facturas si se agrega número de factura o archivo
            if invoice_number or invoice_file_path:
                details_list = []
                if invoice_number:
                    details_list.append(f"Número de Factura: {invoice_number}")
                if invoice_file_path:
                    details_list.append("Archivo de Factura física adjuntado")
                
                cur.execute(
                    """
                    INSERT INTO sales_payment_history (sale_id, action, user_name, changed_at, details)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        sale_id,
                        'Factura Modificada',
                        user_responsible,
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        ', '.join(details_list)
                    )
                )

        conn.commit()

    flash(f'El estado de la venta se actualizó a "{new_status}" con éxito.', 'success')
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

@ventas_bp.route('/ventas/cotizacion/nueva', methods=['GET', 'POST'])
def nueva_cotizacion():
    """Crear una nueva cotización"""
    from db import get_connection
    if request.method == 'POST':
        customer_name = request.form.get('customer_name', '').strip()
        customer_email = request.form.get('customer_email', '').strip()
        customer_category = request.form.get('customer_category', '').strip()
        sale_date = request.form.get('sale_date', '').strip()
        notes = request.form.get('notes', '').strip()
        
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        
        # Guardar / Actualizar categoría del cliente
        if customer_email and customer_category:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO client_categories (email, category_id)
                        VALUES (%s, %s)
                        ON CONFLICT (email) DO UPDATE SET category_id = EXCLUDED.category_id
                        """,
                        (customer_email, customer_category)
                    )
                conn.commit()

        # Obtener nombres de productos y construir el JSON
        products_list = []
        total_amount = 0.0
        
        # Cargar productos para buscar nombres
        all_prods = {str(p['id']): p for p in list_products()}
        
        for p_id, qty, price in zip(product_ids, quantities, unit_prices):
            if not p_id or not qty or not price:
                continue
            qty_int = int(qty)
            price_float = float(price)
            subtotal = qty_int * price_float
            total_amount += subtotal
            
            prod_info = all_prods.get(p_id, {})
            products_list.append({
                "product_id": int(p_id),
                "product_name": prod_info.get('name', 'Producto Desconocido'),
                "quantity": qty_int,
                "price": price_float,
                "subtotal": subtotal
            })
            
        if not products_list:
            flash("Debe agregar al menos un producto a la cotización.", "warning")
            return redirect(url_for('ventas.nueva_cotizacion'))
            
        # Generar número de cotización
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(MAX(id), 0) + 1 as next_id FROM sales")
                next_id = cur.fetchone()["next_id"]
                sale_number = f"COT-{next_id:05d}"
                
        # Construir registro de cotización
        sale_data = {
            "sale_number": sale_number,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_initials": "".join([part[0].upper() for part in customer_name.split() if part])[:3],
            "sale_date": sale_date,
            "sale_time": datetime.now().strftime("%H:%M:%S"),
            "products": products_list,
            "total_amount": round(total_amount, 2),
            "status": "Cotización",
            "seller_name": session.get('user_name', 'Vendedor'),
            "seller_initials": session.get('user_initials', 'V'),
            "payment_method": "Cotización",
            "payment_status": "Cotización",
            "delivery_status": "Cotización",
            "notes": notes,
            "created_at": datetime.utcnow().isoformat(timespec='seconds')
        }
        
        insert_sale(sale_data)
        flash("Cotización guardada exitosamente.", "success")
        return redirect(url_for('ventas.ventas'))
        
    products = list_products()
    default_date = datetime.today().strftime('%Y-%m-%d')
    
    # Lógica de construcción de precios por categorías de clientes para la cotización
    config = get_page_data("price_list_config")
    if not config or "categories" not in config:
        config = {
            "base_margin": 20.0,
            "categories": [
                {"id": "cat_0", "name": "Categoría A", "margin": 5.0},
                {"id": "cat_1", "name": "Categoría B", "margin": 10.0},
                {"id": "cat_2", "name": "Categoría C", "margin": 15.0},
                {"id": "cat_3", "name": "Categoría D", "margin": 20.0}
            ]
        }
        
    vpp_map = {}
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT product_id, SUM(quantity) as total_qty, SUM(total) as total_spent
                FROM inventory_entry_items
                GROUP BY product_id
                """
            )
            for row in cur.fetchall():
                qty = row["total_qty"] or 0
                spent = row["total_spent"] or 0.0
                if qty > 0:
                    vpp_map[row["product_id"]] = spent / qty

    catalog_prices = {}
    inventory_items = get_page_data("inventory_items") or []
    for item in inventory_items:
        catalog_prices[item["code"]] = item.get("price", 0.0)

    prod_margins_map = {}
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM product_margins")
            for row in cur.fetchall():
                prod_margins_map[row["product_sku"]] = dict(row)

    products_prices_map = {}
    for p in products:
        sku = p["sku"]
        p_id = p["id"]
        
        vpp = vpp_map.get(p_id)
        if vpp is None:
            vpp = catalog_prices.get(sku, 0.0)
            
        m = prod_margins_map.get(sku)
        product_cat_margins = {}
        if m:
            base_margin = m["base_margin"]
            product_cat_margins = m["category_margins"] or {}
        else:
            base_margin = config["base_margin"]
            
        price_base = vpp * (1 + base_margin / 100)
        
        prices = {
            "default": round(price_base, 2)  # fallback si no se selecciona categoría
        }
        for cat in config["categories"]:
            cat_id = cat["id"]
            margin = product_cat_margins.get(cat_id)
            if margin is None:
                margin = cat["margin"]
                
            price_final = price_base * (1 + margin / 100)
            prices[cat_id] = round(price_final, 2)
            
        products_prices_map[str(p_id)] = prices

    return render_template(
        'nueva_cotizacion.html',
        products=products,
        default_date=default_date,
        categories=config["categories"],
        products_prices_map=products_prices_map
    )

@ventas_bp.route('/api/clientes/<string:email>/categoria')
def get_client_category(email):
    from db import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT category_id FROM client_categories WHERE email = %s", (email.strip(),))
            row = cur.fetchone()
            if row:
                return jsonify({"email": email, "category_id": row["category_id"]})
    return jsonify({"error": "Cliente no encontrado"}), 404

@ventas_bp.route('/ventas/cotizacion/<int:sale_id>/convertir', methods=['POST'])
def convertir_cotizacion(sale_id):
    """Convertir una cotización a venta real (Pendiente)"""
    from db import get_connection
    sale = get_sale(sale_id)
    if not sale:
        flash("Cotización no encontrada.", "danger")
        return redirect(url_for('ventas.ventas'))
        
    if sale["status"] != "Cotización":
        flash("Esta venta ya ha sido emitida.", "warning")
        return redirect(url_for('ventas.ventas'))
        
    # Generar folio VTA-
    new_sale_number = f"VTA-{sale_id:05d}"
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sales 
                SET status = 'Pendiente', 
                    payment_status = 'Pendiente', 
                    delivery_status = 'Pendiente',
                    payment_method = 'Por definir',
                    sale_number = %s 
                WHERE id = %s
                """,
                (new_sale_number, sale_id)
            )
            # Agregar historial de estado
            cur.execute(
                """
                INSERT INTO sales_status_history (sale_id, status, user_name, changed_at, comment)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    sale_id, 
                    "Pendiente", 
                    session.get('user_name', 'Sistema'), 
                    datetime.utcnow().isoformat(timespec='seconds'),
                    "Convertido desde Cotización"
                )
            )
        conn.commit()
        
    flash(f"Cotización convertida a Venta {new_sale_number} exitosamente.", "success")
    return redirect(url_for('ventas.ventas'))
