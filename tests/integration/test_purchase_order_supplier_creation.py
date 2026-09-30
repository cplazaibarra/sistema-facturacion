import pytest
import json
from datetime import datetime
from app import app
from core.database import get_connection
from core.utils import validate_chilean_rut, calculate_chilean_dv
from tests.conftest import get_csrf_token
from db import (
    get_supplier_by_rut,
    get_supplier,
    insert_supplier,
    create_purchase_order,
    get_purchase_order
)

@pytest.fixture
def auth_client_no_csrf():
    """Client autenticado con CSRF deshabilitado para pruebas directas de API."""
    old_csrf = app.config.get('WTF_CSRF_ENABLED', True)
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    try:
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 1
                sess['username'] = 'admin'
                sess['role_name'] = 'Administrativo'
                sess['full_name'] = 'Administrador'
                sess['permissions'] = {
                    'dashboard': True,
                    'ventas': True,
                    'inventario': True,
                    'productos': True,
                    'reportes': True,
                    'compras': True,
                    'produccion': True,
                    'trazabilidad': True,
                    'administracion': True,
                }
            yield client
    finally:
        app.config['WTF_CSRF_ENABLED'] = old_csrf

def test_chilean_rut_validation_utility():
    """Valida la función core validate_chilean_rut y calculate_chilean_dv con diversos casos."""
    valid_cases = [
        "11.111.111-1",
        "11111111-1",
        "111111111",
        "76.123.456-0",
        "761234560",
        "76123456-0",
        "18.456.789-K",
        "18456789-k",
        "18456789K"
    ]
    for r in valid_cases:
        is_val, formatted, err = validate_chilean_rut(r)
        assert is_val is True, f"Fallo validación de RUT válido: {r} (error: {err})"
        assert '-' in formatted
        assert '.' in formatted

    invalid_cases = [
        "",
        "abc",
        "123",
        "11.111.111-9",
        "76.123.456-5",
        "1234567890123-4"
    ]
    for r in invalid_cases:
        is_val, _, err = validate_chilean_rut(r)
        assert is_val is False, f"Se esperaba inválido para: {r}"
        assert err != ""

def test_api_create_supplier_success_and_contact(auth_client_no_csrf):
    """Crea un proveedor completo vía /api/proveedores/crear y verifica contacto."""
    ts = int(datetime.now().timestamp() * 1000)
    body_rut = f"76{ts % 1000000:06d}"
    dv = calculate_chilean_dv(body_rut)
    valid_rut = f"{body_rut}-{dv}"

    payload = {
        "name": f"Distribuidora Los Andes {ts}",
        "razon_social": f"Distribuidora Los Andes SpA {ts}",
        "rut": valid_rut,
        "giro": "Venta al por mayor de insumos industriales",
        "direccion": "Av. Las Industrias 456",
        "comuna": "Pudahuel",
        "ciudad": "Santiago",
        "contacto": "Juan Pérez",
        "phone": "+56 9 8765 4321",
        "email": f"contacto{ts}@losandes.cl",
        "default_payment_terms": "NET_60",
        "website": "https://www.losandes.cl",
        "description": "Proveedor preferente de materias primas"
    }

    res = auth_client_no_csrf.post('/api/proveedores/crear', data=json.dumps(payload), content_type='application/json')
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert "supplier" in data
    supplier = data["supplier"]
    assert supplier["id"] > 0
    assert supplier["name"] == payload["name"]
    assert supplier["default_payment_terms"] == "NET_60"

    supp_db = get_supplier(supplier["id"])
    assert supp_db is not None
    assert supp_db["rut"] == supplier["rut"]
    assert supp_db["giro"] == payload["giro"]
    assert supp_db["comuna"] == payload["comuna"]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM supplier_contacts WHERE supplier_id = %s", (supplier["id"],))
            contacts = cur.fetchall()
            assert len(contacts) >= 1
            assert contacts[0]["name"] == "Juan Pérez"
            assert contacts[0]["email"] == payload["email"]

def test_api_create_supplier_invalid_rut_returns_400(auth_client_no_csrf):
    """Verifica que un RUT inválido retorne 400 y mensaje de error específico."""
    payload = {
        "name": "Proveedor Invalido",
        "rut": "11.111.111-9",
        "default_payment_terms": "CASH"
    }
    res = auth_client_no_csrf.post('/api/proveedores/crear', data=json.dumps(payload), content_type='application/json')
    assert res.status_code == 400
    data = res.get_json()
    assert data["status"] == "error"
    assert data["field"] == "rut"
    assert "dígito verificador no coincide" in data["message"]

def test_api_create_supplier_invalid_email_returns_400(auth_client_no_csrf):
    """Verifica que un email inválido retorne 400."""
    ts = int(datetime.now().timestamp() * 1000)
    body_rut = f"77{ts % 1000000:06d}"
    dv = calculate_chilean_dv(body_rut)
    payload = {
        "name": "Proveedor Test",
        "rut": f"{body_rut}-{dv}",
        "email": "correo_sin_arroba.cl"
    }
    res = auth_client_no_csrf.post('/api/proveedores/crear', data=json.dumps(payload), content_type='application/json')
    assert res.status_code == 400
    data = res.get_json()
    assert data["status"] == "error"
    assert data["field"] == "email"

def test_api_create_supplier_duplicate_rut_returns_409(auth_client_no_csrf):
    """Verifica que si ya existe un proveedor con ese RUT, retorne 409 y los datos del existente."""
    ts = int(datetime.now().timestamp() * 1000)
    body_rut = f"78{ts % 1000000:06d}"
    dv = calculate_chilean_dv(body_rut)
    valid_rut = f"{body_rut}-{dv}"

    payload1 = {
        "name": f"Proveedor Original {ts}",
        "rut": valid_rut,
        "default_payment_terms": "NET_30"
    }
    res1 = auth_client_no_csrf.post('/api/proveedores/crear', data=json.dumps(payload1), content_type='application/json')
    assert res1.status_code == 200
    s1_id = res1.get_json()["supplier"]["id"]

    payload2 = {
        "name": f"Proveedor Duplicado {ts}",
        "rut": valid_rut.replace(".", "").replace("-", ""),
        "default_payment_terms": "NET_60"
    }
    res2 = auth_client_no_csrf.post('/api/proveedores/crear', data=json.dumps(payload2), content_type='application/json')
    assert res2.status_code == 409
    data2 = res2.get_json()
    assert data2["status"] == "duplicate"
    assert data2["supplier"]["id"] == s1_id
    assert data2["supplier"]["name"] == payload1["name"]
    assert "Ya existe un proveedor registrado con este RUT" in data2["message"]

def test_api_create_supplier_csrf_protection_enabled(auth_client):
    """Verifica que con CSRF activado, la petición con token en header sea exitosa."""
    token = get_csrf_token(auth_client, '/compras/oc/nueva')
    assert token is not None

    ts = int(datetime.now().timestamp() * 1000)
    body_rut = f"80{ts % 1000000:06d}"
    dv = calculate_chilean_dv(body_rut)
    valid_rut = f"{body_rut}-{dv}"

    payload = {
        "name": f"Proveedor CSRF OK {ts}",
        "rut": valid_rut,
        "default_payment_terms": "NET_30"
    }

    res = auth_client.post(
        '/api/proveedores/crear',
        data=json.dumps(payload),
        content_type='application/json',
        headers={'X-CSRFToken': token}
    )
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"

def test_get_supplier_by_rut_normalization():
    """Verifica que get_supplier_by_rut encuentre proveedores sin importar puntuación."""
    ts = int(datetime.now().timestamp() * 1000)
    body = f"79{ts % 1000000:06d}"
    dv = calculate_chilean_dv(body)
    raw_rut = f"{body}-{dv}"

    supp_id = insert_supplier({
        "name": f"Proveedor Normalizacion {ts}",
        "rut": raw_rut,
        "default_payment_terms": "CASH"
    })
    
    found1 = get_supplier_by_rut(raw_rut)
    assert found1 is not None
    assert found1["id"] == supp_id

    found2 = get_supplier_by_rut(f"{body}{dv}")
    assert found2 is not None
    assert found2["id"] == supp_id

    found3 = get_supplier_by_rut(body, dv)
    assert found3 is not None
    assert found3["id"] == supp_id

def test_nueva_oc_view_renders_modal(auth_client):
    """Verifica que la página /compras/oc/nueva cargue el modal compacto de proveedor."""
    res = auth_client.get('/compras/oc/nueva')
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    assert 'id="modal-quick-supplier"' in html
    assert 'id="quick-supplier-rut"' in html
    assert 'id="quick-supplier-name"' in html
    assert 'id="quick-supplier-giro"' in html
    assert 'id="quick-supplier-dir"' in html
    assert 'id="quick-supplier-comuna"' in html
    assert 'id="quick-supplier-ciudad"' in html
    assert 'id="quick-supplier-contact"' in html
    assert 'id="quick-supplier-terms"' in html
    assert 'btn-select-existing-supplier' in html
    assert 'Agregar Proveedor' in html
