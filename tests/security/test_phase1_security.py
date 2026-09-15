import os
import io
import re
import pytest
from werkzeug.security import check_password_hash, generate_password_hash
from security import (
    validate_secret_key,
    is_hashed_password,
    verify_and_upgrade_password,
    allowed_file,
    safe_save_upload,
    ALLOWED_UPLOAD_EXTENSIONS,
    INSECURE_DEFAULT_SECRET
)
from db import get_connection, insert_user, delete_user
from tests.conftest import get_csrf_token


# ============================================================================
# 1. Configuración & SECRET_KEY Tests
# ============================================================================

def test_secret_key_required():
    """Valida que no se permita iniciar la aplicación sin SECRET_KEY."""
    with pytest.raises(ValueError, match="SECRET_KEY no está configurada"):
        validate_secret_key(None)
    with pytest.raises(ValueError, match="SECRET_KEY no está configurada"):
        validate_secret_key("")


def test_insecure_default_secret_rejected():
    """Valida que la clave insegura por defecto sea explícitamente rechazada."""
    with pytest.raises(ValueError, match="SECRET_KEY insegura detectada"):
        validate_secret_key(INSECURE_DEFAULT_SECRET)
    with pytest.raises(ValueError, match="demasiado corta"):
        validate_secret_key("clave_corta_123")


def test_secret_key_loaded_from_environment(client):
    """Valida que la clave configurada en la app provenga de entorno y sea segura."""
    from app import app
    sec_key = app.config.get('SECRET_KEY')
    assert sec_key is not None
    assert sec_key != INSECURE_DEFAULT_SECRET
    assert len(sec_key) >= 24


# ============================================================================
# 2. Password Hashing & Migración On-Login Tests
# ============================================================================

def test_legacy_password_login(client):
    """Prueba que un usuario con clave legacy texto plano puede iniciar sesión."""
    test_username = "test_legacy_user_1"
    raw_pass = "mypassword_legacy_123"

    # Insertar directamente en la BD con texto plano simulando usuario legacy
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE username = %s", (test_username,))
            cur.execute(
                """
                INSERT INTO users (username, email, password, full_name, role_id, is_active, created_at)
                VALUES (%s, %s, %s, %s, 1, TRUE, '2026-09-01T00:00:00')
                RETURNING id
                """,
                (test_username, "legacy1@test.com", raw_pass, "Legacy User 1")
            )
            uid = cur.fetchone()["id"]
        conn.commit()

    try:
        token = get_csrf_token(client)
        resp = client.post('/login', data={'username': test_username, 'password': raw_pass, 'csrf_token': token})
        assert resp.status_code == 302
        assert '/dashboard' in resp.headers.get('Location', '')
    finally:
        delete_user(uid)


def test_legacy_password_upgraded_after_login(client):
    """Prueba que la contraseña legacy en texto plano es migrada inmediatamente a hash al loguearse."""
    test_username = "test_legacy_user_upg"
    raw_pass = "migrateme_now_987"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE username = %s", (test_username,))
            cur.execute(
                """
                INSERT INTO users (username, email, password, full_name, role_id, is_active, created_at)
                VALUES (%s, %s, %s, %s, 1, TRUE, '2026-09-01T00:00:00')
                RETURNING id
                """,
                (test_username, "legacy_upg@test.com", raw_pass, "Legacy User Upg")
            )
            uid = cur.fetchone()["id"]
        conn.commit()

    try:
        # Verificar que inicialmente está en texto plano
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT password FROM users WHERE id = %s", (uid,))
                initial_pw = cur.fetchone()["password"]
        assert initial_pw == raw_pass

        # Iniciar sesión
        token = get_csrf_token(client)
        resp = client.post('/login', data={'username': test_username, 'password': raw_pass, 'csrf_token': token})
        assert resp.status_code == 302

        # Verificar que en la base de datos ya fue migrado a hash
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT password FROM users WHERE id = %s", (uid,))
                updated_pw = cur.fetchone()["password"]

        assert updated_pw != raw_pass
        assert is_hashed_password(updated_pw)
        assert check_password_hash(updated_pw, raw_pass)
    finally:
        delete_user(uid)


def test_hashed_password_login(client):
    """Prueba que un usuario con hash puede loguearse normalmente."""
    test_username = "test_hashed_user"
    raw_pass = "hashed_pass_456"
    pw_hash = generate_password_hash(raw_pass)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE username = %s", (test_username,))
            cur.execute(
                """
                INSERT INTO users (username, email, password, full_name, role_id, is_active, created_at)
                VALUES (%s, %s, %s, %s, 1, TRUE, '2026-09-01T00:00:00')
                RETURNING id
                """,
                (test_username, "hashed@test.com", pw_hash, "Hashed User")
            )
            uid = cur.fetchone()["id"]
        conn.commit()

    try:
        token = get_csrf_token(client)
        resp = client.post('/login', data={'username': test_username, 'password': raw_pass, 'csrf_token': token})
        assert resp.status_code == 302
        assert '/dashboard' in resp.headers.get('Location', '')
    finally:
        delete_user(uid)


def test_wrong_password_does_not_upgrade(client):
    """Prueba que un intento con contraseña errónea no actualiza ni altera el registro en la BD."""
    test_username = "test_wrong_pwd_user"
    raw_pass = "original_pwd_789"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE username = %s", (test_username,))
            cur.execute(
                """
                INSERT INTO users (username, email, password, full_name, role_id, is_active, created_at)
                VALUES (%s, %s, %s, %s, 1, TRUE, '2026-09-01T00:00:00')
                RETURNING id
                """,
                (test_username, "wrong@test.com", raw_pass, "Wrong Test User")
            )
            uid = cur.fetchone()["id"]
        conn.commit()

    try:
        token = get_csrf_token(client)
        resp = client.post('/login', data={'username': test_username, 'password': 'incorrect_password', 'csrf_token': token})
        assert resp.status_code == 200

        # Verificar que el password en la BD sigue intacto y no fue modificado
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT password FROM users WHERE id = %s", (uid,))
                current_pw = cur.fetchone()["password"]
        assert current_pw == raw_pass
    finally:
        delete_user(uid)


def test_password_not_stored_plaintext_for_new_user():
    """Prueba que insert_user nunca almacene contraseñas en texto plano."""
    user_data = {
        "username": "new_created_user_sec",
        "email": "secuser@test.com",
        "full_name": "Security Test User",
        "role_id": 1,
        "password": "plaintext_raw_password_999",
        "is_active": True,
        "created_at": "2026-09-14T00:00:00"
    }

    uid = insert_user(user_data)
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT password FROM users WHERE id = %s", (uid,))
                stored_pw = cur.fetchone()["password"]

        assert stored_pw != user_data["password"]
        assert is_hashed_password(stored_pw)
        assert check_password_hash(stored_pw, user_data["password"])
    finally:
        delete_user(uid)


# ============================================================================
# 3. Control de Acceso RBAC Tests
# ============================================================================

def test_unauthorized_user_cannot_access_admin_routes(client):
    """Un usuario con rol sin permisos administrativos ni de usuarios debe recibir 403 en /usuarios."""
    with client.session_transaction() as sess:
        sess['user_id'] = 9999
        sess['username'] = 'vendedor_test'
        sess['full_name'] = 'Vendedor Test'
        sess['user_name'] = 'Vendedor Test'
        sess['role_name'] = 'Área Ventas'
        sess['permissions'] = {
            "dashboard": False,
            "usuarios": False,
            "ventas": True,
            "inventario": False,
            "productos": True,
            "administracion": False,
            "reportes": False,
            "configuracion": False,
            "crear_registros": True,
            "aprobar_registros": False,
            "solo_ver": False
        }

    resp = client.get('/usuarios')
    assert resp.status_code == 403


def test_authorized_user_can_access_allowed_routes(client):
    """Un usuario con rol Área Ventas puede acceder a /ventas (200), pero no a /administracion (403)."""
    with client.session_transaction() as sess:
        sess['user_id'] = 9998
        sess['username'] = 'vendedor_test_2'
        sess['full_name'] = 'Vendedor Test 2'
        sess['user_name'] = 'Vendedor Test 2'
        sess['role_name'] = 'Área Ventas'
        sess['permissions'] = {
            "dashboard": False,
            "usuarios": False,
            "ventas": True,
            "inventario": False,
            "productos": True,
            "administracion": False,
            "reportes": False,
            "configuracion": False,
            "crear_registros": True,
            "aprobar_registros": False,
            "solo_ver": False
        }

    # Acceso a ruta permitida
    resp_ok = client.get('/ventas')
    assert resp_ok.status_code == 200

    # Acceso a ruta no permitida
    resp_denied = client.get('/administracion')
    assert resp_denied.status_code == 403


# ============================================================================
# 4. Protección CSRF Tests
# ============================================================================

def test_post_without_csrf_is_rejected(client):
    """Petición POST sin token CSRF debe ser rechazada con código HTTP 400."""
    resp = client.post('/login', data={'username': 'admin', 'password': 'admin123'})
    assert resp.status_code == 400


def test_post_with_valid_csrf_is_accepted(client):
    """Petición POST con token CSRF válido debe ser procesada (no rechazada con 400)."""
    token = get_csrf_token(client)
    assert token is not None
    resp = client.post('/login', data={'username': 'admin', 'password': 'admin123', 'csrf_token': token})
    # Debe procesarse y redirigir a dashboard (302)
    assert resp.status_code == 302
    assert '/dashboard' in resp.headers.get('Location', '')


# ============================================================================
# 5. Seguridad en Uploads & Path Traversal Tests
# ============================================================================

def test_upload_invalid_extension_rejected():
    """Valida que extensiones no autorizadas (.php, .exe, .sh, .py, etc.) sean rechazadas."""
    assert allowed_file("malicious.php") is False
    assert allowed_file("shell.exe") is False
    assert allowed_file("script.sh") is False
    assert allowed_file("hack.py") is False
    assert allowed_file("archivo_sin_extension") is False
    assert allowed_file("") is False


def test_upload_path_traversal_prevented(tmp_path):
    """Valida que nombres de archivo con secuencias de path traversal sean bloqueados."""
    assert allowed_file("../../../etc/passwd") is False
    assert allowed_file("..\\windows\\system32\\cmd.exe") is False

    # Probar safe_save_upload con mock de file storage
    class MockFile:
        def __init__(self, filename, content=b"dummy"):
            self.filename = filename
            self.content = content
        def save(self, dest):
            with open(dest, "wb") as f:
                f.write(self.content)

    # Intento con extensión no permitida
    with pytest.raises(ValueError, match="Tipo de archivo no permitido"):
        safe_save_upload(MockFile("exploit.php"), str(tmp_path), "exploit.php")


def test_upload_valid_file_accepted(tmp_path):
    """Valida que extensiones permitidas (png, jpg, jpeg, webp, pdf) sean aceptadas y guardadas."""
    valid_names = ["factura.pdf", "comprobante.png", "foto.jpg", "imagen.jpeg", "documento.webp"]
    for name in valid_names:
        assert allowed_file(name) is True

    class MockFile:
        def __init__(self, filename, content=b"safe-content"):
            self.filename = filename
            self.content = content
        def save(self, dest):
            with open(dest, "wb") as f:
                f.write(self.content)

    target_dir = str(tmp_path / "uploads_test")
    saved_path = safe_save_upload(MockFile("factura_001.pdf"), target_dir, "factura_001.pdf")
    assert os.path.isfile(saved_path)
    assert saved_path.endswith("factura_001.pdf")
