from flask import Blueprint, render_template, make_response, request
from security import require_permission
from db import (
    get_income_report_data,
    get_cash_flow_data,
    get_cash_flow_data_weekly,
    get_sales_report_data,
    get_purchases_report_data,
    get_expenses_report_data,
)

reportes_bp = Blueprint('reportes', __name__)

@reportes_bp.route('/reporteria/ventas')
def reportes_ventas():
    """Reporte de Ventas con datos reales consolidados"""
    year = request.args.get('year', type=int)
    data = get_sales_report_data(year=year)
    return render_template('reporte_ventas.html', data=data, selected_year=year)

@reportes_bp.route('/reporteria/compras')
def reportes_compras():
    """Reporte de Compras con datos reales consolidados"""
    year = request.args.get('year', type=int)
    data = get_purchases_report_data(year=year)
    return render_template('reporte_compras.html', data=data, selected_year=year)

@reportes_bp.route('/reporteria/gastos')
def reportes_gastos():
    """Reporte de Gastos con datos reales consolidados"""
    month = request.args.get('month')
    data = get_expenses_report_data(month=month)
    return render_template('reporte_gastos.html', data=data, selected_month=month)

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
@require_permission('reportes')
def reportes_flujo_caja():
    """Flujo de Caja Oficial Consolidado del ERP con proyecciones y saldo bancario real"""
    from datetime import date, timedelta
    from db import list_bank_accounts, calculate_cash_flow_consolidation

    today = date.today()
    horizonte = request.args.get('horizonte', 'proximas_4_semanas')
    agrupacion = request.args.get('agrupacion', 'semanal')
    cuenta_id_raw = request.args.get('bank_account_id', '')
    filtro_tipo = request.args.get('flow_type', 'todos')
    filtro_origen = request.args.get('origin', 'todos')
    filtro_conciliacion = request.args.get('reconciliation_status', 'todos')

    # The detail grid is server-paginated with a fixed backend page size.
    # Invalid or stale values are safely clamped by the consolidation helper.
    try:
        page = max(1, int(request.args.get('page', '1')))
    except (TypeError, ValueError):
        page = 1

    bank_account_id = int(cuenta_id_raw) if cuenta_id_raw and cuenta_id_raw.isdigit() else None

    # Cálculo dinámico de fechas según horizonte
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if not start_date or not end_date:
        if horizonte == 'esta_semana':
            start_d = today - timedelta(days=today.weekday())
            end_d = start_d + timedelta(days=6)
        elif horizonte == 'proximas_4_semanas':
            start_d = today - timedelta(days=today.weekday())
            end_d = start_d + timedelta(weeks=4) - timedelta(days=1)
        elif horizonte == 'proximos_30_dias':
            start_d = today
            end_d = today + timedelta(days=30)
        elif horizonte == 'proximos_60_dias':
            start_d = today
            end_d = today + timedelta(days=60)
        elif horizonte == 'proximos_90_dias':
            start_d = today
            end_d = today + timedelta(days=90)
        elif horizonte == 'este_mes':
            start_d = today.replace(day=1)
            import calendar
            end_d = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        elif horizonte == 'proximo_mes':
            import calendar
            first_this = today.replace(day=1)
            start_d = (first_this + timedelta(days=32)).replace(day=1)
            end_d = start_d.replace(day=calendar.monthrange(start_d.year, start_d.month)[1])
        else:
            # Histórico 4 semanas + Proyección 8 semanas
            start_d = today - timedelta(weeks=4)
            end_d = today + timedelta(weeks=8)
        start_date = start_d.isoformat()
        end_date = end_d.isoformat()

    cf = calculate_cash_flow_consolidation(
        start_date=start_date,
        end_date=end_date,
        bank_account_id=bank_account_id,
        grouping=agrupacion,
        filter_type=filtro_tipo,
        filter_origin=filtro_origen,
        filter_reconciliation=filtro_conciliacion,
        page=page,
    )

    accounts = list_bank_accounts()

    response = make_response(render_template(
        'reporte_flujo_caja.html',
        cf=cf,
        accounts=accounts,
        horizonte=horizonte,
        agrupacion=agrupacion,
        selected_account_id=bank_account_id,
        filtro_tipo=filtro_tipo,
        filtro_origen=filtro_origen,
        filtro_conciliacion=filtro_conciliacion,
        start_date=start_date,
        end_date=end_date,
        page=page,
    ))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response


@reportes_bp.route('/reporteria/flujo-caja/exportar-excel')
@require_permission('reportes')
def exportar_flujo_caja_excel():
    """Exportación canónica de Flujo de Caja en formato Excel con fórmulas y detalle de movimientos"""
    import io
    from flask import send_file
    from db import get_bank_account, calculate_cash_flow_consolidation
    from services.cash_flow_excel_service import export_cash_flow_to_excel

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    agrupacion = request.args.get('agrupacion', 'semanal')
    cuenta_id_raw = request.args.get('bank_account_id', '')
    filtro_tipo = request.args.get('flow_type', 'todos')
    filtro_origen = request.args.get('origin', 'todos')
    filtro_conciliacion = request.args.get('reconciliation_status', 'todos')

    bank_account_id = int(cuenta_id_raw) if cuenta_id_raw and cuenta_id_raw.isdigit() else None
    account = get_bank_account(bank_account_id) if bank_account_id else None
    account_name = f"{account['bank_name']} ({account['account_number']})" if account else None

    if not start_date or not end_date:
        from datetime import date, timedelta
        today = date.today()
        start_date = (today - timedelta(days=today.weekday())).isoformat()
        end_date = (today + timedelta(weeks=4)).isoformat()

    cf = calculate_cash_flow_consolidation(
        start_date=start_date,
        end_date=end_date,
        bank_account_id=bank_account_id,
        grouping=agrupacion,
        filter_type=filtro_tipo,
        filter_origin=filtro_origen,
        filter_reconciliation=filtro_conciliacion,
    )

    excel_bytes = export_cash_flow_to_excel(cf, account_name=account_name)
    filename = f"flujo_caja_{start_date}_a_{end_date}.xlsx"
    return send_file(
        io.BytesIO(excel_bytes),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename,
    )

@reportes_bp.route('/reporteria/inventario-lotes')
def reportes_inventario_lotes():
    """Reporte oficial de Inventario y Existencias por Lote y Bodega con paginación server-side"""
    from db import get_lot_stock_paginated, get_page_data

    search_query = request.args.get('search', '').strip()
    selected_warehouse = request.args.get('warehouse', '').strip()
    selected_status = request.args.get('status', '').strip()

    try:
        current_page = int(request.args.get('page', 1))
        if current_page < 1:
            current_page = 1
    except (ValueError, TypeError):
        current_page = 1

    try:
        per_page = int(request.args.get('per_page', 25))
        if per_page not in (25, 50, 100):
            per_page = 25
    except (ValueError, TypeError):
        per_page = 25

    result = get_lot_stock_paginated(
        page=current_page,
        per_page=per_page,
        search=search_query,
        warehouse=selected_warehouse,
        status=selected_status
    )

    metrics = result["metrics"]
    warehouses_set = set(get_page_data("ingreso_warehouses") or ["Almacén Principal", "Almacén Secundario"])
    for wh in result.get("warehouses", []):
        if wh:
            warehouses_set.add(wh)
    warehouses_list = sorted(list(warehouses_set))

    return render_template(
        'reporte_inventario_lotes.html',
        lot_stock_list=result["items"],
        warehouses_list=warehouses_list,
        total_lotes=metrics["total_lotes"],
        lotes_activos=metrics["lotes_activos"],
        lotes_agotados=metrics["lotes_agotados"],
        unidades_disponibles=metrics["unidades_disponibles"],
        valor_total_lotes=metrics["valor_total_lotes"],
        current_page=result["page"],
        per_page=result["per_page"],
        total_pages=result["total_pages"],
        total_records=result["total"],
        search_query=search_query,
        selected_warehouse=selected_warehouse,
        selected_status=selected_status
    )


# ─── REPORTE 1: FACTURAS DE COMPRA Y GASTOS (HISTÓRICO / DOCUMENTAL) ───────────

@reportes_bp.route('/reporteria/facturas-compras-gastos', methods=['GET'])
@require_permission('reportes')
def reportes_facturas_compras_gastos():
    """
    Reporte consolidado de Facturas de Compra y Gastos Operacionales.
    Permite visualizar, filtrar, paginar y auditar todos los egresos y documentos oficiales.
    """
    from db import (
        get_purchases_and_expenses_report_data,
        list_suppliers,
        list_expense_categories,
    )

    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    doc_type = request.args.get('doc_type', 'all').strip()
    supplier_beneficiary = request.args.get('supplier_beneficiary', '').strip()
    category = request.args.get('category', '').strip()
    payment_status = request.args.get('payment_status', 'all').strip()
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort_by', 'date').strip()
    sort_order = request.args.get('sort_order', 'desc').strip()

    try:
        page = int(request.args.get('page', 1))
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = int(request.args.get('per_page', 25))
        if per_page not in (25, 50, 100):
            per_page = 25
    except (ValueError, TypeError):
        per_page = 25

    report_data = get_purchases_and_expenses_report_data(
        date_from=date_from or None,
        date_to=date_to or None,
        doc_type=doc_type or 'all',
        supplier_beneficiary=supplier_beneficiary or None,
        category=category or None,
        payment_status=payment_status or 'all',
        search=search or None,
        page=page,
        per_page=per_page,
        sort_by=sort_by or 'date',
        sort_order=sort_order or 'desc',
    )

    suppliers = list_suppliers()
    categories = list_expense_categories()

    return render_template(
        'reporte_facturas_compras_gastos.html',
        items=report_data["items"],
        metrics=report_data["metrics"],
        current_page=report_data["page"],
        per_page=report_data["per_page"],
        total_pages=report_data["total_pages"],
        total_records=report_data["total"],
        filters=report_data["filters"],
        suppliers=suppliers,
        categories=categories,
    )


@reportes_bp.route('/reporteria/facturas-compras-gastos/exportar-excel', methods=['GET'])
@require_permission('reportes')
def exportar_facturas_compras_gastos_excel():
    """Exporta a Excel (.xlsx) todos los registros filtrados del reporte Facturas y Gastos."""
    from services.report_export_service import export_purchases_and_expenses_to_excel
    from flask import send_file
    from datetime import date

    filter_params = {
        "date_from": request.args.get('date_from', '').strip() or None,
        "date_to": request.args.get('date_to', '').strip() or None,
        "doc_type": request.args.get('doc_type', 'all').strip() or 'all',
        "supplier_beneficiary": request.args.get('supplier_beneficiary', '').strip() or None,
        "category": request.args.get('category', '').strip() or None,
        "payment_status": request.args.get('payment_status', 'all').strip() or 'all',
        "search": request.args.get('search', '').strip() or None,
        "sort_by": request.args.get('sort_by', 'date').strip() or 'date',
        "sort_order": request.args.get('sort_order', 'desc').strip() or 'desc',
    }

    excel_buffer = export_purchases_and_expenses_to_excel(filter_params)
    filename = f"Facturas_Compra_Gastos_{date.today().isoformat()}.xlsx"

    return send_file(
        excel_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ─── REPORTE 2: CUENTAS POR PAGAR (OPERACIONAL FINANCIERO) ──────────────────────

@reportes_bp.route('/reporteria/cuentas-por-pagar', methods=['GET'])
@require_permission('reportes')
def reportes_cuentas_por_pagar():
    """
    Reporte operacional financiero de Cuentas por Pagar.
    Muestra exclusivamente obligaciones activas con Saldo Pendiente > 0.
    """
    from db import (
        get_accounts_payable_report_data,
        list_suppliers,
        list_expense_categories,
        list_bank_accounts,
    )

    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    due_date_from = request.args.get('due_date_from', '').strip()
    due_date_to = request.args.get('due_date_to', '').strip()
    doc_type = request.args.get('doc_type', 'all').strip()
    supplier_beneficiary = request.args.get('supplier_beneficiary', '').strip()
    category = request.args.get('category', '').strip()
    status = request.args.get('status', 'all').strip()
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort_by', 'due_date').strip()
    sort_order = request.args.get('sort_order', 'asc').strip()

    try:
        page = int(request.args.get('page', 1))
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = int(request.args.get('per_page', 25))
        if per_page not in (25, 50, 100):
            per_page = 25
    except (ValueError, TypeError):
        per_page = 25

    payable_data = get_accounts_payable_report_data(
        date_from=date_from or None,
        date_to=date_to or None,
        due_date_from=due_date_from or None,
        due_date_to=due_date_to or None,
        doc_type=doc_type or 'all',
        supplier_beneficiary=supplier_beneficiary or None,
        category=category or None,
        status=status or 'all',
        search=search or None,
        page=page,
        per_page=per_page,
        sort_by=sort_by or 'due_date',
        sort_order=sort_order or 'asc',
    )

    suppliers = list_suppliers()
    categories = list_expense_categories()
    bank_accounts = list_bank_accounts()

    return render_template(
        'reporte_cuentas_por_pagar.html',
        items=payable_data["items"],
        metrics=payable_data["metrics"],
        current_page=payable_data["page"],
        per_page=payable_data["per_page"],
        total_pages=payable_data["total_pages"],
        total_records=payable_data["total"],
        filters=payable_data["filters"],
        suppliers=suppliers,
        categories=categories,
        bank_accounts=bank_accounts,
    )


@reportes_bp.route('/reporteria/cuentas-por-pagar/exportar-excel', methods=['GET'])
@require_permission('reportes')
def exportar_cuentas_por_pagar_excel():
    """Exporta a Excel (.xlsx) todas las cuentas por pagar activas según los filtros."""
    from services.report_export_service import export_accounts_payable_to_excel
    from flask import send_file
    from datetime import date

    filter_params = {
        "date_from": request.args.get('date_from', '').strip() or None,
        "date_to": request.args.get('date_to', '').strip() or None,
        "due_date_from": request.args.get('due_date_from', '').strip() or None,
        "due_date_to": request.args.get('due_date_to', '').strip() or None,
        "doc_type": request.args.get('doc_type', 'all').strip() or 'all',
        "supplier_beneficiary": request.args.get('supplier_beneficiary', '').strip() or None,
        "category": request.args.get('category', '').strip() or None,
        "status": request.args.get('status', 'all').strip() or 'all',
        "search": request.args.get('search', '').strip() or None,
        "sort_by": request.args.get('sort_by', 'due_date').strip() or 'due_date',
        "sort_order": request.args.get('sort_order', 'asc').strip() or 'asc',
    }

    excel_buffer = export_accounts_payable_to_excel(filter_params)
    filename = f"Cuentas_Por_Pagar_{date.today().isoformat()}.xlsx"

    return send_file(
        excel_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ─── REPORTE 3: CUENTAS POR COBRAR (CLIENTES Y COBRANZAS) ─────────────────────

@reportes_bp.route('/reporteria/cuentas-por-cobrar', methods=['GET'])
@require_permission('reportes')
def reportes_cuentas_por_cobrar():
    """
    Reporte operacional financiero de Cuentas por Cobrar.
    Muestra exclusivamente ventas no canceladas con Saldo Pendiente > 0.
    """
    from db import (
        get_accounts_receivable_report_data,
        list_bank_accounts,
    )

    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    due_date_from = request.args.get('due_date_from', '').strip()
    due_date_to = request.args.get('due_date_to', '').strip()
    customer = request.args.get('customer', '').strip()
    payment_status = request.args.get('payment_status', 'all').strip()
    sale_status = request.args.get('sale_status', 'all').strip()
    quick_filter = request.args.get('quick_filter', 'all').strip()
    filter_gestion = request.args.get('filter_gestion', 'all').strip()
    filter_antiguedad_gestion = request.args.get('filter_antiguedad_gestion', 'all').strip()
    filter_tipo_gestion = request.args.get('filter_tipo_gestion', 'all').strip()
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort_by', 'due_date').strip()
    sort_order = request.args.get('sort_order', 'asc').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)

    report_result = get_accounts_receivable_report_data(
        date_from=date_from or None,
        date_to=date_to or None,
        due_date_from=due_date_from or None,
        due_date_to=due_date_to or None,
        customer=customer or None,
        payment_status=payment_status or "all",
        sale_status=sale_status or "all",
        quick_filter=quick_filter or "all",
        filter_gestion=filter_gestion or "all",
        filter_antiguedad_gestion=filter_antiguedad_gestion or "all",
        filter_tipo_gestion=filter_tipo_gestion or "all",
        search=search or None,
        page=page,
        per_page=per_page,
        sort_by=sort_by or "due_date",
        sort_order=sort_order or "asc",
    )

    bank_accounts = list_bank_accounts()

    return render_template(
        'reporte_cuentas_por_cobrar.html',
        items=report_result['items'],
        metrics=report_result['metrics'],
        filters=report_result['filters'],
        current_page=report_result['page'],
        per_page=report_result['per_page'],
        total_pages=report_result['total_pages'],
        total_records=report_result['total'],
        bank_accounts=bank_accounts,
    )


@reportes_bp.route('/reporteria/cuentas-por-cobrar/exportar-excel', methods=['GET'])
@require_permission('reportes')
def exportar_cuentas_por_cobrar_excel():
    """Exporta a Excel (.xlsx) todas las cuentas por cobrar activas según los filtros."""
    from services.report_export_service import export_accounts_receivable_to_excel
    from flask import send_file
    from datetime import date

    filter_params = {
        "date_from": request.args.get('date_from', '').strip() or None,
        "date_to": request.args.get('date_to', '').strip() or None,
        "due_date_from": request.args.get('due_date_from', '').strip() or None,
        "due_date_to": request.args.get('due_date_to', '').strip() or None,
        "customer": request.args.get('customer', '').strip() or None,
        "payment_status": request.args.get('payment_status', 'all').strip() or 'all',
        "sale_status": request.args.get('sale_status', 'all').strip() or 'all',
        "quick_filter": request.args.get('quick_filter', 'all').strip() or 'all',
        "filter_gestion": request.args.get('filter_gestion', 'all').strip() or 'all',
        "filter_antiguedad_gestion": request.args.get('filter_antiguedad_gestion', 'all').strip() or 'all',
        "filter_tipo_gestion": request.args.get('filter_tipo_gestion', 'all').strip() or 'all',
        "search": request.args.get('search', '').strip() or None,
        "sort_by": request.args.get('sort_by', 'due_date').strip() or 'due_date',
        "sort_order": request.args.get('sort_order', 'asc').strip() or 'asc',
    }

    excel_buffer = export_accounts_receivable_to_excel(filter_params)
    filename = f"Cuentas_Por_Cobrar_{date.today().isoformat()}.xlsx"

    return send_file(
        excel_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@reportes_bp.route('/reporteria/cuentas-por-cobrar/gestiones', methods=['POST'])
@require_permission('reportes')
def registrar_gestion_cobranza():
    """
    Registra una nueva acción de cobranza para una venta.
    El usuario que registra se obtiene de forma inmutable desde la sesión autenticada.
    """
    from flask import flash, redirect, url_for, session, jsonify
    from db import insert_collection_action, get_sale

    sale_id_raw = request.form.get('sale_id') or (request.json.get('sale_id') if request.is_json else None)
    if not sale_id_raw:
        if request.is_json:
            return jsonify({"status": "error", "message": "ID de venta requerido"}), 400
        flash("ID de venta requerido", "error")
        return redirect(url_for('reportes.reportes_cuentas_por_cobrar'))

    try:
        sale_id = int(sale_id_raw)
    except (ValueError, TypeError):
        if request.is_json:
            return jsonify({"status": "error", "message": "ID de venta inválido"}), 400
        flash("ID de venta inválido", "error")
        return redirect(url_for('reportes.reportes_cuentas_por_cobrar'))

    sale = get_sale(sale_id)
    if not sale:
        if request.is_json:
            return jsonify({"status": "error", "message": "La venta especificada no existe"}), 404
        flash("La venta no existe", "error")
        return redirect(url_for('reportes.reportes_cuentas_por_cobrar'))

    if request.is_json:
        data = request.json
    else:
        data = request.form

    action_type = (data.get('action_type') or '').strip()
    action_date = (data.get('action_date') or '').strip()
    action_time = (data.get('action_time') or '').strip() or '00:00'
    contact_name = (data.get('contact_name') or '').strip() or None
    result = (data.get('result') or '').strip()
    next_action = (data.get('next_action') or '').strip() or None
    next_action_date = (data.get('next_action_date') or '').strip() or None
    payment_commitment_date = (data.get('payment_commitment_date') or '').strip() or None
    payment_commitment_amount_raw = data.get('payment_commitment_amount')
    notes = (data.get('notes') or '').strip() or None

    if not action_type or not action_date or not result:
        msg = "Tipo de gestión, fecha y resultado son campos obligatorios"
        if request.is_json:
            return jsonify({"status": "error", "message": msg}), 400
        flash(msg, "error")
        return_url = request.form.get('return_url') or url_for('reportes.reportes_cuentas_por_cobrar')
        return redirect(return_url)

    commitment_amount = None
    if payment_commitment_amount_raw is not None and str(payment_commitment_amount_raw).strip() != "":
        try:
            commitment_amount = float(payment_commitment_amount_raw)
            if commitment_amount < 0:
                commitment_amount = 0.0
        except (ValueError, TypeError):
            commitment_amount = None

    user_name = session.get('full_name') or session.get('username') or 'Sistema'

    action_payload = {
        "sale_id": sale_id,
        "action_type": action_type,
        "action_date": action_date,
        "action_time": action_time,
        "contact_name": contact_name,
        "result": result,
        "next_action": next_action,
        "next_action_date": next_action_date,
        "payment_commitment_date": payment_commitment_date,
        "payment_commitment_amount": commitment_amount,
        "notes": notes,
        "user_name": user_name,
    }

    try:
        new_id = insert_collection_action(action_payload)
        msg = f"Gestión de cobranza ({action_type}) registrada exitosamente"
        if request.is_json:
            return jsonify({"status": "success", "message": msg, "action_id": new_id})
        flash(msg, "success")
    except Exception as e:
        err_msg = f"Error al registrar la gestión de cobranza: {e}"
        if request.is_json:
            return jsonify({"status": "error", "message": err_msg}), 500
        flash(err_msg, "error")

    return_url = request.form.get('return_url') or url_for('reportes.reportes_cuentas_por_cobrar')
    return redirect(return_url)


@reportes_bp.route('/reporteria/cuentas-por-cobrar/<int:sale_id>/historial-cobranza', methods=['GET'])
@require_permission('reportes')
def obtener_historial_cobranza(sale_id: int):
    """
    Retorna el historial completo de gestiones de cobranza para una venta en formato JSON.
    """
    from flask import jsonify
    from db import list_collection_actions, get_sale

    sale = get_sale(sale_id)
    if not sale:
        return jsonify({"status": "error", "message": "Venta no encontrada"}), 404

    actions = list_collection_actions(sale_id)
    return jsonify({
        "status": "success",
        "sale_id": sale_id,
        "sale_number": sale.get("sale_number"),
        "customer_name": sale.get("customer_name"),
        "actions": actions,
        "total_actions": len(actions)
    })


# =========================================================================
# CONCILIACIÓN BANCARIA (FASE A, B, C)
# =========================================================================

@reportes_bp.route('/reporteria/conciliacion-bancaria', methods=['GET'])
@require_permission('reportes')
def conciliacion_bancaria():
    """
    Vista principal de Conciliación Bancaria.
    Consolida movimientos bancarios de múltiples cuentas con filtros, KPIs y paginación.
    """
    from db import (
        list_bank_accounts,
        list_bank_transactions,
        get_bank_reconciliation_kpis,
        list_bank_transaction_categories,
    )

    bank_accounts = list_bank_accounts()
    categories = list_bank_transaction_categories(active_only=True)

    bank_account_id = request.args.get('bank_account_id', type=int)
    start_date = request.args.get('start_date', '').strip() or None
    end_date = request.args.get('end_date', '').strip() or None
    movement_type = request.args.get('movement_type', '').strip().upper() or None
    reconciliation_status = request.args.get('reconciliation_status', '').strip().upper() or None
    category_id = request.args.get('category_id', type=int)
    search = request.args.get('search', '').strip() or None
    sort_by = request.args.get('sort_by', 'transaction_date')
    order = request.args.get('order', 'desc')
    page = request.args.get('page', 1, type=int)
    from core.pagination import PAGE_SIZE, pagination_meta
    per_page = PAGE_SIZE

    transactions, total_count = list_bank_transactions(
        bank_account_id=bank_account_id,
        start_date=start_date,
        end_date=end_date,
        movement_type=movement_type,
        reconciliation_status=reconciliation_status,
        category_id=category_id,
        search=search,
        sort_by=sort_by,
        order=order,
        page=page,
        per_page=per_page,
    )

    kpis = get_bank_reconciliation_kpis(
        bank_account_id=bank_account_id,
        start_date=start_date,
        end_date=end_date,
        movement_type=movement_type,
        reconciliation_status=reconciliation_status,
        category_id=category_id,
        search=search,
    )

    pagination = pagination_meta(total_count, page)
    page = pagination["page"]
    total_pages = max(1, (total_count + per_page - 1) // per_page)

    return render_template(
        'conciliacion_bancaria.html',
        bank_accounts=bank_accounts,
        categories=categories,
        transactions=transactions,
        pagination=pagination,
        total_count=total_count,
        kpis=kpis,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        selected_account_id=bank_account_id,
        start_date=start_date or '',
        end_date=end_date or '',
        movement_type=movement_type or '',
        reconciliation_status=reconciliation_status or '',
        category_id=category_id,
        search=search or '',
        sort_by=sort_by,
        order=order,
    )


@reportes_bp.route('/reporteria/conciliacion-bancaria/plantilla', methods=['GET'])
@require_permission('reportes')
def descargar_plantilla_cartola():
    """Descarga la plantilla Excel oficial para importación de cartola bancaria."""
    from services.bank_reconciliation_excel_service import generate_bank_statement_template
    from flask import send_file

    bank_account_id = request.args.get('bank_account_id', type=int)
    excel_stream = generate_bank_statement_template(bank_account_id)
    return send_file(
        excel_stream,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='plantilla_cartola_bancaria.xlsx',
    )


@reportes_bp.route('/reporteria/conciliacion-bancaria/exportar-excel', methods=['GET'])
@require_permission('reportes')
def exportar_movimientos_bancarios_excel():
    """Exporta los movimientos bancarios filtrados en el formato canónico idéntico a la plantilla."""
    from services.bank_reconciliation_excel_service import export_bank_transactions_to_excel
    from flask import send_file
    from datetime import datetime

    bank_account_id = request.args.get('bank_account_id', type=int)
    start_date = request.args.get('start_date', '').strip() or None
    end_date = request.args.get('end_date', '').strip() or None
    movement_type = request.args.get('movement_type', '').strip().upper() or None
    reconciliation_status = request.args.get('reconciliation_status', '').strip().upper() or None
    category_id = request.args.get('category_id', type=int)
    search = request.args.get('search', '').strip() or None

    excel_stream = export_bank_transactions_to_excel(
        bank_account_id=bank_account_id,
        start_date=start_date,
        end_date=end_date,
        movement_type=movement_type,
        reconciliation_status=reconciliation_status,
        category_id=category_id,
        search=search,
    )

    filename = f"movimientos_bancarios_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        excel_stream,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename,
    )


@reportes_bp.route('/reporteria/conciliacion-bancaria/preview-excel', methods=['POST'])
@require_permission('reportes')
def preview_excel_cartola():
    """Valida y previsualiza la cartola bancaria subida antes de persistir."""
    from flask import jsonify, session
    from services.bank_reconciliation_excel_service import parse_and_preview_bank_statement

    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No se subió ningún archivo"}), 400

    file = request.files['file']
    if not file or not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({"status": "error", "message": "Formato de archivo inválido. Suba un archivo Excel (.xlsx)"}), 400

    bank_account_id = request.form.get('bank_account_id', type=int)
    if not bank_account_id:
        return jsonify({"status": "error", "message": "Debe seleccionar la cuenta bancaria de destino"}), 400

    file_bytes = file.read()
    preview = parse_and_preview_bank_statement(file_bytes, bank_account_id)

    if preview.get("status") == "error":
        return jsonify(preview), 400

    # Guardar temporalmente en sesión para confirmación
    session['bank_statement_preview'] = {
        "filename": file.filename,
        "bank_account_id": bank_account_id,
        "summary": preview["summary"],
        "valid_transactions": preview["valid_transactions"],
    }

    return jsonify(preview)


@reportes_bp.route('/reporteria/conciliacion-bancaria/confirmar-importacion', methods=['POST'])
@require_permission('reportes')
def confirmar_importacion_cartola():
    """Confirma la importación y persiste atómicamente los movimientos válidos."""
    from flask import jsonify, session
    from services.bank_reconciliation_excel_service import commit_bank_statement_import

    cached = session.get('bank_statement_preview')
    if not cached:
        # Check if sent via JSON payload
        req_json = request.get_json(silent=True) or {}
        cached = req_json.get('preview_data')

    if not cached or not cached.get('valid_transactions'):
        return jsonify({"status": "error", "message": "No hay movimientos pendientes de confirmación o la sesión expiró"}), 400

    user_name = session.get('full_name') or session.get('username') or 'Sistema'
    bank_account_id = cached['bank_account_id']
    filename = cached.get('filename', 'cartola.xlsx')
    summary = cached.get('summary', {})
    valid_transactions = cached['valid_transactions']

    result = commit_bank_statement_import(
        valid_transactions=valid_transactions,
        bank_account_id=bank_account_id,
        filename=filename,
        user_name=user_name,
        summary=summary,
    )

    # Limpiar de sesión
    session.pop('bank_statement_preview', None)

    return jsonify({
        "status": "success",
        "message": f"Se importaron {result['inserted_count']} movimientos bancarios exitosamente",
        "import_id": result["import_id"],
        "inserted_count": result["inserted_count"],
    })


@reportes_bp.route('/reporteria/conciliacion-bancaria/movimientos/<int:tx_id>/categorizar', methods=['POST'])
@require_permission('reportes')
def categorizar_movimiento_bancario(tx_id: int):
    """Asigna o actualiza la categoría de un movimiento bancario con auditoría."""
    from flask import jsonify, session
    from db import update_transaction_category

    req_data = request.get_json(silent=True) or request.form
    category_id = req_data.get('category_id')
    category_id = int(category_id) if category_id and str(category_id).isdigit() else None
    notes = req_data.get('notes')
    user_name = session.get('full_name') or session.get('username') or 'Sistema'

    success = update_transaction_category(
        transaction_id=tx_id,
        category_id=category_id,
        user_name=user_name,
        notes=notes,
    )

    if not success:
        return jsonify({"status": "error", "message": "Movimiento no encontrado"}), 404

    return jsonify({"status": "success", "message": "Categoría actualizada exitosamente"})


@reportes_bp.route('/reporteria/conciliacion-bancaria/categorias', methods=['GET', 'POST'])
@require_permission('reportes')
def gestionar_categorias_bancarias():
    """Consulta o crea categorías bancarias en JSON."""
    from flask import jsonify
    from db import list_bank_transaction_categories, create_bank_transaction_category

    if request.method == 'POST':
        req_data = request.get_json(silent=True) or request.form
        name = req_data.get('name', '').strip()
        flow_type = req_data.get('flow_type', 'AMBOS').strip().upper()

        success, msg, new_id = create_bank_transaction_category(name, flow_type)
        if not success:
            return jsonify({"status": "error", "message": msg}), 400

        return jsonify({
            "status": "success",
            "message": msg,
            "category": {"id": new_id, "name": name, "flow_type": flow_type}
        })

    cats = list_bank_transaction_categories(active_only=False)
    return jsonify({"status": "success", "categories": cats})


@reportes_bp.route('/reporteria/conciliacion-bancaria/categorias/<int:cat_id>', methods=['PUT', 'POST', 'DELETE'])
@require_permission('reportes')
def operacion_categoria_bancaria(cat_id: int):
    """Actualiza o elimina una categoría bancaria."""
    from flask import jsonify
    from db import update_bank_transaction_category, delete_bank_transaction_category

    if request.method == 'DELETE':
        success, msg = delete_bank_transaction_category(cat_id)
        if not success:
            return jsonify({"status": "error", "message": msg}), 400
        return jsonify({"status": "success", "message": msg})

    # PUT or POST for update
    req_data = request.get_json(silent=True) or request.form
    name = req_data.get('name', '').strip()
    flow_type = req_data.get('flow_type', 'AMBOS').strip().upper()

    success, msg = update_bank_transaction_category(cat_id, name, flow_type)
    if not success:
        return jsonify({"status": "error", "message": msg}), 400
    return jsonify({"status": "success", "message": msg})


@reportes_bp.route('/reporteria/conciliacion-bancaria/movimientos/<int:tx_id>/sugerencias', methods=['GET'])
@require_permission('reportes')
def sugerencias_conciliacion(tx_id: int):
    """Busca candidatos determinísticos para conciliar contra un movimiento bancario."""
    from flask import jsonify
    from db import get_suggested_reconciliation_matches

    res = get_suggested_reconciliation_matches(tx_id)
    if "error" in res and not res.get("matches"):
        return jsonify({"status": "error", "message": res["error"]}), 404
    return jsonify({"status": "success", "data": res})


@reportes_bp.route('/reporteria/conciliacion-bancaria/movimientos/<int:tx_id>/conciliar', methods=['POST'])
@require_permission('reportes')
def conciliar_movimiento(tx_id: int):
    """Concilia un movimiento bancario contra una operación del ERP."""
    from flask import jsonify, session
    from db import reconcile_transaction

    req_data = request.get_json(silent=True) or request.form
    reconciled_type = req_data.get('reconciled_type')
    reconciled_id = req_data.get('reconciled_id')
    notes = req_data.get('notes')

    if not reconciled_type or not reconciled_id:
        return jsonify({"status": "error", "message": "Datos de conciliación incompletos"}), 400

    try:
        reconciled_id = int(reconciled_id)
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "ID de conciliación inválido"}), 400

    user_name = session.get('full_name') or session.get('username') or 'Sistema'
    success, msg = reconcile_transaction(
        transaction_id=tx_id,
        reconciled_type=reconciled_type,
        reconciled_id=reconciled_id,
        user_name=user_name,
        notes=notes,
    )

    if not success:
        return jsonify({"status": "error", "message": msg}), 400

    return jsonify({"status": "success", "message": msg})


@reportes_bp.route('/reporteria/conciliacion-bancaria/movimientos/<int:tx_id>/desconciliar', methods=['POST'])
@require_permission('reportes')
def desconciliar_movimiento(tx_id: int):
    """Desconcilia un movimiento bancario revirtiendo su estado con auditoría."""
    from flask import jsonify, session
    from db import unreconcile_transaction

    req_data = request.get_json(silent=True) or request.form
    notes = req_data.get('notes')
    user_name = session.get('full_name') or session.get('username') or 'Sistema'

    success, msg = unreconcile_transaction(
        transaction_id=tx_id,
        user_name=user_name,
        notes=notes,
    )

    if not success:
        return jsonify({"status": "error", "message": msg}), 400

    return jsonify({"status": "success", "message": msg})


@reportes_bp.route('/reporteria/conciliacion-bancaria/movimientos/<int:tx_id>/historial', methods=['GET'])
@require_permission('reportes')
def historial_conciliacion(tx_id: int):
    """Retorna la bitácora de auditoría de un movimiento bancario."""
    from flask import jsonify
    from db import get_transaction_audit_history, get_bank_transaction

    tx = get_bank_transaction(tx_id)
    if not tx:
        return jsonify({"status": "error", "message": "Movimiento no encontrado"}), 404

    history = get_transaction_audit_history(tx_id)
    return jsonify({
        "status": "success",
        "transaction_id": tx_id,
        "history": history,
    })


# =========================================================
# FINANZAS → DEUDAS (Módulo de Deudas Financieras)
# =========================================================

@reportes_bp.route('/reporteria/deudas', methods=['GET'])
@require_permission('reportes')
def finanzas_deudas():
    """Pantalla principal de Deudas: KPIs, filtros y listado."""
    from db import list_debts, get_debts_kpis, list_debt_types

    debt_type_id = request.args.get('debt_type_id', type=int)
    status = request.args.get('status', '').strip()
    creditor = request.args.get('creditor', '').strip()
    bank_account_id = request.args.get('bank_account_id', type=int)
    search = request.args.get('search', '').strip()
    from core.pagination import parse_page

    debts = list_debts(
        debt_type_id=debt_type_id,
        status=status,
        creditor=creditor,
        bank_account_id=bank_account_id,
        search=search,
        page=parse_page(request.args.get('page')),
    )
    debts, pagination = debts
    kpis = get_debts_kpis()
    debt_types = list_debt_types(active_only=True)

    return render_template(
        'finanzas_deudas.html',
        debts=debts,
        pagination=pagination,
        kpis=kpis,
        debt_types=debt_types,
        selected_debt_type_id=debt_type_id,
        selected_status=status,
        selected_creditor=creditor,
        selected_bank_account_id=bank_account_id,
        search=search,
    )


@reportes_bp.route('/reporteria/deudas/nueva', methods=['POST'])
@require_permission('reportes')
def crear_nueva_deuda():
    """Registra una nueva deuda con generación o importación de plan de cuotas."""
    from flask import jsonify, session, flash, redirect, url_for
    from decimal import Decimal
    from db import create_debt_with_schedule

    req_data = request.get_json(silent=True) or request.form
    name = req_data.get('name', '').strip()
    debt_type_id = int(req_data.get('debt_type_id', 0))
    creditor_name = req_data.get('creditor_name', '').strip()
    creditor_rut = req_data.get('creditor_rut', '').strip()
    contract_number = req_data.get('contract_number', '').strip()
    original_amount = req_data.get('original_amount', 0)
    currency = req_data.get('currency', 'CLP').strip().upper()
    start_date = req_data.get('start_date', '').strip()
    installments_count = int(req_data.get('installments_count', 0))
    periodicity = req_data.get('periodicity', 'Mensual').strip()
    interest_rate = req_data.get('interest_rate', 0.0)
    # El selector es opcional en el formulario HTML y envía cadena vacía cuando
    # no se elige cuenta; normalizarla antes de convertir evita un HTTP 500.
    bank_account_id = int(req_data.get('bank_account_id') or 0) or None
    first_due_date = req_data.get('first_due_date', '').strip()
    notes = req_data.get('notes', '').strip()
    user_name = session.get('full_name') or session.get('username') or 'Sistema'

    success, msg, new_id = create_debt_with_schedule(
        name=name,
        debt_type_id=debt_type_id,
        creditor_name=creditor_name,
        original_amount=original_amount,
        start_date=start_date,
        installments_count=installments_count,
        first_due_date=first_due_date,
        currency=currency,
        periodicity=periodicity,
        interest_rate=interest_rate,
        creditor_rut=creditor_rut,
        contract_number=contract_number,
        bank_account_id=bank_account_id,
        notes=notes,
        created_by=user_name,
    )

    if request.is_json:
        if not success:
            return jsonify({"status": "error", "message": msg}), 400
        return jsonify({"status": "success", "message": msg, "debt_id": new_id})

    if not success:
        flash(f"Error al crear deuda: {msg}", "danger")
        return redirect(url_for('reportes.finanzas_deudas'))

    flash(msg, "success")
    return redirect(url_for('reportes.detalle_deuda', debt_id=new_id))


@reportes_bp.route('/reporteria/deudas/<int:debt_id>', methods=['GET'])
@require_permission('reportes')
def detalle_deuda(debt_id: int):
    """Muestra el resumen de la deuda, el plan de cuotas interactivo y el historial de pagos."""
    from db import get_debt_detail, list_debt_installments, list_debt_payment_history, list_bank_accounts

    debt = get_debt_detail(debt_id)
    if not debt:
        from flask import flash, redirect, url_for
        flash("Deuda no encontrada", "danger")
        return redirect(url_for('reportes.finanzas_deudas'))

    installments = list_debt_installments(debt_id)
    payments = list_debt_payment_history(debt_id=debt_id)
    bank_accounts = list_bank_accounts()

    return render_template(
        'finanzas_deuda_detalle.html',
        debt=debt,
        installments=installments,
        payments=payments,
        bank_accounts=bank_accounts,
    )


@reportes_bp.route('/reporteria/deudas/cuotas/<int:inst_id>/pago', methods=['POST'])
@require_permission('reportes')
def registrar_pago_cuota(inst_id: int):
    """Registra pago total o parcial de una cuota de deuda financiera."""
    from flask import jsonify, session, request
    import os
    from werkzeug.utils import secure_filename
    from db import register_debt_installment_payment

    req_data = request.form if request.form else (request.get_json(silent=True) or {})
    amount = req_data.get('payment_amount')
    payment_date = req_data.get('payment_date')
    bank_account_id = int(req_data.get('bank_account_id', 0) or 0)
    payment_method = req_data.get('payment_method', 'Transferencia')
    reference = req_data.get('reference', '')
    notes = req_data.get('notes', '')
    user_name = session.get('full_name') or session.get('username') or 'Sistema'

    if not bank_account_id:
        if request.is_json:
            return jsonify({"status": "error", "message": "Debe seleccionar la cuenta bancaria de egreso"}), 400
        from flask import flash, redirect
        flash("Debe seleccionar la cuenta bancaria de egreso", "danger")
        return redirect(request.referrer or '/reporteria/deudas')

    # Manejo de comprobante adjunto si existe
    proof_filename = None
    file = request.files.get('proof_file')
    if file and file.filename:
        filename = secure_filename(f"debt_pay_{inst_id}_{int(datetime.now().timestamp())}_{file.filename}")
        upload_folder = os.path.join(os.getcwd(), 'uploads', 'comprobantes_pagos')
        os.makedirs(upload_folder, exist_ok=True)
        file.save(os.path.join(upload_folder, filename))
        proof_filename = filename

    success, msg, pay_id = register_debt_installment_payment(
        installment_id=inst_id,
        payment_amount=amount,
        payment_date=payment_date,
        bank_account_id=bank_account_id,
        payment_method=payment_method,
        reference=reference,
        proof_file=proof_filename,
        notes=notes,
        user_name=user_name,
    )

    if request.is_json:
        if not success:
            return jsonify({"status": "error", "message": msg}), 400
        return jsonify({"status": "success", "message": msg, "payment_id": pay_id})

    from flask import flash, redirect
    if not success:
        flash(f"Error al registrar pago: {msg}", "danger")
    else:
        flash(msg, "success")
    return redirect(request.referrer or '/reporteria/deudas')


@reportes_bp.route('/reporteria/deudas/cuotas/<int:inst_id>/editar', methods=['POST'])
@require_permission('reportes')
def editar_cuota_deuda(inst_id: int):
    """Permite ajustar los componentes y fecha de una cuota pendiente."""
    from flask import jsonify, session, request, flash, redirect
    from db import update_installment_details

    req_data = request.form if request.form else (request.get_json(silent=True) or {})
    due_date = req_data.get('due_date')
    capital = req_data.get('capital', 0)
    interest = req_data.get('interest', 0)
    fees = req_data.get('fees', 0)
    insurance = req_data.get('insurance', 0)
    other_charges = req_data.get('other_charges', 0)
    notes = req_data.get('notes', '')
    user_name = session.get('full_name') or session.get('username') or 'Sistema'

    success, msg = update_installment_details(
        installment_id=inst_id,
        due_date=due_date,
        capital=capital,
        interest=interest,
        fees=fees,
        insurance=insurance,
        other_charges=other_charges,
        notes=notes,
        user_name=user_name,
    )

    if request.is_json:
        if not success:
            return jsonify({"status": "error", "message": msg}), 400
        return jsonify({"status": "success", "message": msg})

    if not success:
        flash(f"Error al editar cuota: {msg}", "danger")
    else:
        flash(msg, "success")
    return redirect(request.referrer or '/reporteria/deudas')


@reportes_bp.route('/reporteria/deudas/<int:debt_id>/exportar-excel', methods=['GET'])
@require_permission('reportes')
def exportar_plan_cuotas_excel(debt_id: int):
    """Exporta el plan de cuotas de una deuda en formato canónico Excel."""
    from flask import send_file, flash, redirect, url_for
    import io
    from db import get_debt_detail, list_debt_installments
    from services.debt_excel_service import export_debt_schedule_excel

    debt = get_debt_detail(debt_id)
    if not debt:
        flash("Deuda no encontrada", "danger")
        return redirect(url_for('reportes.finanzas_deudas'))

    installments = list_debt_installments(debt_id)
    excel_bytes = export_debt_schedule_excel(debt, installments)

    clean_name = "".join(c for c in debt.get("name", "deuda") if c.isalnum() or c in (" ", "-", "_")).strip()
    filename = f"plan_cuotas_{clean_name}_{debt_id}.xlsx"

    return send_file(
        io.BytesIO(excel_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


@reportes_bp.route('/reporteria/deudas/<int:debt_id>/importar-excel', methods=['POST'])
@require_permission('reportes')
def importar_plan_cuotas_excel(debt_id: int):
    """Importa y actualiza el plan de cuotas desde un Excel canónico validado."""
    from flask import jsonify, session, request, flash, redirect
    from db import get_debt_detail, list_debt_installments, get_connection
    from services.debt_excel_service import parse_and_validate_debt_schedule_excel
    import json

    debt = get_debt_detail(debt_id)
    if not debt:
        if request.is_json:
            return jsonify({"status": "error", "message": "Deuda no encontrada"}), 404
        flash("Deuda no encontrada", "danger")
        return redirect(request.referrer or '/reporteria/deudas')

    file = request.files.get('file')
    if not file or not file.filename:
        if request.is_json:
            return jsonify({"status": "error", "message": "Debe seleccionar un archivo Excel (.xlsx)"}), 400
        flash("Debe seleccionar un archivo Excel (.xlsx)", "danger")
        return redirect(request.referrer or '/reporteria/deudas')

    file_bytes = file.read()
    ok, msg, installments = parse_and_validate_debt_schedule_excel(file_bytes)
    if not ok:
        if request.is_json:
            return jsonify({"status": "error", "message": msg}), 400
        flash(f"Error al validar archivo: {msg}", "danger")
        return redirect(request.referrer or '/reporteria/deudas')

    # Validar que no se borren o alteren cuotas con pagos existentes
    existing_inst = list_debt_installments(debt_id)
    has_paid = any(i["paid_amount"] > 0 for i in existing_inst)
    if has_paid:
        msg_err = "No se puede reemplazar automáticamente el plan de cuotas porque ya existen pagos registrados. Edite las cuotas individuales."
        if request.is_json:
            return jsonify({"status": "error", "message": msg_err}), 400
        flash(msg_err, "danger")
        return redirect(request.referrer or '/reporteria/deudas')

    user_name = session.get('full_name') or session.get('username') or 'Sistema'

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Delete old installments and replace
            cur.execute("DELETE FROM debt_installments WHERE debt_id = %s", (debt_id,))
            for inst in installments:
                cur.execute(
                    """
                    INSERT INTO debt_installments (
                        debt_id, installment_number, due_date, capital, interest,
                        fees, insurance, other_charges, total_amount, paid_amount,
                        balance, status, notes
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0.00, %s, 'PENDIENTE', %s)
                    """,
                    (
                        debt_id,
                        inst["installment_number"],
                        inst["due_date"],
                        inst["capital"],
                        inst["interest"],
                        inst["fees"],
                        inst["insurance"],
                        inst["other_charges"],
                        inst["total_amount"],
                        inst["total_amount"],
                        inst.get("notes") or None,
                    ),
                )

            # Update debt header installments count
            cur.execute(
                """
                UPDATE debts
                SET installments_count = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (len(installments), debt_id),
            )

            # Audit
            cur.execute(
                """
                INSERT INTO debt_audit (debt_id, action, user_name, notes)
                VALUES (%s, 'IMPORT_SCHEDULE', %s, %s)
                """,
                (debt_id, user_name, f"Plan de cuotas importado desde Excel: {len(installments)} cuotas"),
            )
        conn.commit()

    if request.is_json:
        return jsonify({"status": "success", "message": f"Plan de cuotas actualizado exitosamente ({len(installments)} cuotas)"})

    flash(f"Plan de cuotas actualizado exitosamente ({len(installments)} cuotas)", "success")
    return redirect(request.referrer or f'/reporteria/deudas/{debt_id}')
