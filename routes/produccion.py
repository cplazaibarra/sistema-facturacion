from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
import json
from db import get_connection, get_page_data, set_page_data, list_products

produccion_bp = Blueprint('produccion', __name__)

@produccion_bp.route('/produccion')
def list_ots():
    """Listar órdenes de trabajo (OT)"""
    from db import get_connection
    ots = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT po.id, po.ot_number, po.quantity, po.status, po.notes, po.created_at, po.approved_at, po.completed_at,
                       p.sku as final_product_sku, p.name as final_product_name
                FROM production_orders po
                JOIN products p ON po.final_product_id = p.id
                ORDER BY po.id DESC
                """
            )
            rows = cur.fetchall()
            for r in rows:
                ot_id = r["id"]
                # Cargar insumos para esta OT
                cur.execute(
                    """
                    SELECT poi.quantity_required, p.sku as input_sku, p.name as input_name
                    FROM production_order_items poi
                    JOIN products p ON poi.input_product_id = p.id
                    WHERE poi.production_order_id = %s
                    """,
                    (ot_id,)
                )
                items = [dict(row) for row in cur.fetchall()]
                ot_dict = dict(r)
                ot_dict["items"] = items
                ots.append(ot_dict)
                
    return render_template('produccion.html', ots=ots)

@produccion_bp.route('/produccion/nueva', methods=['GET', 'POST'])
def nueva_ot():
    """Crear una nueva Orden de Trabajo"""
    from db import get_connection
    if request.method == 'POST':
        final_product_id = int(request.form.get('final_product_id'))
        quantity = int(request.form.get('quantity', 0))
        notes = request.form.get('notes', '').strip()
        
        input_ids = request.form.getlist('input_product_id[]')
        quantities = request.form.getlist('quantity_required[]')
        
        if not final_product_id or quantity <= 0:
            flash("Debe seleccionar un producto final y una cantidad válida.", "danger")
            return redirect(url_for('produccion.nueva_ot'))
            
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Generar ot_number
                cur.execute("SELECT COALESCE(MAX(id), 0) + 1 as next_id FROM production_orders")
                next_id = cur.fetchone()["next_id"]
                ot_number = f"OT-{next_id:05d}"
                
                # Insertar OT
                cur.execute(
                    """
                    INSERT INTO production_orders (ot_number, final_product_id, quantity, status, notes, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        ot_number,
                        final_product_id,
                        quantity,
                        "Solicitada",
                        notes,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                )
                ot_id = cur.fetchone()["id"]
                
                # Insertar insumos
                for inp_id, qty in zip(input_ids, quantities):
                    if not inp_id or not qty:
                        continue
                    cur.execute(
                        """
                        INSERT INTO production_order_items (production_order_id, input_product_id, quantity_required)
                        VALUES (%s, %s, %s)
                        """,
                        (ot_id, int(inp_id), float(qty))
                    )
            conn.commit()
            
        flash(f"Solicitud de Fabricación {ot_number} creada correctamente.", "success")
        return redirect(url_for('produccion.list_ots'))
        
    products = list_products()
    final_products = [p for p in products if p.get('product_type', 'Final') == 'Final']
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
        "created_at": datetime.utcnow().isoformat(timespec='seconds')
    }
    
    try:
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
        return jsonify({"status": "error", "message": str(e)}), 500

@produccion_bp.route('/produccion/ot/<int:ot_id>/aprobar', methods=['POST'])
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
    from db import get_connection
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Cargar datos de la OT
            cur.execute(
                """
                SELECT po.id, po.quantity, po.status, p.sku as final_sku
                FROM production_orders po
                JOIN products p ON po.final_product_id = p.id
                WHERE po.id = %s
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
                SELECT poi.quantity_required, p.sku as input_sku
                FROM production_order_items poi
                JOIN products p ON poi.input_product_id = p.id
                WHERE poi.production_order_id = %s
                """,
                (ot_id,)
            )
            items = cur.fetchall()
            
            # 3. Descontar stock e incrementar stock en inventory_items
            inventory_items = get_page_data("inventory_items") or []
            
            # Mapear inventario por código para facilitar acceso
            inv_map = {item["code"]: item for item in inventory_items}
            
            # Descontar insumos
            for item in items:
                sku = item["input_sku"]
                qty = item["quantity_required"]
                if sku in inv_map:
                    # Rebaja física definitiva
                    inv_map[sku]["stock"] = max(0.0, inv_map[sku]["stock"] - qty)
                    
            # Incrementar producto terminado
            final_sku = ot["final_sku"]
            if final_sku in inv_map:
                inv_map[final_sku]["stock"] = inv_map[final_sku]["stock"] + ot["quantity"]
            else:
                # Si no existía en el listado de inventario, lo agregamos
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
            
            # Guardar inventario
            set_page_data("inventory_items", inventory_items)
            
            # 4. Actualizar estado de la OT
            cur.execute(
                """
                UPDATE production_orders
                SET status = 'Finalizada', completed_at = %s
                WHERE id = %s
                """,
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ot_id)
            )
        conn.commit()
        
    flash("Orden de Trabajo finalizada. Insumos rebajados y producto terminado ingresado al stock.", "success")
    return redirect(url_for('produccion.list_ots'))
