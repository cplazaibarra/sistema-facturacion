from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from security import require_permission, log_security_event
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
@require_permission('administracion')
def administracion():
    """Módulo de Administración"""
    modules = get_page_data("admin_modules") or []
    modules = [m for m in modules if m.get('link') != '/administracion/listas-precios']
    if not any(m.get('link') == '/administracion/gastos-operacionales' for m in modules):
        modules.insert(2, {"icon": "💸", "title": "Gastos Operacionales", "desc": "Administrar gastos recurrentes y sus proyecciones", "action": "Administrar", "link": "/administracion/gastos-operacionales"})
    settings = get_page_data("admin_settings")
    return render_template('administracion.html', modules=modules, settings=settings)


def _operational_expense_form_data():
    from db import list_bank_accounts
    data = {
        'name': request.form.get('name', '').strip(),
        'category_id': request.form.get('category_id', type=int),
        'description': request.form.get('description', '').strip(),
        'amount_type': request.form.get('amount_type', 'Fijo').strip(),
        'frequency': request.form.get('frequency', 'Mensual').strip(),
        'start_date': request.form.get('start_date', '').strip(),
        'due_rule': request.form.get('due_rule', 'Día del mes').strip(),
        'due_day': request.form.get('due_day', type=int),
        'end_date': request.form.get('end_date', '').strip() or None,
        'bank_account_id': request.form.get('bank_account_id', type=int),
        'beneficiary': request.form.get('beneficiary', '').strip(),
        'observations': request.form.get('observations', '').strip(),
        'status': request.form.get('status', 'Activo').strip(),
    }
    try:
        raw_amount = request.form.get('amount', '0').strip().replace('$', '').replace(' ', '')
        if ',' in raw_amount and '.' in raw_amount:
            raw_amount = raw_amount.replace('.', '').replace(',', '.')
        elif ',' in raw_amount:
            raw_amount = raw_amount.replace(',', '.')
        elif '.' in raw_amount and len(raw_amount.rsplit('.', 1)[1]) == 3:
            raw_amount = raw_amount.replace('.', '')
        data['amount'] = Decimal(raw_amount)
    except (AttributeError, InvalidOperation):
        data['amount'] = Decimal('0')
    return data


@usuarios_bp.route('/administracion/gastos-operacionales', methods=['GET', 'POST'])
@require_permission('administracion')
def gastos_operacionales():
    from db import create_operational_expense, list_bank_accounts, list_operational_expenses, list_expense_categories
    if request.method == 'POST':
        data = _operational_expense_form_data()
        if not data['name'] or not data.get('category_id') or data['amount'] <= 0 or not data['start_date']:
            flash('Nombre, categoría, monto y fecha de inicio son obligatorios.', 'warning')
        elif data['frequency'] not in {'Diario', 'Semanal', 'Quincenal', 'Mensual', 'Bimestral', 'Trimestral', 'Semestral', 'Anual'} or data['amount_type'] not in {'Fijo', 'Estimado'}:
            flash('Frecuencia o tipo de monto inválido.', 'danger')
        else:
            try:
                create_operational_expense(data, session.get('user_id'))
                log_security_event('OPERATIONAL_EXPENSE_CREATED', session.get('username'), data['name'])
                flash('Gasto operacional creado correctamente.', 'success')
            except ValueError as exc:
                flash(str(exc), 'warning')
        return redirect(url_for('usuarios.gastos_operacionales'))
    from repositories.operational_expenses_repo import calculate_next_occurrence_date
    expenses = list_operational_expenses(request.args.get('search', '').strip() or None, request.args.get('category') or None, request.args.get('status') or None)
    # Jinja/JSON necesita valores serializables para el formulario de edición.
    for expense in expenses:
        next_due = calculate_next_occurrence_date(expense)
        expense['next_due_date'] = next_due.isoformat() if next_due else None
        for key in ('start_date', 'end_date', 'created_at', 'updated_at'):
            if expense.get(key) is not None and hasattr(expense[key], 'isoformat'):
                expense[key] = expense[key].isoformat()
        if expense.get('amount') is not None:
            expense['amount'] = float(expense['amount'])
    categories = list_expense_categories()
    for category in categories:
        for key in ('created_at', 'updated_at'):
            if category.get(key) is not None and hasattr(category[key], 'isoformat'):
                category[key] = category[key].isoformat()
    return render_template('gastos_operacionales.html', expenses=expenses, categories=categories, bank_accounts=[a for a in list_bank_accounts() if a.get('status') == 'Activa'], editing=None)


@usuarios_bp.route('/administracion/gastos-operacionales/<int:expense_id>/editar', methods=['POST'])
@require_permission('administracion')
def editar_gasto_operacional(expense_id):
    from db import update_operational_expense
    data = _operational_expense_form_data()
    if not data['name'] or not data.get('category_id') or data['amount'] <= 0 or not data['start_date']:
        flash('Nombre, categoría, monto y fecha de inicio son obligatorios.', 'warning')
    else:
        try:
            update_operational_expense(expense_id, data, session.get('user_id'))
            log_security_event('OPERATIONAL_EXPENSE_UPDATED', session.get('username'), f'Gasto {expense_id}')
            flash('Gasto operacional actualizado. El historial no fue modificado.', 'success')
        except ValueError as exc:
            flash(str(exc), 'warning')
    return redirect(url_for('usuarios.gastos_operacionales'))


@usuarios_bp.route('/administracion/gastos-operacionales/categorias', methods=['POST'])
@require_permission('administracion')
def crear_categoria_gasto_operacional():
    from db import create_expense_category
    try:
        create_expense_category(request.form.get('name'), request.form.get('description'), session.get('user_id'))
        flash('Categoría creada correctamente.', 'success')
    except ValueError as exc:
        flash(str(exc), 'warning')
    return redirect(url_for('usuarios.gastos_operacionales'))


@usuarios_bp.route('/administracion/gastos-operacionales/categorias/<int:category_id>/editar', methods=['POST'])
@require_permission('administracion')
def editar_categoria_gasto_operacional(category_id):
    from db import update_expense_category
    try:
        if not update_expense_category(category_id, request.form.get('name'), request.form.get('description')):
            flash('La categoría no existe.', 'warning')
        else:
            flash('Categoría actualizada correctamente.', 'success')
    except ValueError as exc:
        flash(str(exc), 'warning')
    return redirect(url_for('usuarios.gastos_operacionales'))


@usuarios_bp.route('/administracion/gastos-operacionales/categorias/<int:category_id>/eliminar', methods=['POST'])
@require_permission('administracion')
def eliminar_categoria_gasto_operacional(category_id):
    from db import delete_expense_category
    try:
        deleted, count = delete_expense_category(category_id)
        if not deleted and count:
            flash(f'No se puede eliminar esta categoría porque está siendo utilizada por {count} gastos operacionales.', 'warning')
        elif deleted:
            flash('Categoría eliminada correctamente.', 'success')
        else:
            flash('La categoría no existe.', 'warning')
    except Exception:
        flash('No se pudo eliminar la categoría.', 'danger')
    return redirect(url_for('usuarios.gastos_operacionales'))


@usuarios_bp.route('/administracion/gastos-operacionales/<int:expense_id>/estado', methods=['POST'])
@require_permission('administracion')
def cambiar_estado_gasto_operacional(expense_id):
    from db import set_operational_expense_status
    status = request.form.get('status', 'Inactivo')
    if status not in {'Activo', 'Inactivo'}:
        flash('Estado inválido.', 'danger')
    else:
        set_operational_expense_status(expense_id, status, session.get('user_id'))
        flash('Estado del gasto actualizado.', 'success')
    return redirect(url_for('usuarios.gastos_operacionales'))


@usuarios_bp.route('/administracion/gastos-operacionales/<int:expense_id>/eliminar', methods=['POST'])
@require_permission('administracion')
def eliminar_gasto_operacional(expense_id):
    from db import delete_operational_expense
    if delete_operational_expense(expense_id, session.get('user_id')):
        log_security_event('OPERATIONAL_EXPENSE_DELETED', session.get('username'), f'Gasto {expense_id}')
        flash('Gasto operacional eliminado.', 'success')
    else:
        flash('Este gasto posee historial y no puede eliminarse físicamente. Puedes desactivarlo.', 'warning')
    return redirect(url_for('usuarios.gastos_operacionales'))

@usuarios_bp.route('/administracion/listas-precios', methods=['GET', 'POST'])
@require_permission('administracion')
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
                        VALUES (%s, 0, %s::jsonb)
                        ON CONFLICT (product_sku) DO UPDATE
                        SET category_margins = EXCLUDED.category_margins
                        """,
                        (sku, json.dumps(category_margins))
                    )
                conn.commit()
            return jsonify({"status": "ok", "message": f"Márgenes de {sku} actualizados."})

    # 1. Parámetros de paginación y búsqueda server-side
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

    # 2. Obtener productos de la página activa mediante SQL paginado
    from db import get_price_list_products_paginated, get_products_batch_calculated_cost
    paginated = get_price_list_products_paginated(
        page=current_page,
        per_page=per_page,
        search=search_query
    )
    products_db = paginated["items"]
    total_products = paginated["total"]
    total_pages = paginated["total_pages"]
    current_page = paginated["page"]

    # 3. Carga BATCH de Costo/VPP en máximo 2 queries solo para los 25 productos visibles (0 N+1)
    p_ids = [p["id"] for p in products_db]
    vpp_map = get_products_batch_calculated_cost(p_ids)

    # 4. Mapeo de precios por catálogo fallback
    catalog_prices = {}
    inventory_items = get_page_data("inventory_items") or []
    for item in inventory_items:
        catalog_prices[item["code"]] = item.get("price", 0.0)

    # 5. Carga de márgenes específicos de producto en lote
    prod_margins_map = {}
    p_skus = [p["sku"] for p in products_db]
    if p_skus:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM product_margins WHERE product_sku = ANY(%s)", (p_skus,))
                for row in cur.fetchall():
                    prod_margins_map[row["product_sku"]] = dict(row)

    products_display = []
    for p in products_db:
        sku = p["sku"]
        p_id = p["id"]
        
        vpp = vpp_map.get(p_id)
        if vpp is None:
            vpp = catalog_prices.get(sku)
            
        if vpp is None or vpp == 0.0:
            vpp = float(p.get("cost", 0.0) or 0.0)
            
        m = prod_margins_map.get(sku)
        product_cat_margins = {}
        if m:
            product_cat_margins = m.get("category_margins") or {}
            
        categories_display = []
        for cat in config.get("categories", []):
            cat_id = cat["id"]
            margin = product_cat_margins.get(cat_id)
            if margin is None:
                margin = cat["margin"]
            
            price_final = vpp * (1 + margin / 100.0)
            
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
            "categories": categories_display
        })

    return render_template(
        'listas_precios.html',
        config=config,
        products=products_display,
        current_page=current_page,
        per_page=per_page,
        total_pages=total_pages,
        total_products=total_products,
        search_query=search_query
    )

@usuarios_bp.route('/usuarios', methods=['GET', 'POST'])
@require_permission('usuarios')
def usuarios():
    """Gestión de usuarios"""
    if request.method == 'POST':
        user = {
            "username": request.form.get('username', '').strip(),
            "email": request.form.get('email', '').strip(),
            "full_name": request.form.get('full_name', '').strip(),
            "role_id": int(request.form.get('role_id', 0)),
            "password": request.form.get('password', '').strip() or 'password123',
            "is_active": int(request.form.get('is_active', 1)),
            "created_at": datetime.now(timezone.utc).isoformat(timespec='seconds'),
        }

        if user["username"] and user["email"] and user["full_name"] and user["role_id"]:
            new_id = insert_user(user)
            log_security_event('USER_CREATED', session.get('username'), f"Usuario '{user['username']}' (ID: {new_id}) creado")
            flash("Usuario creado exitosamente.", "success")

        return redirect(url_for('usuarios.usuarios'))

    users = list_users()
    roles = list_roles()
    return render_template('usuarios.html', users=users, roles=roles)

@usuarios_bp.route('/usuarios/<int:user_id>/editar', methods=['GET', 'POST'])
@require_permission('usuarios')
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
        log_security_event('USER_UPDATED', session.get('username'), f"Usuario ID {user_id} modificado")
        flash("Usuario actualizado correctamente.", "success")
        return redirect(url_for('usuarios.usuarios'))

    user = get_user(user_id)
    roles = list_roles()
    return render_template('editar_usuario.html', user=user, roles=roles)

@usuarios_bp.route('/usuarios/<int:user_id>/eliminar', methods=['POST'])
@require_permission('usuarios')
def eliminar_usuario(user_id):
    """Eliminar usuario"""
    delete_user(user_id)
    log_security_event('USER_DELETED', session.get('username'), f"Usuario ID {user_id} eliminado")
    flash("Usuario eliminado correctamente.", "success")
    referrer = request.referrer
    if referrer and '/roles' in referrer:
        return redirect(url_for('usuarios.roles'))
    return redirect(url_for('usuarios.usuarios'))

@usuarios_bp.route('/roles', methods=['GET', 'POST'])
@require_permission('usuarios')
def roles():
    """Gestión de roles"""
    if request.method == 'POST':
        # Construir JSON de permisos desde checkboxes
        perms = {}
        for p in ["dashboard", "usuarios", "ventas", "inventario", "productos", "administracion", "reportes", "configuracion", "crear_registros", "aprobar_registros", "inventory_adjustment_request", "inventory_adjustment_approve", "solo_ver"]:
            perms[p] = True if request.form.get(f"perm_{p}") else False
            
        role = {
            "name": request.form.get('name', '').strip(),
            "description": request.form.get('description', '').strip(),
            "permissions": json.dumps(perms),
            "created_at": datetime.now(timezone.utc).isoformat(timespec='seconds'),
        }

        if role["name"]:
            r_id = insert_role(role)
            log_security_event('ROLE_CREATED', session.get('username'), f"Rol '{role['name']}' creado")
            flash("Rol creado exitosamente.", "success")

        return redirect(url_for('usuarios.roles'))

    all_roles = list_roles()
    users = list_users()
    return render_template('roles.html', roles=all_roles, users=users)

@usuarios_bp.route('/roles/<int:role_id>/editar', methods=['GET', 'POST'])
@require_permission('usuarios')
def editar_rol(role_id):
    """Editar rol"""
    if request.method == 'POST':
        # Construir JSON de permisos desde checkboxes
        perms = {}
        for p in ["dashboard", "usuarios", "ventas", "inventario", "productos", "administracion", "reportes", "configuracion", "crear_registros", "aprobar_registros", "inventory_adjustment_request", "inventory_adjustment_approve", "solo_ver"]:
            perms[p] = True if request.form.get(f"perm_{p}") else False

        role = {
            "name": request.form.get('name', '').strip(),
            "description": request.form.get('description', '').strip(),
            "permissions": json.dumps(perms),
        }
        update_role(role_id, role)
        log_security_event('ROLE_UPDATED', session.get('username'), f"Rol ID {role_id} modificado")
        flash("Rol actualizado exitosamente.", "success")
        return redirect(url_for('usuarios.roles'))

    role = get_role(role_id)
    return render_template('editar_rol.html', role=role)

@usuarios_bp.route('/roles/<int:role_id>/eliminar', methods=['POST'])
@require_permission('usuarios')
def eliminar_rol(role_id):
    """Eliminar rol"""
    delete_role(role_id)
    log_security_event('ROLE_DELETED', session.get('username'), f"Rol ID {role_id} eliminado")
    flash("Rol eliminado correctamente.", "success")
    return redirect(url_for('usuarios.roles'))

@usuarios_bp.route('/usuarios/<int:user_id>/reasignar-rol', methods=['POST'])
@require_permission('usuarios')
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
    log_security_event('USER_ROLE_REASSIGNED', session.get('username'), f"Usuario ID {user_id} reasignado a rol {role_id}")
    flash(f"Rol del usuario {user['full_name']} actualizado correctamente.", "success")
    return redirect(url_for('usuarios.roles'))


# === Endpoints para Cuentas Bancarias de la Empresa ===

@usuarios_bp.route('/administracion/cuentas-bancarias', methods=['GET', 'POST'])
@require_permission('administracion')
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
                acc_id = insert_bank_account(account_data)
                log_security_event('BANK_ACCOUNT_CREATED', session.get('username'), f"Cuenta bancaria {acc_id} registrada")
                flash("Cuenta bancaria registrada exitosamente.", "success")
            except Exception as e:
                flash(f"Error al registrar la cuenta: Cuenta duplicada o datos inválidos.", "danger")
        return redirect(url_for('usuarios.cuentas_bancarias'))

    from repositories.finance_repo import get_bank_accounts_page
    accounts, pagination = get_bank_accounts_page(request.args.get('page'))
    return render_template('cuentas_bancarias.html', accounts=accounts, pagination=pagination)


@usuarios_bp.route('/administracion/cuentas-bancarias/<int:account_id>/editar', methods=['POST'])
@require_permission('administracion')
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
        log_security_event('BANK_ACCOUNT_UPDATED', session.get('username'), f"Cuenta bancaria {account_id} actualizada")
        flash("Cuenta bancaria actualizada correctamente.", "success")
    except Exception as e:
        flash(f"Error al actualizar la cuenta.", "danger")
    return redirect(url_for('usuarios.cuentas_bancarias'))


@usuarios_bp.route('/administracion/cuentas-bancarias/<int:account_id>/eliminar', methods=['POST'])
@require_permission('administracion')
def eliminar_cuenta_bancaria(account_id):
    """Eliminar una cuenta bancaria"""
    from db import delete_bank_account
    try:
        delete_bank_account(account_id)
        log_security_event('BANK_ACCOUNT_DELETED', session.get('username'), f"Cuenta bancaria {account_id} eliminada")
        flash("Cuenta bancaria eliminada correctamente.", "success")
    except Exception as e:
        flash("No se puede eliminar la cuenta porque tiene pagos asociados.", "danger")
    return redirect(url_for('usuarios.cuentas_bancarias'))
