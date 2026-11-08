"""Real PostgreSQL regressions, independent Decimal expectations and concurrency."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as D
import pytest
from test_certification import query,tag,bank,product,purchase,quote,payment,statement,expense,physical

def obligation(client):
    from repositories.purchases_repo import create_purchase_invoice
    from test_certification import supplier
    account=bank()
    i=create_purchase_invoice(dict(supplier_id=supplier(),invoice_number=tag(),invoice_amount=11900,
        invoice_date='2026-10-05',due_date='2026-11-05',bank_account_id=account,payment_status='Pendiente'))
    return i,account

def pay(i,a,amount,key=None,day='2026-10-20'):
    from repositories.finance_repo import register_purchase_payment
    return register_purchase_payment(i,dict(payment_amount=amount,payment_date=day,payment_method='Efectivo',bank_account_id=a,idempotency_key=key or tag()))

def flow(a,start='2026-10-01',end='2026-11-30'):
    from repositories.cash_flow_repo import calculate_cash_flow_consolidation
    return calculate_cash_flow_consolidation(start,end,bank_account_id=a)

@pytest.mark.parametrize('scenario',range(1,11))
def test_repairs_cxp(scenario,client,check):
    """Partial, second, total, overpay, concurrency, retry, recurrent, overdue, invalid, bank."""
    i,a=obligation(client)
    if scenario==1:
        assert pay(i,a,2000);check('saldo parcial',D(query('SELECT invoice_amount-payment_amount b FROM purchase_invoices WHERE id=%s',(i,))[0]['b']),D(9900))
    elif scenario==2:
        assert pay(i,a,2000);assert pay(i,a,3900);check('segundo saldo',D(query('SELECT payment_amount p FROM purchase_invoices WHERE id=%s',(i,))[0]['p']),D(5900))
    elif scenario==3:
        assert pay(i,a,2000);assert pay(i,a,9900);check('cerrada',query('SELECT payment_status s FROM purchase_invoices WHERE id=%s',(i,))[0]['s'],'Pagada')
    elif scenario==4:
        assert not pay(i,a,11901);check('sobrepago sin escritura',query('SELECT count(*) n FROM purchase_payment_items WHERE invoice_id=%s',(i,))[0]['n'],0)
    elif scenario==5:
        with ThreadPoolExecutor(2) as pool: result=list(pool.map(lambda _:pay(i,a,7000),range(2)))
        check('concurrencia un ganador',sum(result),1);check('concurrencia importe',query('SELECT SUM(payment_amount) p FROM purchase_payment_items WHERE invoice_id=%s',(i,))[0]['p'],D(7000))
    elif scenario==6:
        key=tag();assert pay(i,a,2000,key);assert pay(i,a,2000,key);assert not pay(i,a,3000,key)
        check('reintento único',query('SELECT count(*) n FROM purchase_payment_items WHERE invoice_id=%s',(i,))[0]['n'],1)
    elif scenario==7:
        from repositories.operational_expenses_repo import materialize_next_occurrence,update_operational_expense_occurrence,get_operational_expense
        e=expense(account=a);occ=materialize_next_occurrence(e,1,override_due_date='2026-10-05')
        assert update_operational_expense_occurrence(occ,dict(amount=11900,status='Pagado',payment_amount=11900,paid_date='2026-10-20',bank_account_id=a),1)
        check('gasto real único',flow(a)['kpis']['real_outflows'],D(11900));check('regla intacta',get_operational_expense(e)['amount'],D(11900))
    elif scenario==8:
        query("UPDATE purchase_invoices SET due_date='2026-09-01' WHERE id=%s",(i,));assert pay(i,a,2000)
        check('abono vencido mantiene vencimiento',query('SELECT payment_status s FROM purchase_invoices WHERE id=%s',(i,))[0]['s'],'Vencida')
    elif scenario==9:
        for bad in ['NaN','Infinity','-1','0','0.001','no-numero']: assert not pay(i,a,bad)
        check('invalidos sin escritura',query('SELECT count(*) n FROM purchase_payment_items WHERE invoice_id=%s',(i,))[0]['n'],0)
    else:
        from repositories.bank_reconciliation_repo import reconcile_transaction
        assert pay(i,a,2000);p=query('SELECT id FROM purchase_payment_items WHERE invoice_id=%s',(i,))[0]['id'];tx,_=statement(a,-2000)
        assert reconcile_transaction(tx['id'],'PURCHASE_PAYMENT_ITEM',p,'CERT')[0]
        check('banco sin duplicar abono',flow(a)['kpis']['real_outflows'],D(2000))

@pytest.mark.parametrize('scenario',range(1,11))
def test_repairs_flow(scenario,client,check):
    """Pending, partial, full, reconciled, recurrence projection/materialization, transfer, dates, month."""
    i,a=obligation(client)
    if scenario==1: check('compromiso original',flow(a)['kpis']['projected_outflows'],D(11900))
    elif scenario in (2,3,4,10):
        amount=11900 if scenario==3 else 2000;assert pay(i,a,amount)
        if scenario==4:
            from repositories.bank_reconciliation_repo import reconcile_transaction
            p=query('SELECT id FROM purchase_payment_items WHERE invoice_id=%s',(i,))[0]['id'];t,_=statement(a,-amount);assert reconcile_transaction(t['id'],'PURCHASE_PAYMENT_ITEM',p,'CERT')[0]
        k=flow(a)['kpis'];check('real sólo pagado',k['real_outflows'],D(amount));check('pendiente sólo saldo',k['projected_outflows'],D(11900-amount))
    elif scenario in (5,6):
        from repositories.operational_expenses_repo import materialize_next_occurrence
        e=expense(account=a)
        if scenario==6: materialize_next_occurrence(e,1,override_due_date='2026-11-05',override_amount=15000)
        check('precedencia gasto período',flow(a,'2026-11-01','2026-11-30')['kpis']['projected_outflows'],D(11900+(15000 if scenario==6 else 11900)))
    elif scenario==7:
        from repositories.bank_reconciliation_repo import reconcile_transaction
        b=bank();t,_=statement(a,-5000);u,_=statement(b,5000);assert reconcile_transaction(t['id'],'INTERNAL_TRANSFER',u['id'],'CERT')[0]
        check('transferencia neutra',flow(a)['kpis']['real_outflows']-flow(b)['kpis']['real_inflows'],D(0))
    elif scenario==8:
        assert pay(i,a,2000,day='2026-11-20');check('pago futuro no efectivo octubre',flow(a,'2026-10-01','2026-10-31')['kpis']['real_outflows'],D(0));check('pago noviembre',flow(a,'2026-11-01','2026-11-30')['kpis']['real_outflows'],D(2000))
    elif scenario==9:
        query("UPDATE purchase_invoices SET due_date='2026-10-01' WHERE id=%s",(i,));check('vencido conserva saldo',flow(a)['kpis']['projected_outflows'],D(11900))

@pytest.mark.parametrize('scenario',range(1,11))
def test_repairs_reconciliation(scenario,client,check):
    """Exact, one peso, large, duplicate, partial, full, retry, race, reversal, balance."""
    from repositories.bank_reconciliation_repo import reconcile_transaction,unreconcile_transaction
    a=bank();s=quote(client,product(),1,10000,0,convert=True);amount=2000 if scenario==5 else 11900
    item=payment(client,s['id'],amount,account=a)[0];tx,_=statement(a,11901 if scenario==2 else 15000 if scenario==3 else amount)
    if scenario==8:
        second,_=statement(a,amount)
        with ThreadPoolExecutor(2) as pool: result=list(pool.map(lambda t:reconcile_transaction(t,'SALE_PAYMENT',item['id'],'CERT')[0],[tx['id'],second['id']]))
        check('destino único concurrente',sum(result),1)
    else:
        ok,msg=reconcile_transaction(tx['id'],'SALE_PAYMENT',item['id'],'CERT');check('igualdad estricta',ok,scenario not in (2,3))
        if scenario in (4,7):check('duplicado rechazado',reconcile_transaction(tx['id'],'SALE_PAYMENT',item['id'],'CERT')[0],False)
        if scenario==9:
            assert unreconcile_transaction(tx['id'],'CERT')[0];check('pago conservado',query('SELECT payment_amount p FROM sale_payment_items WHERE id=%s',(item['id'],))[0]['p'],D(amount))
        if scenario==10:check('sin doble ingreso',flow(a)['kpis']['real_inflows'],D(amount))
    check('no crea pagos',query('SELECT count(*) n FROM sale_payment_items WHERE sale_id=%s',(s['id'],))[0]['n'],1)

@pytest.mark.parametrize('scenario',range(1,11))
def test_repairs_production(scenario,client,check,monkeypatch):
    """Normal, missing, FIFO/PPP, partial, retry, late rollback, concurrency, canceled, ledger."""
    from repositories.production_repo import create_production_order
    from services.operario_service import OperarioService as O
    raw=product(raw=True,lot=True);pt=product(cost=0,lot=True);lot=tag();purchase(raw,10,1000,lot=lot,receive=True)
    oid,_=create_production_order(pt,4,status='Aprobada',items=[{'input_product_id':raw,'quantity_required':1}])
    if scenario==2:
        ok,_,_=O.finalize_production(oid,4,tag());check('sin consumos bloqueada',ok,False);check('sin entrada fantasma',physical(pt),D(0));return
    if scenario==9:
        query("UPDATE production_orders SET status='Cancelada' WHERE id=%s",(oid,));assert not O.finalize_production(oid,4,tag())[0];check('cancelada sin entrada',physical(pt),D(0));return
    qty=2 if scenario==5 else 4
    assert O.validate_and_record_consumption(oid,raw,lot,qty)[0]
    if scenario==8:
        with ThreadPoolExecutor(2) as pool: result=list(pool.map(lambda _:O.finalize_production(oid,qty,tag())[0],range(2)))
        check('finalización concurrente única',sum(result),1)
    elif scenario==7:
        # PostgreSQL fault after the output-lot INSERT, without mocking persistence.
        query("""CREATE OR REPLACE FUNCTION cert_output_fault() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.production_order_id="""+str(oid)+""" THEN RAISE EXCEPTION 'CERT injected intermediate failure'; END IF; RETURN NEW; END $$""")
        query("CREATE TRIGGER cert_output_fault BEFORE INSERT ON production_lot_outputs FOR EACH ROW EXECUTE FUNCTION cert_output_fault()")
        before=query('SELECT count(*) n FROM lots')[0]['n']
        with pytest.raises(Exception,match='CERT injected intermediate failure'):O.finalize_production(oid,qty,tag())
        query('DROP TRIGGER cert_output_fault ON production_lot_outputs')
        query('DROP FUNCTION cert_output_fault()')
        check('rollback lotes',query('SELECT count(*) n FROM lots')[0]['n'],before)
        check('rollback output',physical(pt),D(0));return
    else:
        assert O.finalize_production(oid,qty,tag())[0]
        if scenario==6:assert not O.finalize_production(oid,qty,tag())[0]
    check('salida legítima',physical(pt),D(qty));check('costo PPP transferido',query('SELECT unit_cost c FROM production_orders WHERE id=%s',(oid,))[0]['c'],D(1000))
    check('MP remanente',physical(raw),D(10-qty));check('entrada única',query("SELECT count(*) n FROM inventory_movements WHERE reference_type='production_order' AND reference_id=%s AND movement_type='PRODUCTION_OUTPUT'",(oid,))[0]['n'],1)

@pytest.mark.parametrize('scenario',range(1,7))
def test_repairs_expense_partial(scenario,client,check):
    from repositories.operational_expenses_repo import materialize_next_occurrence,update_operational_expense_occurrence as update
    a=bank();e=expense(account=a);o=materialize_next_occurrence(e,1,override_due_date='2026-10-05')
    def apply(amount,key=None):return update(o,dict(status='Pagado',payment_amount=amount,paid_date='2026-10-20',bank_account_id=a,idempotency_key=key or tag()),1)
    if scenario==1:
        assert apply(2000);check('gasto saldo parcial',flow(a,'2026-10-01','2026-10-31')['kpis']['projected_outflows'],D(9900));check('gasto egreso real',flow(a,'2026-10-01','2026-10-31')['kpis']['real_outflows'],D(2000))
    elif scenario==2:
        assert apply(2000);assert apply(9900);check('gasto cerrado',query('SELECT status s FROM operational_expense_occurrences WHERE id=%s',(o,))[0]['s'],'Pagado')
    elif scenario==3:
        assert not apply(11901);check('gasto sobrepago sin escritura',query('SELECT count(*) n FROM expense_payment_items WHERE occurrence_id=%s',(o,))[0]['n'],0)
    elif scenario==4:
        with ThreadPoolExecutor(2) as pool:r=list(pool.map(lambda _:apply(7000),range(2)))
        check('gasto concurrente único',sum(r),1)
    elif scenario==5:
        k=tag();assert apply(2000,k);assert apply(2000,k);check('gasto reintento único',query('SELECT count(*) n FROM expense_payment_items WHERE occurrence_id=%s',(o,))[0]['n'],1)
    else:
        from repositories.bank_reconciliation_repo import reconcile_transaction
        assert apply(2000);p=query('SELECT id FROM expense_payment_items WHERE occurrence_id=%s',(o,))[0]['id'];t,_=statement(a,-2000)
        assert reconcile_transaction(t['id'],'EXPENSE_PAYMENT_ITEM',p,'CERT')[0];check('gasto conciliado único',flow(a,'2026-10-01','2026-10-31')['kpis']['real_outflows'],D(2000))

@pytest.mark.parametrize('source',['purchase','expense'])
def test_repairs_legacy_partial_preserved(source,client,check):
    from repositories.bank_reconciliation_repo import reconcile_transaction
    a=bank()
    if source=='purchase':
        i,a=obligation(client)
        query("UPDATE purchase_invoices SET payment_amount=2000,payment_date='2026-10-10',bank_account_id=%s,payment_status='Pendiente' WHERE id=%s",(a,i))
        assert pay(i,a,3900,day='2026-10-20')
        events=query('SELECT * FROM purchase_payment_events WHERE invoice_id=%s ORDER BY payment_date',(i,))
        check('snapshot inicial preservado',events[0]['payment_amount'],D(2000));check('nuevo abono',events[1]['payment_amount'],D(3900))
        t,_=statement(a,-2000,'2026-10-10');assert reconcile_transaction(t['id'],'PURCHASE_PAYMENT',i,'CERT')[0]
    else:
        from repositories.operational_expenses_repo import materialize_next_occurrence,update_operational_expense_occurrence
        e=expense(account=a);i=materialize_next_occurrence(e,1,override_due_date='2026-10-05')
        query("UPDATE operational_expense_occurrences SET payment_amount=2000,paid_date='2026-10-10',bank_account_id=%s WHERE id=%s",(a,i))
        assert update_operational_expense_occurrence(i,dict(status='Pagado',payment_amount=3900,paid_date='2026-10-20',bank_account_id=a,idempotency_key=tag()),1)
        events=query('SELECT * FROM expense_payment_events WHERE occurrence_id=%s ORDER BY paid_date',(i,))
        check('snapshot inicial preservado',events[0]['payment_amount'],D(2000));check('nuevo abono',events[1]['payment_amount'],D(3900))
        t,_=statement(a,-2000,'2026-10-10');assert reconcile_transaction(t['id'],'EXPENSE',i,'CERT')[0]
    check('parciales reales sin duplicar',flow(a,'2026-10-01','2026-10-31')['kpis']['real_outflows'],D(5900))

@pytest.mark.parametrize('scenario',['paid_edit','history','no_bank','empty_plan','missing_cost','document_retry'])
def test_repairs_integrity_edges(scenario,client,check):
    if scenario in ('paid_edit','history','no_bank'):
        i,a=obligation(client)
        if scenario=='no_bank':
            from repositories.finance_repo import register_purchase_payment
            assert not register_purchase_payment(i,dict(payment_amount=1000,payment_date='2026-10-20',payment_method='Transferencia'))
            check('sin cuenta sin escritura',query('SELECT count(*) n FROM purchase_payment_items WHERE invoice_id=%s',(i,))[0]['n'],0)
        elif scenario=='paid_edit':
            assert pay(i,a,5900)
            client.post(f'/compras/facturas/{i}/editar',data=dict(invoice_amount='1000',due_date='2026-11-05',invoice_number=tag()))
            check('no reducir debajo de abonos',query('SELECT invoice_amount a FROM purchase_invoices WHERE id=%s',(i,))[0]['a'],D(11900))
        else:
            assert pay(i,a,2000);assert pay(i,a,9900,day='2026-10-21')
            response=client.get(f'/compras/facturas/{i}/pagos');check('historial accesible',response.status_code,200)
            assert '2,000.00' in response.text and '9,900.00' in response.text
            check('histórico conserva dos pagos',query('SELECT count(*) n FROM purchase_payment_events WHERE invoice_id=%s',(i,))[0]['n'],2)
    elif scenario=='document_retry':
        from repositories.operational_expenses_repo import materialize_next_occurrence,update_operational_expense_occurrence as update
        a=bank();e=expense(account=a);o=materialize_next_occurrence(e,1,override_due_date='2026-10-05')
        data=dict(status='Pagado',payment_amount=11900,paid_date='2026-10-20',bank_account_id=a,idempotency_key=tag())
        assert update(o,data,1);assert update(o,{**data,'document_file':'CERT/nuevo-adjunto.pdf'},1)
        check('reintento conserva nuevo adjunto',query('SELECT document_file f FROM operational_expense_occurrences WHERE id=%s',(o,))[0]['f'],'CERT/nuevo-adjunto.pdf')
        check('adjunto no duplica pago',query('SELECT count(*) n FROM expense_payment_items WHERE occurrence_id=%s',(o,))[0]['n'],1)
    else:
        from repositories.production_repo import create_production_order
        from services.operario_service import OperarioService as O
        pt=product(cost=0,lot=True);raw=product(cost=0,raw=True,lot=True);lot=tag()
        o,_=create_production_order(pt,1,status='Aprobada',items=[] if scenario=='empty_plan' else [{'input_product_id':raw,'quantity_required':1}])
        if scenario=='missing_cost':purchase(raw,1,0,lot=lot,receive=True);assert O.validate_and_record_consumption(o,raw,lot,1)[0]
        assert not O.finalize_production(o,1,tag())[0]
        check('no genera stock sin respaldo',physical(pt),D(0))

@pytest.mark.parametrize('invalid',['currency','account','sign','unapproved'])
def test_repairs_reconciliation_identity(invalid,client,check):
    from repositories.bank_reconciliation_repo import reconcile_transaction
    a=bank();s=quote(client,product(),1,10000,0,convert=True);item=payment(client,s['id'],11900,account=a)[0]
    t,_=statement(bank() if invalid=='account' else a,-11900 if invalid=='sign' else 11900)
    if invalid=='currency':query("UPDATE bank_transactions SET currency='USD' WHERE id=%s",(t['id'],))
    if invalid=='unapproved':query('UPDATE sale_payment_items SET accounting_approved=0 WHERE id=%s',(item['id'],))
    check('identidad bancaria inválida rechazada',reconcile_transaction(t['id'],'SALE_PAYMENT',item['id'],'CERT')[0],False)
    check('sin vinculo parcial',query('SELECT reconciliation_status s FROM bank_transactions WHERE id=%s',(t['id'],))[0]['s'],'PENDIENTE')

@pytest.mark.parametrize('amount',['11900','0','-1','NaN','Infinity'])
def test_repairs_invoice_creation(amount,client,check):
    from test_certification import supplier
    a=bank();doc=tag()
    client.post('/compras/facturas/nueva',data=dict(supplier_id=supplier(),invoice_number=doc,invoice_amount=amount,
        invoice_date='2026-10-05',due_date='2026-11-05',payment_status='Pagada',payment_date='2026-10-20',payment_method='Transferencia bancaria',bank_account_id=a))
    rows=query('SELECT * FROM purchase_invoices WHERE invoice_number=%s',(doc,))
    if amount!='11900':check('importe inválido sin obligación',len(rows),0)
    else:
        check('factura pagada persiste',rows[0]['payment_status'],'Pagada')
        check('factura pagada tiene abono',query('SELECT SUM(payment_amount) p FROM purchase_payment_items WHERE invoice_id=%s',(rows[0]['id'],))[0]['p'],D(11900))
