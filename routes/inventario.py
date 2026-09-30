from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app, jsonify, session, Response, send_file
from werkzeug.utils import secure_filename
import os
import io
from datetime import datetime, timezone
from db import (
    get_page_data,
    list_products,
    get_product,
    insert_product,
    update_product,
    delete_product,
    list_suppliers,
    get_supplier,
    list_product_suppliers,
    add_product_supplier,
    remove_product_supplier,
    list_products_by_supplier,
    rename_category,
    delete_category,
    set_page_data,
    list_sales
)

from security import allowed_file, validate_and_sanitize_filename, require_permission

inventario_bp = Blueprint('inventario', __name__)


@inventario_bp.before_request
def _require_inventory_or_product_permission():
    if request.path.startswith('/uploads/'):
        return None
    permission = 'productos' if request.path.startswith('/productos') or request.path.startswith('/kardex') else 'inventario'
    @require_permission(permission)
    def _authorized():
        return None
    return _authorized()


def _adjustment_actor():
    return session.get('user_id'), session.get('full_name') or session.get('username') or 'Usuario'


@inventario_bp.route('/inventario/ajustes', methods=['GET'])
@require_permission('inventory_adjustment_request')
def ajustes_inventario():
    from repositories.inventory_adjustments_repo import list_adjustments
    status_raw = (request.args.get('status') or '').strip().upper()
    status = {'PENDIENTE': 'PENDING', 'APROBADO': 'APPLIED', 'APLICADO': 'APPLIED', 'RECHAZADO': 'REJECTED'}.get(status_raw, status_raw) or None
    adjustments = list_adjustments(status=status, warehouse=(request.args.get('warehouse') or '').strip() or None)
    search = (request.args.get('search') or '').strip().lower()
    if search:
        adjustments = [a for a in adjustments if search in str(a.get('sku','')).lower() or search in str(a.get('product_name','')).lower()]
    return render_template('ajustes_inventario.html', adjustments=adjustments, selected_status=status_raw, search=search)


@inventario_bp.route('/inventario/ajustes/nuevo', methods=['GET', 'POST'])
@require_permission('inventory_adjustment_request')
def nuevo_ajuste_inventario():
    from services.inventory_adjustment_service import ADJUSTMENT_REASONS
    from repositories.inventory_adjustments_repo import create_adjustment
    products = list_products()
    from services.stock_context import get_reserved_stock_by_sku
    reservation_diagnostics = []
    reserved_by_sku = get_reserved_stock_by_sku(
        products, list_sales({'status': 'Pendiente'}), reservation_diagnostics
    )
    from repositories.inventory_repo import get_batch_products_available_stock
    physical_by_id = get_batch_products_available_stock(products)
    for product in products:
        physical = float(physical_by_id.get(product['id'], 0) or 0)
        reserved = float(reserved_by_sku.get(product.get('sku'), 0) or 0)
        product['physical_stock'] = physical
        product['reserved_stock'] = reserved
        product['available_stock'] = max(physical - reserved, 0.0)
    warehouses = sorted(set(get_page_data('ingreso_warehouses') or ['Almacén Principal']))
    if request.method == 'POST':
        try:
            product_id = request.form.get('product_id', type=int)
            counted = float(request.form.get('counted_quantity', ''))
            row = create_adjustment(product_id=product_id, warehouse=request.form.get('warehouse'),
                                    counted_quantity=counted, reason=request.form.get('reason'),
                                    observation=request.form.get('observation'), requested_by=session.get('user_id'),
                                    requested_by_name=session.get('full_name') or session.get('username') or 'Usuario')
            flash('Solicitud de ajuste creada correctamente.', 'success')
            return redirect(url_for('inventario.detalle_ajuste_inventario', adjustment_id=row['id']))
        except (TypeError, ValueError) as exc:
            flash(str(exc), 'danger')
        except Exception:
            current_app.logger.exception('Error creando solicitud de ajuste')
            flash('No fue posible crear la solicitud de ajuste.', 'danger')
    return render_template('nuevo_ajuste_inventario.html', products=products, warehouses=warehouses,
                           adjustment_reasons=ADJUSTMENT_REASONS,
                           reservation_diagnostics=reservation_diagnostics,
                           selected_product_id=request.args.get('product_id'), selected_warehouse=request.args.get('warehouse'))


@inventario_bp.route('/inventario/ajustes/<int:adjustment_id>', methods=['GET'])
@require_permission('inventory_adjustment_request')
def detalle_ajuste_inventario(adjustment_id):
    from repositories.inventory_adjustments_repo import get_adjustment, _reserved, _stock
    from core.database import get_connection
    adjustment = get_adjustment(adjustment_id)
    if not adjustment:
        flash('Solicitud de ajuste no encontrada.', 'danger')
        return redirect(url_for('inventario.ajustes_inventario'))
    with get_connection() as conn:
        with conn.cursor() as cur:
            current = _stock(cur, adjustment['product_id'], adjustment['warehouse'])
            is_pending = (adjustment.get('status') or '').upper() == 'PENDING'
            adjustment['inventory_changed'] = is_pending and abs(current - float(adjustment['stock_snapshot'])) > 1e-6
            adjustment['current_reserved'] = _reserved(cur, adjustment['product_id'])
            adjustment['current_stock'] = current
            adjustment['resulting_stock'] = current + float(adjustment['difference']) if is_pending else current
    return render_template('detalle_ajuste_inventario.html', adjustment=adjustment)


@inventario_bp.route('/inventario/ajustes/<int:adjustment_id>/aprobar', methods=['POST'])
@require_permission('inventory_adjustment_approve')
def aprobar_ajuste_inventario(adjustment_id):
    from repositories.inventory_adjustments_repo import approve_adjustment
    try:
        actor_id, actor_name = _adjustment_actor()
        # El rol administrativo es el aprobador de máxima confianza en este
        # entorno; conserva el permiso específico y permite completar pruebas
        # de solicitudes creadas por el administrador. Otros roles mantienen
        # la segregación y no pueden autoaprobarse.
        admin_self_approval = (session.get('role_name') or '').lower() in ('admin', 'administrador', 'administrativo')
        approve_adjustment(adjustment_id, actor_id=actor_id, actor_name=actor_name,
                           approver_may_self_approve=admin_self_approval)
        flash('Ajuste aprobado y aplicado correctamente.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    except Exception:
        current_app.logger.exception('Error aprobando ajuste %s', adjustment_id)
        flash('No fue posible aprobar el ajuste.', 'danger')
    return redirect(url_for('inventario.detalle_ajuste_inventario', adjustment_id=adjustment_id))


@inventario_bp.route('/inventario/ajustes/<int:adjustment_id>/rechazar', methods=['POST'])
@require_permission('inventory_adjustment_approve')
def rechazar_ajuste_inventario(adjustment_id):
    from repositories.inventory_adjustments_repo import reject_adjustment
    try:
        actor_id, actor_name = _adjustment_actor()
        reject_adjustment(adjustment_id, actor_id=actor_id, actor_name=actor_name,
                          comment=request.form.get('approver_comment', ''))
        flash('Solicitud rechazada.', 'success')
    except ValueError as exc:
        flash(str(exc), 'danger')
    except Exception:
        current_app.logger.exception('Error rechazando ajuste %s', adjustment_id)
        flash('No fue posible rechazar el ajuste.', 'danger')
    return redirect(url_for('inventario.detalle_ajuste_inventario', adjustment_id=adjustment_id))

def handle_photo_upload(product_id):
    """Maneja la subida de foto de producto. Retorna la ruta de la foto o None"""
    if 'photo_file' in request.files:
        file = request.files['photo_file']
        if file and file.filename:
            if not allowed_file(file.filename):
                flash("Formato de imagen no permitido. Formatos válidos: PNG, JPG, JPEG, WEBP, PDF.", "danger")
                return None
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = secure_filename(f"product_{product_id}_{int(datetime.now(timezone.utc).timestamp())}.{ext}")
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            return f"/uploads/{filename}"
    return None

@inventario_bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@inventario_bp.route('/inventario')
def inventario():
    """Módulo de Inventario"""
    import re
    inventory_stats = get_page_data("inventory_stats") or {"total": 0, "low_stock": 0, "total_value": 0.0}
    inventory_items = get_page_data("inventory_items") or []
    inventory_categories = get_page_data("inventory_categories")
    inventory_stock_filters = get_page_data("inventory_stock_filters")
    
    # 1. Obtener todas las ventas pendientes
    pending_sales = list_sales({"status": "Pendiente"})
    
    # 2. Cargar todos los productos para mapeo ID -> SKU y Nombre -> SKU
    products_db = list_products()
    product_by_sku = {p.get('sku'): p for p in products_db}
    id_to_sku = {p['id']: p['sku'] for p in products_db}
    name_to_sku = {p['name'].strip().lower(): p['sku'] for p in products_db}
    
    from services.stock_context import get_reserved_stock_by_sku
    reservation_diagnostics = []
    reserved_by_sku = get_reserved_stock_by_sku(products_db, pending_sales, reservation_diagnostics)
    from core.database import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 3.6 Obtener la distribución del stock físico ingresado por bodegas para cada producto
            cur.execute(
                """
                SELECT p.sku, entries.warehouse, SUM(items.quantity) as qty
                FROM inventory_entry_items items
                JOIN inventory_entries entries ON items.inventory_entry_id = entries.id
                JOIN products p ON items.product_id = p.id
                GROUP BY p.sku, entries.warehouse
                """
            )
            warehouse_distribution = {}
            for row in cur.fetchall():
                sku = row["sku"]
                warehouse = row["warehouse"] or "Principal"
                qty = float(row["qty"] or 0)
                if sku not in warehouse_distribution:
                    warehouse_distribution[sku] = {}
                warehouse_distribution[sku][warehouse] = qty

    # 4.1 Aumentar cada ítem con stock reservado, total, bodegas, PPP y Valoración
    from repositories.kardex_repo import get_all_products_kardex_summary
    low_stock_count = 0
    total_bodega_value = 0.0

    # Carga BATCH de Kardex y PPP para todo el catálogo en una sola pasada (0 consultas N+1)
    kardex_summary = get_all_products_kardex_summary()
    kardex_by_id = {p['id']: p for p in kardex_summary.get('products', [])}

    # Diccionario SKU -> ID para mapeo rápido
    sku_to_id = {p['sku']: p['id'] for p in products_db}

    from repositories.inventory_repo import get_batch_products_available_stock
    physical_by_id = get_batch_products_available_stock(products_db)
    for item in inventory_items:
        sku = item.get("code")
        product_ref = product_by_sku.get(sku) or {}
        # Las limpiezas de datos de prueba pueden dejar proyecciones legacy sin
        # precio. La pantalla debe tolerar esa fila y usar el costo/catalogo
        # como fallback; no se modifica el ledger ni el stock oficial.
        if item.get("price") is None:
            item["price"] = item.get("cost")
        if item.get("price") is None:
            item["price"] = product_ref.get("cost") or 0.0
        reserved = reserved_by_sku.get(sku, 0)
        physical = float(physical_by_id.get(sku_to_id.get(sku), 0) or 0)
        available = max(physical - float(reserved or 0), 0.0)
        item["physical_stock"] = physical
        item["reserved"] = reserved
        item["total_stock"] = physical
        item["stock"] = available

        # Obtener PPP y valor inventario desde el mapa consolidado de Kardex
        p_id = sku_to_id.get(sku)
        item["product_id"] = p_id
        item_ppp = float(item.get("cost") or 0.0)
        item_val = 0.0

        if p_id and p_id in kardex_by_id:
            kp = kardex_by_id[p_id]
            item_ppp = kp["current_ppp"]
            item["movement_stock"] = kp["current_stock"]
            item["stock_delta"] = round(kp["current_stock"] - item["physical_stock"], 3)
            item_val = round(item["physical_stock"] * item_ppp, 2)
        else:
            item_val = round(item["physical_stock"] * item_ppp, 2)

        item["ppp"] = item_ppp
        item["inventory_value"] = item_val
        total_bodega_value += item_val
        
        # Calcular distribución proporcional por bodegas basándose en los ingresos históricos de mercadería
        dist_map = warehouse_distribution.get(sku, {})
        total_ingresos = sum(dist_map.values())
        
        warehouse_shares = []
        if total_ingresos > 0:
            # Distribuir el stock disponible actual proporcionalmente
            remaining_stock = item["physical_stock"]
            keys = list(dist_map.keys())
            for i, wh in enumerate(keys):
                if i == len(keys) - 1:
                    # Asignar el remanente a la última bodega para evitar errores de redondeo
                    wh_qty = remaining_stock
                else:
                    share = dist_map[wh] / total_ingresos
                    wh_qty = round(item["physical_stock"] * share)
                    remaining_stock -= wh_qty
                
                if wh_qty > 0:
                    # Limpiar decimales si son enteros
                    wh_qty_display = int(wh_qty) if wh_qty.is_integer() else round(wh_qty, 2)
                    warehouse_shares.append(f"{wh}({wh_qty_display})")
        else:
            # Fallback si no hay ingresos previos registrados: poner todo el stock en la bodega 'Principal'
            if item["physical_stock"] > 0:
                wh_qty_display = int(item["physical_stock"]) if float(item["physical_stock"]).is_integer() else item["physical_stock"]
                warehouse_shares.append(f"Principal({wh_qty_display})")
                
        item["warehouse_display"] = ", ".join(warehouse_shares) if warehouse_shares else "Sin Stock"
        
        min_stock = item.get("min_stock", 10)
        if item["total_stock"] <= min_stock:
            item["status"] = "Stock Bajo"
            low_stock_count += 1
        else:
            item["status"] = "Normal"
            
        item["stock_percent"] = min(100, int((item["total_stock"] / max(1, item["stock"] + 100)) * 100))
        
    inventory_stats["low_stock"] = low_stock_count
    inventory_stats["total_value"] = round(total_bodega_value, 2)
    
    from db import get_all_lot_stock
    lot_stock_list = get_all_lot_stock()

    warehouses_set = set(get_page_data("ingreso_warehouses") or ["Almacén Principal", "Almacén Secundario"])
    for lot in lot_stock_list:
        if lot.get("warehouse"):
            warehouses_set.add(lot["warehouse"])
    warehouses_list = sorted(list(warehouses_set))

    return render_template(
        'inventario.html',
        inventory_stats=inventory_stats,
        inventory_items=inventory_items,
        inventory_categories=inventory_categories,
        inventory_stock_filters=inventory_stock_filters,
        lot_stock_list=lot_stock_list,
        warehouses_list=warehouses_list,
        reservation_diagnostics=reservation_diagnostics,
    )

@inventario_bp.route('/ingreso-mercaderia', methods=['GET', 'POST'])
def ingreso_mercaderia():
    """Módulo de Ingreso de Mercadería con validación de OC y registro de documento"""
    default_date = datetime.now().strftime('%Y-%m-%d')
    import os
    from db import (
        list_suppliers,
        get_page_data,
        register_inventory_entry,
        list_inventory_entries,
        create_purchase_invoice,
    )

    if request.method == 'POST':
        ingreso_date    = (request.form.get('ingreso_date') or default_date).strip()
        document_number = (request.form.get('document_number') or '').strip()
        order_number    = (request.form.get('order_number') or document_number).strip()
        po_id           = request.form.get('purchase_order_id', type=int)
        warehouse       = (request.form.get('warehouse') or '').strip()
        notes           = (request.form.get('notes') or '').strip()

        # Campos de documento
        document_type   = request.form.get('document_type', 'guia_despacho').strip()
        invoice_amount  = request.form.get('invoice_amount', type=float) or 0.0
        invoice_date    = (request.form.get('invoice_date') or ingreso_date).strip()
        due_date        = (request.form.get('due_date') or '').strip()

        if not document_number:
            doc_label = "Factura" if document_type == 'factura' else "Guía de Despacho"
            flash(f"Debe ingresar el N° de {doc_label}.", "danger")
            return redirect(url_for('inventario.ingreso_mercaderia'))

        if document_type == 'factura' and not due_date:
            flash("Para ingresos con Factura, debe ingresar la Fecha de Vencimiento.", "danger")
            return redirect(url_for('inventario.ingreso_mercaderia'))

        product_ids = request.form.getlist('product_id[]')
        quantities  = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        lot_numbers = request.form.getlist('lot_number[]')

        from db import get_product
        items = []
        for i, (pid, qty_raw, price_raw) in enumerate(zip(product_ids, quantities, unit_prices)):
            if not pid:
                continue
            try:
                qty   = int(qty_raw)   if qty_raw   else 0
                price = float(price_raw) if price_raw else 0.0
            except ValueError:
                continue
            lot_num = (lot_numbers[i] if i < len(lot_numbers) else "").strip()

            # Validación de lote obligatorio si el producto lo requiere
            prod = get_product(int(pid))
            if prod and prod.get('requires_lot') and not lot_num:
                flash(f"El producto '{prod.get('name')}' requiere obligatoriamente registrar su Número de Lote.", "danger")
                return redirect(url_for('inventario.ingreso_mercaderia'))

            if qty > 0:
                items.append({
                    "product_id": int(pid),
                    "quantity": qty,
                    "unit_price": price,
                    "lot_number": lot_num
                })

        if not order_number or not po_id or not warehouse or not items:
            flash("Complete todos los campos obligatorios y agregue productos válidos.", "danger")
            return redirect(url_for('inventario.ingreso_mercaderia'))

        # Manejo de upload de foto del documento
        doc_file_path = None
        doc_file = request.files.get('document_file')
        if doc_file and doc_file.filename:
            if not allowed_file(doc_file.filename):
                flash("Formato de documento no permitido. Formatos válidos: PNG, JPG, JPEG, WEBP, PDF.", "danger")
                return redirect(url_for('inventario.ingreso_mercaderia'))
            upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'documentos_compra')
            os.makedirs(upload_dir, exist_ok=True)
            from werkzeug.utils import secure_filename
            clean_original = secure_filename(doc_file.filename)
            ext = os.path.splitext(clean_original)[1].lower()
            safe_base = secure_filename(f"{document_type}_{document_number or order_number}")
            filename = f"{safe_base}{ext}"
            save_path = os.path.abspath(os.path.join(upload_dir, filename))
            if not save_path.startswith(os.path.abspath(upload_dir) + os.sep) and save_path != os.path.abspath(upload_dir):
                flash("Nombre de archivo inválido detectado.", "danger")
                return redirect(url_for('inventario.ingreso_mercaderia'))
            doc_file.save(save_path)
            doc_file_path = f"documentos_compra/{filename}"

        try:
            # Recalcular obligatoriamente en el backend como fuente de verdad:
            # Neto = suma de (cantidad * precio_unitario) de los productos recibidos
            # IVA = 19% del Neto
            # Total = Neto + IVA
            neto_receipt = sum(item["quantity"] * item["unit_price"] for item in items)
            iva_receipt = round(neto_receipt * 0.19)
            total_receipt = neto_receipt + iva_receipt

            entry_id = register_inventory_entry(
                po_id, order_number, ingreso_date, warehouse, notes, items,
                document_type=document_type,
                document_number=document_number,
                document_file=doc_file_path,
            )

            # Si es factura → crear registro en purchase_invoices como "Pendiente" con monto total calculado (Neto + IVA)
            # Si es guía de despacho → crear registro como "Sin Factura" (alerta activa) con monto estimado
            if document_type == 'factura':
                inv_status = 'Pendiente'
                calculated_invoice_amount = total_receipt
            else:
                inv_status = 'Sin Factura'   # guía: aún no llega la factura
                calculated_invoice_amount = total_receipt

            # Obtener supplier_id de la OC
            from db import get_purchase_order
            po = get_purchase_order(po_id)
            supplier_id = po['supplier_id'] if po else None

            create_purchase_invoice({
                'inventory_entry_id': entry_id,
                'purchase_order_id':  po_id,
                'supplier_id':        supplier_id,
                'invoice_number':     document_number if document_type == 'factura' else '',
                'invoice_amount':     calculated_invoice_amount,
                'invoice_date':       invoice_date,
                'due_date':           due_date,
                'document_file':      doc_file_path,
                'payment_status':     inv_status,
                'notes':              f"Doc. tipo: {document_type} N°{document_number} (Neto: ${neto_receipt:,.0f} + IVA: ${iva_receipt:,.0f})",
            })

            flash(f"Ingreso de mercadería #{order_number} registrado con éxito y stock actualizado.", "success")
        except ValueError as e:
            flash(f"Error al registrar ingreso: {str(e)}", "danger")

        return redirect(url_for('inventario.ingreso_mercaderia'))

    suppliers       = list_suppliers()
    warehouses      = get_page_data("ingreso_warehouses")
    recent_ingresos = list_inventory_entries(limit=20)
    selected_po_id  = request.args.get('po_id', type=int)

    # Cargar OCs activas disponibles para recepcionar
    from db import get_connection
    active_ocs = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT po.id, po.oc_number, po.order_date, po.total_amount, po.supplier_id, s.name as supplier_name
                FROM purchase_orders po
                JOIN suppliers s ON po.supplier_id = s.id
                WHERE po.status IN ('Emitida', 'Parcialmente Recibida')
                ORDER BY po.id DESC
                """
            )
            active_ocs = [dict(r) for r in cur.fetchall()]

    selected_supplier_id = request.args.get('supplier_id', type=int)
    if selected_po_id and not selected_supplier_id:
        for oc in active_ocs:
            if oc['id'] == selected_po_id:
                selected_supplier_id = oc['supplier_id']
                break

    return render_template(
        'ingreso_mercaderia.html',
        default_date=default_date,
        ingreso_date=default_date,
        order_number='',
        warehouse='',
        notes='',
        suppliers=suppliers,
        warehouses=warehouses,
        recent_ingresos=recent_ingresos,
        active_ocs=active_ocs,
        selected_po_id=selected_po_id,
        selected_supplier_id=selected_supplier_id,
        selected_product_id=None,
    )

@inventario_bp.route('/productos', methods=['GET', 'POST'])
def productos():
    """Gestión de productos"""
    return_to = (request.args.get('return_to') or '').strip()
    supplier_id = request.args.get('supplier_id', type=int)
    supplier = get_supplier(supplier_id) if supplier_id else None
    categories = get_page_data("inventory_categories") or []
    category_descriptions = get_page_data("inventory_category_descriptions") or {}
    
    # Normalizar y eliminar duplicados manteniendo orden
    normalized_seen = set()
    unique_categories = []
    for category in categories:
        if not isinstance(category, str):
            continue
        clean = category.strip()
        if not clean:
            continue
        if clean.lower() not in normalized_seen:
            normalized_seen.add(clean.lower())
            unique_categories.append(clean)
    
    categories = unique_categories
    category_message = request.args.get('cat_message')
    show_categories = request.args.get('show_categories')

    def normalize_category(value: str) -> str:
        if not value:
            return ""
        val = value.strip()
        if val.lower().startswith("categoria-"):
            return val
        return val

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'rename_category':
            rename_old = (request.form.get('rename_old_category') or '').strip()
            rename_new = (request.form.get('rename_new_category') or '').strip()
            rename_description = (request.form.get('rename_description') or '').strip()
            if rename_old and rename_new and rename_old != rename_new:
                if rename_old in categories:
                    categories = [rename_new if c == rename_old else c for c in categories]
                if rename_new not in categories:
                    categories.append(rename_new)
                set_page_data("inventory_categories", categories)
                rename_category(rename_old, rename_new)
                if rename_old in category_descriptions:
                    category_descriptions[rename_new] = category_descriptions.pop(rename_old)
                if rename_description:
                    category_descriptions[rename_new] = rename_description
                set_page_data("inventory_category_descriptions", category_descriptions)
            elif rename_old and rename_description:
                category_descriptions[rename_old] = rename_description
                set_page_data("inventory_category_descriptions", category_descriptions)
            return redirect(url_for('inventario.productos', cat_message='updated', show_categories=1))
        
        if action == 'delete_category':
            delete_name = (request.form.get('delete_category') or '').strip()
            if delete_name:
                normalized_delete = normalize_category(delete_name).lower()
                categories = [c for c in categories if c.lower() != normalized_delete]
                set_page_data("inventory_categories", categories)
                to_delete = [key for key in category_descriptions.keys() if key.lower() == normalized_delete]
                for key in to_delete:
                    category_descriptions.pop(key, None)
                set_page_data("inventory_category_descriptions", category_descriptions)
                delete_category(normalized_delete)
            return redirect(url_for('inventario.productos', cat_message='updated', show_categories=1))
        
        selected_category = (request.form.get('category') or '').strip()
        category_value = selected_category
        if category_value and category_value not in categories:
            categories.append(category_value)
            set_page_data("inventory_categories", categories)
            
        assoc_kg_val = request.form.get('associated_kg') or request.form.get('weight_kg')
        assoc_kg = float(assoc_kg_val.replace(',', '.')) if assoc_kg_val and assoc_kg_val.strip() else None

        min_stk_val = request.form.get('min_stock')
        min_stk = float(min_stk_val.replace(',', '.')) if min_stk_val and min_stk_val.strip() else 0.0

        product = {
            "sku": request.form.get('sku', '').strip(),
            "name": request.form.get('name', '').strip(),
            "description": request.form.get('description', '').strip(),
            "barcode": request.form.get('barcode', '').strip(),
            "internal_code": request.form.get('internal_code', '').strip(),
            "category": category_value,
            "photo_url": request.form.get('photo_url', '').strip(),
            "width_cm": request.form.get('width_cm') or None,
            "height_cm": request.form.get('height_cm') or None,
            "depth_cm": request.form.get('depth_cm') or None,
            "weight_kg": assoc_kg,
            "associated_kg": assoc_kg,
            "product_type": request.form.get('product_type', 'Final').strip(),
            "cost": float(request.form.get('cost', 0.0) or 0.0),
            "requires_lot": True if request.form.get('requires_lot') else False,
            "subcategory_material": request.form.get('subcategory_material', '').strip(),
            "line": request.form.get('line', '').strip(),
            "variety": request.form.get('variety', '').strip(),
            "line_variety": request.form.get('line_variety', '').strip() or (f"{request.form.get('line', '').strip()} - {request.form.get('variety', '').strip()}".strip(" -")),
            "format_capacity": request.form.get('format_capacity', '').strip(),
            "unit_of_measure": request.form.get('unit_of_measure', 'UN').strip() or 'UN',
            "min_stock": min_stk,
            "status": request.form.get('status', 'Activo').strip() or 'Activo',
            "bom_recipe": request.form.get('bom_recipe', '').strip(),
            "labeling": request.form.get('labeling', '').strip(),
            "notes": request.form.get('notes', '').strip(),
            "attachment_url": request.form.get('attachment_url', '').strip(),
            "created_at": datetime.now(timezone.utc).isoformat(timespec='seconds'),
        }

        if product["sku"] and product["name"]:
            product_id = insert_product(product)
            if supplier_id:
                add_product_supplier(product_id, supplier_id)

        if return_to:
            separator = '&' if '?' in return_to else '?'
            return redirect(f"{return_to}{separator}product_id={product_id}")
        return redirect(url_for('inventario.productos'))

    from db import get_products_paginated

    from core.pagination import PAGE_SIZE, parse_page
    page = parse_page(request.args.get('page'))
    per_page = PAGE_SIZE

    search_query = (request.args.get('search') or '').strip()
    selected_cat_filter = (request.args.get('category') or '').strip()
    selected_type_filter = (request.args.get('product_type') or '').strip()

    paginated_result = get_products_paginated(
        page=page,
        per_page=per_page,
        search=search_query,
        category=selected_cat_filter or None,
        product_type=selected_type_filter or None
    )

    return render_template(
        'productos.html',
        products=paginated_result["items"],
        pagination=paginated_result,
        search_query=search_query,
        current_category=selected_cat_filter,
        current_product_type=selected_type_filter,
        per_page=paginated_result["per_page"],
        current_page=paginated_result["page"],
        total_pages=paginated_result["total_pages"],
        total_products=paginated_result["total"],
        categories=categories,
        category_descriptions=category_descriptions,
        category_message=category_message,
        show_categories=show_categories,
        return_to=return_to,
        supplier_id=supplier_id,
        supplier=supplier,
    )


@inventario_bp.route('/productos/exportar')
def exportar_productos_excel():
    """Exporta el catálogo de productos (filtrado o completo) en formato Excel .xlsx"""
    from db import list_all_products_for_export
    from repositories.kardex_repo import get_all_products_kardex_summary
    from services.products_excel_service import generate_products_excel

    search_query = (request.args.get('search') or '').strip()
    category_filter = (request.args.get('category') or '').strip()
    type_filter = (request.args.get('product_type') or '').strip()

    # 1. Obtener catálogo según filtros (o completo si no hay filtros)
    products = list_all_products_for_export(
        search=search_query or None,
        category=category_filter or None,
        product_type=type_filter or None
    )

    # 2. Cargar en BATCH Stock y PPP referencial de Kardex (0 queries N+1)
    kardex_summary = get_all_products_kardex_summary()
    for p in products:
        sku = p.get("sku")
        k_data = kardex_summary.get(sku, {})
        p["current_stock"] = k_data.get("stock", 0)
        p["ppp_cost"] = k_data.get("ppp", p.get("cost", 0.0))

    excel_io = generate_products_excel(products, is_template=False)
    today_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"productos_{today_str}.xlsx"

    return send_file(
        excel_io,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )


@inventario_bp.route('/productos/plantilla-excel')
def plantilla_productos_excel():
    """Descarga la plantilla vacía oficial de productos en formato Excel .xlsx"""
    from services.products_excel_service import generate_products_excel

    excel_io = generate_products_excel([], is_template=True)
    filename = "plantilla_productos.xlsx"

    return send_file(
        excel_io,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )


@inventario_bp.route('/productos/importar/preview', methods=['POST'])
def importar_productos_preview():
    """Valida el archivo Excel subido y genera la previsualización de diferencias"""
    from db import get_products_lookup_maps
    from services.products_excel_service import parse_and_validate_products_excel

    if 'file' not in request.files:
        flash("No se ha seleccionado ningún archivo para importar.", "danger")
        return redirect(url_for('inventario.productos'))

    file = request.files['file']
    if not file or not file.filename:
        flash("Archivo no válido o vacío.", "danger")
        return redirect(url_for('inventario.productos'))

    if not file.filename.lower().endswith('.xlsx'):
        flash("El archivo debe tener extensión .xlsx (Excel).", "danger")
        return redirect(url_for('inventario.productos'))

    by_sku, by_id = get_products_lookup_maps()
    result = parse_and_validate_products_excel(file.stream, by_sku, by_id)

    if not result["success"]:
        flash(result["error"], "danger")
        return redirect(url_for('inventario.productos'))

    # Guardar en almacenamiento temporal del servidor (server-side cache) con import_id seguro
    from services.products_excel_service import store_preview_cache, pop_preview_cache
    user_id = session.get('user_id', 'anonymous')
    import_id = store_preview_cache(user_id, result["items"], result["summary"])
    session['products_import_id'] = import_id

    return render_template(
        'productos_import_preview.html',
        items=result["items"],
        summary=result["summary"],
        import_id=import_id
    )


@inventario_bp.route('/productos/importar/confirmar', methods=['POST'])
def importar_productos_confirmar():
    """Aplica las creaciones y actualizaciones validadas de productos en la base de datos"""
    from db import insert_product, update_product, get_connection
    from services.products_excel_service import pop_preview_cache

    user_id = session.get('user_id', 'anonymous')
    import_id = request.form.get('import_id') or session.pop('products_import_id', None)
    session.pop('products_import_id', None)

    if not import_id:
        flash("La sesión de importación expiró o no es válida. Por favor vuelva a subir el archivo.", "warning")
        return redirect(url_for('inventario.productos'))

    preview_data = pop_preview_cache(import_id, user_id)
    if not preview_data or 'items' not in preview_data:
        flash("La sesión de importación expiró o no es válida. Por favor vuelva a subir el archivo.", "warning")
        return redirect(url_for('inventario.productos'))

    items = preview_data["items"]
    created_count = 0
    updated_count = 0
    errors_count = 0

    with get_connection() as conn:
        for item in items:
            action = item.get("action")
            payload = item.get("payload", {})
            target_id = item.get("target_id")

            try:
                if action == "NUEVO":
                    payload["created_at"] = datetime.now(timezone.utc).isoformat(timespec='seconds')
                    insert_product(payload)
                    created_count += 1
                elif action == "MODIFICADO" and target_id:
                    update_product(target_id, payload)
                    updated_count += 1
            except Exception as e:
                errors_count += 1

    msg = f"Importación finalizada con éxito: {created_count} producto(s) creados, {updated_count} producto(s) actualizados."
    if errors_count > 0:
        msg += f" {errors_count} registro(s) tuvieron errores al persistir."
    flash(msg, "success" if errors_count == 0 else "warning")

    return redirect(url_for('inventario.productos'))


@inventario_bp.route('/productos/<int:product_id>/editar', methods=['GET', 'POST'])
def editar_producto(product_id):
    """Editar producto"""
    if request.method == 'POST':
        categories = get_page_data("inventory_categories") or []
        selected_category = (request.form.get('category') or '').strip()
        category_value = selected_category
        if category_value and category_value not in categories:
            categories.append(category_value)
            set_page_data("inventory_categories", categories)

        assoc_kg_val = request.form.get('associated_kg') or request.form.get('weight_kg')
        assoc_kg = float(assoc_kg_val.replace(',', '.')) if assoc_kg_val and assoc_kg_val.strip() else None

        min_stk_val = request.form.get('min_stock')
        min_stk = float(min_stk_val.replace(',', '.')) if min_stk_val and min_stk_val.strip() else 0.0

        product = {
            "sku": request.form.get('sku', '').strip(),
            "name": request.form.get('name', '').strip(),
            "description": request.form.get('description', '').strip(),
            "barcode": request.form.get('barcode', '').strip(),
            "internal_code": request.form.get('internal_code', '').strip(),
            "category": category_value,
            "photo_url": request.form.get('photo_url', '').strip(),
            "width_cm": request.form.get('width_cm') or None,
            "height_cm": request.form.get('height_cm') or None,
            "depth_cm": request.form.get('depth_cm') or None,
            "weight_kg": assoc_kg,
            "associated_kg": assoc_kg,
            "product_type": request.form.get('product_type', 'Final').strip(),
            "cost": float(request.form.get('cost', 0.0) or 0.0),
            "requires_lot": True if request.form.get('requires_lot') else False,
            "subcategory_material": request.form.get('subcategory_material', '').strip(),
            "line": request.form.get('line', '').strip(),
            "variety": request.form.get('variety', '').strip(),
            "line_variety": request.form.get('line_variety', '').strip() or (f"{request.form.get('line', '').strip()} - {request.form.get('variety', '').strip()}".strip(" -")),
            "format_capacity": request.form.get('format_capacity', '').strip(),
            "unit_of_measure": request.form.get('unit_of_measure', 'UN').strip() or 'UN',
            "min_stock": min_stk,
            "status": request.form.get('status', 'Activo').strip() or 'Activo',
            "bom_recipe": request.form.get('bom_recipe', '').strip(),
            "labeling": request.form.get('labeling', '').strip(),
            "notes": request.form.get('notes', '').strip(),
            "attachment_url": request.form.get('attachment_url', '').strip(),
        }

        # Manejar subida de foto
        if 'photo_file' in request.files and request.files['photo_file'].filename:
            photo_url = handle_photo_upload(product_id)
            if photo_url:
                product['photo_url'] = photo_url

        if product["sku"] and product["name"]:
            update_product(product_id, product)

        return redirect(url_for('inventario.productos'))

    product = get_product(product_id)
    categories = get_page_data("inventory_categories") or []
    all_suppliers = list_suppliers()
    product_suppliers = list_product_suppliers(product_id)
    return render_template(
        'editar_producto.html',
        product=product,
        categories=categories,
        all_suppliers=all_suppliers,
        product_suppliers=product_suppliers,
    )

@inventario_bp.route('/productos/<int:product_id>/eliminar', methods=['POST'])
def eliminar_producto(product_id):
    """Eliminar producto"""
    delete_product(product_id)
    return redirect(url_for('inventario.productos'))

@inventario_bp.route('/productos/<int:product_id>/proveedores/agregar', methods=['POST'])
def agregar_proveedor_producto(product_id):
    """Agregar proveedor a un producto"""
    supplier_id = request.form.get('supplier_id')
    if supplier_id:
        add_product_supplier(product_id, int(supplier_id))
    return redirect(url_for('inventario.editar_producto', product_id=product_id))

@inventario_bp.route('/productos/<int:product_id>/proveedores/<int:supplier_id>/eliminar', methods=['POST'])
def eliminar_proveedor_producto(product_id, supplier_id):
    """Eliminar proveedor de un producto"""
    remove_product_supplier(product_id, supplier_id)
    return redirect(url_for('inventario.editar_producto', product_id=product_id))

@inventario_bp.route('/api/proveedores/<int:supplier_id>/productos')
def productos_por_proveedor(supplier_id):
    """Obtener productos asociados a un proveedor"""
    products = list_products_by_supplier(supplier_id)
    return jsonify(products)

@inventario_bp.route('/inventario/producto/<string:code>/min-stock', methods=['POST'])
def update_product_min_stock(code):
    """Actualiza el stock mínimo de un producto en el JSON de inventario"""
    new_min = request.form.get('min_stock', type=int)
    if new_min is None or new_min < 0:
        flash("Valor de stock mínimo no válido.", "danger")
        return redirect(url_for('inventario.inventario'))
        
    items = get_page_data("inventory_items") or []
    updated = False
    for item in items:
        if item.get("code") == code:
            item["min_stock"] = new_min
            updated = True
            break
            
    if updated:
        set_page_data("inventory_items", items)
        flash(f"Stock mínimo del producto {code} actualizado a {new_min} correctamente.", "success")
    else:
        flash("Producto no encontrado en el inventario.", "danger")
        
    return redirect(url_for('inventario.inventario'))

@inventario_bp.route('/api/inventario/producto/<string:code>/entradas')
def product_entries_api(code):
    """Obtiene el historial de entradas y promedio ponderado para un producto en los últimos X meses"""
    from db import get_connection
    from datetime import datetime, timedelta
    
    months = request.args.get('months', default=1, type=int)
    if months <= 0:
        months = 1
        
    cutoff_date = (datetime.now() - timedelta(days=months * 30)).strftime('%Y-%m-%d')
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM products WHERE sku = %s", (code,))
            prod = cur.fetchone()
            if not prod:
                return jsonify({"error": "Producto no encontrado"}), 404
                
            product_id = prod["id"]
            product_name = prod["name"]
            
            cur.execute(
                """
                SELECT ie.entry_date, ie.order_number, iei.quantity, iei.unit_price, iei.total
                FROM inventory_entry_items iei
                JOIN inventory_entries ie ON iei.inventory_entry_id = ie.id
                WHERE iei.product_id = %s AND ie.entry_date >= %s
                ORDER BY ie.entry_date DESC
                """,
                (product_id, cutoff_date)
            )
            rows = cur.fetchall()
            
            entries = []
            total_qty = 0
            total_amount = 0.0
            
            for row in rows:
                r_dict = dict(row)
                entries.append(r_dict)
                total_qty += r_dict["quantity"]
                total_amount += r_dict["total"]
                
            avg_price = total_amount / total_qty if total_qty > 0 else 0.0
            
            return jsonify({
                "product_code": code,
                "product_name": product_name,
                "total_qty": total_qty,
                "total_amount": round(total_amount, 2),
                "avg_price": round(avg_price, 2),
                "entries": entries
            })

@inventario_bp.route('/kardex')
def ver_kardex():
    """
    Página centralizada del Kardex Valorizado / PPP con paginación server-side.
    - Si no se especifica producto (o product_id vacío): Muestra el listado paginado (25 por pág) con búsqueda server-side y tarjetas globales.
    - Si se especifica product_id: Muestra los movimientos paginados (25 por pág) preservando con exactitud el cálculo continuo del PPP.
    """
    from db import (
        get_product,
        get_product_kardex_history,
        get_all_products_kardex_paginated,
        list_products,
        MOVEMENT_TYPE_LABELS
    )

    all_products_list = list_products()
    product_id = request.args.get('product_id', type=int)

    selected_product = None
    kardex_data = None
    current_filters = {}

    try:
        page = int(request.args.get('page', 1))
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = int(request.args.get('per_page', 25))
    except (ValueError, TypeError):
        per_page = 25

    search_query = request.args.get('search', '').strip()

    if product_id:
        selected_product = get_product(product_id)
        if not selected_product:
            flash("El producto seleccionado no existe.", "warning")
            return redirect(url_for('inventario.ver_kardex'))

        order_dir = request.args.get('order', 'desc')
        order_asc = (order_dir.lower() == 'asc')
        start_date = request.args.get('start_date') or None
        end_date = request.args.get('end_date') or None
        movement_type_filter = request.args.get('movement_type') or None

        kardex_data = get_product_kardex_history(
            product_id=product_id,
            start_date=start_date,
            end_date=end_date,
            movement_type_filter=movement_type_filter,
            order_asc=order_asc,
            page=page,
            per_page=per_page
        )
        from services.stock_context import get_operational_balance
        kardex_data['operational_balance'] = get_operational_balance(selected_product['sku'])
        if kardex_data['operational_balance'] is not None:
            kardex_data['stock_delta'] = round(kardex_data['current_stock'] - kardex_data['operational_balance']['physical'], 3)
        current_filters = {
            "order": "asc" if order_asc else "desc",
            "start_date": start_date or "",
            "end_date": end_date or "",
            "movement_type": movement_type_filter or "",
            "page": kardex_data.get("page", 1),
            "per_page": kardex_data.get("per_page", 25)
        }
        all_summary = None
    else:
        all_summary = get_all_products_kardex_paginated(
            page=page,
            per_page=per_page,
            search=search_query
        )
        current_filters = {
            "search": search_query,
            "page": all_summary["page"],
            "per_page": all_summary["per_page"]
        }

    return render_template(
        'kardex.html',
        all_products=all_products_list,
        selected_product=selected_product,
        kardex=kardex_data,
        all_summary=all_summary,
        movement_type_labels=MOVEMENT_TYPE_LABELS,
        current_filters=current_filters
    )


@inventario_bp.route('/productos/<int:product_id>/kardex')
def ver_kardex_producto(product_id):
    """Redirección o vista directa del Kardex para un producto específico conservando query params."""
    args = dict(request.args)
    args['product_id'] = product_id
    return redirect(url_for('inventario.ver_kardex', **args))


@inventario_bp.route('/api/productos/<int:product_id>/kardex')
def api_kardex_producto(product_id):
    """Endpoint API JSON para consultar el Kardex Valorizado de un producto con filtros y paginación opcional."""
    from db import get_product_kardex_history
    order_dir = request.args.get('order', 'desc')
    order_asc = (order_dir.lower() == 'asc')
    start_date = request.args.get('start_date') or None
    end_date = request.args.get('end_date') or None
    movement_type_filter = request.args.get('movement_type') or None
    page = request.args.get('page', type=int)
    per_page = request.args.get('per_page', type=int)

    kardex_data = get_product_kardex_history(
        product_id=product_id,
        start_date=start_date,
        end_date=end_date,
        movement_type_filter=movement_type_filter,
        order_asc=order_asc,
        page=page,
        per_page=per_page
    )
    if not kardex_data:
        return jsonify({"error": "Producto no encontrado"}), 404

    return jsonify(kardex_data)

@inventario_bp.route('/api/recepciones/<int:entry_id>')
def api_inventory_entry_detail(entry_id):
    """
    Endpoint API JSON para consultar el detalle completo de un ingreso de mercadería
    específico por su ID real (inventory_entries.id).
    Aplica RBAC y autenticación.
    """
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "Autenticación requerida"}), 401

    # RBAC: Requiere permiso de inventario, compras o administración/crear_registros
    user_perms = session.get('permissions', {})
    user_role = session.get('role_name', '')
    has_permission = (
        user_role in ('Administrativo', 'Gerente') or
        user_perms.get('inventario') is True or
        user_perms.get('compras') is True or
        user_perms.get('productos') is True or
        user_perms.get('administracion') is True
    )
    if not has_permission:
        return jsonify({"status": "error", "message": "Acceso no autorizado a recepciones de inventario."}), 403

    from db import get_inventory_entry_detail
    detail = get_inventory_entry_detail(entry_id)
    if not detail:
        return jsonify({"status": "error", "message": "Ingreso de mercadería no encontrado."}), 404

    return jsonify({"status": "success", "data": detail})
