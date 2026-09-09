import os
import json
from dotenv import load_dotenv
load_dotenv()  # Cargar variables del archivo .env local

from flask import Flask, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from db import init_db

# Inicializar Flask
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)

# Configuración
app.config['SECRET_KEY'] = 'tu-clave-secreta-aqui'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

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
    """Serve uploaded files"""
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

from flask import request, redirect, url_for, session

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
            from flask import jsonify
            return jsonify({"status": "error", "message": "Sesión expirada. Por favor vuelva a iniciar sesión."}), 401
        return redirect(url_for('auth.login'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=True)
