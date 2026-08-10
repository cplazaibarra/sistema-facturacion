from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app
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
    set_page_data
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
    inventory_stats = get_page_data("inventory_stats")
    inventory_items = get_page_data("inventory_items")
    inventory_categories = get_page_data("inventory_categories")
    inventory_stock_filters = get_page_data("inventory_stock_filters")
    return render_template(
        'inventario.html',
        inventory_stats=inventory_stats,
        inventory_items=inventory_items,
        inventory_categories=inventory_categories,
        inventory_stock_filters=inventory_stock_filters,
    )

@inventario_bp.route('/ingreso-mercaderia', methods=['GET', 'POST'])
def ingreso_mercaderia():
    """Módulo de Ingreso de Mercadería"""
    default_date = datetime.now().strftime('%Y-%m-%d')
    if request.method == 'POST':
        ingreso_date = (request.form.get('ingreso_date') or default_date).strip()
        order_number = (request.form.get('order_number') or '').strip()
        supplier_id = request.form.get('supplier_id', type=int)
        warehouse = (request.form.get('warehouse') or '').strip()
        notes = (request.form.get('notes') or '').strip()
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')

        total_amount = 0.0
        items = []
        for product_id, qty_raw, price_raw in zip(product_ids, quantities, unit_prices):
            if not product_id:
                continue
            try:
                qty = int(float(qty_raw)) if qty_raw else 0
            except ValueError:
                qty = 0
            try:
                price = float(price_raw) if price_raw else 0.0
            except ValueError:
                price = 0.0
            if qty <= 0:
                continue
            line_total = qty * price
            total_amount += line_total
            items.append({
                "product_id": int(product_id),
                "quantity": qty,
                "unit_price": price,
                "total": line_total,
            })

        if not order_number or not supplier_id or not warehouse:
            error_message = "Completa número de orden, proveedor y almacén."
            suppliers = list_suppliers()
            warehouses = get_page_data("ingreso_warehouses")
            products = list_products()
            recent_ingresos = get_page_data("ingreso_recent")
            return render_template(
                'ingreso_mercaderia.html',
                default_date=default_date,
                ingreso_date=ingreso_date,
                order_number=order_number,
                warehouse=warehouse,
                notes=notes,
                suppliers=suppliers,
                warehouses=warehouses,
                products=products,
                recent_ingresos=recent_ingresos,
                selected_supplier_id=supplier_id,
                selected_product_id=None,
                error_message=error_message,
            )

        if not items:
            error_message = "Agrega al menos un producto con cantidad válida."
            suppliers = list_suppliers()
            warehouses = get_page_data("ingreso_warehouses")
            products = list_products()
            recent_ingresos = get_page_data("ingreso_recent")
            return render_template(
                'ingreso_mercaderia.html',
                default_date=default_date,
                ingreso_date=ingreso_date,
                order_number=order_number,
                warehouse=warehouse,
                notes=notes,
                suppliers=suppliers,
                warehouses=warehouses,
                products=products,
                recent_ingresos=recent_ingresos,
                selected_supplier_id=supplier_id,
                selected_product_id=None,
                error_message=error_message,
            )

        if items:
            supplier = get_supplier(supplier_id) if supplier_id else None
            recent = get_page_data("ingreso_recent") or []
            try:
                date_display = datetime.strptime(ingreso_date, '%Y-%m-%d').strftime('%d/%m/%Y')
            except ValueError:
                date_display = ingreso_date

            new_ingreso = {
                "id": len(recent) + 1,
                "order_number": order_number,
                "date": date_display,
                "supplier": supplier["name"] if supplier else "Proveedor",
                "items_count": len(items),
                "total": f"${total_amount:,.2f}",
                "warehouse": warehouse,
                "notes": notes,
                "status": "Completado"
            }
            recent.insert(0, new_ingreso)
            set_page_data("ingreso_recent", recent)
            flash(f"Ingreso de mercadería #{order_number} registrado con éxito.", "success")
            return redirect(url_for('inventario.ingreso_mercaderia'))

    suppliers = list_suppliers()
    warehouses = get_page_data("ingreso_warehouses")
    products = list_products()
    recent_ingresos = get_page_data("ingreso_recent")
    return render_template(
        'ingreso_mercaderia.html',
        default_date=default_date,
        ingreso_date=default_date,
        order_number='',
        warehouse='',
        notes='',
        suppliers=suppliers,
        warehouses=warehouses,
        products=products,
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
        }

        # Manejar subida de foto
        if 'photo_file' in request.files and request.files['photo_file'].filename:
            photo_url = handle_photo_upload(product_id)
            if photo_url:
                product['photo_url'] = photo_url

        if product["sku"] and product["name"]:
            update_product(product_id, product)

        return redirect(url_for('inventario.editar_producto', product_id=product_id))

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
