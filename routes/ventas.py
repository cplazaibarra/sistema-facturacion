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

def _get_formatted_sales_data():
    sales_list = list_sales(None)
    today_str = datetime.today().strftime('%Y-%m-%d')
    ventas_records_all = []
    from db import get_connection

    # Cargar mapa de clientes para enriquecer datos
    clients_map = {}
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM clients")
            for c in cur.fetchall():
                c_dict = dict(c)
                if c_dict.get("email"):
                    clients_map[c_dict["email"].lower().strip()] = c_dict
                if c_dict.get("razon_social"):
                    clients_map[c_dict["razon_social"].lower().strip()] = c_dict
                if c_dict.get("rut"):
                    clients_map[c_dict["rut"].strip()] = c_dict

            for sale in sales_list:
                raw_p_status = sale.get("payment_status") or "Pendiente"
                due_date = sale.get("invoice_due_date") or ""
                
                calculated_payment_status = raw_p_status
                if raw_p_status != "Pagado" and due_date and due_date != "-":
                    if due_date < today_str:
                        calculated_payment_status = "Retrasada"

                cur.execute(
                    "SELECT status, user_name, changed_at, comment FROM sales_status_history WHERE sale_id = %s ORDER BY id DESC",
                    (sale["id"],)
                )
                history = [dict(row) for row in cur.fetchall()]

                cur.execute(
                    "SELECT action, user_name, changed_at, details FROM sales_payment_history WHERE sale_id = %s ORDER BY id DESC",
                    (sale["id"],)
                )
                payment_history = [dict(row) for row in cur.fetchall()]

                # Obtener el bank_account_id del último pago en sale_payment_items
                cur.execute(
                    "SELECT bank_account_id FROM sale_payment_items WHERE sale_id = %s ORDER BY id DESC LIMIT 1",
                    (sale["id"],)
                )
                bank_acc_row = cur.fetchone()
                bank_account_id = bank_acc_row["bank_account_id"] if bank_acc_row else None

                c_email = (sale.get("customer_email") or "").lower().strip()
                c_name = (sale.get("customer_name") or "").lower().strip()
                c_data = clients_map.get(c_email) or clients_map.get(c_name) or {}

                notes_str = sale.get("notes") or ""
                rut_val = c_data.get("rut") or ""
                dv_val = c_data.get("dv") or ""
                if not rut_val and "RUT:" in notes_str:
                    try:
                        rut_part = notes_str.split("RUT:")[1].split("|")[0].strip()
                        if "-" in rut_part:
                            rut_val, dv_val = rut_part.split("-", 1)
                        else:
                            rut_val = rut_part
                    except Exception:
                        pass

                ventas_records_all.append({
                    "id": sale["id"],
                    "sale_number": sale["sale_number"],
                    "customer": {
                        "id": c_data.get("id"),
                        "rut": rut_val,
                        "dv": dv_val,
                        "name": sale["customer_name"],
                        "email": sale.get("customer_email", ""),
                        "phone": c_data.get("phone", ""),
                        "direccion": c_data.get("direccion", ""),
                        "comuna": c_data.get("comuna", ""),
                        "ciudad": c_data.get("ciudad", ""),
                        "giro": c_data.get("giro", ""),
                        "tipo_compra": c_data.get("tipo_compra", "Del Giro"),
                        "category_id": c_data.get("category_id", ""),
                        "initials": sale.get("customer_initials", ""),
                    },
                    "date": sale["sale_date"],
                    "time": sale["sale_time"],
                    "products": sale["products"],
                    "total": f"${sale['total_amount']:.2f}",
                    "total_raw": sale['total_amount'],
                    "payment_method": sale.get("payment_method") or "Efectivo",
                    "payment_status": calculated_payment_status,
                    "invoice_due_date": sale.get("invoice_due_date") or "-",
                    "payment_date": sale.get("payment_date") or "-",
                    "payment_proof_file": sale.get("payment_proof_file") or "",
                    "invoice_number": sale.get("invoice_number") or "",
                    "invoice_file": sale.get("invoice_file") or "",
                    "notes": sale.get("notes") or "",
                    "bank_account_id": bank_account_id,
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
    return ventas_records_all, today_str


@ventas_bp.route('/ventas')
def ventas():
    """Módulo exclusivo de Ventas"""
    card_filter = request.args.get('filter', '')
    active_filter = card_filter

    ventas_records_all, today_str = _get_formatted_sales_data()

    # Excluir cotizaciones para esta vista
    only_ventas = [r for r in ventas_records_all if r['status']['label'] != 'Cotización' and not str(r['sale_number']).startswith('COT-')]

    count_retrasadas = sum(1 for v in only_ventas if v['payment_status'] == 'Retrasada')

    ventas_records = []
    for record in only_ventas:
        if card_filter == 'Ventas Pendientes':
            if record['status']['label'] == 'Pendiente':
                ventas_records.append(record)
        elif card_filter == 'Ventas Completadas':
            if record['status']['label'] == 'Completada':
                ventas_records.append(record)
        elif card_filter in ['Pago Retrasado', 'Pagos Retrasados', 'Retrasada']:
            if record['payment_status'] == 'Retrasada':
                ventas_records.append(record)
        elif card_filter == 'Ventas Hoy':
            if record['date'] == today_str:
                ventas_records.append(record)
        else:
            ventas_records.append(record)

    # Extraer clientes y productos únicos para filtros
    all_clients = sorted(list(set(v['customer']['name'] for v in only_ventas if v['customer']['name'])))
    all_products_set = set()
    for v in only_ventas:
        for p in v['products']:
            p_name = p.get('product_name') or p.get('name') if isinstance(p, dict) else str(p)
            if p_name:
                all_products_set.add(p_name)
    all_products = sorted(list(all_products_set))

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
            "icon": "<i class=\"fa-solid fa-triangle-exclamation\"></i>",
            "value": str(count_retrasadas),
            "label": "Pago Retrasado",
            "secondary": "pagos vencidos",
            "color": "red",
        },
        {
            "icon": "<i class=\"fa-solid fa-users\"></i>",
            "value": str(metrics['clientes_activos']),
            "label": "Clientes Activos",
            "secondary": "clientes únicos",
            "color": "green",
        },
    ]

    from db import list_bank_accounts
    bank_accounts = [acc for acc in list_bank_accounts() if acc.get("status") == "Activa"]

    roles = list_roles()
    config = get_page_data("price_list_config")
    categories = config.get("categories", [])
    from flask import make_response
    response = make_response(render_template(
        'ventas.html',
        ventas_metrics=ventas_metrics,
        ventas_records=ventas_records,
        all_clients=all_clients,
        all_products=all_products,
        roles=roles,
        categories=categories,
        active_filter=active_filter,
        bank_accounts=bank_accounts,
    ))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response


@ventas_bp.route('/ventas/cotizaciones')
def cotizaciones():
    """Módulo exclusivo de Cotizaciones"""
    card_filter = request.args.get('filter', '')
    active_filter = card_filter

    ventas_records_all, today_str = _get_formatted_sales_data()

    # Incluir únicamente cotizaciones
    only_cotizaciones = [r for r in ventas_records_all if r['status']['label'] == 'Cotización' or str(r['sale_number']).startswith('COT-')]

    cotizaciones_records = []
    for record in only_cotizaciones:
        if card_filter == 'Cotizaciones Hoy':
            if record['date'] == today_str:
                cotizaciones_records.append(record)
        else:
            cotizaciones_records.append(record)

    # Extraer clientes y productos únicos para filtros
    all_clients = sorted(list(set(c['customer']['name'] for c in only_cotizaciones if c['customer']['name'])))
    all_products_set = set()
    for c in only_cotizaciones:
        for p in c['products']:
            p_name = p.get('product_name') or p.get('name') if isinstance(p, dict) else str(p)
            if p_name:
                all_products_set.add(p_name)
    all_products = sorted(list(all_products_set))

    total_amount_cotizaciones = sum(c['total_raw'] for c in only_cotizaciones)
    unique_clients_count = len(set(c['customer']['name'] for c in only_cotizaciones if c['customer']['name']))

    cotizaciones_metrics = [
        {
            "icon": "<i class=\"fa-solid fa-file-invoice-dollar\"></i>",
            "value": str(len(only_cotizaciones)),
            "label": "Total Cotizaciones",
            "secondary": "emitidas en sistema",
            "color": "blue",
        },
        {
            "icon": "<i class=\"fa-solid fa-clock\"></i>",
            "value": str(len(cotizaciones_records)),
            "label": "Cotizaciones Activas",
            "secondary": "pendientes a venta",
            "color": "orange",
        },
        {
            "icon": "<i class=\"fa-solid fa-sack-dollar\"></i>",
            "value": f"${total_amount_cotizaciones:.0f}",
            "label": "Monto Cotizado",
            "secondary": "monto total",
            "color": "green",
        },
        {
            "icon": "<i class=\"fa-solid fa-users\"></i>",
            "value": str(unique_clients_count),
            "label": "Clientes Cotizados",
            "secondary": "receptores únicos",
            "color": "purple",
        },
    ]

    roles = list_roles()
    config = get_page_data("price_list_config")
    categories = config.get("categories", [])
    from flask import make_response
    response = make_response(render_template(
        'cotizaciones.html',
        cotizaciones_metrics=cotizaciones_metrics,
        cotizaciones_records=cotizaciones_records,
        all_clients=all_clients,
        all_products=all_products,
        roles=roles,
        categories=categories,
        active_filter=active_filter,
    ))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response


@ventas_bp.route('/ventas/clientes/guardar_modal', methods=['POST'])
def guardar_cliente_modal():
    """Guardar o actualizar datos de un cliente desde el modal flotante"""
    from db import upsert_client_by_rut, get_connection
    rut = request.form.get('rut', '').strip()
    dv = request.form.get('dv', '').strip()
    razon_social = request.form.get('razon_social', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    tipo_compra = request.form.get('tipo_compra', 'Del Giro').strip()
    category_id = request.form.get('category_id', '').strip()
    direccion = request.form.get('direccion', '').strip()
    giro = request.form.get('giro', '').strip()

    if not razon_social:
        flash("La Razón Social es requerida.", "warning")
        return redirect(request.referrer or url_for('ventas.ventas'))

    if rut:
        upsert_client_by_rut({
            "rut": rut,
            "dv": dv,
            "razon_social": razon_social,
            "email": email,
            "phone": phone,
            "tipo_compra": tipo_compra,
            "category_id": category_id,
            "direccion": direccion,
            "giro": giro
        })
    else:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if email:
                    cur.execute("SELECT id FROM clients WHERE email = %s", (email,))
                    row = cur.fetchone()
                    if row:
                        cur.execute(
                            """
                            UPDATE clients SET razon_social = %s, phone = %s, tipo_compra = %s, category_id = %s, direccion = %s, giro = %s
                            WHERE email = %s
                            """,
                            (razon_social, phone, tipo_compra, category_id, direccion, giro, email)
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO clients (razon_social, email, phone, tipo_compra, category_id, direccion, giro)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            (razon_social, email, phone, tipo_compra, category_id, direccion, giro)
                        )
                else:
                    cur.execute(
                        """
                        INSERT INTO clients (razon_social, email, phone, tipo_compra, category_id, direccion, giro)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (razon_social, email, phone, tipo_compra, category_id, direccion, giro)
                    )
            conn.commit()

    if email and category_id:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO client_categories (email, category_id)
                    VALUES (%s, %s)
                    ON CONFLICT (email) DO UPDATE SET category_id = EXCLUDED.category_id
                    """,
                    (email, category_id)
                )
            conn.commit()

    flash(f"Cliente '{razon_social}' actualizado exitosamente.", "success")
    return redirect(request.referrer or url_for('ventas.ventas'))

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

            # 4. Registrar en la tabla de transacciones de pago (sale_payment_items) si hay comprobante o se marca como Pagado
            if payment_status in ['Pagado', 'Pendiente Aprobación Pago']:
                bank_acc_id_str = request.form.get('bank_account_id')
                bank_account_id = int(bank_acc_id_str) if bank_acc_id_str and bank_acc_id_str.isdigit() else None
                
                # Chequear si ya existe un registro de comprobante en sale_payment_items
                cur.execute(
                    "SELECT id FROM sale_payment_items WHERE sale_id = %s ORDER BY id DESC LIMIT 1",
                    (sale_id,)
                )
                existing_item = cur.fetchone()
                
                if existing_item:
                    # Actualizar
                    cur.execute(
                        """
                        UPDATE sale_payment_items
                        SET payment_amount = %s,
                            payment_date = %s,
                            payment_proof_file = COALESCE(%s, payment_proof_file),
                            bank_account_id = %s,
                            accounting_approved = %s,
                            accounting_approved_by = %s,
                            accounting_approved_at = %s,
                            accounting_comment = %s
                        WHERE id = %s
                        """,
                        (
                            total_amount,
                            payment_date,
                            final_proof_file,
                            bank_account_id,
                            1 if payment_status == 'Pagado' else 0,
                            user_responsible if payment_status == 'Pagado' else None,
                            datetime.utcnow().isoformat() if payment_status == 'Pagado' else None,
                            "Pago verificado y aprobado automáticamente" if payment_status == 'Pagado' else "Pendiente de validación",
                            existing_item["id"]
                        )
                    )
                else:
                    # Insertar nuevo registro
                    cur.execute(
                        """
                        INSERT INTO sale_payment_items (
                            sale_id, payment_amount, payment_date, payment_proof_file, created_at,
                            bank_account_id, accounting_approved, accounting_approved_by, accounting_approved_at, accounting_comment
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            sale_id,
                            total_amount,
                            payment_date,
                            final_proof_file,
                            datetime.utcnow().isoformat(),
                            bank_account_id,
                            1 if payment_status == 'Pagado' else 0,
                            user_responsible if payment_status == 'Pagado' else None,
                            datetime.utcnow().isoformat() if payment_status == 'Pagado' else None,
                            "Pago verificado y aprobado automáticamente" if payment_status == 'Pagado' else "Pendiente de validación"
                        )
                    )

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

    # Validar que si el estado es 'Completada', obligatoriamente exista o se haya subido un archivo de factura/boleta
    if new_status == 'Completada':
        has_file = bool(invoice_file_path)
        if not has_file:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT invoice_file FROM sale_payments WHERE sale_id = %s", (sale_id,))
                    row = cur.fetchone()
                    if row and row.get("invoice_file"):
                        has_file = True

        if not has_file:
            flash("Para marcar la venta como Completada es obligatorio adjuntar el archivo de la Factura o Boleta.", "warning")
            return redirect(url_for('ventas.ventas'))

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
                now_str = datetime.utcnow().isoformat(timespec='seconds')
                cur.execute(
                    """
                    INSERT INTO sale_payments (sale_id, invoice_number, invoice_file, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (sale_id, invoice_number, invoice_file_path, 'Factura pendiente', now_str, now_str)
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
        customer_rut = request.form.get('customer_rut', '').strip()
        customer_dv = request.form.get('customer_dv', '').strip()
        doc_type = request.form.get('doc_type', 'Boleta').strip()
        sale_date = request.form.get('sale_date', '').strip()
        notes = request.form.get('notes', '').strip()
        
        if customer_rut:
            rut_str = f"RUT: {customer_rut}-{customer_dv}" if customer_dv else f"RUT: {customer_rut}"
            notes = f"{rut_str} | Doc: {doc_type}\n{notes}".strip()
        else:
            notes = f"Doc: {doc_type}\n{notes}".strip()
        
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        discounts = request.form.getlist('discount[]')
        
        # Guardar / Actualizar datos del cliente en la base de datos (con RUT como llave primaria)
        from db import upsert_client_by_rut
        if customer_rut:
            upsert_client_by_rut({
                "rut": customer_rut,
                "dv": customer_dv,
                "razon_social": customer_name,
                "email": customer_email,
                "category_id": customer_category
            })

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
        
        for idx, (p_id, qty, price) in enumerate(zip(product_ids, quantities, unit_prices)):
            if not p_id or not qty or not price:
                continue
            qty_int = int(qty)
            price_float = float(price)
            discount_float = float(discounts[idx]) if idx < len(discounts) and discounts[idx] else 0.0
            
            subtotal = qty_int * price_float * (1.0 - (discount_float / 100.0))
            total_amount += subtotal
            
            prod_info = all_prods.get(p_id, {})
            products_list.append({
                "product_id": int(p_id),
                "product_name": prod_info.get('name', 'Producto Desconocido'),
                "quantity": qty_int,
                "price": price_float,
                "discount": discount_float,
                "subtotal": round(subtotal, 2)
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
                
        # Estado seleccionado (Borrador vs Cotización)
        cot_status = request.form.get('status', 'Cotización').strip()
        
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
            "status": cot_status,
            "seller_name": session.get('user_name', 'Vendedor'),
            "seller_initials": session.get('user_initials', 'V'),
            "payment_method": request.form.get('payment_method', 'Efectivo').strip(),
            "payment_status": cot_status,
            "delivery_status": cot_status,
            "notes": notes,
            "created_at": datetime.utcnow().isoformat(timespec='seconds')
        }
        
        insert_sale(sale_data)
        flash(f"Cotización guardada como '{cot_status}' exitosamente.", "success")
        return redirect(url_for('ventas.cotizaciones'))
        
    products = [p for p in list_products() if p.get('product_type', 'Final') == 'Final']
    default_date = datetime.today().strftime('%Y-%m-%d')
    
    # Clonar cotización existente si se pasa clone_id
    clone_id = request.args.get('clone_id', type=int)
    cloned_quotation = None
    if clone_id:
        from db import get_sale
        cloned_sale = get_sale(clone_id)
        if cloned_sale:
            notes_str = cloned_sale.get("notes") or ""
            doc_type = "Boleta"
            rut_val = ""
            dv_val = ""
            
            if "Doc: Factura" in notes_str:
                doc_type = "Factura"
            elif "Doc: Boleta" in notes_str:
                doc_type = "Boleta"
                
            if "RUT:" in notes_str:
                try:
                    rut_part = notes_str.split("RUT:")[1].split("|")[0].strip()
                    if "-" in rut_part:
                        rut_val, dv_val = rut_part.split("-", 1)
                    else:
                        rut_val = rut_part
                except Exception:
                    pass
            
            from db import get_client_by_rut
            cat_id = ""
            if rut_val:
                c_data = get_client_by_rut(rut_val)
                if c_data:
                    cat_id = c_data.get("category_id") or ""

            clean_notes = notes_str
            if "\n" in notes_str:
                clean_notes = notes_str.split("\n", 1)[1]
            elif "Doc:" in notes_str or "RUT:" in notes_str:
                clean_notes = ""

            cloned_quotation = {
                "id": cloned_sale["id"],
                "doc_type": doc_type,
                "customer_rut": rut_val,
                "customer_dv": dv_val,
                "customer_name": cloned_sale.get("customer_name", ""),
                "customer_email": cloned_sale.get("customer_email", ""),
                "customer_category": cat_id,
                "notes": clean_notes,
                "products": cloned_sale.get("products", [])
            }
    
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
        products_prices_map=products_prices_map,
        cloned_quotation=cloned_quotation
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

@ventas_bp.route('/ventas/cotizacion/<int:sale_id>/emitir-cotizacion', methods=['POST'])
def emitir_cotizacion(sale_id):
    """Cambiar estado de Borrador a Cotización"""
    from db import get_connection, get_sale
    sale = get_sale(sale_id)
    if not sale:
        flash("Cotización no encontrada.", "danger")
        return redirect(url_for('ventas.cotizaciones'))
        
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sales 
                SET status = 'Cotización', 
                    payment_status = 'Cotización', 
                    delivery_status = 'Cotización'
                WHERE id = %s
                """,
                (sale_id,)
            )
        conn.commit()
        
    flash(f"La cotización {sale['sale_number']} se ha emitido oficialmente.", "success")
    return redirect(url_for('ventas.cotizaciones'))


@ventas_bp.route('/ventas/cotizacion/<int:sale_id>/convertir', methods=['POST'])
def convertir_cotizacion(sale_id):
    """Convertir una cotización a venta real (Crea VTA- sin eliminar COT-)"""
    from db import get_connection, insert_sale
    quotation = get_sale(sale_id)
    if not quotation:
        flash("Cotización no encontrada.", "danger")
        return redirect(url_for('ventas.cotizaciones'))
        
    if quotation["status"] != "Cotización" and not str(quotation.get("sale_number", "")).startswith("COT-"):
        flash("Este registro no es una cotización válida.", "warning")
        return redirect(url_for('ventas.cotizaciones'))
        
    # Generar folio VTA- para la nueva venta
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(id), 0) + 1 as next_id FROM sales")
            next_id = cur.fetchone()["next_id"]
            new_sale_number = f"VTA-{next_id:05d}"

    from datetime import timedelta
    sale_date_dt = datetime.today()
    sale_date = sale_date_dt.strftime('%Y-%m-%d')
    
    pay_method = quotation.get("payment_method") or "Efectivo"
    notes_raw = (quotation.get("notes") or "").lower()
    
    # Determinar si el pago es a 30 días o al contado / mismo día
    if "30" in pay_method.lower() or "30" in notes_raw:
        due_date_dt = sale_date_dt + timedelta(days=30)
    else:
        due_date_dt = sale_date_dt
    invoice_due_date = due_date_dt.strftime('%Y-%m-%d')

    # Preservar notas y origen de la cotización
    cot_notes = quotation.get("notes") or ""
    origin_tag = f"Cotización de Origen: {quotation['sale_number']}"
    full_notes = f"{origin_tag}\n{cot_notes}" if cot_notes else origin_tag

    # Crear nueva venta manteniendo la cotización original intacta
    new_sale_data = {
        "sale_number": new_sale_number,
        "customer_name": quotation["customer_name"],
        "customer_email": quotation.get("customer_email", ""),
        "customer_initials": quotation.get("customer_initials", ""),
        "sale_date": sale_date,
        "sale_time": datetime.now().strftime("%H:%M:%S"),
        "products": quotation["products"],
        "total_amount": quotation["total_amount"],
        "status": "Pendiente",
        "seller_name": session.get('user_name', quotation.get("seller_name", "Vendedor")),
        "seller_initials": session.get('user_initials', quotation.get("seller_initials", "V")),
        "payment_method": pay_method,
        "payment_status": "Pendiente",
        "delivery_status": "Pendiente",
        "notes": full_notes,
        "created_at": datetime.utcnow().isoformat(timespec='seconds'),
    }

    new_sale_id = insert_sale(new_sale_data)

    now_str = datetime.utcnow().isoformat(timespec='seconds')
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Crear registro inicial de pagos con la fecha de cobro/vencimiento automática
            cur.execute(
                """
                INSERT INTO sale_payments (sale_id, invoice_due_date, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (new_sale_id, invoice_due_date, 'Factura pendiente', now_str, now_str)
            )
            # 2. Registrar historial de la nueva venta
            cur.execute(
                """
                INSERT INTO sales_status_history (sale_id, status, user_name, changed_at, comment)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    new_sale_id,
                    "Pendiente",
                    session.get('user_name', 'Sistema'),
                    now_str,
                    f"Venta creada a partir de Cotización {quotation['sale_number']}"
                )
            )
            # 3. Guardar en las notas de la cotización de origen qué venta fue creada a partir de ella
            new_cot_notes = quotation.get("notes") or ""
            reference_line = f"Venta Generada: {new_sale_number}"
            updated_cot_notes = f"{reference_line}\n{new_cot_notes}" if new_cot_notes else reference_line
            cur.execute(
                "UPDATE sales SET notes = %s WHERE id = %s",
                (updated_cot_notes, sale_id)
            )
        conn.commit()
        
    from markupsafe import Markup
    msg = Markup(f"Venta {new_sale_number} creada exitosamente a partir de la Cotización {quotation['sale_number']}. <a href='{url_for('ventas.ventas')}?filter=Ventas+Pendientes' style='font-weight: bold; text-decoration: underline; color: #1A365D;'>Haz clic aquí para ir a ver la nueva venta</a>.")
    flash(msg, "success")
    return redirect(url_for('ventas.cotizaciones'))


@ventas_bp.route('/ventas/clientes', methods=['GET', 'POST'])
def clientes():
    from db import list_clients, insert_client, get_page_data
    if request.method == 'POST':
        client_data = {
            "rut": request.form.get('rut', '').strip(),
            "dv": request.form.get('dv', '').strip(),
            "razon_social": request.form.get('razon_social', '').strip(),
            "tipo_compra": request.form.get('tipo_compra', 'Del Giro').strip(),
            "direccion": request.form.get('direccion', '').strip(),
            "comuna": request.form.get('comuna', '').strip(),
            "ciudad": request.form.get('ciudad', '').strip(),
            "giro": request.form.get('giro', '').strip(),
            "contacto": request.form.get('contacto', '').strip(),
            "rut_solicita": request.form.get('rut_solicita', '').strip(),
            "dv_solicita": request.form.get('dv_solicita', '').strip(),
            "email": request.form.get('email', '').strip(),
            "phone": request.form.get('phone', '').strip(),
            "category_id": request.form.get('category_id', '').strip()
        }
        if client_data['razon_social']:
            insert_client(client_data)
            flash("Cliente registrado exitosamente.", "success")
        else:
            flash("La Razón Social es requerida.", "warning")
        return redirect(url_for('ventas.clientes'))

    clients_list = list_clients()
    config = get_page_data("price_list_config") or {}
    categories = config.get("categories", [
        {"id": "cat_0", "name": "Categoría A", "margin": 5.0},
        {"id": "cat_1", "name": "Categoría B", "margin": 10.0},
        {"id": "cat_2", "name": "Categoría C", "margin": 15.0},
        {"id": "cat_3", "name": "Categoría D", "margin": 20.0}
    ])
    return render_template('clientes.html', clients=clients_list, categories=categories)


@ventas_bp.route('/ventas/clientes/<int:client_id>/editar', methods=['POST'])
def editar_cliente(client_id):
    from db import update_client
    client_data = {
        "rut": request.form.get('rut', '').strip(),
        "dv": request.form.get('dv', '').strip(),
        "razon_social": request.form.get('razon_social', '').strip(),
        "tipo_compra": request.form.get('tipo_compra', 'Del Giro').strip(),
        "direccion": request.form.get('direccion', '').strip(),
        "comuna": request.form.get('comuna', '').strip(),
        "ciudad": request.form.get('ciudad', '').strip(),
        "giro": request.form.get('giro', '').strip(),
        "contacto": request.form.get('contacto', '').strip(),
        "rut_solicita": request.form.get('rut_solicita', '').strip(),
        "dv_solicita": request.form.get('dv_solicita', '').strip(),
        "email": request.form.get('email', '').strip(),
        "phone": request.form.get('phone', '').strip(),
        "category_id": request.form.get('category_id', '').strip()
    }
    update_client(client_id, client_data)
    flash("Cliente actualizado exitosamente.", "success")
    return redirect(url_for('ventas.clientes'))


@ventas_bp.route('/ventas/clientes/<int:client_id>/eliminar', methods=['POST'])
def eliminar_cliente(client_id):
    from db import delete_client
    delete_client(client_id)
    flash("Cliente eliminado correctamente.", "info")
    return redirect(url_for('ventas.clientes'))


@ventas_bp.route('/api/clientes/buscar_por_rut/<path:rut>')
def api_buscar_cliente_por_rut(rut):
    from db import get_client_by_rut
    client = get_client_by_rut(rut)
    if client:
        return jsonify({
            "status": "ok",
            "client": {
                "id": client["id"],
                "rut": client["rut"],
                "dv": client.get("dv", ""),
                "razon_social": client.get("razon_social", ""),
                "email": client.get("email", ""),
                "phone": client.get("phone", ""),
                "category_id": client.get("category_id", "")
            }
        })
    return jsonify({"status": "not_found", "message": "Cliente no encontrado"}), 404


