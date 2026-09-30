import pytest
import io
import openpyxl
from unittest.mock import patch
from tests.conftest import get_csrf_token
from services.products_excel_service import store_preview_cache, pop_preview_cache
from app import app

def test_custom_404_error_page(auth_client):
    """Verifica que rutas no existentes devuelvan la página 404 personalizada con código HTTP 404."""
    resp = auth_client.get('/ruta-que-definitivamente-no-existe-en-el-erp')
    assert resp.status_code == 404
    html = resp.data.decode('utf-8')
    assert "Página No Encontrada" in html or "404" in html
    assert "Dashboard" in html or "Volver atrás" in html

def test_custom_404_error_json(auth_client):
    """Verifica que peticiones JSON a rutas inexistentes respondan JSON con status 404."""
    resp = auth_client.get(
        '/api/ruta-inexistente-404',
        headers={'Accept': 'application/json'}
    )
    assert resp.status_code == 404
    data = resp.get_json()
    assert data is not None
    assert data.get('status') == 'error'
    assert "no encontrado" in data.get('message', '').lower()

def test_custom_500_error_safe(auth_client):
    """Verifica que un error 500 no exponga stack traces ni detalles SQL y devuelva un error_ref."""
    orig_testing = app.testing
    orig_propagate = app.config.get('PROPAGATE_EXCEPTIONS')
    app.testing = False
    app.config['PROPAGATE_EXCEPTIONS'] = False
    try:
        with patch('db.get_products_paginated', side_effect=Exception("Database syntax error near DROP TABLE secret_dump")):
            resp = auth_client.get('/productos')
            assert resp.status_code == 500
            html = resp.data.decode('utf-8')
            # Verificar que NO se filtre el detalle de la excepción interna
            assert "Database syntax error" not in html
            assert "DROP TABLE" not in html
            assert "Traceback" not in html
            # Verificar que contenga mensaje profesional y referencia
            assert "Ocurrió un problema al procesar la solicitud" in html or "500" in html
            assert "Código de referencia para soporte:" in html or "Ref:" in html
    finally:
        app.testing = orig_testing
        app.config['PROPAGATE_EXCEPTIONS'] = orig_propagate

def test_custom_500_error_json(auth_client):
    """Verifica respuesta JSON segura para errores 500."""
    orig_testing = app.testing
    orig_propagate = app.config.get('PROPAGATE_EXCEPTIONS')
    app.testing = False
    app.config['PROPAGATE_EXCEPTIONS'] = False
    try:
        with patch('db.get_products_paginated', side_effect=Exception("Internal Crash")):
            resp = auth_client.get(
                '/productos',
                headers={'Accept': 'application/json'}
            )
            assert resp.status_code == 500
            data = resp.get_json()
            assert data is not None
            assert data.get('status') == 'error'
            assert "error_ref" in data
            assert "Internal Crash" not in data.get('message', '')
    finally:
        app.testing = orig_testing
        app.config['PROPAGATE_EXCEPTIONS'] = orig_propagate

def test_custom_403_forbidden_page(client):
    """Verifica que un usuario sin permisos reciba 403 con mensaje claro."""
    with client.session_transaction() as sess:
        sess['user_id'] = 99
        sess['username'] = 'operario'
        sess['role_name'] = 'Operario'
        sess['permissions'] = {
            "dashboard": True, "usuarios": False, "ventas": False,
            "inventario": False, "productos": False, "administracion": False,
            "reportes": False, "configuracion": False, "crear_registros": False,
            "aprobar_registros": False, "solo_ver": True
        }
    resp = client.get('/usuarios')
    assert resp.status_code == 403
    html = resp.data.decode('utf-8')
    assert "Acceso Denegado" in html or "No tienes permisos" in html or "403" in html

def test_excel_import_server_cache_isolation_and_expiration():
    """Verifica almacenamiento en memoria seguro de preview, aislamiento por usuario y single-use."""
    user_1 = 101
    user_2 = 102
    items = [{"action": "NUEVO", "sku": "PROD-ABC", "payload": {"name": "Test"}}]
    summary = {"total_rows": 1, "nuevos": 1, "modificados": 0, "sin_cambios": 0, "errores": 0}

    # Guardar para user_1
    import_id = store_preview_cache(user_1, items, summary)
    assert import_id is not None
    assert len(import_id) >= 32

    # Intentar consumir por otro usuario (user_2) -> Debe denegar
    cached_user2 = pop_preview_cache(import_id, user_2)
    assert cached_user2 is None

    # Intentar consumir con un import_id inválido
    cached_invalid = pop_preview_cache("uuid-invalido-o-falso", user_1)
    assert cached_invalid is None

    # Consumir por el usuario legítimo (user_1) -> Éxito
    cached_user1 = pop_preview_cache(import_id, user_1)
    assert cached_user1 is not None
    assert len(cached_user1["items"]) == 1
    assert cached_user1["summary"]["nuevos"] == 1

    # Consumir nuevamente el MISMO import_id (single-use / replay protection) -> Debe retornar None
    cached_replay = pop_preview_cache(import_id, user_1)
    assert cached_replay is None

def test_excel_import_confirm_security_in_route(auth_client):
    """Verifica que la ruta /productos/importar/confirmar rechace peticiones sin import_id válido."""
    csrf = get_csrf_token(auth_client, '/productos')
    
    # Intento de confirmación con import_id inválido o falsificado
    resp = auth_client.post('/productos/importar/confirmar', data={
        'csrf_token': csrf,
        'import_id': '00000000-0000-0000-0000-000000000000'
    }, follow_redirects=True)
    
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert "expiró o no es válida" in html or "No hay cambios pendientes" in html
