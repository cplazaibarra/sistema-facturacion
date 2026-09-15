import os
import json
from dotenv import load_dotenv
load_dotenv()  # Cargar variables del archivo .env local

from flask import Flask, send_from_directory, request, redirect, url_for, session, jsonify, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_wtf.csrf import CSRFProtect, CSRFError

from db import init_db
from security import validate_secret_key, log_security_event

# Inicializar Flask
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)

# Configuración de Entorno y Clave Secreta
app_env = os.getenv('APP_ENV', 'development').lower()
raw_secret = os.getenv('SECRET_KEY')
if app_env == 'testing' and not raw_secret:
    raw_secret = 'test_secret_key_environment_variable_for_tests_only_secure_1234'

app.config['APP_ENV'] = app_env
app.config['SECRET_KEY'] = validate_secret_key(raw_secret, app_env=app_env)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Configuración de Seguridad en Cookies de Sesión
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
if app_env == 'production':
    app.config['SESSION_COOKIE_SECURE'] = True

# Protección CSRF Global
csrf = CSRFProtect(app)

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    user = session.get('username') if 'user_id' in session else 'ANONYMOUS'
    log_security_event('CSRF_ERROR', user, f"Ruta: {request.path} | Motivo: {e.description}", level='warning')
    if request.path.startswith('/api/') or request.is_json:
        return jsonify({"status": "error", "message": f"Error CSRF: {e.description}"}), 400
    return render_template('csrf_error.html', error_description=e.description), 400

# Crear carpeta de uploads si no existe
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Agregar filtro custom para convertir JSON
@app.template_filter('from_json')
def from_json_filter(value):
    if isinstance(value, str):
        return json.loads(value)
    return value

@app.template_filter('date_cl')
def date_cl_filter(value):
    """Formatea cualquier fecha o string ISO a formato chileno DD/MM/AAAA."""
    if not value:
        return ''
    val_str = str(value).strip()
    if not val_str:
        return ''
    # Si viene con hora '2026-09-09 14:30:00'
    date_part = val_str.split(' ')[0].split('T')[0]
    parts = date_part.split('-')
    if len(parts) == 3 and len(parts[0]) == 4:
        # yyyy-mm-dd -> dd/mm/yyyy
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return val_str

# Inicializar Base de Datos
init_db()

# Servir archivos estáticos subidos
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve uploaded files from both root uploads/ and static/uploads/"""
    root_uploads = os.path.join(os.path.dirname(__file__), 'uploads')
    if os.path.isfile(os.path.join(root_uploads, filename)):
        return send_from_directory(root_uploads, filename)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Registrar Blueprints
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.inventario import inventario_bp
from routes.ventas import ventas_bp
from routes.usuarios import usuarios_bp
from routes.proveedores import proveedores_bp
from routes.reportes import reportes_bp
from routes.compras import compras_bp
from routes.produccion import produccion_bp

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(inventario_bp)
app.register_blueprint(ventas_bp)
app.register_blueprint(usuarios_bp)
app.register_blueprint(proveedores_bp)
app.register_blueprint(reportes_bp)
app.register_blueprint(compras_bp)
app.register_blueprint(produccion_bp)

@app.before_request
def check_login():
    # Permitir la ruta de login y los archivos estáticos (CSS, JS, imágenes, etc.)
    if request.path.startswith('/static') or request.path.startswith('/uploads'):
        return
    if request.endpoint in ('auth.login', 'uploaded_file'):
        return
    # Si no hay usuario en sesión, redirigir a login o responder JSON si es API
    if 'user_id' not in session:
        if request.path.startswith('/api/'):
            return jsonify({"status": "error", "message": "Sesión expirada. Por favor vuelva a iniciar sesión."}), 401
        return redirect(url_for('auth.login'))

if __name__ == '__main__':
    is_debug = app.config.get('APP_ENV') != 'production' and os.getenv('FLASK_DEBUG', '0') == '1'
    app.run(debug=is_debug, host='0.0.0.0', port=5001, use_reloader=is_debug)
