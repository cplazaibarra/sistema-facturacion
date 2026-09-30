import json
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from db import get_connection
from security import verify_and_upgrade_password, log_security_event

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.id, u.username, u.password, u.full_name, r.name as role_name, r.permissions as role_permissions
                    FROM users u
                    JOIN roles r ON u.role_id = r.id
                    WHERE u.username = %s AND u.is_active = TRUE
                    """,
                    (username,)
                )
                user = cur.fetchone()

        is_authenticated = False
        if user:
            stored_pw = user.get('password')
            user_id = user['id']
            is_valid, upgraded = verify_and_upgrade_password(stored_pw, password, user_id)
            if is_valid:
                is_authenticated = True
                if upgraded:
                    log_security_event('PASSWORD_MIGRATED', username, f"Usuario ID {user_id} migrado a hash")

        if is_authenticated and user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['user_name'] = user['full_name']
            session['role_name'] = user['role_name']
            
            # Parsear permisos de rol y guardar en sesión
            perms = user.get('role_permissions')
            if isinstance(perms, str):
                try:
                    perms = json.loads(perms)
                except Exception:
                    perms = {}
            elif not isinstance(perms, dict):
                perms = {}
            session['permissions'] = perms

            parts = [p for p in (user['full_name'] or '').strip().split() if p]
            if len(parts) >= 2:
                session['user_initials'] = (parts[0][0] + parts[1][0]).upper()
            elif len(parts) == 1:
                session['user_initials'] = parts[0][:2].upper()
            else:
                session['user_initials'] = user['username'][:2].upper()

            log_security_event('LOGIN_SUCCESS', username, f"Rol: {user['role_name']}")
            flash(f'¡Bienvenido {user["full_name"]}!', 'success')
            if user['role_name'] == 'Operario de Bodega' or perms.get('operario_bodega'):
                return redirect(url_for('operario.home'))
            if perms.get('dashboard') or user['role_name'].lower() in ('administrativo', 'administrador', 'admin'):
                return redirect(url_for('dashboard.dashboard'))
            if perms.get('ventas'):
                return redirect(url_for('ventas.ventas'))
            if perms.get('inventario'):
                return redirect(url_for('inventario.inventario'))
            if perms.get('productos'):
                return redirect(url_for('inventario.productos'))
            if perms.get('reportes'):
                return redirect(url_for('reportes.reportes_cuentas_por_cobrar'))
            if perms.get('usuarios'):
                return redirect(url_for('usuarios.usuarios'))
            return render_template('403.html', permission='un módulo autorizado'), 403
        else:
            log_security_event('LOGIN_FAILED', username, "Credenciales inválidas o usuario inactivo", level='warning')
            flash('Usuario o contraseña incorrectos.', 'danger')

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    username = session.get('username')
    log_security_event('LOGOUT', username, "Cierre de sesión")
    session.clear()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('auth.login'))
