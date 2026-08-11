from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from db import get_connection

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
                    SELECT u.id, u.username, u.full_name, r.name as role_name
                    FROM users u
                    JOIN roles r ON u.role_id = r.id
                    WHERE u.username = %s AND u.password = %s AND u.is_active = TRUE
                    """,
                    (username, password)
                )
                user = cur.fetchone()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role_name'] = user['role_name']
            flash(f'¡Bienvenido {user["full_name"]}!', 'success')
            return redirect(url_for('dashboard.dashboard'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('auth.login'))
