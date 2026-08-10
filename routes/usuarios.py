from flask import Blueprint, render_template, request, redirect, url_for
from datetime import datetime
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
    delete_user
)

usuarios_bp = Blueprint('usuarios', __name__)

@usuarios_bp.route('/administracion')
def administracion():
    """Módulo de Administración"""
    modules = get_page_data("admin_modules")
    settings = get_page_data("admin_settings")
    return render_template('administracion.html', modules=modules, settings=settings)

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
    return redirect(url_for('usuarios.usuarios'))

@usuarios_bp.route('/roles', methods=['GET', 'POST'])
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

        return redirect(url_for('usuarios.roles'))

    all_roles = list_roles()
    return render_template('roles.html', roles=all_roles)

@usuarios_bp.route('/roles/<int:role_id>/editar', methods=['GET', 'POST'])
def editar_rol(role_id):
    """Editar rol"""
    if request.method == 'POST':
        role = {
            "name": request.form.get('name', '').strip(),
            "description": request.form.get('description', '').strip(),
            "permissions": request.form.get('permissions', '{}'),
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
