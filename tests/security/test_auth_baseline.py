import pytest

def test_login_invalid_credentials(client):
    """Login con credenciales incorrectas debe fallar y permanecer en login."""
    resp = client.post('/login', data={'username': 'admin', 'password': 'clave_erronea_123'}, follow_redirects=True)
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert "Usuario o contrase" in html or "incorrectos" in html

def test_login_valid_credentials(client):
    """Login con credenciales válidas redirige a dashboard y establece sesión."""
    resp = client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=False)
    assert resp.status_code == 302
    assert '/dashboard' in resp.headers.get('Location', '')

def test_logout_clears_session(auth_client):
    """Logout limpia la sesión y redirige a login."""
    resp = auth_client.get('/logout', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers.get('Location', '')
    
    # Verificar que tras logout ya no puede acceder a dashboard
    resp_dash = auth_client.get('/dashboard', follow_redirects=False)
    assert resp_dash.status_code == 302
    assert '/login' in resp_dash.headers.get('Location', '')

def test_api_unauthenticated_returns_401(client):
    """Rutas /api/ sin sesión deben retornar código 401 en JSON."""
    resp = client.get('/api/dashboard-data')
    assert resp.status_code == 401
    json_data = resp.get_json()
    assert json_data is not None
    assert json_data.get('status') == 'error'
