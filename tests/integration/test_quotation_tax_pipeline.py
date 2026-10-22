import json
import uuid
import pytest
from db import get_connection
from repositories.products_repo import create_product
from repositories.sales_repo import get_sale, get_sale_financial_summary
from repositories.kardex_repo import get_batch_current_ppp, get_current_ppp
from services.money import document_amounts
from tests.conftest import get_csrf_token


def post_quote(client, name, pid, **changes):
    form = {'customer_name':name,'customer_email':'','status':'Cotización',
            'quotation_status':'Activa','customer_category':'cat_0',
            'product_id[]':[str(pid)],'quantity[]':['3'],'unit_price[]':['10000'],
            'discount[]':['10'],'csrf_token':get_csrf_token(client,'/ventas/cotizacion/nueva')}
    form.update(changes)
    return client.post('/ventas/cotizacion/nueva',data=form)


def test_quote_conversion_cxc_and_profit_use_the_same_gross_total(auth_client):
    marker='TAX-'+uuid.uuid4().hex[:10]
    pid=create_product(sku=marker,name=marker,product_type='Final',cost=1000)
    response=post_quote(auth_client,marker,pid)
    assert response.status_code==302
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT id FROM sales WHERE customer_name=%s',(marker,))
        qid=cur.fetchone()['id']
    quote=get_sale(qid)
    assert quote['total_amount']==32130  # net 27,000 + VAT 5,130
    assert quote['products'][0]['subtotal']==27000
    assert document_amounts(quote['products'],quote['total_amount'])['net']==27000
    token=get_csrf_token(auth_client,'/ventas/cotizaciones')
    response=auth_client.post(f'/ventas/cotizacion/{qid}/convertir',data={'csrf_token':token})
    assert response.status_code==302
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM sales WHERE customer_name=%s AND status='Pendiente'",(marker,))
        sid=cur.fetchone()['id']
        cur.execute('SELECT count(*) AS n FROM sale_items WHERE sale_id=%s',(sid,))
        assert cur.fetchone()['n']==0
    sale=get_sale(sid)
    assert sale['total_amount']==32130
    financial=get_sale_financial_summary(sid)
    assert financial['neto']==27000
    assert financial['iva']==5130
    assert financial['products_cost']==3000
    assert financial['real_margin']==24000
    assert financial['cost_status']=='estimated'
    assert financial['costs_complete']
    from repositories.reporting_repo import get_accounts_receivable_report_data
    # The exact gross total is also the receivable, not the tax-exclusive line sum.
    report=get_accounts_receivable_report_data(search=marker,per_page=None)
    rows=report.get('items',report.get('rows',report.get('records',[]))) if isinstance(report,dict) else report
    assert any(r.get('id',r.get('sale_id'))==sid and r['total_amount']==32130 for r in rows)
    from repositories.reporting_repo import get_sales_report_data
    report = get_sales_report_data()
    assert abs(sum(p['revenue'] for p in report['products'])-report['total_income']) < .02
    assert report['total_net'] + report['total_vat'] == pytest.approx(report['total_income'])


@pytest.mark.parametrize('change',[{'unit_price[]':['NaN']},{'unit_price[]':['-1']},{'quantity[]':['0']},{'quantity[]':['1.2']},{'discount[]':['101']},{'quantity[]':['1','2']}])
def test_bad_quote_cannot_create_document(auth_client,change):
    marker='BAD-TAX-'+uuid.uuid4().hex[:10]
    pid=create_product(sku=marker,name=marker,product_type='Final',cost=1000)
    assert post_quote(auth_client,marker,pid,**change).status_code==302
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT count(*) AS n FROM sales WHERE customer_name=%s',(marker,))
        assert cur.fetchone()['n']==0


def test_pricing_batch_matches_ppp_including_valuations_and_master_fallback():
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT id FROM products ORDER BY id LIMIT 100')
        ids=[r['id'] for r in cur.fetchall()]
        batch=get_batch_current_ppp(ids,conn=conn)
        assert batch=={pid:get_current_ppp(pid,conn=conn) for pid in ids}


def test_quote_and_price_list_use_the_same_net_cost(auth_client):
    from flask import template_rendered
    from app import app
    marker='COST-PARITY-'+uuid.uuid4().hex[:8]
    pid=create_product(sku=marker,name=marker,product_type='Final',cost=1234)
    contexts=[]
    def capture(sender,template,context,**kwargs):
        contexts.append(context)
    template_rendered.connect(capture,app)
    try:
        assert auth_client.get('/ventas/cotizacion/nueva').status_code==200
        quote=contexts[-1]
        assert auth_client.get('/administracion/listas-precios?search='+marker).status_code==200
        listing=contexts[-1]
        product=next(p for p in listing['products'] if p['id']==pid)
        assert product['vpp']==1234
        for category in product['categories']:
            assert quote['products_prices_map'][str(pid)][category['id']]==category['price_final']
    finally:
        template_rendered.disconnect(capture,app)


def test_cancelled_variants_are_excluded_from_sales_reports(auth_client):
    from repositories.reporting_repo import get_sales_report_data, get_accounts_receivable_report_data
    from repositories.sales_repo import insert_sale
    from datetime import datetime, timezone
    marker='P-VOID-'+uuid.uuid4().hex[:8]
    base=get_sales_report_data()['total_income']
    sid=insert_sale({'sale_number':marker,'customer_name':marker,'sale_date':'2026-10-20','sale_time':'12:00:00','products':[{'quantity':1,'price':10000,'subtotal':10000}],'total_amount':11900,'status':'Anulada','created_at':datetime.now(timezone.utc).isoformat()})
    assert get_sales_report_data()['total_income']==base
    assert not get_accounts_receivable_report_data(search=marker)['items']


def test_missing_cost_is_not_presented_as_a_reliable_zero_cost_margin():
    from repositories.sales_repo import insert_sale
    from datetime import datetime, timezone
    marker='P-NO-COST-'+uuid.uuid4().hex[:8]
    pid=create_product(sku=marker,name=marker,product_type='Final',cost=0)
    sid=insert_sale({'sale_number':marker,'customer_name':marker,'sale_date':'2026-10-20','sale_time':'12:00:00','products':[{'product_id':pid,'quantity':1,'price':10000,'subtotal':10000}],'total_amount':11900,'status':'Pendiente','created_at':datetime.now(timezone.utc).isoformat()})
    financial=get_sale_financial_summary(sid)
    assert financial['cost_status']=='incomplete'
    assert not financial['costs_complete']
