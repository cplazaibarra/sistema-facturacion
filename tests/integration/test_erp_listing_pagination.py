"""SQL-backed acceptance tests for the transversal pagination work."""
import re
import uuid
from decimal import Decimal

import openpyxl
import pytest
from psycopg2.extras import RealDictCursor
from core.database import get_connection
from core.pagination import PAGE_SIZE, pagination_meta
from repositories.bank_reconciliation_repo import list_bank_transactions, get_bank_reconciliation_kpis
from services.bank_reconciliation_excel_service import export_bank_transactions_to_excel


@pytest.fixture
def bank_listing():
    marker = 'PAGING-' + uuid.uuid4().hex
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO bank_accounts (bank_name,account_number,account_type,holder_name,status)
                VALUES ('Pagination test',%s,'Cuenta Corriente','Test','Activa') RETURNING id""", (marker,))
            account_id = cur.fetchone()['id']
        conn.commit()
    def seed(n):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO bank_transactions
                    (bank_account_id,transaction_date,description,credit,charge,amount,movement_type,fingerprint,reconciliation_status)
                    SELECT %s,DATE '2026-01-01',%s || '-' || i,10,0,10,'ABONO',%s || '-' || i,'PENDIENTE'
                    FROM generate_series(1,%s) i""", (account_id, marker, marker, n))
            conn.commit()
    yield account_id, marker, seed
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM bank_transactions WHERE bank_account_id=%s', (account_id,))
            cur.execute('DELETE FROM bank_accounts WHERE id=%s', (account_id,))
        conn.commit()


@pytest.mark.parametrize('n', [0, 1, 30, 31, 60, 61])
def test_bank_sql_pages_and_complete_export(bank_listing, auth_client, monkeypatch, n):
    account_id, marker, seed = bank_listing
    seed(n)
    import psycopg2
    original_connect = psycopg2.connect
    fetched = []
    class RecordingCursor(RealDictCursor):
        def fetchall(self):
            rows = super().fetchall()
            query = self.query.decode() if self.query else ''
            if 'bt.import_id' in query:
                fetched.append((query, len(rows)))
            return rows
    def connect(*args, **kwargs):
        kwargs['cursor_factory'] = RecordingCursor
        return original_connect(*args, **kwargs)
    monkeypatch.setattr(psycopg2, 'connect', connect)
    ids = []
    for page in range(1, pagination_meta(n)['total_pages'] + 1):
        rows, count = list_bank_transactions(bank_account_id=account_id, page=page, per_page=100000)
        assert count == n
        assert len(rows) <= PAGE_SIZE
        ids.extend(row['id'] for row in rows)
    assert len(ids) == len(set(ids)) == n
    assert all('LIMIT 30 OFFSET' in sql and count <= 30 for sql, count in fetched)
    for invalid in ('abc', -1, 999999):
        rows, count = list_bank_transactions(bank_account_id=account_id, page=invalid)
        assert count == n
        assert len(rows) <= 30
        response = auth_client.get(f'/reporteria/conciliacion-bancaria?bank_account_id={account_id}&page={invalid}&per_page=100000&sort_by=amount&order=asc')
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert len(re.findall(r'id="row-tx-\d+"', html)) <= 30
        assert f'de {n} registros' in html
        if n > 30:
            assert 'sort_by=amount' in html and 'order=asc' in html
    kpis = get_bank_reconciliation_kpis(bank_account_id=account_id, search=marker, movement_type='ABONO')
    assert kpis['total_count'] == n
    assert kpis['total_abonos'] == Decimal(n * 10)
    assert get_bank_reconciliation_kpis(bank_account_id=account_id, movement_type='CARGO')['total_count'] == 0
    book = openpyxl.load_workbook(export_bank_transactions_to_excel(bank_account_id=account_id), data_only=True)
    # Canonical file has one header row; blank styled rows are ignored.
    values = list(book.active.values)
    exported = [row for row in values if any(isinstance(v, str) and marker in v for v in row)]
    assert len(exported) == n
    if n:
        rows, count = list_bank_transactions(bank_account_id=account_id, search=marker + '-1')
        assert count >= 1
        assert all(marker + '-1' in row['description'] for row in rows)


@pytest.mark.parametrize('n', [0, 1, 30, 31, 60, 61])
def test_quotation_sql_pages(bank_listing, auth_client, n):
    import json
    from repositories.sales_repo import get_quotation_page
    _, marker, _ = bank_listing
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO sales (sale_number,customer_name,sale_date,sale_time,products_json,
                    total_amount,status,seller_name,quotation_status,created_at)
                    SELECT 'COT-' || %s || '-' || i,%s,'2026-01-01','12:00:00',%s,100,'Cotización','Test','Activa','2026-01-01'
                    FROM generate_series(1,%s) i""", (marker,marker,json.dumps([{'name':'Remote product','quantity':1}]),n))
            conn.commit()
        ids = []
        for page in range(1,pagination_meta(n)['total_pages']+1):
            with get_connection() as conn:
                with conn.cursor() as cur:
                    rows, pagination, metrics, _, _ = get_quotation_page(cur,page=page,search=marker,product='Remote product')
                    assert len(rows) <= 30
                    assert pagination['total'] == metrics['total'] == n
                    assert metrics['active'] == n
                    ids.extend(r['id'] for r in rows)
        assert len(ids) == len(set(ids)) == n
        for invalid in ('abc','-1','999999'):
            response = auth_client.get('/ventas/cotizaciones',query_string={'search':marker,'page':invalid,'per_page':100000})
            assert response.status_code == 200
            html = response.get_data(as_text=True)
            assert html.count('<tr class="sf-table-row"') <= 30
            assert f'de {n} registros' in html
        if n:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    rows,pagination,*_ = get_quotation_page(cur,search=marker,product='missing product')
                    assert pagination['total'] == 0 and not rows
    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('DELETE FROM sales WHERE customer_name=%s', (marker,))
            conn.commit()


@pytest.mark.parametrize('n', [0, 1, 30, 31, 60, 61])
def test_matrix_sql_pages_full_totals_and_csv(bank_listing, auth_client, n):
    from repositories.reporting_repo import get_purchased_products_matrix
    _, marker, _ = bank_listing
    po_id = None
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO purchase_orders (oc_number,supplier_id,order_date,status,total_amount,created_at)
                    SELECT %s,id,'2026-01-01','Emitida',0,'2026-01-01' FROM suppliers ORDER BY id LIMIT 1 RETURNING id""",(marker,))
                po_id = cur.fetchone()['id']
                cur.execute("""INSERT INTO products (sku,name,category,created_at)
                    SELECT %s || '-' || i,'Same name',%s,'2026-01-01' FROM generate_series(1,%s) i RETURNING id""",(marker,marker,n))
                product_ids = [r['id'] for r in cur.fetchall()]
                cur.execute("""INSERT INTO purchase_order_items (purchase_order_id,product_id,quantity_ordered,unit_price,total_price)
                    SELECT %s,id,2,10,20 FROM products WHERE id=ANY(%s)""",(po_id,product_ids))
            conn.commit()
        ids = []
        for page in range(1,pagination_meta(n)['total_pages']+1):
            result = get_purchased_products_matrix(2026,category=marker,page=page,per_page=100000)
            assert len(result['products']) <= 30
            assert result['total_skus'] == n
            assert result['grand_total_qty'] == n * 2
            assert result['grand_total_amount'] == n * 20
            assert result['monthly_totals'][1] == n * 2
            ids.extend(r['product_id'] for r in result['products'])
        assert len(ids) == len(set(ids)) == n
        assert len(get_purchased_products_matrix(2026,category=marker)['products']) == n
        result = get_purchased_products_matrix(2026,category=marker,page=999999)
        assert result['page'] == pagination_meta(n,999999)['page']
        response = auth_client.get('/compras/productos-comprados/exportar-csv',query_string={'year':2026,'category':marker,'page':2})
        assert response.status_code == 200
        assert sum(line.startswith(marker+'-') for line in response.get_data(as_text=True).splitlines()) == n
        missing = auth_client.get('/compras/productos-comprados/exportar-csv', query_string={'year':2026,'category':marker,'search':'nonexistent item'})
        assert missing.status_code == 200
        assert not any(line.startswith(marker+'-') for line in missing.get_data(as_text=True).splitlines())
    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if po_id:
                    cur.execute('DELETE FROM purchase_order_items WHERE purchase_order_id=%s',(po_id,))
                    cur.execute('DELETE FROM purchase_orders WHERE id=%s',(po_id,))
                cur.execute('DELETE FROM products WHERE category=%s',(marker,))
            conn.commit()


def test_accounts_sql_page_and_rbac(auth_client):
    from app import app
    client = app.test_client()
    from repositories.finance_repo import get_bank_accounts_page
    rows, meta = get_bank_accounts_page('999999')
    assert len(rows) <= 30
    assert meta['page'] == meta['total_pages']
    for route in ('/administracion/cuentas-bancarias','/reporteria/conciliacion-bancaria'):
        assert auth_client.get(route).status_code == 200
        assert client.get(route).status_code == 302
        with client.session_transaction() as session:
            session['user_id'] = 1
            session['permissions'] = {'administracion':False,'reportes':False}
        assert client.get(route).status_code == 403
        with client.session_transaction() as session:
            session.clear()


def test_purchase_invoice_list_is_fixed_sql_page_and_searchable(auth_client):
    from repositories.purchases_repo import get_purchase_invoices_page, get_purchase_invoice_summary
    page1, meta1 = get_purchase_invoices_page(page=1)
    assert len(page1) <= 30
    assert meta1['per_page'] == 30
    page2, meta2 = get_purchase_invoices_page(page=2)
    assert meta2['total'] == meta1['total']
    assert {r['id'] for r in page1}.isdisjoint({r['id'] for r in page2})
    if page1:
        item=page1[0]
        search=item.get('invoice_number') or item.get('supplier_name') or item.get('oc_number')
        matched,search_meta=get_purchase_invoices_page(search=search)
        assert search_meta['total'] >= 1
        assert any(r['id']==item['id'] for r in matched)
        filtered,filtered_meta=get_purchase_invoices_page(status_filter=item['payment_status'])
        assert filtered_meta['total'] >= 1
        assert all(r['payment_status']==item['payment_status'] for r in filtered)
    rows=__import__('repositories.purchases_repo',fromlist=['list_purchase_invoices']).list_purchase_invoices()
    summary=get_purchase_invoice_summary()
    assert summary['n_pendientes']==sum(r['payment_status'] in ('Pendiente','Vencida') for r in rows)
    assert summary['n_vencidas']==sum(r['payment_status']=='Vencida' for r in rows)
    assert auth_client.get('/compras/cuentas-por-pagar?page=999999&per_page=100000').status_code==200
    html=auth_client.get('/compras/cuentas-por-pagar?filtro=todas&page=1').get_data(as_text=True)
    assert html.count('id="invoices-table-body"')==1
    assert html.count('<tr style="border-bottom:1px solid #f0f0f0;">') <= 30
    assert 'Mostrando 1–30 de' in html or meta1['total'] <= 30


def test_purchase_form_remote_selectors_are_bounded(auth_client):
    suppliers=auth_client.get('/api/compras/selectores/proveedores').get_json()
    banks=auth_client.get('/api/compras/selectores/cuentas-bancarias').get_json()
    assert len(suppliers['items']) <= 30
    assert len(banks['items']) <= 30
    if suppliers['items']:
        item=suppliers['items'][0]
        resolved=auth_client.get('/api/compras/selectores/proveedores',query_string={'id':item['id']}).get_json()
        assert resolved['items'][0]['id']==item['id']
    if banks['items']:
        item=banks['items'][0]
        resolved=auth_client.get('/api/compras/selectores/cuentas-bancarias',query_string={'id':item['id']}).get_json()
        assert resolved['items'][0]['id']==item['id']
    assert auth_client.get('/api/compras/selectores/nope').status_code==404
