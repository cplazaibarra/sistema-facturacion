from flask import Flask, render_template, jsonify, request, redirect, url_for
from datetime import datetime
import json
from db import (
    init_db,
    get_page_data,
    list_sales_entries,
    insert_sales_entry,
    list_products,
    insert_product,
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
)

app = Flask(__name__)

# Configuración
app.config['SECRET_KEY'] = 'tu-clave-secreta-aqui'

# Agregar filtro custom para convertir JSON
@app.template_filter('from_json')
def from_json_filter(value):
    if isinstance(value, str):
        return json.loads(value)
    return value

init_db()

@app.route('/')
@app.route('/dashboard')
def dashboard():
    """Página principal - Dashboard con gráficos y estadísticas"""
    recent_sales = get_page_data("dashboard_recent_sales")
    return render_template('dashboard.html', recent_sales=recent_sales)

@app.route('/administracion')
def administracion():
    """Módulo de Administración"""
    modules = get_page_data("admin_modules")
    settings = get_page_data("admin_settings")
    return render_template('administracion.html', modules=modules, settings=settings)

@app.route('/inventario')
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

@app.route('/ingreso-mercaderia')
def ingreso_mercaderia():
    """Módulo de Ingreso de Mercadería"""
    default_date = get_page_data("ingreso_default_date")
    suppliers = get_page_data("ingreso_suppliers")
    warehouses = get_page_data("ingreso_warehouses")
    products = get_page_data("ingreso_products")
    recent_ingresos = get_page_data("ingreso_recent")
    return render_template(
        'ingreso_mercaderia.html',
        default_date=default_date,
        suppliers=suppliers,
        warehouses=warehouses,
        products=products,
        recent_ingresos=recent_ingresos,
    )

@app.route('/proyeccion-ventas')
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

@app.route('/ventas')
def ventas():
    """Módulo de Ventas"""
    ventas_metrics = get_page_data("ventas_metrics")
    ventas_records = get_page_data("ventas_records")
    return render_template(
        'ventas.html',
        ventas_metrics=ventas_metrics,
        ventas_records=ventas_records,
    )


@app.route('/ingreso-ventas', methods=['GET', 'POST'])
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

        return redirect(url_for('ingreso_ventas'))

    entries = list_sales_entries()
    return render_template(
        'ingreso_ventas.html',
        payment_status_options=payment_status_options,
        payment_method_options=payment_method_options,
        delivery_status_options=delivery_status_options,
        entries=entries,
    )


@app.route('/productos', methods=['GET', 'POST'])
def productos():
    """Gestión de productos"""
    if request.method == 'POST':
        product = {
            "sku": request.form.get('sku', '').strip(),
            "name": request.form.get('name', '').strip(),
            "description": request.form.get('description', '').strip(),
            "photo_url": request.form.get('photo_url', '').strip(),
            "width_cm": request.form.get('width_cm') or None,
            "height_cm": request.form.get('height_cm') or None,
            "depth_cm": request.form.get('depth_cm') or None,
            "weight_kg": request.form.get('weight_kg') or None,
            "created_at": datetime.utcnow().isoformat(timespec='seconds'),
        }

        if product["sku"] and product["name"]:
            insert_product(product)

        return redirect(url_for('productos'))

    products = list_products()
    return render_template('productos.html', products=products)

# API endpoints para datos de gráficos
@app.route('/api/dashboard-data')
def dashboard_data():
    """Datos para el dashboard"""
    ventas_mensuales = get_page_data("dashboard_sales_chart")
    productos_top = get_page_data("dashboard_products_top")
    estadisticas = get_page_data("dashboard_stats")
    return jsonify(
        {
            "ventas_mensuales": ventas_mensuales,
            "productos_top": productos_top,
            "estadisticas": estadisticas,
        }
    )


@app.route('/usuarios', methods=['GET', 'POST'])
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

        return redirect(url_for('usuarios'))

    users = list_users()
    roles = list_roles()
    return render_template('usuarios.html', users=users, roles=roles)


@app.route('/usuarios/<int:user_id>/editar', methods=['GET', 'POST'])
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
        return redirect(url_for('usuarios'))

    user = get_user(user_id)
    roles = list_roles()
    return render_template('editar_usuario.html', user=user, roles=roles)


@app.route('/usuarios/<int:user_id>/eliminar', methods=['POST'])
def eliminar_usuario(user_id):
    """Eliminar usuario"""
    delete_user(user_id)
    return redirect(url_for('usuarios'))


@app.route('/roles', methods=['GET', 'POST'])
def roles():
    """Gestión de roles"""
    if request.method == 'POST':
        role = {
            "name": request.form.get('name', '').strip(),
            "description": request.form.get('description', '').strip(),
            "permissions": request.form.get('permissions', '{}'),
            "created_at": datetime.utcnow().isoformat(timespec='seconds'),
        }

        if role["name"]:
            insert_role(role)

        return redirect(url_for('roles'))

    all_roles = list_roles()
    return render_template('roles.html', roles=all_roles)


@app.route('/roles/<int:role_id>/editar', methods=['GET', 'POST'])
def editar_rol(role_id):
    """Editar rol"""
    if request.method == 'POST':
        role = {
            "name": request.form.get('name', '').strip(),
            "description": request.form.get('description', '').strip(),
            "permissions": request.form.get('permissions', '{}'),
        }
        update_role(role_id, role)
        return redirect(url_for('roles'))

    role = get_role(role_id)
    return render_template('editar_rol.html', role=role)


@app.route('/roles/<int:role_id>/eliminar', methods=['POST'])
def eliminar_rol(role_id):
    """Eliminar rol"""
    delete_role(role_id)
    return redirect(url_for('roles'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
