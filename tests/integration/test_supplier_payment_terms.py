import pytest
import json
from datetime import datetime
from app import app
from core.database import get_connection
from db import (
    insert_supplier,
    get_supplier,
    update_supplier,
    list_suppliers,
    create_purchase_order,
    get_purchase_order,
    update_purchase_order,
    format_payment_terms,
    PAYMENT_TERMS_LABELS,
    VALID_PAYMENT_TERMS,
    DEFAULT_PAYMENT_TERMS
)
from core.utils import calculate_chilean_dv


def _available_test_rut(prefix, timestamp_ms):
    """Return a valid test RUT not already present in the current test DB."""
    start = timestamp_ms % 10000
    for offset in range(10000):
        body = f"{prefix}{(start + offset) % 10000:04d}"
        rut = f"{body}-{calculate_chilean_dv(body)}"
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM suppliers WHERE rut = %s", (rut,))
                if cur.fetchone() is None:
                    return rut
    raise AssertionError("No unused test RUT available for supplier payment terms flow")

@pytest.fixture
def auth_client():
    """Client autenticado con CSRF deshabilitado para pruebas de proveedores y compras."""
    old_csrf = app.config.get('WTF_CSRF_ENABLED', True)
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    try:
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 1
                sess['username'] = 'admin'
                sess['role_name'] = 'Administrativo'
                sess['full_name'] = 'Administrador Sistema'
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


def test_supplier_default_payment_terms():
    """Valida creación de proveedores con cada forma de pago permitida."""
    ts = int(datetime.now().timestamp() * 1000)
    
    # 1. Al contado -> CASH
    s1_id = insert_supplier({
        "name": f"Prov Contado {ts}",
        "rut": f"70111{ts % 10000:04d}-1",
        "default_payment_terms": 'CASH'
    })
    s1 = get_supplier(s1_id)
    assert s1['default_payment_terms'] == 'CASH'
    
    # 2. A 30 días -> NET_30
    s2_id = insert_supplier({
        "name": f"Prov 30 Dias {ts}",
        "rut": f"70222{ts % 10000:04d}-2",
        "default_payment_terms": 'NET_30'
    })
    s2 = get_supplier(s2_id)
    assert s2['default_payment_terms'] == 'NET_30'
    
    # 3. A 60 días -> NET_60
    s3_id = insert_supplier({
        "name": f"Prov 60 Dias {ts}",
        "rut": f"70333{ts % 10000:04d}-3",
        "default_payment_terms": 'NET_60'
    })
    s3 = get_supplier(s3_id)
    assert s3['default_payment_terms'] == 'NET_60'


def test_supplier_default_payment_terms_default_net30():
    """Valida que si no se especifica default_payment_terms, asume NET_30 por defecto."""
    ts = int(datetime.now().timestamp() * 1000)
    s_id = insert_supplier({
        "name": f"Prov Default {ts}",
        "rut": f"70444{ts % 10000:04d}-4"
    })
    s = get_supplier(s_id)
    assert s['default_payment_terms'] == 'NET_30'


def test_supplier_payment_terms_can_be_updated():
    """Valida que la forma de pago predeterminada de un proveedor puede editarse."""
    ts = int(datetime.now().timestamp() * 1000)
    s_id = insert_supplier({
        "name": f"Prov Editable {ts}",
        "rut": f"70555{ts % 10000:04d}-5",
        "default_payment_terms": 'CASH'
    })
    s = get_supplier(s_id)
    assert s['default_payment_terms'] == 'CASH'
    
    # Actualizar a NET_60
    update_supplier(
        supplier_id=s_id,
        supplier={
            "name": s['name'],
            "rut": s['rut'],
            "default_payment_terms": 'NET_60'
        }
    )
    s_updated = get_supplier(s_id)
    assert s_updated['default_payment_terms'] == 'NET_60'


def test_new_po_inherits_supplier_payment_terms(auth_client):
    """Valida que al crear una nueva OC, hereda la forma de pago del proveedor si no se sobreescribe."""
    ts = int(datetime.now().timestamp() * 1000)
    s_id = insert_supplier({
        "name": f"Prov Heredable {ts}",
        "rut": f"70666{ts % 10000:04d}-6",
        "default_payment_terms": 'NET_60'
    })
    
    # Creación por repo
    po_num = create_purchase_order(
        supplier_id=s_id,
        order_date="2026-09-17",
        notes="OC Test Herencia",
        items=[{"product_id": 1, "quantity": 2, "unit_price": 1000.0}],
        payment_terms='NET_60'
    )
    assert po_num.startswith("OC-")
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, payment_terms FROM purchase_orders WHERE oc_number = %s", (po_num,))
            po = cur.fetchone()
            assert po['payment_terms'] == 'NET_60'
    
    # Creación vía endpoint web /compras/oc/nueva
    res = auth_client.post('/compras/oc/nueva', data={
        'supplier_id': str(s_id),
        'order_date': '2026-09-17',
        'notes': 'OC via Web Herencia',
        'product_id[]': ['1'],
        'quantity[]': ['1'],
        'unit_price[]': ['500'],
        'payment_terms': 'NET_60'
    }, follow_redirects=True)
    assert res.status_code == 200


def test_changing_supplier_updates_po_payment_terms(auth_client):
    """Valida que el endpoint API /api/proveedores/<id> devuelve default_payment_terms para actualización dinámica."""
    ts = int(datetime.now().timestamp() * 1000)
    s1_id = insert_supplier({
        "name": f"Prov A {ts}",
        "rut": f"70777{ts % 10000:04d}-7",
        "default_payment_terms": 'CASH'
    })
    s2_id = insert_supplier({
        "name": f"Prov B {ts}",
        "rut": f"70888{ts % 10000:04d}-8",
        "default_payment_terms": 'NET_60'
    })
    
    res1 = auth_client.get(f'/api/proveedores/{s1_id}')
    assert res1.status_code == 200
    data1 = res1.get_json()
    assert data1['default_payment_terms'] == 'CASH'
    assert data1['default_payment_terms_formatted'] == 'Al contado'
    
    res2 = auth_client.get(f'/api/proveedores/{s2_id}')
    assert res2.status_code == 200
    data2 = res2.get_json()
    assert data2['default_payment_terms'] == 'NET_60'
    assert data2['default_payment_terms_formatted'] == 'A 60 días'


def test_po_payment_terms_can_be_overridden():
    """Valida que el usuario puede elegir una forma de pago distinta a la predeterminada del proveedor al crear o editar la OC."""
    ts = int(datetime.now().timestamp() * 1000)
    # Proveedor configurado como NET_30
    s_id = insert_supplier({
        "name": f"Prov Override {ts}",
        "rut": f"70999{ts % 10000:04d}-9",
        "default_payment_terms": 'NET_30'
    })
    
    # En la OC se selecciona Al contado (CASH)
    po_num = create_purchase_order(
        supplier_id=s_id,
        order_date="2026-09-17",
        notes="OC Con Override",
        items=[{"product_id": 1, "quantity": 1, "unit_price": 2000.0}],
        payment_terms='CASH'
    )
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, payment_terms FROM purchase_orders WHERE oc_number = %s", (po_num,))
            po = cur.fetchone()
            po_id = po['id']
            assert po['payment_terms'] == 'CASH'
    
    # El usuario edita la OC y cambia a NET_60
    update_purchase_order(
        po_id=po_id,
        supplier_id=s_id,
        order_date="2026-09-17",
        notes="OC Con Override Editada",
        items=[{"product_id": 1, "quantity": 1, "unit_price": 2000.0}],
        payment_terms='NET_60'
    )
    po_after = get_purchase_order(po_id)
    assert po_after['payment_terms'] == 'NET_60'


def test_po_override_does_not_change_supplier():
    """Valida que cambiar la forma de pago en la OC NO altera la configuración del proveedor."""
    ts = int(datetime.now().timestamp() * 1000)
    s_id = insert_supplier({
        "name": f"Prov Intacto {ts}",
        "rut": f"71000{ts % 10000:04d}-0",
        "default_payment_terms": 'NET_30'
    })
    
    # OC con CASH
    po_num = create_purchase_order(
        supplier_id=s_id,
        order_date="2026-09-17",
        notes="OC Override Check",
        items=[{"product_id": 1, "quantity": 1, "unit_price": 1000.0}],
        payment_terms='CASH'
    )
    
    # El proveedor debe seguir teniendo NET_30
    supplier_after = get_supplier(s_id)
    assert supplier_after['default_payment_terms'] == 'NET_30'


def test_existing_po_keeps_payment_terms_after_supplier_change():
    """Valida que modificar la forma de pago predeterminada del proveedor NO afecta a las OCs ya existentes (snapshot histórico)."""
    ts = int(datetime.now().timestamp() * 1000)
    s_id = insert_supplier({
        "name": f"Prov Hist {ts}",
        "rut": f"71111{ts % 10000:04d}-1",
        "default_payment_terms": 'CASH'
    })
    
    # Se crea OC con CASH heredado
    po_num = create_purchase_order(
        supplier_id=s_id,
        order_date="2026-09-17",
        notes="OC Historica",
        items=[{"product_id": 1, "quantity": 1, "unit_price": 1000.0}],
        payment_terms='CASH'
    )
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, payment_terms FROM purchase_orders WHERE oc_number = %s", (po_num,))
            po_id = cur.fetchone()['id']
    
    # Ahora el proveedor cambia su forma de pago a NET_60
    update_supplier(
        supplier_id=s_id,
        supplier={
            "name": "Prov Hist Modif",
            "rut": get_supplier(s_id)['rut'],
            "default_payment_terms": 'NET_60'
        }
    )
    assert get_supplier(s_id)['default_payment_terms'] == 'NET_60'
    
    # La OC histórica DEBE mantener CASH
    po_reloaded = get_purchase_order(po_id)
    assert po_reloaded['payment_terms'] == 'CASH'


def test_po_pdf_displays_payment_terms(auth_client):
    """Valida que la generación de PDF de la OC incluye la forma de pago correcta con su etiqueta legible."""
    ts = int(datetime.now().timestamp() * 1000)
    s_id = insert_supplier({
        "name": f"Prov PDF {ts}",
        "rut": f"71222{ts % 10000:04d}-2",
        "default_payment_terms": 'NET_60'
    })
    po_num = create_purchase_order(
        supplier_id=s_id,
        order_date="2026-09-17",
        notes="OC para PDF",
        items=[{"product_id": 1, "quantity": 1, "unit_price": 5000.0}],
        payment_terms='NET_60'
    )
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM purchase_orders WHERE oc_number = %s", (po_num,))
            po_id = cur.fetchone()['id']
    
    res = auth_client.get(f'/compras/oc/{po_id}/pdf')
    assert res.status_code == 200
    assert res.headers['Content-Type'] == 'application/pdf'
    assert len(res.data) > 500
    
    # Validar API detalle de OC también
    res_api = auth_client.get(f'/api/compras/oc/{po_id}/detalle')
    assert res_api.status_code == 200
    data_api = res_api.get_json()
    assert data_api['order']['payment_terms'] == 'NET_60'
    assert data_api['order']['payment_terms_formatted'] == 'A 60 días'


def test_invalid_payment_terms_rejected():
    """Valida que valores fuera del conjunto CASH, NET_30, NET_60 sean rechazados por la BD / validaciones."""
    ts = int(datetime.now().timestamp() * 1000)
    
    # En base de datos hay CHECK constraint
    with pytest.raises(Exception):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO suppliers (name, rut, default_payment_terms) VALUES (%s, %s, %s)",
                    (f"Prov Invalido {ts}", f"71333{ts % 10000:04d}-3", "NET_90")
                )
    
    with pytest.raises(Exception):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO purchase_orders (oc_number, supplier_id, payment_terms) VALUES (%s, %s, %s)",
                    (f"OC-INV-{ts}", 1, "A 45 días")
                )


def test_e2e_supplier_and_po_payment_terms_flow(auth_client):
    """
    Prueba integral end-to-end de los 3 escenarios obligatorios:
    - Escenario 1: Proveedor A (Al contado) -> OC creada hereda "Al contado".
    - Escenario 2: Proveedor B (A 30 días) -> OC creada con override manual a "A 60 días"
                   -> OC queda con "A 60 días" y Proveedor B mantiene "A 30 días".
    - Escenario 3: Proveedor C (A 60 días) -> OC creada con "A 60 días".
                   Luego Proveedor C se edita a "Al contado".
                   -> OC histórica mantiene "A 60 días", nueva OC de Proveedor C hereda "Al contado".
    """
    ts = int(datetime.now().timestamp() * 1000)
    
    # ----------------------------------------------------
    # Escenario 1: Proveedor A (Al contado) -> OC con "Al contado"
    # ----------------------------------------------------
    rut_a = _available_test_rut("7144", ts)
    resp_s_a = auth_client.post('/api/proveedores/crear', data=json.dumps({
        'name': f"Proveedor Alpha {ts}",
        'rut': rut_a,
        'default_payment_terms': 'CASH'
    }), content_type='application/json')
    assert resp_s_a.status_code == 200
    s_a_id = resp_s_a.get_json()['supplier']['id']
    
    # Crear OC para Proveedor A usando su forma de pago predeterminada
    po_a_num = create_purchase_order(
        supplier_id=s_a_id,
        order_date="2026-09-17",
        notes="Escenario 1",
        items=[{"product_id": 1, "quantity": 1, "unit_price": 1000.0}],
        payment_terms='CASH'
    )
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, payment_terms FROM purchase_orders WHERE oc_number = %s", (po_a_num,))
            po_a = cur.fetchone()
    assert po_a['payment_terms'] == 'CASH'
    assert format_payment_terms(po_a['payment_terms']) == 'Al contado'
    
    # ----------------------------------------------------
    # Escenario 2: Proveedor B (A 30 días) -> OC con override manual a "A 60 días"
    # ----------------------------------------------------
    rut_b = _available_test_rut("7155", ts)
    resp_s_b = auth_client.post('/api/proveedores/crear', data=json.dumps({
        'name': f"Proveedor Beta {ts}",
        'rut': rut_b,
        'default_payment_terms': 'NET_30'
    }), content_type='application/json')
    assert resp_s_b.status_code == 200
    s_b_id = resp_s_b.get_json()['supplier']['id']
    
    # Crear OC para Proveedor B pero el usuario sobreescribe a NET_60
    po_b_num = create_purchase_order(
        supplier_id=s_b_id,
        order_date="2026-09-17",
        notes="Escenario 2 Override",
        items=[{"product_id": 1, "quantity": 1, "unit_price": 1000.0}],
        payment_terms='NET_60'
    )
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, payment_terms FROM purchase_orders WHERE oc_number = %s", (po_b_num,))
            po_b = cur.fetchone()
    assert po_b['payment_terms'] == 'NET_60'
    assert format_payment_terms(po_b['payment_terms']) == 'A 60 días'
    
    # Verificar que el Proveedor B sigue teniendo NET_30
    s_b = get_supplier(s_b_id)
    assert s_b['default_payment_terms'] == 'NET_30'
    assert format_payment_terms(s_b['default_payment_terms']) == 'A 30 días'
    
    # ----------------------------------------------------
    # Escenario 3: Proveedor C (A 60 días) -> OC 1 hereda "A 60 días"
    # Luego Proveedor C cambia a "Al contado".
    # OC 1 mantiene "A 60 días", OC 2 hereda "Al contado".
    # ----------------------------------------------------
    rut_c = _available_test_rut("7166", ts)
    resp_s_c = auth_client.post('/api/proveedores/crear', data=json.dumps({
        'name': f"Proveedor Gamma {ts}",
        'rut': rut_c,
        'default_payment_terms': 'NET_60'
    }), content_type='application/json')
    assert resp_s_c.status_code == 200
    s_c_id = resp_s_c.get_json()['supplier']['id']
    
    # OC 1
    po_c1_num = create_purchase_order(
        supplier_id=s_c_id,
        order_date="2026-09-17",
        notes="Escenario 3 OC 1",
        items=[{"product_id": 1, "quantity": 1, "unit_price": 1000.0}],
        payment_terms='NET_60'
    )
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, payment_terms FROM purchase_orders WHERE oc_number = %s", (po_c1_num,))
            po_c1_id = cur.fetchone()['id']
    
    # Proveedor C cambia su configuración a CASH
    auth_client.post(f'/proveedores/{s_c_id}/editar', data={
        'name': f"Proveedor Gamma Modificado {ts}",
        'rut': rut_c,
        'default_payment_terms': 'CASH'
    }, follow_redirects=True)
    
    s_c_updated = get_supplier(s_c_id)
    assert s_c_updated['default_payment_terms'] == 'CASH'
    
    # OC 1 histórica debe mantenerse intacta
    po_c1_after = get_purchase_order(po_c1_id)
    assert po_c1_after['payment_terms'] == 'NET_60'
    assert format_payment_terms(po_c1_after['payment_terms']) == 'A 60 días'
    
    # OC 2 nueva para Proveedor C hereda CASH
    po_c2_num = create_purchase_order(
        supplier_id=s_c_id,
        order_date="2026-09-17",
        notes="Escenario 3 OC 2",
        items=[{"product_id": 1, "quantity": 1, "unit_price": 1000.0}],
        payment_terms=s_c_updated['default_payment_terms']
    )
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, payment_terms FROM purchase_orders WHERE oc_number = %s", (po_c2_num,))
            po_c2 = cur.fetchone()
    assert format_payment_terms(po_c2['payment_terms']) == 'Al contado'
