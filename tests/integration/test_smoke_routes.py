import pytest

def test_unauthenticated_redirect(client):
    """Acceso anónimo a ruta protegida debe redirigir a /login."""
    resp = client.get('/dashboard', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers.get('Location', '')

def test_login_page_loads(client):
    """Página de login debe responder 200 con formulario."""
    resp = client.get('/login')
    assert resp.status_code == 200
    assert b'Iniciar Sesi' in resp.data or b'username' in resp.data

def test_dashboard_authenticated(auth_client):
    """1. Dashboard responde 200 para usuario autenticado."""
    resp = auth_client.get('/dashboard')
    assert resp.status_code == 200

def test_productos_loads(auth_client):
    """2. Módulo Productos responde 200."""
    resp = auth_client.get('/productos')
    assert resp.status_code == 200

def test_proveedores_loads(auth_client):
    """3. Módulo Proveedores responde 200."""
    resp = auth_client.get('/proveedores')
    assert resp.status_code == 200

def test_clientes_loads(auth_client):
    """4. Módulo Clientes responde 200."""
    resp = auth_client.get('/ventas/clientes')
    assert resp.status_code == 200

def test_compras_oc_loads(auth_client):
    """5. Módulo Compras (OC) responde 200."""
    resp = auth_client.get('/compras/oc')
    assert resp.status_code == 200

def test_inventario_loads(auth_client):
    """6. Módulo Inventario / Stock responde 200."""
    resp = auth_client.get('/inventario')
    assert resp.status_code == 200

def test_cotizaciones_loads(auth_client):
    """7. Módulo Cotizaciones responde 200."""
    resp = auth_client.get('/ventas/cotizaciones')
    assert resp.status_code == 200

def test_ventas_loads(auth_client):
    """8. Módulo Ventas responde 200."""
    resp = auth_client.get('/ventas')
    assert resp.status_code == 200

def test_produccion_loads(auth_client):
    """9. Módulo Producción (OTs) responde 200."""
    resp = auth_client.get('/produccion')
    assert resp.status_code == 200

def test_cuentas_por_pagar_loads(auth_client):
    """10. Módulo Cuentas por Pagar (CxP) responde 200."""
    resp = auth_client.get('/compras/cuentas-por-pagar')
    assert resp.status_code == 200

def test_cuentas_por_cobrar_loads(auth_client):
    """11. Módulo Cuentas por Cobrar (CxC / Ventas cobros) responde 200."""
    resp = auth_client.get('/ventas?filter=pendiente')
    assert resp.status_code == 200

def test_cuentas_bancarias_loads(auth_client):
    """12. Módulo Cuentas Bancarias responde 200."""
    resp = auth_client.get('/administracion/cuentas-bancarias')
    assert resp.status_code == 200
