import pytest
from core.test_database_guard import assert_current_test_database_authorized

# This runs before dotenv or application imports. A normal .env is never a
# permissible implicit target for pytest.
assert_current_test_database_authorized()

from dotenv import load_dotenv
load_dotenv()
from app import app
from db import get_connection

@pytest.fixture
def client():
    """Test client para Flask sin sesión autenticada."""
    with app.test_client() as client:
        yield client

import re

def get_csrf_token(client, path='/login'):
    """Extrae el token CSRF generado en el formulario o cabecera HTML."""
    resp = client.get(path)
    html = resp.data.decode('utf-8')
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if match:
        return match.group(1)
    match = re.search(r'name="csrf-token"\s+content="([^"]+)"', html)
    if match:
        return match.group(1)
    return None

@pytest.fixture
def auth_client():
    """Test client para Flask con sesión de usuario Administrador."""
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['full_name'] = 'Administrador'
            sess['user_name'] = 'Administrador'
            sess['role_name'] = 'Administrativo'
            sess['user_initials'] = 'AD'
            sess['permissions'] = {
                "dashboard": True, "usuarios": True, "ventas": True,
                "inventario": True, "productos": True, "administracion": True,
                "reportes": True, "configuracion": True, "crear_registros": True,
                "aprobar_registros": True, "solo_ver": False
            }
        yield client

@pytest.fixture
def db_conn():
    """Conexión a la base de datos PostgreSQL en modo lectura/rollback para tests."""
    conn = get_connection()
    yield conn
    conn.rollback()
    conn.close()
