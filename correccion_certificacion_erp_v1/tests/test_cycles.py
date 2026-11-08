import io,json,os,shutil
from pathlib import Path
import pytest
from decimal import Decimal
from reference import invoice,D
from test_certification import product,purchase,quote,prepare,payment,physical,bank,statement,expense,debt,query,tag

@pytest.mark.parametrize('cycle',[1,2,3,4,5])
def test_complete_business_cycle(cycle,client,check):
    """Ciclo empresarial independiente con oráculo Decimal y comprobaciones entre módulos."""
    from repositories.bank_reconciliation_repo import reconcile_transaction
    from repositories.cash_flow_repo import calculate_cash_flow_consolidation
    from repositories.sales_repo import get_sale_financial_summary
    if cycle==1:
        account=bank();statement(account,1000000,'2026-09-30')
        pid=product(lot=True);po,entry=purchase(pid,10,1000,lot=tag(),receive=True,client=client)
        inv=query('SELECT * FROM purchase_invoices WHERE inventory_entry_id=%s',(entry,))[0]
        check('C1 compra bruta',inv['invoice_amount'],D(11900))
        sale=quote(client,pid,3,10000,10,convert=True);check('C1 reserva sin salida',physical(pid),D(10))
        prepare(client,sale['id']);prepare(client,sale['id'],'Para Despacho')
        client.post('/ventas/actualizar-estado',data={'sale_id':sale['id'],'status':'Completada','invoice_number':tag(),'invoice_file':(io.BytesIO(b'%PDF-1.4 CERT factura sintetica'),'cert.pdf')},content_type='multipart/form-data')
        check('C1 stock final',physical(pid),D(7));check('C1 estado despachado',query('SELECT status FROM sales WHERE id=%s',(sale['id'],))[0]['status'],'Completada')
        fin=get_sale_financial_summary(sale['id']);check('C1 neto',fin['neto'],D(27000));check('C1 IVA',fin['iva'],D(5130));check('C1 costo vendido',fin['products_cost'],D(3000));check('C1 utilidad',fin['real_margin'],D(24000))
        pays=payment(client,sale['id'],32130,account=account);check('C1 cobro íntegro',sum(D(p['payment_amount']) for p in pays),D(32130))
        tx,_=statement(account,32130);check('C1 conciliación',reconcile_transaction(tx['id'],'SALE_PAYMENT',pays[0]['id'],'CERT')[0],True)
        cash=calculate_cash_flow_consolidation('2026-10-01','2026-10-31',bank_account_id=account)
        check('C1 ingreso único',cash['kpis']['real_inflows'],D(32130));check('C1 banco final',cash['kpis']['current_balance'],D(1032130))
    elif cycle==2:
        from repositories.production_repo import create_production_order
        raw=product(lot=True,raw=True);finished=product(lot=True,cost=0)
        purchase(raw,10,1000,lot=tag(),receive=True,client=client);purchase(raw,10,1500,lot=tag(),receive=True,client=client)
        client.post('/produccion/recetas/nueva',data={'final_product_id':finished,'recipe_code':tag(),'input_product_id[]':[raw],'quantity_required[]':['1'],'unit[]':['UN']})
        check('C2 receta persiste',query('SELECT count(*) n FROM product_recipes WHERE final_product_id=%s',(finished,))[0]['n'],1)
        ot,_=create_production_order(finished,15,status='Aprobada',items=[{'input_product_id':raw,'quantity_required':1}])
        client.post(f'/produccion/ot/{ot}/finalizar',data={'output_lot_number':tag()})
        check('C2 MP remanente',physical(raw),D(5));check('C2 PT fabricado',physical(finished),D(15))
        row=query('SELECT unit_cost FROM production_orders WHERE id=%s',(ot,))[0]
        check('C2 costo unitario',row['unit_cost'],D(1250));check('C2 valor transferido',D(row['unit_cost'])*15,D(18750))
        sale=quote(client,finished,5,2500,0,convert=True);prepare(client,sale['id'])
        fin=get_sale_financial_summary(sale['id']);check('C2 costo vendido',fin['products_cost'],D(6250));check('C2 utilidad neta',fin['real_margin'],D(6250));check('C2 IVA',fin['iva'],D(2375));check('C2 PT final',physical(finished),D(10))
    elif cycle==3:
        from repositories.operational_expenses_repo import materialize_next_occurrence,update_operational_expense_occurrence,get_operational_expense
        account=bank();statement(account,1000000,'2026-09-30');rule=expense(11900,account)
        o1=materialize_next_occurrence(rule,1,override_due_date='2026-10-05');o2=materialize_next_occurrence(rule,1,override_due_date='2026-11-05')
        for oid,amount,day in [(o1,14280,'2026-10-20'),(o2,17850,'2026-11-20')]:
            update_operational_expense_occurrence(oid,{'amount':amount,'invoice_number':tag(),'document_file':'CERT/factura-sintetica.pdf','status':'Pagado','paid_date':day,'payment_amount':amount,'bank_account_id':account},1)
            from reportlab.pdfgen import canvas
            document=io.BytesIO();pdf=canvas.Canvas(document);pdf.drawString(40,800,'CERT Factura ficticia de gasto '+day);pdf.drawString(40,780,'Total con IVA: '+str(amount));pdf.save();document.seek(0)
            client.post(f'/administracion/gastos-operacionales/ocurrencias/{oid}/editar',data={'amount':str(amount),'invoice_number':tag(),'invoice_date':day,'mark_as_paid':'1','paid_date':day,'payment_amount':str(amount),'bank_account_id':account,'document_file':(document,'cert-factura.pdf')},content_type='multipart/form-data')
            stored=query('SELECT document_file FROM operational_expense_occurrences WHERE id=%s',(oid,))[0]['document_file']
            path=Path(os.environ['CERTIFICATION_WORK'])/'uploads'/stored
            check('C3 adjunto físico '+day,path.is_file(),True)
            check('C3 PDF registrado '+day,path.read_bytes()[:4],b'%PDF')
            shutil.copy2(path,Path(os.environ['CERTIFICATION_OUT'])/'evidencia'/('E2E-gasto-'+day+'.pdf'))
            tx,_=statement(account,-amount,day);check('C3 conciliación gasto '+day,reconcile_transaction(tx['id'],'EXPENSE',oid,'CERT')[0],True)
        check('C3 regla recurrente inmutable',get_operational_expense(rule)['amount'],D(11900))
        cash=calculate_cash_flow_consolidation('2026-10-01','2026-11-30',bank_account_id=account,filter_type='real')
        check('C3 egresos únicos',cash['kpis']['real_outflows'],D(14280+17850));check('C3 saldo final',cash['kpis']['current_balance'],D(967870))
    elif cycle==4:
        pid=product();purchase(pid,10,1000,receive=True,client=client)
        a=quote(client,pid,8,2000,0,convert=True);b=quote(client,pid,5,2000,0,convert=True)
        from services.stock_context import get_operational_balance
        sku=query('SELECT sku FROM products WHERE id=%s',(pid,))[0]['sku'];balance=get_operational_balance(sku)
        check('C4 reserva mayor al físico',balance['reserved_stock'],D(13));check('C4 disponible cero',balance['available_stock'],D(0))
        prepare(client,b['id']);check('C4 operador elige B',physical(pid),D(5))
        prepare(client,a['id']);check('C4 A bloqueada',query('SELECT status FROM sales WHERE id=%s',(a['id'],))[0]['status'],'Pendiente')
        check('C4 no segunda salida',physical(pid),D(5))
    else:
        from repositories.debts_repo import list_debt_installments,register_debt_installment_payment
        from repositories.operational_expenses_repo import materialize_next_occurrence,update_operational_expense_occurrence
        account=bank();other=bank();statement(account,1000000,'2026-09-30')
        did=debt(300000,account);inst=list_debt_installments(did)[0]
        ok,msg,payid=register_debt_installment_payment(inst['id'],50000,'2026-10-20',bank_account_id=account)
        check('C5 cuota parcial',ok,True);tx,_=statement(account,-50000);check('C5 conciliar cuota',reconcile_transaction(tx['id'],'DEBT_PAYMENT',payid,'CERT')[0],True)
        rule=expense(11900,account);oid=materialize_next_occurrence(rule,1,override_due_date='2026-10-05')
        update_operational_expense_occurrence(oid,{'amount':11900,'status':'Pagado','paid_date':'2026-10-20','payment_amount':11900,'bank_account_id':account},1)
        tx,_=statement(account,-11900);check('C5 conciliar gasto',reconcile_transaction(tx['id'],'EXPENSE',oid,'CERT')[0],True)
        po,entry=purchase(product(),10,1000,receive=True,client=client);inv=query('SELECT id FROM purchase_invoices WHERE inventory_entry_id=%s',(entry,))[0]['id']
        client.post(f'/compras/facturas/{inv}/registrar-pago',data={'payment_amount':'11900','payment_date':'2026-10-20','payment_method':'Transferencia bancaria','bank_account_id':account})
        tx,_=statement(account,-11900);check('C5 conciliar compra',reconcile_transaction(tx['id'],'PURCHASE_PAYMENT',inv,'CERT')[0],True)
        sale=quote(client,product(),1,10000,0,convert=True);pays=payment(client,sale['id'],11900,account=account)
        tx,_=statement(account,11900);check('C5 conciliar cobro',reconcile_transaction(tx['id'],'SALE_PAYMENT',pays[0]['id'],'CERT')[0],True)
        out,_=statement(account,-100000);inc,_=statement(other,100000)
        check('C5 transferencia interna',reconcile_transaction(out['id'],'INTERNAL_TRANSFER',inc['id'],'CERT')[0],True)
        # Per-account balances and consolidation cannot be inferred from HTTP success.
        cash=calculate_cash_flow_consolidation('2026-10-01','2026-10-31',bank_account_id=account,filter_type='real')
        check('C5 saldo cuenta origen',cash['kpis']['current_balance'],D(838100))
