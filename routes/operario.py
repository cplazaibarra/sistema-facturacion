"""
routes/operario.py
Blueprint for Mobile Web Operator interface (/operario).
Designed exclusively for warehouse and production operators (Option 4 - Minimalist UX).
Enforces backend RBAC via @require_permission('operario_bodega').
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, Response
from datetime import datetime, timezone
import json

from security import require_permission
import repositories.purchases_repo as purchases_repo
import repositories.production_repo as production_repo
import repositories.inventory_repo as inventory_repo
import repositories.lot_genealogy_repo as lot_repo
from services.operario_service import OperarioService

operario_bp = Blueprint('operario', __name__, url_prefix='/operario')


@operario_bp.route('/manifest.json')
def pwa_manifest():
    """Sirve el manifest de PWA para instalación móvil standalone."""
    manifest = {
        "name": "Bodega Miel - Operario",
        "short_name": "Bodega",
        "start_url": "/operario",
        "display": "standalone",
        "background_color": "#F8FAFC",
        "theme_color": "#10B981",
        "icons": [
            {
                "src": "/static/img/icon-192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/static/img/icon-512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }
    return Response(json.dumps(manifest), mimetype='application/manifest+json')


@operario_bp.route('/')
@require_permission('operario_bodega')
def home():
    """Pantalla principal móvil para el operario (Opción 4 — Minimalista)."""
    user_id = session.get('user_id')
    recent = OperarioService.get_recent_actions(user_id=user_id, limit=5)
    return render_template('operario/home.html', recent_actions=recent)


# ========================================================
# 1. RECEPCIÓN DE MERCADERÍA
# ========================================================

@operario_bp.route('/recepcion')
@require_permission('operario_bodega')
def recepcion_list():
    """Listado y búsqueda de Órdenes de Compra pendientes de recepción."""
    q = request.args.get('q', '').strip()
    orders = purchases_repo.list_receivable_purchase_orders(search_query=q)
    return render_template('operario/recepcion_list.html', purchase_orders=orders, query=q)


@operario_bp.route('/recepcion/<int:po_id>', methods=['GET', 'POST'])
@require_permission('operario_bodega')
def recepcion_detail(po_id):
    """Detalle de recepción de una OC con ingreso de lote y cantidad."""
    po = purchases_repo.get_purchase_order(po_id)
    if not po:
        flash("Orden de Compra no encontrada.", "danger")
        return redirect(url_for('operario.recepcion_list'))

    items = purchases_repo.get_purchase_order_items(po_id)

    if request.method == 'POST':
        product_id = int(request.form.get('product_id', 0))
        qty_str = request.form.get('quantity', '0')
        lot_number = request.form.get('lot_number', '').strip()
        warehouse = request.form.get('warehouse', 'Principal').strip()
        doc_number = request.form.get('document_number', '').strip()
        entry_date = datetime.now().strftime("%Y-%m-%d")

        try:
            quantity = float(qty_str)
        except ValueError:
            quantity = 0.0

        if quantity <= 0 or not product_id:
            flash("Debe especificar un producto y una cantidad válida a recibir.", "danger")
            return redirect(url_for('operario.recepcion_detail', po_id=po_id))

        # Encontrar el ítem y validar si requiere lote obligatorio
        selected_item = next((it for it in items if it["product_id"] == product_id), None)
        if not selected_item:
            flash("El producto seleccionado no pertenece a esta Orden de Compra.", "danger")
            return redirect(url_for('operario.recepcion_detail', po_id=po_id))

        requires_lot = selected_item.get("requires_lot", False)
        if requires_lot and not lot_number:
            flash("LOTE OBLIGATORIO: Este producto exige ingresar o escanear el lote físico.", "danger")
            return redirect(url_for('operario.recepcion_detail', po_id=po_id))

        pending = selected_item["quantity_ordered"] - selected_item["quantity_received"]
        if quantity > pending + 1e-6:
            flash(f"La cantidad ingresada ({quantity:g}) supera el saldo pendiente de la OC ({pending:g}).", "danger")
            return redirect(url_for('operario.recepcion_detail', po_id=po_id))

        # Registrar recepción usando el repositorio oficial transaccional
        try:
            items_payload = [{
                "product_id": product_id,
                "quantity": quantity,
                "unit_price": selected_item.get("unit_price", 0.0),
                "lot_number": lot_number
            }]
            entry_id = inventory_repo.register_inventory_entry(
                po_id=po_id,
                order_number=po["oc_number"],
                entry_date=entry_date,
                warehouse=warehouse,
                notes=f"Recepción Móvil Operario / {po['oc_number']}",
                items=items_payload,
                document_type='guia_despacho',
                document_number=doc_number
            )

            return render_template(
                'operario/recepcion_success.html',
                oc_number=po["oc_number"],
                product_name=selected_item["product_name"],
                quantity=quantity,
                lot_number=lot_number
            )
        except Exception as e:
            flash(f"Error procesando la recepción: {str(e)}", "danger")
            return redirect(url_for('operario.recepcion_detail', po_id=po_id))

    return render_template('operario/recepcion_form.html', po=po, items=items)


# ========================================================
# 2. OPERAR ORDEN DE TRABAJO (OT) & CONSUMO DE LOTES
# ========================================================

@operario_bp.route('/ot')
@require_permission('operario_bodega')
def ot_list():
    """Listado de Órdenes de Trabajo activas para operarios."""
    ots = production_repo.list_active_production_orders()
    return render_template('operario/ot_list.html', ots=ots)


@operario_bp.route('/ot/<int:ot_id>')
@require_permission('operario_bodega')
def ot_detail(ot_id):
    """Detalle de una OT: insumos necesarios, lote recomendado FIFO y consumos."""
    ot = production_repo.get_production_order_by_id(ot_id)
    if not ot:
        flash("Orden de Trabajo no encontrada.", "danger")
        return redirect(url_for('operario.ot_list'))

    if ot.get("status") == "Borrador":
        flash("Esta Orden de Trabajo está en estado Borrador y aún no ha sido activada para producción.", "warning")
        return redirect(url_for('operario.ot_list'))

    # Obtener lotes recomendados FIFO para cada insumo
    recommended = {}
    for item in ot.get("plan_items", []):
        fifo_lot = OperarioService.get_recommended_fifo_lot(item["input_product_id"])
        if fifo_lot:
            recommended[item["input_product_id"]] = fifo_lot

    return render_template('operario/ot_detail.html', ot=ot, recommended_lots=recommended)


@operario_bp.route('/ot/<int:ot_id>/consumo', methods=['POST'])
@require_permission('operario_bodega')
def ot_record_consumption(ot_id):
    """Registra el consumo de un lote específico para una OT."""
    product_id = int(request.form.get('input_product_id', 0))
    lot_number = request.form.get('lot_number', '').strip()
    qty_str = request.form.get('quantity', '0')

    try:
        qty = float(qty_str)
    except ValueError:
        qty = 0.0

    ok, msg, data = OperarioService.validate_and_record_consumption(
        ot_id=ot_id,
        input_product_id=product_id,
        lot_number=lot_number,
        quantity=qty
    )

    if not ok:
        flash(f"⚠ {msg}", "danger")
    else:
        flash(f"✓ Consumo de {qty:g} unidades del lote {lot_number} registrado correctamente.", "success")

    return redirect(url_for('operario.ot_detail', ot_id=ot_id))


# ========================================================
# 3. TERMINAR FABRICACIÓN
# ========================================================

@operario_bp.route('/finalizar')
@require_permission('operario_bodega')
def finalizar_menu():
    """Acceso directo al listado de OTs para finalizar fabricación."""
    ots = production_repo.list_active_production_orders()
    return render_template('operario/ot_list.html', ots=ots)


@operario_bp.route('/ot/<int:ot_id>/finalizar', methods=['GET', 'POST'])
@require_permission('operario_bodega')
def finalizar_ot(ot_id):
    """Pantalla y acción para terminar fabricación de la OT con lote terminado."""
    ot = production_repo.get_production_order_by_id(ot_id)
    if not ot:
        flash("Orden de Trabajo no encontrada.", "danger")
        return redirect(url_for('operario.ot_list'))

    if ot["status"] == "Finalizada":
        flash("⚠ ESTA OT YA FUE FINALIZADA previamente.", "warning")
        return redirect(url_for('operario.ot_detail', ot_id=ot_id))

    if request.method == 'POST':
        actual_qty_str = request.form.get('actual_quantity', '0')
        output_lot_number = request.form.get('output_lot_number', '').strip()
        warehouse = request.form.get('warehouse', 'Principal').strip()
        expiry_date = request.form.get('expiry_date', '').strip()

        try:
            actual_qty = float(actual_qty_str)
        except ValueError:
            actual_qty = 0.0

        ok, msg, res = OperarioService.finalize_production(
            ot_id=ot_id,
            actual_quantity=actual_qty,
            output_lot_number=output_lot_number,
            warehouse=warehouse,
            expiry_date=expiry_date
        )

        if not ok:
            flash(f"⚠ {msg}", "danger")
            return render_template('operario/ot_finalizar.html', ot=ot)

        return render_template(
            'operario/fabricacion_success.html',
            ot_number=res["ot_number"],
            product_name=res["product_name"],
            quantity=res["quantity"],
            lot_number=res["lot_number"]
        )

    return render_template('operario/ot_finalizar.html', ot=ot)


# ========================================================
# 4. ESCANEAR AHORA (UNIVERSAL) & CONSULTA RÁPIDA
# ========================================================

@operario_bp.route('/escanear')
@require_permission('operario_bodega')
def escanear():
    """Pantalla de escáner universal móvil (cámara / entrada manual)."""
    return render_template('operario/scanner.html')


@operario_bp.route('/api/resolver-codigo')
@require_permission('operario_bodega')
def api_resolver_codigo():
    """API para identificar rápidamente códigos escaneados (OC, OT, Lote, Producto)."""
    code = request.args.get('code', '').strip()
    res = OperarioService.resolve_scanned_code(code)
    return jsonify(res)


@operario_bp.route('/lote/<int:lot_id>')
@require_permission('operario_bodega')
def lote_detalle(lot_id):
    """Ficha rápida operacional de lote escaneado."""
    lot = lot_repo.get_lot(lot_id)
    if not lot:
        flash("Lote no encontrado.", "danger")
        return redirect(url_for('operario.home'))
    return render_template('operario/lote_detalle.html', lot=lot)


# ========================================================
# 5. HISTORIAL Y PERFIL
# ========================================================

@operario_bp.route('/historial')
@require_permission('operario_bodega')
def historial():
    """Historial inmutable de acciones del operario."""
    user_id = session.get('user_id')
    actions = OperarioService.get_recent_actions(user_id=user_id, limit=30)
    return render_template('operario/historial.html', actions=actions)


@operario_bp.route('/perfil')
@require_permission('operario_bodega')
def perfil():
    """Perfil del operario con botón de cierre de sesión seguro."""
    return render_template('operario/perfil.html')
