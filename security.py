"""
Módulo Central de Seguridad - Sistema de Facturación / ERP Bodega Miel
Fase 1: Control de Acceso, Criptografía, Uploads Seguros y Auditoría
"""

import os
import re
import logging
from functools import wraps
from flask import request, redirect, url_for, session, flash, jsonify, render_template, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# --- Logging de Seguridad ---
security_logger = logging.getLogger("erp.security")
if not security_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [SECURITY] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    security_logger.addHandler(handler)
    security_logger.setLevel(logging.INFO)

# --- Constantes de Seguridad ---
INSECURE_DEFAULT_SECRET = 'tu-clave-secreta-aqui'
MIN_SECRET_KEY_LENGTH = 24
ALLOWED_UPLOAD_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'pdf'}
HASH_PREFIXES = ('scrypt:', 'pbkdf2:', 'argon2:')


def validate_secret_key(secret_key: str | None, app_env: str = 'development') -> str:
    """
    Valida que la SECRET_KEY cumpla los requisitos de robustez y rechaza claves por defecto.
    """
    if not secret_key:
        raise ValueError(
            "SECRET_KEY no está configurada en las variables de entorno. "
            "Por favor configure SECRET_KEY en el archivo .env (mínimo 24 caracteres)."
        )
    
    clean_key = secret_key.strip()
    if clean_key == INSECURE_DEFAULT_SECRET:
        raise ValueError(
            "SECRET_KEY insegura detectada: no se permite utilizar la clave por defecto "
            f"'{INSECURE_DEFAULT_SECRET}'. Genere una clave criptográficamente segura."
        )

    if len(clean_key) < MIN_SECRET_KEY_LENGTH:
        raise ValueError(
            f"SECRET_KEY demasiado corta ({len(clean_key)} caracteres). "
            f"Debe tener al menos {MIN_SECRET_KEY_LENGTH} caracteres."
        )

    return clean_key


def is_hashed_password(password_str: str | None) -> bool:
    """Verifica si una cadena corresponde a un hash de contraseña reconocido por Werkzeug."""
    if not password_str:
        return False
    return password_str.startswith(HASH_PREFIXES)


def verify_and_upgrade_password(stored_password: str | None, provided_password: str, user_id: int) -> tuple[bool, bool]:
    """
    Verifica credenciales y realiza migración transparente on-login si la contraseña
    almacenada está en texto plano.
    
    Retorna:
        (is_valid, was_upgraded)
    """
    from db import get_connection
    
    if not stored_password or not provided_password:
        return False, False

    # Caso 1: Ya está hasheada
    if is_hashed_password(stored_password):
        is_valid = check_password_hash(stored_password, provided_password)
        return is_valid, False

    # Caso 2: Contraseña legacy en texto plano
    if stored_password == provided_password:
        # Migración transparente inmediata a hash seguro
        new_hash = generate_password_hash(provided_password)
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE users SET password = %s WHERE id = %s", (new_hash, user_id))
                conn.commit()
            security_logger.info(
                "Contraseña legacy migrada exitosamente a hash para usuario ID %s", user_id
            )
            return True, True
        except Exception as e:
            security_logger.error(
                "Error actualizando hash de contraseña para usuario ID %s: %s", user_id, e
            )
            return True, False

    # Contraseña incorrecta -> no se migra
    return False, False


def require_permission(permission_name: str):
    """
    Decorador para proteger rutas según el sistema RBAC del ERP.
    Verifica que el usuario autenticado tenga el permiso requerido en roles.permissions.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Verificar autenticación
            if 'user_id' not in session:
                if request.path.startswith('/api/') or request.is_json:
                    return jsonify({"status": "error", "message": "Autenticación requerida"}), 401
                return redirect(url_for('auth.login'))

            # 2. Obtener permisos de la sesión
            role_name = session.get('role_name', '')
            perms = session.get('permissions')

            # Si permisos no están en sesión o es Administrador
            if role_name.lower() in ('administrativo', 'administrador', 'admin'):
                # Superusuario administrativo tiene acceso total
                return f(*args, **kwargs)

            if perms is None:
                # Cargar permisos desde la BD si no están en sesión
                from db import get_connection
                import json
                try:
                    with get_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                SELECT r.permissions 
                                FROM users u 
                                JOIN roles r ON u.role_id = r.id 
                                WHERE u.id = %s
                                """,
                                (session['user_id'],)
                            )
                            row = cur.fetchone()
                            if row and row.get('permissions'):
                                p_data = row['permissions']
                                perms = json.loads(p_data) if isinstance(p_data, str) else p_data
                            else:
                                perms = {}
                    session['permissions'] = perms
                except Exception as e:
                    security_logger.error("Error cargando permisos para usuario %s: %s", session.get('user_id'), e)
                    perms = {}

            # 3. Verificar si el permiso específico está otorgado
            has_perm = bool(perms.get(permission_name, False))
            if not has_perm:
                client_ip = request.remote_addr or 'unknown'
                security_logger.warning(
                    "ACCESO DENEGADO 403: Usuario '%s' (rol: '%s', IP: %s) intentó acceder a '%s' requiriendo permiso '%s'",
                    session.get('username'), role_name, client_ip, request.path, permission_name
                )
                if request.path.startswith('/api/') or request.is_json:
                    return jsonify({
                        "status": "error",
                        "message": f"Acceso denegado: permiso '{permission_name}' requerido."
                    }), 403
                
                flash("Acceso denegado: no dispone de permisos suficientes para realizar esta acción.", "danger")
                try:
                    return render_template('403.html', permission=permission_name), 403
                except Exception:
                    return ("<h1>403 Prohibido</h1><p>No tiene permisos suficientes para acceder a este recurso.</p>", 403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator


# --- Validaciones de Uploads ---

def allowed_file(filename: str) -> bool:
    """Verifica si la extensión del archivo está permitida."""
    if not filename or '.' not in filename:
        return False
    # Validar caracteres nulos o secuencias sospechosas
    if '\x00' in filename or '/' in filename or '\\' in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_UPLOAD_EXTENSIONS


def validate_and_sanitize_filename(original_filename: str, prefix: str = 'file') -> str:
    """
    Sanitiza y genera un nombre seguro para el archivo subido, previniendo path traversal.
    """
    if not original_filename:
        raise ValueError("Nombre de archivo vacío.")
    
    clean_base = secure_filename(original_filename)
    if not clean_base or '.' not in clean_base:
        raise ValueError("Nombre de archivo inválido.")

    ext = clean_base.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValueError(f"Extensión .{ext} no permitida. Extensiones válidas: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}")

    return clean_base


def safe_save_upload(file_storage, target_directory: str, filename: str) -> str:
    """
    Guarda un archivo de forma segura comprobando path traversal mediante rutas canónicas.
    Retorna la ruta absoluta donde se guardó.
    """
    if not allowed_file(file_storage.filename):
        raise ValueError(f"Tipo de archivo no permitido. Solo se aceptan: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}")

    abs_target_dir = os.path.abspath(target_directory)
    os.makedirs(abs_target_dir, exist_ok=True)

    safe_name = secure_filename(filename)
    dest_path = os.path.abspath(os.path.join(abs_target_dir, safe_name))

    # Prevenir path traversal asegurando que dest_path esté dentro de abs_target_dir
    if not dest_path.startswith(abs_target_dir + os.sep) and dest_path != abs_target_dir:
        raise ValueError("Intento de path traversal detectado en el nombre de archivo.")

    file_storage.save(dest_path)
    return dest_path


# --- Registro de Auditoría de Seguridad ---

def log_security_event(event_type: str, username: str | None, details: str, level: str = 'info'):
    """Registra eventos de auditoría y seguridad estructurados."""
    ip = request.remote_addr if request else 'N/A'
    msg = f"EVENT={event_type} | USER={username or 'ANONYMOUS'} | IP={ip} | DETAILS={details}"
    if level == 'warning':
        security_logger.warning(msg)
    elif level == 'error':
        security_logger.error(msg)
    else:
        security_logger.info(msg)
