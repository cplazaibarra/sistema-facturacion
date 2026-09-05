from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app, jsonify
from werkzeug.utils import secure_filename
import os
from datetime import datetime
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

inventario_bp = Blueprint('inventario', __name__)

def handle_photo_upload(product_id):
    """Maneja la subida de foto de producto. Retorna la ruta de la foto o None"""
    if 'photo_file' in request.files:
        file = request.files['photo_file']
        if file and file.filename:
            # Generar nombre seguro del archivo
            filename = secure_filename(f"product_{product_id}_{int(datetime.utcnow().timestamp())}.jpg")
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
    id_to_sku = {p['id']: p['sku'] for p in products_db}
    name_to_sku = {p['name'].strip().lower(): p['sku'] for p in products_db}
    
    # 3. Calcular stock reservado por SKU
    reserved_by_sku = {}
    for sale in pending_sales:
        for p in sale.get('products', []):
            qty = 0
            sku = None
            if isinstance(p, dict):
                qty = p.get('quantity', 0)
                p_id = p.get('product_id')
                p_name = p.get('product_name', '')
                if p_id and p_id in id_to_sku:
                    sku = id_to_sku[p_id]
                elif p_name:
                    p_name_clean = p_name.strip().lower()
                    if p_name_clean in name_to_sku:
                        sku = name_to_sku[p_name_clean]
                    else:
                        for name_db, sku_db in name_to_sku.items():
                            if name_db in p_name_clean or p_name_clean in name_db:
                                sku = sku_db
                                break
            elif isinstance(p, str):
                match = re.match(r'^(.*?)\s*\((\d+)\)$', p.strip())
                if match:
                    p_name = match.group(1).strip().lower()
                    qty = int(match.group(2))
                    if p_name in name_to_sku:
                        sku = name_to_sku[p_name]
                    else:
                        for name_db, sku_db in name_to_sku.items():
                            if name_db in p_name or p_name in name_db:
                                sku = sku_db
                                break
            
            if sku and qty > 0:
                reserved_by_sku[sku] = reserved_by_sku.get(sku, 0) + qty

    # 3.5. Obtener insumos reservados de OTs activas (Aprobadas)
    from db import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 3.5.1 Insumos iniciales planificados en OTs Aprobadas
            cur.execute(
                """
                SELECT poi.quantity_required, p.sku
                FROM production_order_items poi
                JOIN production_orders po ON poi.production_order_id = po.id
                JOIN products p ON poi.input_product_id = p.id
                WHERE po.status = 'Aprobada'
                """
            )
            for row in cur.fetchall():
                sku = row["sku"]
                qty = row["quantity_required"]
                reserved_by_sku[sku] = reserved_by_sku.get(sku, 0) + qty

            # 3.5.2 Insumos adicionales sumados en OTs Aprobadas
            cur.execute(
                """
                SELECT poai.quantity, p.sku
                FROM production_order_additional_items poai
                JOIN production_orders po ON poai.production_order_id = po.id
                JOIN products p ON poai.input_product_id = p.id
                WHERE po.status = 'Aprobada'
                """
            )
            for row in cur.fetchall():
                sku = row["sku"]
                qty = row["quantity"]
                reserved_by_sku[sku] = reserved_by_sku.get(sku, 0) + qty

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

    # 4. Aumentar cada ítem del inventario con su stock reservado, total y distribución de bodegas
    low_stock_count = 0
    for item in inventory_items:
        sku = item.get("code")
        reserved = reserved_by_sku.get(sku, 0)
        item["reserved"] = reserved
        item["total_stock"] = item["stock"] + reserved
        
        # Calcular distribución proporcional por bodegas basándose en los ingresos históricos de mercadería
        dist_map = warehouse_distribution.get(sku, {})
        total_ingresos = sum(dist_map.values())
        
        warehouse_shares = []
        if total_ingresos > 0:
            # Distribuir el stock disponible actual proporcionalmente
            remaining_stock = item["stock"]
            keys = list(dist_map.keys())
            for i, wh in enumerate(keys):
                if i == len(keys) - 1:
                    # Asignar el remanente a la última bodega para evitar errores de redondeo
                    wh_qty = remaining_stock
                else:
                    share = dist_map[wh] / total_ingresos
                    wh_qty = round(item["stock"] * share)
                    remaining_stock -= wh_qty
                
                if wh_qty > 0:
                    # Limpiar decimales si son enteros
                    wh_qty_display = int(wh_qty) if wh_qty.is_integer() else round(wh_qty, 2)
                    warehouse_shares.append(f"{wh}({wh_qty_display})")
        else:
            # Fallback si no hay ingresos previos registrados: poner todo el stock en la bodega 'Principal'
            if item["stock"] > 0:
                wh_qty_display = int(item["stock"]) if isinstance(item["stock"], (int, float)) and float(item["stock"]).is_integer() else item["stock"]
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
    
    from db import get_all_lot_stock
    lot_stock_list = get_all_lot_stock()

    return render_template(
        'inventario.html',
        inventory_stats=inventory_stats,
        inventory_items=inventory_items,
        inventory_categories=inventory_categories,
        inventory_stock_filters=inventory_stock_filters,
        lot_stock_list=lot_stock_list,
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
        ingreso_date = (request.form.get('ingreso_date') or default_date).strip()
        order_number = (request.form.get('order_number') or '').strip()
        po_id = request.form.get('purchase_order_id', type=int)
        warehouse = (request.form.get('warehouse') or '').strip()
        notes = (request.form.get('notes') or '').strip()

        # Campos de documento
        document_type   = request.form.get('document_type', 'guia_despacho').strip()
        document_number = (request.form.get('document_number') or '').strip()
        invoice_amount  = request.form.get('invoice_amount', type=float) or 0.0
        invoice_date    = (request.form.get('invoice_date') or ingreso_date).strip()
        due_date        = (request.form.get('due_date') or '').strip()

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
            upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'documentos_compra')
            os.makedirs(upload_dir, exist_ok=True)
            from werkzeug.utils import secure_filename
            ext = os.path.splitext(doc_file.filename)[1].lower()
            filename = secure_filename(f"{document_type}_{document_number or order_number}{ext}")
            save_path = os.path.join(upload_dir, filename)
            doc_file.save(save_path)
            doc_file_path = f"documentos_compra/{filename}"

        try:
            entry_id = register_inventory_entry(
                po_id, order_number, ingreso_date, warehouse, notes, items,
                document_type=document_type,
                document_number=document_number,
                document_file=doc_file_path,
            )

            # Si es factura → crear registro en purchase_invoices como "Pendiente"
            # Si es guía de despacho → crear registro como "Sin Factura" (alerta activa)
            if document_type == 'factura':
                inv_status = 'Pendiente'
            else:
                inv_status = 'Sin Factura'   # guía: aún no llega la factura

            # Obtener supplier_id de la OC
            from db import get_purchase_order
            po = get_purchase_order(po_id)
            supplier_id = po['supplier_id'] if po else None

            create_purchase_invoice({
                'inventory_entry_id': entry_id,
                'purchase_order_id':  po_id,
                'supplier_id':        supplier_id,
                'invoice_number':     document_number if document_type == 'factura' else '',
                'invoice_amount':     invoice_amount or (po['total_amount'] if po else 0),
                'invoice_date':       invoice_date,
                'due_date':           due_date,
                'document_file':      doc_file_path,
                'payment_status':     inv_status,
                'notes':              f"Doc. tipo: {document_type} N°{document_number}",
            })

            flash(f"Ingreso de mercadería #{order_number} registrado con éxito y stock actualizado.", "success")
        except ValueError as e:
            flash(f"Error al registrar ingreso: {str(e)}", "danger")

        return redirect(url_for('inventario.ingreso_mercaderia'))

    suppliers       = list_suppliers()
    warehouses      = get_page_data("ingreso_warehouses")
    recent_ingresos = list_inventory_entries()

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
        selected_supplier_id=None,
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
            "weight_kg": request.form.get('weight_kg') or None,
            "product_type": request.form.get('product_type', 'Final').strip(),
            "cost": float(request.form.get('cost', 0.0) or 0.0),
            "requires_lot": True if request.form.get('requires_lot') else False,
            "created_at": datetime.utcnow().isoformat(timespec='seconds'),
        }

        if product["sku"] and product["name"]:
            product_id = insert_product(product)
            if supplier_id:
                add_product_supplier(product_id, supplier_id)

        if return_to:
            separator = '&' if '?' in return_to else '?'
            return redirect(f"{return_to}{separator}product_id={product_id}")
        return redirect(url_for('inventario.productos'))

    products = list_products()
    return render_template(
        'productos.html',
        products=products,
        categories=categories,
        category_descriptions=category_descriptions,
        category_message=category_message,
        show_categories=show_categories,
        return_to=return_to,
        supplier_id=supplier_id,
        supplier=supplier,
    )

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
            "weight_kg": request.form.get('weight_kg') or None,
            "product_type": request.form.get('product_type', 'Final').strip(),
            "cost": float(request.form.get('cost', 0.0) or 0.0),
            "requires_lot": True if request.form.get('requires_lot') else False,
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
