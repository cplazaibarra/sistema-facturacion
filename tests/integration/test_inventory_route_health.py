def test_inventory_route_renders_without_missing_price(auth_client):
    response = auth_client.get('/inventario')
    assert response.status_code == 200
    assert b'Inventario' in response.data
