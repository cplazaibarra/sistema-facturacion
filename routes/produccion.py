from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timezone
import json
from db import get_connection, get_page_data, set_page_data, list_products, list_production_orders
from security import require_permission

produccion_bp = Blueprint('produccion', __name__)


@produccion_bp.before_request
def _require_inventory_permission_for_production():
    @require_permission('inventario')
    def _authorized():
        return None
    return _authorized()

@produccion_bp.route('/produccion')
def list_ots():
    """Listar órdenes de trabajo (OT) con paginación server-side, búsqueda y disponibilidad de materiales en lote."""
    from db import get_production_orders_paginated, get_material_availability_for_orders

    status_filter = request.args.get('status', 'all').strip()
    search_query = request.args.get('search', '').strip()
    
    try:
        page = int(request.args.get('page', 1))
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = int(request.args.get('per_page', 25))
    except (ValueError, TypeError):
        per_page = 25

    # 1. Obtener OTs paginadas server-side
    paginated_result = get_production_orders_paginated(
        page=page,
        per_page=per_page,
        search=search_query,
        status=status_filter
    )
    ots = paginated_result["items"]

    # 2. Identificar OTs en 'Borrador' de la página activa para calcular disponibilidad en BATCH (0 N+1)
    draft_ot_ids = [ot['id'] for ot in ots if ot.get('status') == 'Borrador']
    availabilities = {}
    if draft_ot_ids:
        availabilities = get_material_availability_for_orders(draft_ot_ids)

    # 3. Enriquecer las OTs de la página activa
    for ot in ots:
        if ot.get('status') == 'Borrador':
            avail = availabilities.get(ot['id'], {
                "is_complete": True,
                "status_label": "Stock disponible",
                "materials": [],
                "missing_materials": []
            })
            ot['is_complete'] = avail['is_complete']
            ot['status_label'] = avail['status_label']
            ot['missing_materials'] = avail.get('missing_materials', [])
            ot['materials_availability'] = avail.get('materials', [])
        else:
            ot['is_complete'] = True
            ot['status_label'] = 'Stock disponible'
            ot['missing_materials'] = []
            ot['materials_availability'] = []

    products = list_products()
    input_products = [p for p in products if p.get('product_type', 'Final') == 'Insumo']
    return render_template(
        'produccion.html',
        ots=ots,
        pagination=paginated_result,
        total_ots=paginated_result["total"],
        all_ots_count=paginated_result["total"],
        current_status=status_filter,
        search_query=search_query,
        per_page=paginated_result["per_page"],
        current_page=paginated_result["page"],
        total_pages=paginated_result["total_pages"],
        input_products=input_products
    )

@produccion_bp.route('/produccion/nueva', methods=['GET', 'POST'])
def nueva_ot():
    """Crear una nueva Orden de Trabajo (en estado Solicitada o Borrador)."""
    from db import get_connection, create_production_order
    from repositories.inventory_repo import get_relational_stock

    if request.method == 'POST':
        final_product_id = int(request.form.get('final_product_id', 0))
        quantity = int(request.form.get('quantity', 0))
        notes = request.form.get('notes', '').strip()
        action_type = request.form.get('action', 'solicitar').strip()  # 'draft' | 'solicitar'
        
        if not final_product_id or quantity <= 0:
            flash("Debe seleccionar un producto final y una cantidad válida.", "danger")
            return redirect(url_for('produccion.nueva_ot'))
            
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Cargar componentes de la receta
                cur.execute(
                    """
                    SELECT pri.input_product_id, pri.quantity_required, p.sku, p.name
                    FROM product_recipe_items pri
                    JOIN product_recipes pr ON pri.recipe_id = pr.id
                    JOIN products p ON pri.input_product_id = p.id
                    WHERE pr.final_product_id = %s
                    ORDER BY pri.id ASC
                    """,
                    (final_product_id,)
                )
                recipe_items = cur.fetchall()
                if not recipe_items:
                    flash("El producto seleccionado no tiene una receta definida.", "danger")
                    return redirect(url_for('produccion.nueva_ot'))

                # Si es para SOLICITAR fabricación inmediata, validar stock disponible oficial
                if action_type != 'draft':
                    insufficient = []
                    for row in recipe_items:
                        req_qty = float(row["quantity_required"]) * quantity
                        avail_qty = get_relational_stock(row["input_product_id"], conn=conn)
                        if avail_qty < req_qty:
                            faltan = req_qty - avail_qty
                            insufficient.append(f"{row['name']} (Faltan {faltan:g} un)")

                    if insufficient:
                        flash(f"No se puede solicitar fabricación porque falta stock de insumos: {', '.join(insufficient)}. Puede guardarla como Borrador para planificarla.", "danger")
                        return redirect(url_for('produccion.nueva_ot'))

        # Crear OT usando repositorio unificado
        target_status = "Borrador" if action_type == 'draft' else "Solicitada"
        scheduled_date_raw = request.form.get('scheduled_date', '').strip() or None
        ot_id, ot_number = create_production_order(
            final_product_id=final_product_id,
            quantity=quantity,
            notes=notes,
            status=target_status,
            scheduled_date=scheduled_date_raw
        )

        if target_status == "Borrador":
            flash(f"Orden de Trabajo {ot_number} guardada como Borrador correctamente.", "success")
        else:
            flash(f"Solicitud de Fabricación {ot_number} creada correctamente.", "success")
        return redirect(url_for('produccion.list_ots'))
        
    # Cargar sólo productos finales que tienen receta definida
    final_products = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.id, p.sku, p.name
                FROM products p
                JOIN product_recipes pr ON p.id = pr.final_product_id
                WHERE p.product_type IN ('Final', 'Producto Terminado')
                """
            )
            final_products = [dict(row) for row in cur.fetchall()]
            
    products = list_products()
    input_products = [p for p in products if p.get('product_type', 'Final') == 'Insumo']
    categories = get_page_data("inventory_categories") or []
    
    return render_template(
        'nueva_ot.html',
        final_products=final_products,
        input_products=input_products,
        categories=categories
    )

@produccion_bp.route('/api/productos/rapido', methods=['POST'])
def crear_producto_rapido():
    """Crear un producto rápidamente via AJAX"""
    from db import get_connection, insert_product
    
    sku = request.form.get('sku', '').strip()
    name = request.form.get('name', '').strip()
    internal_code = request.form.get('internal_code', '').strip() or sku
    category = request.form.get('category', '').strip() or 'Miel'
    product_type = request.form.get('product_type', 'Final').strip()
    
    if not sku or not name:
        return jsonify({"status": "error", "message": "SKU y Nombre son obligatorios"}), 400
        
    product = {
        "sku": sku,
        "name": name,
        "description": "Creado rápidamente desde Producción",
        "barcode": "",
        "internal_code": internal_code,
        "category": category,
        "photo_url": "",
        "width_cm": None,
        "height_cm": None,
        "depth_cm": None,
        "weight_kg": None,
        "product_type": product_type,
        "created_at": datetime.now(timezone.utc).isoformat(timespec='seconds')
    }
    
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM products WHERE sku = %s", (sku,))
                if cur.fetchone():
                    return jsonify({"status": "error", "message": f"El SKU '{sku}' ya está registrado. Por favor ingrese un SKU distinto."}), 400

        product_id = insert_product(product)
        
        # También ingresarlo a inventory_items con stock 0
        inventory_items = get_page_data("inventory_items") or []
        if not any(item["code"] == sku for item in inventory_items):
            inventory_items.append({
                "code": sku,
                "name": name,
                "desc": product["description"],
                "category": category,
                "stock": 0.0,
                "min_stock": 10,
                "price": 0.0,
                "status": "Normal",
                "stock_percent": 100
            })
            set_page_data("inventory_items", inventory_items)
            
        return jsonify({
            "status": "ok",
            "product": {
                "id": product_id,
                "sku": sku,
                "name": name
            }
        })
    except Exception as e:
        err_msg = str(e)
        if "unique" in err_msg.lower() or "products_sku_key" in err_msg:
            return jsonify({"status": "error", "message": f"El SKU '{sku}' ya está registrado en la base de datos."}), 400
        return jsonify({"status": "error", "message": f"Error al guardar producto: {err_msg}"}), 400

@produccion_bp.route('/produccion/ot/<int:ot_id>/activar', methods=['POST'])
def activar_ot(ot_id):
    """Activar una Orden de Trabajo en estado Borrador si cuenta con stock real suficiente."""
    from db import activate_draft_production_order

    ok, msg, detail = activate_draft_production_order(ot_id)
    if ok:
        flash(msg, "success")
    else:
        flash(f"⚠️ {msg}", "danger")
    return redirect(url_for('produccion.list_ots'))


@produccion_bp.route('/produccion/ot/<int:ot_id>/editar', methods=['GET', 'POST'])
def editar_ot(ot_id):
    """Editar una Orden de Trabajo en estado Borrador."""
    from db import (
        get_production_order_by_id,
        update_draft_production_order,
        get_ot_material_availability,
        get_connection,
        list_products
    )

    ot = get_production_order_by_id(ot_id)
    if not ot:
        flash("Orden de Trabajo no encontrada.", "danger")
        return redirect(url_for('produccion.list_ots'))

    if ot["status"] != "Borrador":
        flash(f"Solo se pueden editar Órdenes de Trabajo en estado Borrador. Estado actual: {ot['status']}", "warning")
        return redirect(url_for('produccion.list_ots'))

    if request.method == 'POST':
        final_product_id = int(request.form.get('final_product_id', ot["final_product_id"]))
        quantity = int(request.form.get('quantity', 0))
        notes = request.form.get('notes', '').strip()
        scheduled_date_raw = request.form.get('scheduled_date', '').strip() or None
        schedule_order_raw = request.form.get('schedule_order', '').strip()
        order_val = int(schedule_order_raw) if schedule_order_raw and schedule_order_raw.isdigit() else None

        ok, msg = update_draft_production_order(
            ot_id=ot_id,
            final_product_id=final_product_id,
            quantity=quantity,
            notes=notes,
            scheduled_date=scheduled_date_raw,
            schedule_order=order_val,
            update_schedule=True
        )
        if ok:
            flash(f"Orden de Trabajo {ot['ot_number']} actualizada exitosamente.", "success")
            return redirect(url_for('produccion.list_ots'))
        else:
            flash(f"Error al actualizar la OT: {msg}", "danger")

    # Cargar disponibilidad dinámica actual de materiales
    avail = get_ot_material_availability(ot_id)
    ot["materials_availability"] = avail["materials"]
    ot["is_complete"] = avail["is_complete"]
    ot["status_label"] = avail["status_label"]

    # Cargar productos finales con receta
    final_products = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.id, p.sku, p.name
                FROM products p
                JOIN product_recipes pr ON p.id = pr.final_product_id
                WHERE p.product_type IN ('Final', 'Producto Terminado')
                """
            )
            final_products = [dict(row) for row in cur.fetchall()]

    return render_template('editar_ot.html', ot=ot, final_products=final_products)


@produccion_bp.route('/produccion/ot/<int:ot_id>/eliminar', methods=['POST'])
def eliminar_ot(ot_id):
    """Eliminar o cancelar una Orden de Trabajo en estado Borrador."""
    from db import cancel_draft_production_order

    ok, msg = cancel_draft_production_order(ot_id)
    if ok:
        flash(msg, "success")
    else:
        flash(f"⚠️ {msg}", "danger")
    return redirect(url_for('produccion.list_ots'))


@produccion_bp.route('/api/produccion/ot/<int:ot_id>/disponibilidad')
def api_ot_disponibilidad(ot_id):
    """API para consultar disponibilidad dinámica de materiales de una OT."""
    from db import get_ot_material_availability, get_production_order_by_id

    ot = get_production_order_by_id(ot_id)
    if not ot:
        return jsonify({"error": "Orden de Trabajo no encontrada"}), 404

    avail = get_ot_material_availability(ot_id)
    return jsonify({
        "ot_id": ot_id,
        "ot_number": ot["ot_number"],
        "status": ot["status"],
        "is_complete": avail["is_complete"],
        "status_label": avail["status_label"],
        "materials": avail["materials"]
    })


@produccion_bp.route('/produccion/calendario')
def calendario_produccion():
    """Vista de Calendario y Programación Semanal de Órdenes de Trabajo."""
    from datetime import datetime, timedelta
    from db import list_scheduled_production_orders, list_unscheduled_production_orders

    # Obtener fecha de referencia (?date=YYYY-MM-DD), default hoy
    ref_date_str = request.args.get('date', '').strip()
    try:
        if ref_date_str:
            ref_date = datetime.strptime(ref_date_str, "%Y-%m-%d").date()
        else:
            ref_date = datetime.now().date()
    except ValueError:
        ref_date = datetime.now().date()

    # Calcular lunes y domingo de la semana (ISO 8601: lunes=0 ... domingo=6)
    start_of_week = ref_date - timedelta(days=ref_date.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    # Navegación
    prev_week_date = start_of_week - timedelta(days=7)
    next_week_date = start_of_week + timedelta(days=7)
    today_date = datetime.now().date()

    # Meses en español
    MESES_ES = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]
    DIAS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    # Etiqueta de la semana: ej "21 - 27 Septiembre 2026"
    if start_of_week.month == end_of_week.month:
        week_label = f"{start_of_week.day} - {end_of_week.day} {MESES_ES[start_of_week.month - 1]} {start_of_week.year}"
    else:
        week_label = f"{start_of_week.day} {MESES_ES[start_of_week.month - 1]} - {end_of_week.day} {MESES_ES[end_of_week.month - 1]} {end_of_week.year}"

    start_str = start_of_week.strftime("%Y-%m-%d")
    end_str = end_of_week.strftime("%Y-%m-%d")

    # Obtener OTs programadas de esa semana con filtrado backend SQL
    scheduled_ots = list_scheduled_production_orders(start_str, end_str)

    # Agrupar por día de la semana
    days_data = []
    for i in range(7):
        current_day = start_of_week + timedelta(days=i)
        day_iso = current_day.strftime("%Y-%m-%d")
        day_ots = [ot for ot in scheduled_ots if str(ot.get("scheduled_date")) == day_iso]
        days_data.append({
            "date_iso": day_iso,
            "day_name": DIAS_ES[i],
            "day_number": current_day.day,
            "is_today": (current_day == today_date),
            "is_weekend": (i >= 5),
            "ots": day_ots
        })

    # OTs sin programar
    unscheduled_ots = list_unscheduled_production_orders()

    status_filter = request.args.get('status', 'all').strip()
    availability_filter = request.args.get('availability', 'all').strip()

    return render_template(
        'calendario_produccion.html',
        days_data=days_data,
        unscheduled_ots=unscheduled_ots,
        week_label=week_label,
        start_date=start_str,
        end_date=end_str,
        prev_week=prev_week_date.strftime("%Y-%m-%d"),
        next_week=next_week_date.strftime("%Y-%m-%d"),
        today=today_date.strftime("%Y-%m-%d"),
        current_date_str=ref_date.strftime("%Y-%m-%d"),
        status_filter=status_filter,
        availability_filter=availability_filter
    )


@produccion_bp.route('/api/produccion/ot/<int:ot_id>/programar', methods=['POST'])
def api_programar_ot(ot_id):
    """
    API para programar, reprogramar o desprogramar una OT.
    Acepta JSON o form data:
    {
        "scheduled_date": "YYYY-MM-DD" | null,
        "schedule_order": integer | null
    }
    """
    from db import set_production_order_schedule

    data = request.get_json(silent=True) or request.form
    scheduled_date = data.get("scheduled_date")
    schedule_order = data.get("schedule_order")

    if schedule_order is not None and str(schedule_order).strip() != "":
        try:
            schedule_order = int(schedule_order)
        except (ValueError, TypeError):
            schedule_order = None
    else:
        schedule_order = None

    ok, msg, detail = set_production_order_schedule(
        ot_id=ot_id,
        scheduled_date=scheduled_date,
        schedule_order=schedule_order
    )

    if not ok:
        return jsonify({"success": False, "message": msg}), 400

    return jsonify({"success": True, "message": msg, "detail": detail})



@produccion_bp.route('/produccion/ot/<int:ot_id>/aprobar', methods=['POST'])
@require_permission('aprobar_registros')
def aprobar_ot(ot_id):
    """Aprobar Orden de Trabajo y Reservar Stock"""
    from db import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE production_orders
                SET status = 'Aprobada', approved_at = %s
                WHERE id = %s AND status = 'Solicitada'
                """,
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ot_id)
            )
        conn.commit()
    flash("Orden de Trabajo aprobada y stock de insumos reservado.", "success")
    return redirect(url_for('produccion.list_ots'))

@produccion_bp.route('/produccion/ot/<int:ot_id>/finalizar', methods=['POST'])
def finalizar_ot(ot_id):
    """Finalizar Orden de Trabajo: Descontar insumos e incrementar producto terminado"""
    try:
        return _finalizar_ot_transaction(ot_id)
    except ValueError as exc:
        # La conexión transaccional ya hizo rollback, incluso si otra OT
        # agotó un lote mientras esta operación esperaba el lock FIFO.
        flash(f"No se pudo finalizar la Orden de Trabajo: {exc}", "danger")
        return redirect(url_for('produccion.list_ots'))


def _finalizar_ot_transaction(ot_id):
    """Unidad atómica: consumos FIFO, genealogía, costos y producto terminado."""
    from db import get_connection
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Cargar datos de la OT con bloqueo exclusivo
            cur.execute(
                """
                SELECT po.id, po.ot_number, po.quantity, po.status, po.final_product_id, p.sku as final_sku
                FROM production_orders po
                JOIN products p ON po.final_product_id = p.id
                WHERE po.id = %s
                FOR UPDATE
                """,
                (ot_id,)
            )
            ot = cur.fetchone()
            if not ot or ot["status"] != 'Aprobada':
                flash("La Orden de Trabajo no se encuentra aprobada o no existe.", "danger")
                return redirect(url_for('produccion.list_ots'))
                
            # 2. Cargar insumos requeridos
            cur.execute(
                """
                SELECT poi.id, poi.input_product_id, poi.quantity_required, p.sku as input_sku, p.cost as input_cost
                FROM production_order_items poi
                JOIN products p ON poi.input_product_id = p.id
                WHERE poi.production_order_id = %s
                ORDER BY poi.input_product_id ASC
                """,
                (ot_id,)
            )
            items = cur.fetchall()

            # Cargar insumos adicionales
            cur.execute(
                """
                SELECT poai.id, poai.input_product_id, poai.quantity, p.sku as input_sku, p.cost as input_cost
                FROM production_order_additional_items poai
                JOIN products p ON poai.input_product_id = p.id
                WHERE poai.production_order_id = %s
                ORDER BY poai.input_product_id ASC
                """,
                (ot_id,)
            )
            add_items = cur.fetchall()

            # Bloquear todos los productos involucrados en orden consistente id ASC
            all_involved_ids = sorted(list(set(
                [ot["final_product_id"]] +
                [it["input_product_id"] for it in items] +
                [ait["input_product_id"] for ait in add_items]
            )))
            if all_involved_ids:
                cur.execute(
                    "SELECT id FROM products WHERE id = ANY(%s) ORDER BY id ASC FOR UPDATE",
                    (all_involved_ids,)
                )

            # 3. Descontar stock e incrementar stock en inventory_items (dentro de la misma transacción)
            cur.execute("SELECT json FROM page_data WHERE key = 'inventory_items' FOR UPDATE")
            pd_row = cur.fetchone()
            inventory_items = json.loads(pd_row["json"]) if pd_row and pd_row["json"] else []
            inv_map = {item["code"]: item for item in inventory_items if item.get("code")}
            
            from db import get_current_ppp
            total_manufacturing_cost = 0.0

            # Descontar insumos planificados al PPP vigente previo a la salida
            for item in items:
                sku = item["input_sku"]
                qty = item["quantity_required"]
                input_pid = item["input_product_id"]
                if sku in inv_map:
                    inv_map[sku]["stock"] = max(0.0, inv_map[sku]["stock"] - qty)
                ppp_val = get_current_ppp(input_pid, conn=conn)
                cost_unit = float(ppp_val if ppp_val is not None and ppp_val > 0 else (item.get("input_cost") or 0.0))
                item["effective_unit_cost"] = cost_unit
                total_manufacturing_cost += cost_unit * qty
                cur.execute(
                    "UPDATE production_order_items SET unit_cost = %s WHERE id = %s",
                    (cost_unit, item["id"])
                )

            # Descontar insumos adicionales al PPP vigente previo a la salida
            for item in add_items:
                sku = item["input_sku"]
                qty = item["quantity"]
                input_pid = item["input_product_id"]
                if sku in inv_map:
                    inv_map[sku]["stock"] = max(0.0, inv_map[sku]["stock"] - qty)
                ppp_val = get_current_ppp(input_pid, conn=conn)
                cost_unit = float(ppp_val if ppp_val is not None and ppp_val > 0 else (item.get("input_cost") or 0.0))
                item["effective_unit_cost"] = cost_unit
                total_manufacturing_cost += cost_unit * qty
                cur.execute(
                    "UPDATE production_order_additional_items SET unit_cost = %s WHERE id = %s",
                    (cost_unit, item["id"])
                )
                    
            # Incrementar producto terminado
            final_sku = ot["final_sku"]
            if final_sku in inv_map:
                inv_map[final_sku]["stock"] = inv_map[final_sku]["stock"] + ot["quantity"]
            else:
                cur.execute("SELECT name, category, description FROM products WHERE sku = %s", (final_sku,))
                prod_info = cur.fetchone()
                if prod_info:
                    inventory_items.append({
                        "code": final_sku,
                        "name": prod_info["name"],
                        "desc": prod_info["description"] or "",
                        "category": prod_info["category"] or "Varios",
                        "stock": float(ot["quantity"]),
                        "min_stock": 10,
                        "price": 0.0,
                        "status": "Normal",
                        "stock_percent": 100
                    })
            
            # Guardar inventario en page_data dentro de la transacción
            cur.execute(
                """
                INSERT INTO page_data (key, json) VALUES ('inventory_items', %s)
                ON CONFLICT (key) DO UPDATE SET json = EXCLUDED.json
                """,
                (json.dumps(inventory_items, ensure_ascii=False),)
            )
            
            # 3.8. Registrar el ingreso en el historial de entradas con el costo real recalculado
            actual_unit_price = total_manufacturing_cost / ot["quantity"] if ot["quantity"] > 0 else 0.0
            
            cur.execute(
                """
                INSERT INTO inventory_entries (entry_date, order_number, purchase_order_id, supplier_id, warehouse, notes, total_amount, created_at)
                VALUES (%s, %s, NULL, NULL, 'Principal', %s, %s, %s)
                RETURNING id
                """,
                (
                    datetime.now().strftime("%Y-%m-%d"),
                    ot["ot_number"],
                    f"Ingreso por Fabricación (Costo Real Recalculado) / OT {ot['ot_number']}",
                    total_manufacturing_cost,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            )
            entry_id = cur.fetchone()["id"]
            
            cur.execute(
                """
                INSERT INTO inventory_entry_items (inventory_entry_id, product_id, quantity, unit_price, total)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    entry_id,
                    ot["final_product_id"],
                    ot["quantity"],
                    actual_unit_price,
                    total_manufacturing_cost
                )
            )
            
            # 4. Actualizar estado de la OT
            cur.execute(
                """
                UPDATE production_orders
                SET status = 'Finalizada', completed_at = %s, unit_cost = %s
                WHERE id = %s
                """,
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), actual_unit_price, ot_id)
            )

            # 5. Fase 2 & 5B: Registrar movimientos y genealogía de lotes en Kardex universal
            from db import record_inventory_movement, consume_fifo_lots
            now_iso = datetime.now(timezone.utc).isoformat()

            # 5.1 Consumo de insumos planificados (con FIFO de lotes si aplica)
            for item in items:
                input_pid = item["input_product_id"]
                qty_needed = float(item["quantity_required"])
                cost_u = float(item.get("effective_unit_cost") if item.get("effective_unit_cost") is not None else (item.get("input_cost") or 0.0))

                cur.execute("SELECT requires_lot, name FROM products WHERE id = %s", (input_pid,))
                p_info = cur.fetchone()
                req_lot = p_info["requires_lot"] if p_info else False

                cur.execute("SELECT COUNT(*) as c FROM lot_stock WHERE product_id = %s AND available_qty > 0", (input_pid,))
                has_lots = cur.fetchone()["c"] > 0

                if req_lot or has_lots:
                    consumed_lots = consume_fifo_lots(input_pid, qty_needed, ot_id=ot_id, conn=conn)
                    for c in consumed_lots:
                        cur.execute(
                            """
                            INSERT INTO production_lot_consumptions (
                                production_order_id, input_product_id, input_lot_id, quantity_consumed, created_at
                            ) VALUES (%s, %s, %s, %s, %s)
                            """,
                            (ot_id, input_pid, c["lot_id"], float(c["quantity"]), now_iso)
                        )
                        record_inventory_movement(
                            product_id=input_pid,
                            movement_type="PRODUCTION_INPUT",
                            quantity=-float(c["quantity"]),
                            unit_cost=cost_u,
                            warehouse="Principal",
                            reference_type="production_order",
                            reference_id=ot_id,
                            notes=f"Insumo planificado para OT {ot['ot_number']} (Lote {c['lot_number']})",
                            conn=conn,
                            lot_id=c["lot_id"]
                        )
                else:
                    record_inventory_movement(
                        product_id=input_pid,
                        movement_type="PRODUCTION_INPUT",
                        quantity=-qty_needed,
                        unit_cost=cost_u,
                        warehouse="Principal",
                        reference_type="production_order",
                        reference_id=ot_id,
                        notes=f"Insumo planificado para OT {ot['ot_number']}",
                        conn=conn
                    )

            # 5.2 Consumo de insumos adicionales (con FIFO de lotes si aplica)
            for item in add_items:
                input_pid = item["input_product_id"]
                qty_needed = float(item["quantity"])
                cost_u = float(item.get("effective_unit_cost") if item.get("effective_unit_cost") is not None else (item.get("input_cost") or 0.0))

                cur.execute("SELECT requires_lot, name FROM products WHERE id = %s", (input_pid,))
                p_info = cur.fetchone()
                req_lot = p_info["requires_lot"] if p_info else False

                cur.execute("SELECT COUNT(*) as c FROM lot_stock WHERE product_id = %s AND available_qty > 0", (input_pid,))
                has_lots = cur.fetchone()["c"] > 0

                if req_lot or has_lots:
                    consumed_lots = consume_fifo_lots(input_pid, qty_needed, ot_id=ot_id, conn=conn)
                    for c in consumed_lots:
                        cur.execute(
                            """
                            INSERT INTO production_lot_consumptions (
                                production_order_id, input_product_id, input_lot_id, quantity_consumed, created_at
                            ) VALUES (%s, %s, %s, %s, %s)
                            """,
                            (ot_id, input_pid, c["lot_id"], float(c["quantity"]), now_iso)
                        )
                        record_inventory_movement(
                            product_id=input_pid,
                            movement_type="PRODUCTION_INPUT",
                            quantity=-float(c["quantity"]),
                            unit_cost=cost_u,
                            warehouse="Principal",
                            reference_type="production_order",
                            reference_id=ot_id,
                            notes=f"Insumo adicional para OT {ot['ot_number']} (Lote {c['lot_number']})",
                            conn=conn,
                            lot_id=c["lot_id"]
                        )
                else:
                    record_inventory_movement(
                        product_id=input_pid,
                        movement_type="PRODUCTION_INPUT",
                        quantity=-qty_needed,
                        unit_cost=cost_u,
                        warehouse="Principal",
                        reference_type="production_order",
                        reference_id=ot_id,
                        notes=f"Insumo adicional para OT {ot['ot_number']}",
                        conn=conn
                    )

            # 5.3 Alta de producto terminado y creación de Lote de Producto Terminado
            final_pid = ot["final_product_id"]
            output_lot_number = request.form.get("output_lot_number") or f"PT-{ot['ot_number']}"
            output_qty = float(ot["quantity"])

            cur.execute(
                """
                INSERT INTO lots (
                    product_id, lot_number, lot_type, origin_type, origin_id,
                    production_order_id, initial_quantity, created_at, status, warehouse, notes
                ) VALUES (%s, %s, 'FINISHED_PRODUCT', 'PRODUCTION', %s, %s, %s, %s, 'ACTIVE', 'Principal', %s)
                RETURNING id;
                """,
                (
                    final_pid, output_lot_number, ot_id, ot_id, output_qty,
                    now_iso, f"Producido por OT {ot['ot_number']}"
                )
            )
            output_lot_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO production_lot_outputs (
                    production_order_id, output_product_id, output_lot_id, quantity_produced, created_at
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                (ot_id, final_pid, output_lot_id, output_qty, now_iso)
            )

            cur.execute(
                """
                INSERT INTO lot_stock (product_id, lot_number, entry_id, entry_date, initial_qty, available_qty, warehouse, lot_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (product_id, lot_number) DO UPDATE
                SET available_qty = lot_stock.available_qty + EXCLUDED.available_qty,
                    initial_qty = lot_stock.initial_qty + EXCLUDED.initial_qty,
                    lot_id = COALESCE(lot_stock.lot_id, EXCLUDED.lot_id);
                """,
                (
                    final_pid, output_lot_number, entry_id, datetime.now().strftime("%Y-%m-%d"),
                    output_qty, output_qty, "Principal", output_lot_id
                )
            )

            cur.execute(
                "UPDATE inventory_entry_items SET lot_number = %s, lot_id = %s WHERE inventory_entry_id = %s",
                (output_lot_number, output_lot_id, entry_id)
            )

            record_inventory_movement(
                product_id=final_pid,
                movement_type="PRODUCTION_OUTPUT",
                quantity=output_qty,
                unit_cost=actual_unit_price,
                lot_number=output_lot_number,
                warehouse="Principal",
                reference_type="production_order",
                reference_id=ot_id,
                notes=f"Fabricación finalizada OT {ot['ot_number']} (Lote {output_lot_number})",
                conn=conn,
                lot_id=output_lot_id
            )
            conn.commit()
        
    flash("Orden de Trabajo finalizada. Insumos rebajados y producto terminado ingresado al stock.", "success")
    return redirect(url_for('produccion.list_ots'))

@produccion_bp.route('/produccion/ot/<int:ot_id>/adicionar-insumo', methods=['POST'])
def adicionar_insumo(ot_id):
    """Agregar un insumo adicional a una OT en proceso"""
    from db import get_connection
    
    input_product_id = int(request.form.get('input_product_id', 0))
    quantity = float(request.form.get('quantity', 0.0))
    reason = request.form.get('reason', '').strip()
    
    if not input_product_id or quantity <= 0.0 or not reason:
        flash("Debe completar todos los datos para agregar el insumo adicional.", "danger")
        return redirect(url_for('produccion.list_ots'))
        
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Verificar que la OT esté Aprobada (En Proceso)
            cur.execute("SELECT status FROM production_orders WHERE id = %s", (ot_id,))
            ot = cur.fetchone()
            if not ot or ot["status"] != 'Aprobada':
                flash("Solo se pueden agregar insumos a Órdenes de Trabajo en estado Aprobada.", "danger")
                return redirect(url_for('produccion.list_ots'))
                
            # Registrar el insumo adicional
            cur.execute(
                """
                INSERT INTO production_order_additional_items (production_order_id, input_product_id, quantity, reason, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    ot_id,
                    input_product_id,
                    quantity,
                    reason,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            )
        conn.commit()
        
    flash("Insumo adicional agregado y reservado en stock correctamente.", "success")
    return redirect(url_for('produccion.list_ots'))

@produccion_bp.route('/produccion/recetas')
def list_recetas():
    """Listar recetas de producción con paginación server-side y carga batch (0 consultas N+1)"""
    from db import get_recipes_paginated

    search_query = request.args.get('search', '').strip()
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

    paginated = get_recipes_paginated(
        page=current_page,
        per_page=per_page,
        search=search_query
    )

    return render_template(
        'recetas.html',
        recipes=paginated["items"],
        current_page=paginated["page"],
        per_page=paginated["per_page"],
        total_pages=paginated["total_pages"],
        total_recipes=paginated["total"],
        search_query=search_query
    )

@produccion_bp.route('/produccion/recetas/nueva', methods=['GET', 'POST'])
def nueva_receta():
    """Crear una nueva receta"""
    from db import get_connection
    if request.method == 'POST':
        final_product_id = int(request.form.get('final_product_id'))
        recipe_code = request.form.get('recipe_code', '').strip() or None
        
        input_ids = request.form.getlist('input_product_id[]')
        quantities = request.form.getlist('quantity_required[]')
        units = request.form.getlist('unit[]')
        notes_list = request.form.getlist('notes[]')
        
        if not final_product_id:
            flash("Debe seleccionar un producto final.", "danger")
            return redirect(url_for('produccion.nueva_receta'))
            
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Insertar receta
                cur.execute(
                    """
                    INSERT INTO product_recipes (final_product_id, recipe_code, created_at)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (final_product_id, recipe_code, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )
                recipe_id = cur.fetchone()["id"]
                
                # Sincronizar bom_recipe en tabla products
                if recipe_code:
                    cur.execute("UPDATE products SET bom_recipe = %s WHERE id = %s", (recipe_code, final_product_id))

                # Insertar componentes unitarios
                for i in range(len(input_ids)):
                    inp_id = input_ids[i]
                    if not inp_id:
                        continue
                    qty_str = quantities[i] if i < len(quantities) else '0'
                    try:
                        qty_val = float(qty_str) if qty_str else 0.0
                    except ValueError:
                        qty_val = 0.0
                    unit_val = units[i].strip().upper() if i < len(units) and units[i] else 'UN'
                    note_val = notes_list[i].strip() if i < len(notes_list) and notes_list[i] else None
                    cur.execute(
                        """
                        INSERT INTO product_recipe_items (recipe_id, input_product_id, quantity_required, unit, notes)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (recipe_id, int(inp_id), qty_val, unit_val, note_val)
                    )
            conn.commit()
            
        flash("Receta de fabricación creada correctamente.", "success")
        return redirect(url_for('produccion.list_recetas'))
        
    # Cargar sólo productos finales que no tienen receta
    final_products = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, sku, name
                FROM products
                WHERE product_type IN ('Final', 'Producto Terminado') AND id NOT IN (SELECT final_product_id FROM product_recipes)
                """
            )
            final_products = [dict(row) for row in cur.fetchall()]
            
    products = list_products()
    input_products = [p for p in products if p.get('product_type', 'Final') == 'Insumo']
    categories = get_page_data("inventory_categories") or []
    
    return render_template('nueva_receta.html', final_products=final_products, input_products=input_products, categories=categories)

@produccion_bp.route('/produccion/recetas/<int:recipe_id>/editar', methods=['GET', 'POST'])
def editar_receta(recipe_id):
    """Editar una receta existente y sus componentes"""
    from db import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pr.id, pr.recipe_code, pr.final_product_id, pr.created_at,
                       p.name as final_name, p.sku as final_sku, p.line, p.variety, p.format_capacity
                FROM product_recipes pr
                JOIN products p ON pr.final_product_id = p.id
                WHERE pr.id = %s
                """,
                (recipe_id,)
            )
            recipe = cur.fetchone()
            
    if not recipe:
        flash("Receta no encontrada.", "danger")
        return redirect(url_for('produccion.list_recetas'))

    if request.method == 'POST':
        recipe_code = request.form.get('recipe_code', '').strip() or None
        input_ids = request.form.getlist('input_product_id[]')
        quantities = request.form.getlist('quantity_required[]')
        units = request.form.getlist('unit[]')
        notes_list = request.form.getlist('notes[]')
        
        valid_items = []
        for i in range(len(input_ids)):
            inp_id = input_ids[i]
            if not inp_id:
                continue
            qty_str = quantities[i] if i < len(quantities) else '0'
            try:
                qty_val = float(qty_str) if qty_str else 0.0
            except ValueError:
                qty_val = 0.0
            unit_val = units[i].strip().upper() if i < len(units) and units[i] else 'UN'
            note_val = notes_list[i].strip() if i < len(notes_list) and notes_list[i] else None
            valid_items.append((int(inp_id), qty_val, unit_val, note_val))
            
        if not valid_items:
            flash("Debe incluir al menos un componente o insumo en la receta.", "danger")
            return redirect(url_for('produccion.editar_receta', recipe_id=recipe_id))
            
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Actualizar código de receta
                cur.execute(
                    "UPDATE product_recipes SET recipe_code = %s WHERE id = %s",
                    (recipe_code, recipe_id)
                )
                if recipe_code:
                    cur.execute(
                        "UPDATE products SET bom_recipe = %s WHERE id = %s",
                        (recipe_code, recipe["final_product_id"])
                    )
                    
                # Reemplazar componentes
                cur.execute("DELETE FROM product_recipe_items WHERE recipe_id = %s", (recipe_id,))
                for inp_id, qty_val, unit_val, note_val in valid_items:
                    cur.execute(
                        """
                        INSERT INTO product_recipe_items (recipe_id, input_product_id, quantity_required, unit, notes)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (recipe_id, inp_id, qty_val, unit_val, note_val)
                    )
            conn.commit()
            
        flash("Receta de fabricación actualizada correctamente.", "success")
        return redirect(url_for('produccion.list_recetas'))

    # Cargar insumos actuales de la receta
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pri.id, pri.input_product_id, pri.quantity_required, pri.unit, pri.notes,
                       p.name as input_name, p.sku as input_sku
                FROM product_recipe_items pri
                JOIN products p ON pri.input_product_id = p.id
                WHERE pri.recipe_id = %s
                ORDER BY pri.id ASC
                """,
                (recipe_id,)
            )
            items = [dict(row) for row in cur.fetchall()]

    products = list_products()
    input_products = [p for p in products if p.get('id') != recipe['final_product_id']]
    input_products = sorted(input_products, key=lambda x: (x.get('product_type') != 'Insumo', x.get('name') or ''))

    return render_template('editar_receta.html', recipe=dict(recipe), items=items, input_products=input_products)

@produccion_bp.route('/produccion/recetas/<int:recipe_id>/eliminar', methods=['POST'])
def eliminar_receta(recipe_id):
    """Eliminar una receta"""
    from db import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT final_product_id FROM product_recipes WHERE id = %s", (recipe_id,))
            rec = cur.fetchone()
            if rec:
                cur.execute("UPDATE products SET bom_recipe = NULL WHERE id = %s", (rec["final_product_id"],))
            cur.execute("DELETE FROM product_recipes WHERE id = %s", (recipe_id,))
        conn.commit()
    flash("Receta de fabricación eliminada.", "success")
    return redirect(url_for('produccion.list_recetas'))

@produccion_bp.route('/api/productos/<int:product_id>/receta')
def get_product_recipe(product_id):
    """API para obtener los insumos y cantidades unitarias de la receta de un producto"""
    from db import get_connection
    items = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pri.input_product_id, pri.quantity_required, pri.unit, pri.notes, p.sku as input_sku, p.name as input_name
                FROM product_recipe_items pri
                JOIN product_recipes pr ON pri.recipe_id = pr.id
                JOIN products p ON pri.input_product_id = p.id
                WHERE pr.final_product_id = %s
                ORDER BY pri.id ASC
                """,
                (product_id,)
            )
            items = [dict(row) for row in cur.fetchall()]
            
    if not items:
        return jsonify({"error": "Receta no encontrada"}), 404
        
    from repositories.inventory_repo import get_relational_stock

    # Obtener distribución histórica por bodega
    warehouse_distribution = {}
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.sku, entries.warehouse, SUM(items.quantity) as qty
                FROM inventory_entry_items items
                JOIN inventory_entries entries ON items.inventory_entry_id = entries.id
                JOIN products p ON items.product_id = p.id
                GROUP BY p.sku, entries.warehouse
                """
            )
            for row in cur.fetchall():
                sku = row["sku"]
                warehouse = row["warehouse"] or "Principal"
                qty = float(row["qty"] or 0)
                if sku not in warehouse_distribution:
                    warehouse_distribution[sku] = {}
                warehouse_distribution[sku][warehouse] = qty
    
    from repositories.kardex_repo import get_current_ppp

    for item in items:
        sku = item["input_sku"]
        current_stock = get_relational_stock(item["input_product_id"])
        item["stock"] = current_stock

        # PPP vigente del insumo (para estimación de costo en vista previa de OT)
        try:
            item["ppp_actual"] = get_current_ppp(item["input_product_id"])
        except Exception:
            item["ppp_actual"] = 0.0
        
        # Calcular distribución para el insumo
        dist_map = warehouse_distribution.get(sku, {})
        total_ingresos = sum(dist_map.values())
        
        warehouse_shares = []
        if total_ingresos > 0:
            remaining_stock = current_stock
            keys = list(dist_map.keys())
            for i, wh in enumerate(keys):
                if i == len(keys) - 1:
                    wh_qty = remaining_stock
                else:
                    share = dist_map[wh] / total_ingresos
                    wh_qty = round(current_stock * share)
                    remaining_stock -= wh_qty
                
                if wh_qty > 0:
                    wh_qty_display = int(wh_qty) if wh_qty.is_integer() else round(wh_qty, 2)
                    warehouse_shares.append(f"{wh}({wh_qty_display})")
        else:
            if current_stock > 0:
                wh_qty_display = int(current_stock) if current_stock.is_integer() else current_stock
                warehouse_shares.append(f"Principal({wh_qty_display})")
                
        item["warehouse_display"] = ", ".join(warehouse_shares) if warehouse_shares else "Sin Stock"
        
    return jsonify({"product_id": product_id, "items": items})
