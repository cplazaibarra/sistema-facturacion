import pytest

from app import app


SALES_ROLE_PERMISSIONS = {
    'dashboard': False,
    'usuarios': False,
    'ventas': True,
    'inventario': False,
    'productos': True,
    'administracion': False,
    'reportes': False,
    'configuracion': False,
    'crear_registros': True,
    'aprobar_registros': False,
    'solo_ver': False,
}


@pytest.fixture
def sales_role_client():
    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update({
                'user_id': 3,
                'username': 'master_sales_role',
                'full_name': 'Master Sales Role',
                'role_name': 'Área Ventas',
                'permissions': SALES_ROLE_PERMISSIONS.copy(),
            })
        yield client


@pytest.mark.parametrize('path', [
    '/compras/oc',
    '/proveedores',
    '/produccion',
    '/inventario',
    '/reporteria/flujo-caja',
    '/administracion/cuentas-bancarias',
    '/dashboard',
    '/api/dashboard-data',
    '/api/notificaciones',
])
def test_sales_role_cannot_access_inventory_purchasing_or_admin_modules(sales_role_client, path):
    response = sales_role_client.get(path)
    assert response.status_code == 403


@pytest.mark.parametrize('path', ['/productos', '/ventas/clientes'])
def test_sales_role_can_access_granted_product_and_sales_modules(sales_role_client, path):
    response = sales_role_client.get(path)
    assert response.status_code == 200


def test_sales_mutation_without_csrf_token_is_rejected(sales_role_client):
    response = sales_role_client.post(
        '/ventas/clientes/guardar_modal',
        data={'razon_social': 'Debe quedar bloqueado', 'email': 'csrf@example.invalid'},
    )
    assert response.status_code == 400
