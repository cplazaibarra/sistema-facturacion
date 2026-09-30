import io
import re
import uuid

from db import get_connection
from repositories.sales_repo import insert_sale


def _csrf(client):
    response = client.get('/ventas')
    match = re.search(rb'meta name="csrf-token" content="([^"]+)"', response.data)
    return match.group(1).decode() if match else ''


def _sale(total=100):
    marker = uuid.uuid4().hex[:10]
    sale_id = insert_sale({
        'sale_number': f'VTA-QA-{marker}',
        'customer_name': 'Cliente Pago QA',
        'customer_email': f'qa-{marker}@example.com',
        'sale_date': '2026-09-22',
        'sale_time': '10:00:00',
        'products': [],
        'total_amount': total,
        'status': 'Pendiente',
        'seller_name': 'QA',
        'payment_status': 'Pendiente',
        'created_at': '2026-09-22T10:00:00+00:00',
    })
    return sale_id


def _cleanup(sale_id, bank_id=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM sales_payment_history WHERE sale_id = %s', (sale_id,))
            cur.execute('DELETE FROM sales_status_history WHERE sale_id = %s', (sale_id,))
            cur.execute('DELETE FROM sale_payment_items WHERE sale_id = %s', (sale_id,))
            cur.execute('DELETE FROM sale_payments WHERE sale_id = %s', (sale_id,))
            cur.execute('DELETE FROM sales WHERE id = %s', (sale_id,))
            if bank_id:
                cur.execute('DELETE FROM bank_accounts WHERE id = %s', (bank_id,))
        conn.commit()


def test_transfer_payment_is_formal_idempotent_and_protected(auth_client):
    sale_id = _sale(100)
    bank_id = None
    temporary_bank = False
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM bank_accounts WHERE status = 'Activa' ORDER BY id LIMIT 1")
                row = cur.fetchone()
                if row:
                    bank_id = row['id']
                else:
                    cur.execute("INSERT INTO bank_accounts (bank_name, account_number, account_type, holder_name, status) VALUES ('QA Bank', 'QA-001', 'Corriente', 'ERP QA', 'Activa') RETURNING id")
                    bank_id = cur.fetchone()['id']
                    temporary_bank = True
            conn.commit()

        key = uuid.uuid4().hex
        data = {
            'csrf_token': _csrf(auth_client), 'sale_id': str(sale_id),
            'payment_method': 'Transferencia', 'payment_date': '2026-09-22',
            'payment_amount': '100', 'bank_account_id': str(bank_id),
            'idempotency_key': key,
            'payment_file': (io.BytesIO(b'%PDF-1.4 QA'), 'comprobante.pdf'),
        }
        response = auth_client.post('/ventas/registrar-pago', data=data, content_type='multipart/form-data')
        assert response.status_code == 302
        replay = auth_client.post('/ventas/registrar-pago', data={**data, 'payment_file': (io.BytesIO(b'%PDF-1.4 QA'), 'comprobante.pdf')}, content_type='multipart/form-data')
        assert replay.status_code == 302

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT payment_status FROM sales WHERE id = %s', (sale_id,))
                assert cur.fetchone()['payment_status'] == 'Pagado'
                cur.execute('SELECT COUNT(*) AS n, payment_method, bank_account_id, registered_by, bank_name_snapshot FROM sale_payment_items WHERE sale_id = %s GROUP BY payment_method, bank_account_id, registered_by, bank_name_snapshot', (sale_id,))
                row = cur.fetchone()
                assert row['n'] == 1
                assert row['payment_method'] == 'Transferencia'
                assert row['bank_account_id'] == bank_id
                item_id = None
                cur.execute('SELECT id FROM sale_payment_items WHERE sale_id = %s', (sale_id,))
                item_id = cur.fetchone()['id']

        detail = auth_client.get(f'/ventas/pagos/comprobante/{item_id}')
        assert detail.status_code == 200
    finally:
        _cleanup(sale_id, bank_id if temporary_bank else None)


def test_cash_payment_does_not_require_bank_or_proof(auth_client):
    sale_id = _sale(50)
    try:
        response = auth_client.post('/ventas/registrar-pago', data={
            'csrf_token': _csrf(auth_client), 'sale_id': str(sale_id),
            'payment_method': 'Efectivo', 'payment_date': '2026-09-22',
            'payment_amount': '50', 'payment_notes': 'Pago recibido en caja',
            'idempotency_key': uuid.uuid4().hex,
        })
        assert response.status_code == 302
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT payment_status FROM sales WHERE id = %s', (sale_id,))
                assert cur.fetchone()['payment_status'] == 'Pagado'
                cur.execute('SELECT payment_method, bank_account_id, payment_proof_file, payment_notes FROM sale_payment_items WHERE sale_id = %s', (sale_id,))
                row = cur.fetchone()
                assert row['payment_method'] == 'Efectivo'
                assert row['bank_account_id'] is None
                assert row['payment_proof_file'] is None
                assert row['payment_notes'] == 'Pago recibido en caja'
    finally:
        _cleanup(sale_id)


def test_payment_endpoint_requires_permission(client):
    sale_id = _sale(10)
    try:
        with client.session_transaction() as session:
            session.update({'user_id': 999, 'username': 'readonly', 'role_name': 'Consulta', 'permissions': {}})
        response = client.post('/ventas/registrar-pago', data={'sale_id': str(sale_id), 'csrf_token': _csrf(client)})
        assert response.status_code == 403
    finally:
        _cleanup(sale_id)
