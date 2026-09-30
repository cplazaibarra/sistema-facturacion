"""RBAC regression coverage for master-data CRUD and product Excel import."""

from tests.conftest import get_csrf_token
from app import app


def _read_only_client():
    client = app.test_client()
    with client.session_transaction() as session:
        session.update({
            "user_id": 900001,
            "username": "master_read_only",
            "full_name": "Master Read Only",
            "role_name": "Consulta",
            "permissions": {},
        })
    return client


def test_master_data_read_only_role_is_denied_crud_and_excel_import():
    client = _read_only_client()
    csrf = get_csrf_token(client, "/login")
    assert csrf

    # Reads, edits and import entry points all require the module permission.
    assert client.get("/productos").status_code == 403
    assert client.get("/productos/exportar").status_code == 403
    assert client.get("/proveedores").status_code == 403
    assert client.get("/ventas/clientes").status_code == 403

    headers = {"X-CSRFToken": csrf}
    assert client.post(
        "/productos",
        data={"csrf_token": csrf, "sku": "RBAC-MUST-NOT-CREATE", "name": "No crear"},
        headers=headers,
    ).status_code == 403
    assert client.post(
        "/productos/importar/preview",
        data={"csrf_token": csrf},
        headers=headers,
    ).status_code == 403
    assert client.post(
        "/productos/importar/confirmar",
        data={"csrf_token": csrf, "import_id": "invalid"},
        headers=headers,
    ).status_code == 403
    assert client.post(
        "/ventas/clientes",
        data={"csrf_token": csrf, "razon_social": "No crear", "email": "invalid@example.invalid"},
        headers=headers,
    ).status_code == 403
    response = client.post(
        "/api/proveedores/crear",
        json={"name": "No crear", "rut": "123", "dv": "0"},
        headers=headers,
    )
    assert response.status_code == 403


def test_csrf_rejects_master_data_mutation_before_rbac_or_business_logic():
    client = _read_only_client()
    response = client.post(
        "/productos/importar/confirmar",
        data={"import_id": "invalid"},
    )
    assert response.status_code == 400
