"""Pruebas de dirección de despacho y snapshot comercial de cotizaciones."""

from datetime import datetime, timezone
import uuid

from db import get_connection
from repositories.clients_repo import insert_client, get_client_by_id, update_client
from repositories.sales_repo import insert_sale, get_sale, update_sale


def test_cliente_delivery_address_create_edit_and_quote_snapshot():
    marker = uuid.uuid4().hex[:10]
    rut = f"9{marker[:7]}"
    client_id = insert_client({
        "rut": rut,
        "dv": "K",
        "razon_social": f"Cliente QA {marker}",
        "email": f"qa-{marker}@example.com",
        "category_id": "cat_1",
        "delivery_address": "TEST DIRECCION A",
    })
    sale_id = None
    try:
        client = get_client_by_id(client_id)
        assert client["delivery_address"] == "TEST DIRECCION A"

        update_client(client_id, {
            **client,
            "delivery_address": "TEST DIRECCION B",
        })
        assert get_client_by_id(client_id)["delivery_address"] == "TEST DIRECCION B"

        sale_id = insert_sale({
            "sale_number": f"COT-QA-{marker}",
            "customer_name": client["razon_social"],
            "customer_email": client["email"],
            "sale_date": "2026-01-01",
            "sale_time": "10:00:00",
            "products": [{"product_id": 1, "quantity": 1, "price": 10, "subtotal": 10}],
            "total_amount": 10,
            "status": "Cotización",
            "seller_name": "QA",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "customer_delivery_address": "TEST DIRECCION A",
            "customer_category_snapshot": "Categoría B",
        })
        saved = get_sale(sale_id)
        assert saved["customer_delivery_address"] == "TEST DIRECCION A"
        assert saved["customer_category_snapshot"] == "Categoría B"

        # Cambiar nuevamente el maestro no modifica el snapshot persistido.
        update_client(client_id, {**get_client_by_id(client_id), "delivery_address": "TEST DIRECCION C"})
        historical = get_sale(sale_id)
        assert historical["customer_delivery_address"] == "TEST DIRECCION A"
        assert historical["customer_category_snapshot"] == "Categoría B"
    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if sale_id:
                    cur.execute("DELETE FROM sales WHERE id = %s", (sale_id,))
                cur.execute("DELETE FROM clients WHERE id = %s", (client_id,))
            conn.commit()


def test_customer_search_and_rut_api_expose_delivery_address(auth_client):
    response = auth_client.get("/api/clientes/buscar?q=Cliente")
    assert response.status_code == 200
    assert response.is_json
