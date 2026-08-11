import os
import json
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
from routes.pagos import pagos_bp
from routes.usuarios import usuarios_bp
from routes.proveedores import proveedores_bp
from routes.reportes import reportes_bp
from routes.compras import compras_bp

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(inventario_bp)
app.register_blueprint(ventas_bp)
app.register_blueprint(pagos_bp)
app.register_blueprint(usuarios_bp)
app.register_blueprint(proveedores_bp)
app.register_blueprint(reportes_bp)
app.register_blueprint(compras_bp)

from flask import request, redirect, url_for, session

@app.before_request
def check_login():
    # Permitir la ruta de login y los archivos estáticos (CSS, JS, imágenes, etc.)
    if request.path.startswith('/static') or request.path.startswith('/uploads'):
        return
    if request.endpoint in ('auth.login', 'uploaded_file'):
        return
    # Si no hay usuario en sesión, redirigir a login
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
