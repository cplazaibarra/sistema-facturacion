import pytest
from core.database import get_connection
from db import insert_sale, get_sale, update_quotation_status, update_sale
from tests.conftest import get_csrf_token

def create_test_quotation(status="Activa", probability=70):
    sale_data = {
        "sale_number": "COT-TEST-PROB",
        "customer_name": "Cliente Prueba Regla Perdida",
        "customer_email": "test_perdida@empresa.cl",
        "customer_initials": "CP",
        "sale_date": "2026-09-25",
        "sale_time": "12:00:00",
        "products": [
            {
                "product_id": 1,
                "product_name": "Producto Test",
                "quantity": 1,
                "price": 10000.0,
                "discount": 0.0,
                "subtotal": 10000.0,
                "lot_number": ""
            }
        ],
        "total_amount": 10000.0,
        "status": "Cotización",
        "quotation_status": status,
        "win_probability": probability,
        "seller_name": "Vendedor Test",
        "seller_initials": "VT",
        "payment_method": "Efectivo",
        "payment_status": "Cotización",
        "delivery_status": "Cotización",
        "notes": "Test cotizacion probabilidad",
        "created_at": "2026-09-25T12:00:00Z"
    }
    return insert_sale(sale_data)

def cleanup_test_quotation(sale_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sales WHERE id = %s", (sale_id,))
        conn.commit()


def test_case_1_activa_to_perdida_forces_zero_probability():
    """
    Caso 1:
    Cotización en estado Activa (En Negociación) con 70% de probabilidad.
    Al cambiar a Perdida -> Backend asigna y persiste 0%.
    """
    sale_id = create_test_quotation(status="Activa", probability=70)
    try:
        cot = get_sale(sale_id)
        assert cot["quotation_status"] == "Activa"
        assert cot["win_probability"] == 70

        update_quotation_status(sale_id, status="Perdida", probability=70)
        updated = get_sale(sale_id)
        assert updated["quotation_status"] == "Perdida"
        assert updated["win_probability"] == 0
    finally:
        cleanup_test_quotation(sale_id)


def test_case_2_enviada_to_perdida_forces_zero_probability():
    """
    Caso 2:
    Cotización con 40% de probabilidad.
    Al marcar Perdida -> Backend asigna y persiste 0%.
    """
    sale_id = create_test_quotation(status="Activa", probability=40)
    try:
        cot = get_sale(sale_id)
        assert cot["win_probability"] == 40

        update_quotation_status(sale_id, status="Perdida", probability=40)
        updated = get_sale(sale_id)
        assert updated["quotation_status"] == "Perdida"
        assert updated["win_probability"] == 0
    finally:
        cleanup_test_quotation(sale_id)


def test_case_3_backend_source_of_truth_post_payload_tampering(auth_client):
    """
    Caso 3:
    Envío directo de datos manipulados al endpoint POST:
    quotation_status='Perdida' y win_probability=80.
    El backend DEBE forzar y persistir win_probability=0.
    """
    sale_id = create_test_quotation(status="Activa", probability=70)
    try:
        csrf_token = get_csrf_token(auth_client, path='/ventas/cotizaciones')
        payload = {
            'quotation_status': 'Perdida',
            'win_probability': '80'
        }
        if csrf_token:
            payload['csrf_token'] = csrf_token

        response = auth_client.post(
            f'/ventas/cotizacion/{sale_id}/actualizar-estado',
            data=payload,
            follow_redirects=True
        )
        assert response.status_code == 200

        updated = get_sale(sale_id)
        assert updated["quotation_status"] == "Perdida"
        assert updated["win_probability"] == 0
    finally:
        cleanup_test_quotation(sale_id)


def test_case_4_update_sale_cannot_set_probability_on_perdida():
    """
    Caso 4:
    Intento de modificar cotización en estado Perdida asignando 50% vía update_sale.
    El backend DEBE garantizar que la probabilidad quede en 0%.
    """
    sale_id = create_test_quotation(status="Perdida", probability=0)
    try:
        cot = get_sale(sale_id)
        assert cot["quotation_status"] == "Perdida"
        assert cot["win_probability"] == 0

        # Intentar forzar probabilidad 50%
        cot["win_probability"] = 50
        update_sale(sale_id, cot)

        updated = get_sale(sale_id)
        assert updated["quotation_status"] == "Perdida"
        assert updated["win_probability"] == 0
    finally:
        cleanup_test_quotation(sale_id)


def test_case_5_transition_from_perdida_to_activa_keeps_zero_probability(auth_client):
    """
    Caso 5:
    Cotización pasa de Perdida (0%) a Activa.
    NO debe inventar una probabilidad nueva automáticamente (se mantiene en 0%
    a menos que el usuario especifique explícitamente un valor).
    """
    sale_id = create_test_quotation(status="Perdida", probability=0)
    try:
        csrf_token = get_csrf_token(auth_client, path='/ventas/cotizaciones')
        payload = {
            'quotation_status': 'Activa',
            'win_probability': ''
        }
        if csrf_token:
            payload['csrf_token'] = csrf_token

        response = auth_client.post(
            f'/ventas/cotizacion/{sale_id}/actualizar-estado',
            data=payload,
            follow_redirects=True
        )
        assert response.status_code == 200

        updated = get_sale(sale_id)
        assert updated["quotation_status"] == "Activa"
        assert updated["win_probability"] == 0
    finally:
        cleanup_test_quotation(sale_id)


def test_case_6_transitions_between_non_perdida_states_retain_probability(auth_client):
    """
    Caso 6:
    Cambios entre estados regulares conservan o actualizan su probabilidad normalmente.
    """
    sale_id = create_test_quotation(status="Activa", probability=65)
    try:
        csrf_token = get_csrf_token(auth_client, path='/ventas/cotizaciones')
        payload = {
            'quotation_status': 'Activa',
            'win_probability': '65'
        }
        if csrf_token:
            payload['csrf_token'] = csrf_token

        response = auth_client.post(
            f'/ventas/cotizacion/{sale_id}/actualizar-estado',
            data=payload,
            follow_redirects=True
        )
        assert response.status_code == 200

        updated = get_sale(sale_id)
        assert updated["quotation_status"] == "Activa"
        assert updated["win_probability"] == 65
    finally:
        cleanup_test_quotation(sale_id)
