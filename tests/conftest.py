import pytest
from dotenv import load_dotenv
load_dotenv()
from app import app
from db import get_connection

@pytest.fixture
def client():
    """Test client para Flask sin sesión autenticada."""
    with app.test_client() as client:
        yield client

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
        yield client

@pytest.fixture
def db_conn():
    """Conexión a la base de datos PostgreSQL en modo lectura/rollback para tests."""
    conn = get_connection()
    yield conn
    conn.rollback()
    conn.close()
