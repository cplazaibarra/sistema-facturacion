from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
import json
from db import (
    get_page_data,
    list_roles,
    get_role,
    insert_role,
    update_role,
    delete_role,
    list_users,
    get_user,
    insert_user,
    update_user,
    delete_user,
    set_page_data,
    list_products
)

usuarios_bp = Blueprint('usuarios', __name__)

@usuarios_bp.route('/administracion')
def administracion():
    """Módulo de Administración"""
    modules = get_page_data("admin_modules") or []
    modules = [m for m in modules if m.get('link') != '/administracion/listas-precios']
    settings = get_page_data("admin_settings")
    return render_template('administracion.html', modules=modules, settings=settings)

@usuarios_bp.route('/administracion/listas-precios', methods=['GET', 'POST'])
def listas_precios():
    from db import get_connection
    
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
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'save_config':
            config["base_margin"] = float(request.form.get('base_margin', 20.0))
            
            cat_names = request.form.getlist('cat_name[]')
            cat_margins = request.form.getlist('cat_margin[]')
            
            categories = []
            for i, (name, margin) in enumerate(zip(cat_names, cat_margins)):
                if not name.strip():
                    continue
                categories.append({
                    "id": f"cat_{i}",
                    "name": name.strip(),
                    "margin": float(margin or 0.0)
                })
            config["categories"] = categories
            set_page_data("price_list_config", config)
            flash("Configuración de categorías y márgenes actualizada.", "success")
            return redirect(url_for('usuarios.listas_precios'))
            
        elif action == 'save_product_margins':
            sku = request.form.get('sku')
            base_margin = float(request.form.get('base_margin', 20.0))
            
            category_margins = {}
            for key, value in request.form.items():
                if key.startswith('margins['):
                    cat_id = key.split('[')[1].split(']')[0]
                    category_margins[cat_id] = float(value or 0.0)
            
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO product_margins (product_sku, base_margin, category_margins)
                        VALUES (%s, %s, %s::jsonb)
                        ON CONFLICT (product_sku) DO UPDATE
                        SET base_margin = EXCLUDED.base_margin,
                            category_margins = EXCLUDED.category_margins
                        """,
                        (sku, base_margin, json.dumps(category_margins))
                    )
                conn.commit()
            return jsonify({"status": "ok", "message": f"Márgenes de {sku} actualizados."})

    # Carga de VPP por producto
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

    # Mapeo de precios por catálogo fallback
    catalog_prices = {}
    inventory_items = get_page_data("inventory_items") or []
    for item in inventory_items:
        catalog_prices[item["code"]] = item.get("price", 0.0)

    # Carga de márgenes específicos de producto
    prod_margins_map = {}
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM product_margins")
            for row in cur.fetchall():
                prod_margins_map[row["product_sku"]] = dict(row)

    products_db = list_products()
    products_display = []
    
    for p in products_db:
        if p.get("product_type", "Final") == "Insumo":
            continue
        sku = p["sku"]
        p_id = p["id"]
        
        vpp = vpp_map.get(p_id)
        if vpp is None:
            # Intentar obtener de catalog_prices
            vpp = catalog_prices.get(sku)
            
        if vpp is None or vpp == 0.0:
            # Usar el Costo Unitario de la tabla de productos
            vpp = float(p.get("cost", 0.0) or 0.0)
            
        m = prod_margins_map.get(sku)
        product_cat_margins = {}
        if m:
            base_margin = m["base_margin"]
            product_cat_margins = m["category_margins"] or {}
        else:
            base_margin = config["base_margin"]
            
        price_base = vpp * (1 + base_margin / 100)
        
        categories_display = []
        for cat in config["categories"]:
            cat_id = cat["id"]
            margin = product_cat_margins.get(cat_id)
            if margin is None:
                margin = cat["margin"]
                
            price_final = price_base * (1 + margin / 100)
            categories_display.append({
                "id": cat_id,
                "name": cat["name"],
                "margin": margin,
                "price_final": round(price_final, 2)
            })
            
        products_display.append({
            "id": p_id,
            "sku": sku,
            "name": p["name"],
            "vpp": vpp,
            "base_margin": base_margin,
            "price_base": round(price_base, 2),
            "categories": categories_display
        })

    return render_template(
        'listas_precios.html',
        config=config,
        products=products_display
    )

@usuarios_bp.route('/usuarios', methods=['GET', 'POST'])
def usuarios():
    """Gestión de usuarios"""
    if request.method == 'POST':
        user = {
            "username": request.form.get('username', '').strip(),
            "email": request.form.get('email', '').strip(),
            "full_name": request.form.get('full_name', '').strip(),
            "role_id": int(request.form.get('role_id', 0)),
            "password": request.form.get('password', 'password123'),
            "is_active": int(request.form.get('is_active', 1)),
            "created_at": datetime.utcnow().isoformat(timespec='seconds'),
        }

        if user["username"] and user["email"] and user["full_name"] and user["role_id"]:
            insert_user(user)

        return redirect(url_for('usuarios.usuarios'))

    users = list_users()
    roles = list_roles()
    return render_template('usuarios.html', users=users, roles=roles)

@usuarios_bp.route('/usuarios/<int:user_id>/editar', methods=['GET', 'POST'])
def editar_usuario(user_id):
    """Editar usuario"""
    if request.method == 'POST':
        user = {
            "email": request.form.get('email', '').strip(),
            "full_name": request.form.get('full_name', '').strip(),
            "role_id": int(request.form.get('role_id', 0)),
            "is_active": int(request.form.get('is_active', 1)),
        }
        update_user(user_id, user)
        return redirect(url_for('usuarios.usuarios'))

    user = get_user(user_id)
    roles = list_roles()
    return render_template('editar_usuario.html', user=user, roles=roles)

@usuarios_bp.route('/usuarios/<int:user_id>/eliminar', methods=['POST'])
def eliminar_usuario(user_id):
    """Eliminar usuario"""
    delete_user(user_id)
    referrer = request.referrer
    if referrer and '/roles' in referrer:
        return redirect(url_for('usuarios.roles'))
    return redirect(url_for('usuarios.usuarios'))

@usuarios_bp.route('/roles', methods=['GET', 'POST'])
def roles():
    """Gestión de roles"""
    if request.method == 'POST':
        # Construir JSON de permisos desde checkboxes
        perms = {}
        for p in ["dashboard", "usuarios", "ventas", "inventario", "productos", "administracion", "reportes", "configuracion", "crear_registros", "aprobar_registros", "solo_ver"]:
            perms[p] = True if request.form.get(f"perm_{p}") else False
            
        role = {
            "name": request.form.get('name', '').strip(),
            "description": request.form.get('description', '').strip(),
            "permissions": json.dumps(perms),
            "created_at": datetime.utcnow().isoformat(timespec='seconds'),
        }

        if role["name"]:
            insert_role(role)

        return redirect(url_for('usuarios.roles'))

    all_roles = list_roles()
    users = list_users()
    return render_template('roles.html', roles=all_roles, users=users)

@usuarios_bp.route('/roles/<int:role_id>/editar', methods=['GET', 'POST'])
def editar_rol(role_id):
    """Editar rol"""
    if request.method == 'POST':
        # Construir JSON de permisos desde checkboxes
        perms = {}
        for p in ["dashboard", "usuarios", "ventas", "inventario", "productos", "administracion", "reportes", "configuracion", "crear_registros", "aprobar_registros", "solo_ver"]:
            perms[p] = True if request.form.get(f"perm_{p}") else False

        role = {
            "name": request.form.get('name', '').strip(),
            "description": request.form.get('description', '').strip(),
            "permissions": json.dumps(perms),
        }
        update_role(role_id, role)
        return redirect(url_for('usuarios.roles'))

    role = get_role(role_id)
    return render_template('editar_rol.html', role=role)

@usuarios_bp.route('/roles/<int:role_id>/eliminar', methods=['POST'])
def eliminar_rol(role_id):
    """Eliminar rol"""
    delete_role(role_id)
    return redirect(url_for('usuarios.roles'))

@usuarios_bp.route('/usuarios/<int:user_id>/reasignar-rol', methods=['POST'])
def quick_update_role(user_id):
    """Reasignar rol rápidamente desde la pantalla de roles"""
    role_id = request.form.get('role_id', type=int)
    if not role_id:
        flash("Rol no válido.", "danger")
        return redirect(url_for('usuarios.roles'))
        
    user = get_user(user_id)
    if not user:
        flash("Usuario no encontrado.", "danger")
        return redirect(url_for('usuarios.roles'))
        
    # Conservar el resto de campos del usuario y solo actualizar role_id
    updated_user_data = {
        "email": user["email"],
        "full_name": user["full_name"],
        "role_id": role_id,
        "is_active": user["is_active"]
    }
    update_user(user_id, updated_user_data)
    flash(f"Rol del usuario {user['full_name']} actualizado correctamente.", "success")
    return redirect(url_for('usuarios.roles'))


# === Endpoints para Cuentas Bancarias de la Empresa ===

@usuarios_bp.route('/administracion/cuentas-bancarias', methods=['GET', 'POST'])
def cuentas_bancarias():
    """Administrar cuentas bancarias de la empresa"""
    from db import list_bank_accounts, insert_bank_account
    if request.method == 'POST':
        account_data = {
            "bank_name": request.form.get('bank_name', '').strip(),
            "account_number": request.form.get('account_number', '').strip(),
            "account_type": request.form.get('account_type', '').strip(),
            "holder_name": request.form.get('holder_name', '').strip(),
            "holder_rut": request.form.get('holder_rut', '').strip(),
            "email": request.form.get('email', '').strip(),
            "status": request.form.get('status', 'Activa').strip()
        }
        if not account_data["bank_name"] or not account_data["account_number"] or not account_data["holder_name"]:
            flash("Banco, número de cuenta y titular son requeridos.", "warning")
        else:
            try:
                insert_bank_account(account_data)
                flash("Cuenta bancaria registrada exitosamente.", "success")
            except Exception as e:
                flash(f"Error al registrar la cuenta: Cuenta duplicada o datos inválidos.", "danger")
        return redirect(url_for('usuarios.cuentas_bancarias'))

    accounts = list_bank_accounts()
    return render_template('cuentas_bancarias.html', accounts=accounts)


@usuarios_bp.route('/administracion/cuentas-bancarias/<int:account_id>/editar', methods=['POST'])
def editar_cuenta_bancaria(account_id):
    """Editar una cuenta bancaria existente"""
    from db import update_bank_account
    account_data = {
        "bank_name": request.form.get('bank_name', '').strip(),
        "account_number": request.form.get('account_number', '').strip(),
        "account_type": request.form.get('account_type', '').strip(),
        "holder_name": request.form.get('holder_name', '').strip(),
        "holder_rut": request.form.get('holder_rut', '').strip(),
        "email": request.form.get('email', '').strip(),
        "status": request.form.get('status', 'Activa').strip()
    }
    try:
        update_bank_account(account_id, account_data)
        flash("Cuenta bancaria actualizada correctamente.", "success")
    except Exception as e:
        flash(f"Error al actualizar la cuenta.", "danger")
    return redirect(url_for('usuarios.cuentas_bancarias'))


@usuarios_bp.route('/administracion/cuentas-bancarias/<int:account_id>/eliminar', methods=['POST'])
def eliminar_cuenta_bancaria(account_id):
    """Eliminar una cuenta bancaria"""
    from db import delete_bank_account
    try:
        delete_bank_account(account_id)
        flash("Cuenta bancaria eliminada correctamente.", "success")
    except Exception as e:
        flash("No se puede eliminar la cuenta porque tiene pagos asociados.", "danger")
    return redirect(url_for('usuarios.cuentas_bancarias'))
