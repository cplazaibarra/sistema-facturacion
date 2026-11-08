"""Independent business certification. All mutations target synthetic ephemeral data."""
import io,json,os,uuid
from datetime import date,datetime,timezone
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
import pytest
from reference import invoice,ppp,D
from core.database import get_connection

FEATURES=['productos','proveedores','clientes','ordenes_compra','recepcion','inventario','ppp_fifo','cotizaciones','ventas','despacho','recetas','produccion','cxc','cxp','gastos','deudas','bancos','conciliacion','flujo_caja','reportes','seguridad','ajustes','embalajes','precios','trazabilidad']
FEATURES+=['operario','agenda','excel_productos','excel_bancos','excel_deudas','usuarios_roles','informacion_empresa']
def query(q,args=()):
    with get_connection() as c,c.cursor() as cur:
        cur.execute(q,args)
        rows=cur.fetchall() if cur.description else []
        c.commit()
        return [dict(r) for r in rows]
def tag():return 'CERT-'+uuid.uuid4().hex[:12]
def product(cost=1000,lot=False,raw=False):
    from repositories.products_repo import create_product
    t=tag();return create_product(sku=t,name=t,product_type='Insumo' if raw else 'Final',cost=cost,requires_lot=lot)
def supplier():
    from repositories.suppliers_repo import insert_supplier
    t=tag();return insert_supplier({'name':t,'rut':str(93000000+int(uuid.uuid4().hex[:5],16)%1000000),'email':t+'@cert.invalid','default_payment_terms':'NET_30'})
def bank():
    from db import insert_bank_account
    t=tag();return insert_bank_account({'bank_name':t,'account_number':t,'account_type':'Cuenta Corriente','holder_name':'CERT Empresa Ficticia','status':'Activa'})
def purchase(pid,qty,cost,lot='',receive=False,client=None):
    from repositories.purchases_repo import create_purchase_order
    from repositories.inventory_repo import register_inventory_entry
    items=[{'product_id':pid,'quantity':qty,'unit_price':cost,'lot_number':lot}]
    number=create_purchase_order(supplier(),'2026-10-05',tag(),items)
    po=query('SELECT * FROM purchase_orders WHERE oc_number=%s',(number,))[0]
    if receive:
        if client:
            doc=tag();client.post('/ingreso-mercaderia',data={'purchase_order_id':po['id'],'order_number':tag(),'document_type':'factura','document_number':doc,'due_date':'2026-11-05','warehouse':'Principal','ingreso_date':'2026-10-05','product_id[]':[str(pid)],'quantity[]':[str(qty)],'unit_price[]':[str(cost)],'lot_number[]':[lot]})
            entry=query('SELECT id FROM inventory_entries WHERE document_number=%s',(doc,))[0]['id']
        else:
            entry=register_inventory_entry(po['id'],tag(),'2026-10-05','Principal',tag(),items)
        return po,entry
    return po
def physical(pid):
    from repositories.inventory_repo import get_product_physical_stock
    return get_product_physical_stock(pid)
def quote(client,pid,qty=3,price=10000,discount=10,convert=False,customer=None):
    name=customer['razon_social'] if customer else tag();client.post('/ventas/cotizacion/nueva',data={'customer_name':name,'customer_email':customer['email'] if customer else name+'@cert.invalid','customer_id':str(customer['id']) if customer else '', 'customer_rut':customer['rut'] if customer else '', 'customer_category':'cat_0','sale_date':'2026-10-20','status':'Cotización','quotation_status':'Activa','product_id[]':[str(pid)],'quantity[]':[str(qty)],'unit_price[]':[str(price)],'discount[]':[str(discount)]})
    row=query('SELECT * FROM sales WHERE customer_name=%s ORDER BY id',(name,))[0]
    if convert:
        client.post(f'/ventas/cotizacion/{row["id"]}/convertir')
        row=query("SELECT * FROM sales WHERE customer_name=%s AND status='Pendiente' ORDER BY id DESC",(name,))[0]
    return row
def prepare(client,sid,status='En Preparación'):
    return client.post('/ventas/actualizar-estado',data={'sale_id':sid,'status':status})
def payment(client,sid,amount,account=None,key=None):
    data={'sale_id':sid,'payment_amount':str(amount),'payment_date':'2026-10-20','payment_method':'Transferencia' if account else 'Efectivo','idempotency_key':key or tag()}
    if account:data.update(bank_account_id=str(account),payment_file=(io.BytesIO(b'%PDF-1.4 CERT synthetic payment'),'cert.pdf'))
    client.post('/ventas/registrar-pago',data=data,content_type='multipart/form-data')
    return query('SELECT * FROM sale_payment_items WHERE sale_id=%s ORDER BY id',(sid,))
def statement(account,amount,day='2026-10-20',fingerprint=None):
    from repositories.bank_reconciliation_repo import insert_bank_transactions_bulk,generate_transaction_fingerprint
    description=tag();amount=D(amount);kind='ABONO' if amount>=0 else 'CARGO'
    fp=fingerprint or generate_transaction_fingerprint(account,day,None,amount,kind,None,None,description)
    tx={'transaction_date':day,'description':description,'charge':max(-amount,D(0)),'credit':max(amount,D(0)),'amount':amount,'movement_type':kind,'fingerprint':fp,'currency':'CLP'}
    inserted=insert_bank_transactions_bulk([tx],None,account)
    return query('SELECT * FROM bank_transactions WHERE fingerprint=%s',(fp,))[0],inserted
def expense(amount=11900,account=None):
    from repositories.operational_expenses_repo import create_operational_expense
    cats=query('SELECT id FROM expense_categories ORDER BY id LIMIT 1')
    if not cats:cats=query("INSERT INTO expense_categories(name) VALUES ('CERT Gastos') RETURNING id")
    return create_operational_expense({'name':tag(),'category_id':cats[0]['id'],'amount':amount,'amount_type':'Fijo','frequency':'Mensual','start_date':'2026-10-01','due_rule':'Día del mes','due_day':5,'bank_account_id':account,'status':'Activo','tax_condition':'IVA incluido'},1)
def debt(amount=100001,account=None):
    from repositories.debts_repo import create_debt_with_schedule
    typ=query('SELECT id FROM debt_types WHERE active=TRUE ORDER BY id LIMIT 1') if False else query('SELECT id FROM debt_types ORDER BY id LIMIT 1')
    ok,msg,did=create_debt_with_schedule(name=tag(),debt_type_id=typ[0]['id'],creditor_name='CERT Acreedor',original_amount=amount,start_date='2026-10-01',installments_count=3,first_due_date='2026-10-05',bank_account_id=account)
    assert ok,msg
    return did

@pytest.mark.parametrize('feature',FEATURES)
@pytest.mark.parametrize('variant',[1,2,3,4,5])
def test_business_feature(feature,variant,client,check):
    """Normal, alternativa, límite/validación, integración y repetición/reversa con datos propios."""
    v=variant
    if feature=='productos':
        from repositories.products_repo import create_product,update_product
        pid=product(cost=1234+v,lot=v==2,raw=v==3)
        row=query('SELECT * FROM products WHERE id=%s',(pid,))[0]
        check('costo persistido',row['cost'],D(1234+v));check('sin stock creado',physical(pid),D(0))
        if v==4:
            try:create_product(sku=row['sku'],name='Duplicado CERT',cost=1)
            except Exception:pass
            check('SKU único',query('SELECT count(*) n FROM products WHERE sku=%s',(row['sku'],))[0]['n'],1)
        if v==5:
            purchase(pid,5,1000,receive=True);before=query('SELECT id,quantity,unit_cost FROM inventory_movements WHERE product_id=%s',(pid,))
            update_product(pid,{**row,'name':'CERT Editado','cost':9999})
            check('historial inmutable',query('SELECT id,quantity,unit_cost FROM inventory_movements WHERE product_id=%s',(pid,)),before)
    elif feature=='proveedores':
        from repositories.suppliers_repo import insert_supplier,update_supplier
        sid=supplier();row=query('SELECT * FROM suppliers WHERE id=%s',(sid,))[0]
        check('proveedor persiste',row['default_payment_terms'],'NET_30')
        if v==3:
            response=client.post('/api/proveedores/crear',json={'name':''})
            check('nombre obligatorio',response.status_code in [400,422],True)
        if v>=4:
            from repositories.purchases_repo import create_purchase_order
            num=create_purchase_order(sid,'2026-10-05',tag(),[{'product_id':product(),'quantity':v,'unit_price':1000}])
            update_supplier(sid,{**row,'name':'CERT Proveedor editado'})
            check('relación OC',query('SELECT supplier_id FROM purchase_orders WHERE oc_number=%s',(num,))[0]['supplier_id'],sid)
    elif feature=='clientes':
        from repositories.clients_repo import insert_client,update_client
        t=tag();data={'rut':str(95000000+int(uuid.uuid4().hex[:5],16)%1000000),'dv':'K','razon_social':t,'email':t+'@cert.invalid','delivery_address':'CERT Dirección original'}
        cid=insert_client(data);check('cliente persiste',query('SELECT razon_social FROM clients WHERE id=%s',(cid,))[0]['razon_social'],t)
        if v==3:
            response=client.post('/ventas/clientes/guardar_modal',data={'razon_social':t,'email':'correo-invalido','rut':data['rut']},follow_redirects=True)
            check('correo inválido no persistido',query('SELECT email FROM clients WHERE id=%s',(cid,))[0]['email'],data['email'])
        if v>=4:
            sid=quote(client,product(),customer={**data,'id':cid})['id'];original=query('SELECT total_amount,products_json,customer_delivery_address FROM sales WHERE id=%s',(sid,))[0]
            update_client(cid,{**data,'delivery_address':'CERT Dirección nueva'})
            check('documento histórico',query('SELECT total_amount,products_json,customer_delivery_address FROM sales WHERE id=%s',(sid,))[0],original)
        if v==5:check('RUT no duplica',insert_client(data),cid)
    elif feature=='ordenes_compra':
        pid=product();qty=v+2;cost=1000+v*125
        before=physical(pid);po=purchase(pid,qty,cost)
        check('OC neta',po['total_amount'],D(qty)*D(cost));check('OC no crea stock',physical(pid),D(before))
        if v==3:
            import psycopg2
            with pytest.raises((ValueError,psycopg2.IntegrityError)):
                purchase(product(),-1,1000)
            check('cantidad inválida no persistida',query('SELECT count(*) n FROM purchase_order_items WHERE quantity_ordered<0')[0]['n'],0)
        if v==4:
            from repositories.inventory_repo import register_inventory_entry
            register_inventory_entry(po['id'],tag(),'2026-10-05','Principal','CERT',[{'product_id':pid,'quantity':qty,'unit_price':cost}])
            check('recepción ligada',physical(pid),D(qty))
        if v==5:
            from repositories.purchases_repo import anular_purchase_order
            anular_purchase_order(po['id'],'CERT cancelar')
            check('OC anulada no consume',physical(pid),D(0))
    elif feature=='recepcion':
        pid=product(lot=v==4);qty=v+2;cost=1000+v*75
        po,entry=purchase(pid,qty,cost,lot=tag() if v==4 else '',receive=True,client=client)
        check('stock recibido',physical(pid),D(qty))
        inv=query('SELECT * FROM purchase_invoices WHERE inventory_entry_id=%s',(entry,))[0]
        check('CxP bruta',inv['invoice_amount'],invoice([(qty,cost,0)])['total'])
        if v==2:
            po2=purchase(pid,10,cost)
            from repositories.inventory_repo import register_inventory_entry
            register_inventory_entry(po2['id'],tag(),'2026-10-05','Principal','CERT parcial',[{'product_id':pid,'quantity':3,'unit_price':cost}])
            check('recepción parcial',query('SELECT quantity_received FROM purchase_order_items WHERE purchase_order_id=%s',(po2['id'],))[0]['quantity_received'],D(3))
        if v==5:
            from repositories.inventory_repo import register_inventory_entry
            try:register_inventory_entry(po['id'],tag(),'2026-10-05','Principal','CERT repetición',[{'product_id':pid,'quantity':qty,'unit_price':cost}])
            except Exception:pass
            check('sin sobre-recepción',physical(pid),D(qty))
    elif feature in ['inventario','ppp_fifo','despacho','ventas','trazabilidad','embalajes']:
        pid=product(lot=feature in ['ppp_fifo','trazabilidad'] or v==4)
        purchase(pid,10,1000,lot=tag(),receive=True);purchase(pid,10,1500,lot=tag(),receive=True)
        from repositories.kardex_repo import get_current_ppp
        check('PPP independiente',get_current_ppp(pid),ppp([(10,1000),(10,1500)]))
        sale=quote(client,pid,qty=30 if v==3 else v+1,price=2500,discount=0,convert=True)
        check('venta pendiente sin salida',physical(pid),D(20))
        if feature=='inventario':
            from services.stock_context import get_operational_balance
            sku=query('SELECT sku FROM products WHERE id=%s',(pid,))[0]['sku'];b=get_operational_balance(sku)
            reserved=D(30 if v==3 else v+1)
            check('reserva global',b['reserved_stock'],reserved);check('disponible',b['available_stock'],max(D(20)-reserved,D(0)))
        elif feature=='ppp_fifo' and v in [1,2,3]:
            check('stock de capas',physical(pid),D(20))
        else:
            prepare(client,sale['id'])
            qty=30 if v==3 else v+1
            check('salida o bloqueo por insuficiencia',physical(pid),D(20 if v==3 else 20-qty))
            if v!=3:
                items=query('SELECT * FROM sale_items WHERE sale_id=%s',(sale['id'],))
                check('costo congelado',items[0]['unit_cost_at_sale'],D(1250))
                if feature=='trazabilidad':check('lote sale ligado',bool(query('SELECT * FROM sale_lot_movements WHERE sale_id=%s',(sale['id'],))),True)
                if feature=='embalajes':
                    from repositories.sales_repo import record_sale_packaging,get_sale_financial_summary
                    box=product(cost=100);purchase(box,10,100,receive=True)
                    record_sale_packaging(sale['id'],[{'product_id':box,'quantity':v}])
                    check('costo embalaje',get_sale_financial_summary(sale['id'])['packaging_cost'],D(v*100))
                if v==5:
                    before=query('SELECT id FROM inventory_movements WHERE product_id=%s',(pid,));prepare(client,sale['id'])
                    check('transición idempotente',query('SELECT id FROM inventory_movements WHERE product_id=%s',(pid,)),before)
        if feature=='ventas' and v==5:
            prepare(client,sale['id'],'Cancelada');check('reversa stock',physical(pid),D(20))
        if feature=='ppp_fifo' and v==4:
            # Quantities cross the first physical FIFO layer while accounting keeps PPP.
            second=quote(client,pid,qty=10,price=2500,discount=0,convert=True);prepare(client,second['id'])
            layers=query('SELECT available_qty FROM lot_stock WHERE product_id=%s ORDER BY entry_date,id',(pid,))
            check('FIFO capa antigua agotada',layers[0]['available_qty'],D(0))
        if feature=='ppp_fifo' and v==5:
            from repositories.inventory_revaluation_repo import revalue_inventory_movement
            first=query("SELECT id FROM inventory_movements WHERE product_id=%s AND quantity>0 ORDER BY id LIMIT 1",(pid,))[0]['id']
            revalue_inventory_movement(first,1300,'CERT revaluación sintética autorizada',created_by='CERT')
            check('PPP revaluado independiente',get_current_ppp(pid),ppp([(10,1300),(10,1500),(-6,0)]))
            check('costo congelado histórico conservado',query('SELECT unit_cost_at_sale FROM sale_items WHERE sale_id=%s',(sale['id'],))[0]['unit_cost_at_sale'],D(1250))
    elif feature=='cotizaciones':
        qty,price,discount=[(3,10000,10),(7,'1234.55',15),(1,50,0),(4,10000,100),(3,1000000000,10)][v-1]
        expected=invoice([(qty,price,discount)]);pid=product();row=quote(client,pid,qty,price,discount)
        check('total persistido',row['total_amount'],expected['total'])
        check('subtotal neto',json.loads(row['products_json'])[0]['subtotal'],expected['lines'][0])
        from repositories.sales_repo import get_sale_financial_summary
        amounts=get_sale_financial_summary(row['id']);check('neto servidor',amounts['neto'],expected['net']);check('IVA servidor',amounts['iva'],expected['vat'])
        if v==5:
            client.post('/ventas/cotizacion/nueva',data={'edit_id':row['id'],'customer_name':row['customer_name'],'customer_email':row['customer_email'],'status':'Cotización','quotation_status':'Activa','product_id[]':[pid],'quantity[]':[qty],'unit_price[]':[str(D(price)+1)],'discount[]':[discount]})
            expected=invoice([(qty,D(price)+1,discount)])
            check('cotización modificada',query('SELECT total_amount FROM sales WHERE id=%s',(row['id'],))[0]['total_amount'],expected['total'])
            client.post(f'/ventas/cotizacion/{row["id"]}/convertir')
            converted=query("SELECT total_amount FROM sales WHERE customer_name=%s AND status='Pendiente'",(row['customer_name'],))[0]
            check('conversión mismo bruto',converted['total_amount'],expected['total'])
    elif feature in ['recetas','produccion']:
        from repositories.production_repo import create_production_order
        raw=product(lot=True,raw=True);finished=product(cost=0,lot=True)
        purchase(raw,10,1000,lot=tag(),receive=True);purchase(raw,10,1500,lot=tag(),receive=True)
        if feature=='recetas':
            # Recipe persistence via the actual creation form, not manual business inserts.
            before=query('SELECT count(*) n FROM product_recipes')[0]['n']
            client.post('/produccion/recetas/nueva',data={'name':tag(),'final_product_id':finished,'input_product_id[]':[raw],'quantity_required[]':['1']})
            check('receta creada',query('SELECT count(*) n FROM product_recipes')[0]['n'],before+1)
        ot,num=create_production_order(finished,25 if v==3 else v+1,status='Aprobada',items=[{'input_product_id':raw,'quantity_required':1}])
        if feature=='produccion':
            client.post(f'/produccion/ot/{ot}/finalizar',data={'output_lot_number':tag()})
            check('fabricación o bloqueo',physical(finished),D(0 if v==3 else v+1))
            if v!=3:
                row=query('SELECT unit_cost FROM production_orders WHERE id=%s',(ot,))[0]
                check('costo unitario fabricación',row['unit_cost'],D(1250))
                check('MP consumida',physical(raw),D(20-v-1))
            if v==5:
                before=query('SELECT id FROM inventory_movements WHERE reference_type=\'production_order\' AND reference_id=%s',(ot,));client.post(f'/produccion/ot/{ot}/finalizar',data={'output_lot_number':tag()})
                check('fabricación no duplicada',query('SELECT id FROM inventory_movements WHERE reference_type=\'production_order\' AND reference_id=%s',(ot,)),before)
    elif feature=='cxc':
        row=quote(client,product(),1,10000,0,convert=True);amount=[2000,5900,11901,11900,3000][v-1]
        key=tag();items=payment(client,row['id'],amount,key=key)
        if v==3:check('sobrepago rechazado',len(items),0)
        else:
            check('cobro persistido',sum(D(x['payment_amount']) for x in items),D(amount))
            from repositories.reporting_repo import get_accounts_receivable_report_data
            report=get_accounts_receivable_report_data(search=row['sale_number'])
            actual=sum(D(i['pending_amount']) for i in report['items'])
            check('saldo CxC',actual,D(11900-amount))
            if v==5:
                payment(client,row['id'],amount,key=key);check('pago idempotente',query('SELECT count(*) n FROM sale_payment_items WHERE sale_id=%s',(row['id'],))[0]['n'],1)
    elif feature=='cxp':
        account=bank();po,entry=purchase(product(),10,1000,receive=True,client=client)
        inv=query('SELECT * FROM purchase_invoices WHERE inventory_entry_id=%s',(entry,))[0];amount=[2000,5900,11901,11900,3000][v-1]
        response=client.post(f'/compras/facturas/{inv["id"]}/registrar-pago',data={'payment_amount':str(amount),'payment_date':'2026-10-20','payment_method':'Efectivo','bank_account_id':account})
        changed=query('SELECT * FROM purchase_invoices WHERE id=%s',(inv['id'],))[0]
        if v==3:check('sobrepago CxP rechazado',changed['payment_amount'] or 0,D(0))
        else:
            check('abono CxP aplicado',changed['payment_amount'],D(amount))
            if v in [1,2]:
                from repositories.cash_flow_repo import calculate_cash_flow_consolidation
                flow=calculate_cash_flow_consolidation('2026-10-01','2026-11-30',bank_account_id=account)
                check('saldo CxP proyectado después de abono',flow['kpis']['projected_outflows'],D(11900-amount))
            if v==4:check('obligación pagada',changed['payment_status'],'Pagada')
            if v==5:
                client.post(f'/compras/facturas/{inv["id"]}/registrar-pago',data={'payment_amount':'8900','payment_date':'2026-10-21','payment_method':'Efectivo'})
                final=query('SELECT payment_amount,payment_status FROM purchase_invoices WHERE id=%s',(inv['id'],))[0]
                check('abonos CxP acumulados',final['payment_amount'],D(11900))
                check('CxP cerrada al completar',final['payment_status'],'Pagada')
    elif feature=='gastos':
        from repositories.operational_expenses_repo import materialize_next_occurrence,update_operational_expense_occurrence,get_operational_expense
        rule=expense(11900+v*100);oid=materialize_next_occurrence(rule,1,override_due_date='2026-10-05')
        real=15000+v*111;update_operational_expense_occurrence(oid,{'amount':real,'invoice_number':tag(),'document_file':'CERT/documento-sintetico.pdf'},1)
        check('importe real del mes',query('SELECT amount FROM operational_expense_occurrences WHERE id=%s',(oid,))[0]['amount'],D(real))
        check('regla mensual intacta',get_operational_expense(rule)['amount'],D(11900+v*100))
        if v>=4:
            second=materialize_next_occurrence(rule,1,override_due_date='2026-11-05',override_amount=real+1000)
            check('otro período diferente',query('SELECT amount FROM operational_expense_occurrences WHERE id=%s',(second,))[0]['amount'],D(real+1000))
        if v==5:check('período idempotente',materialize_next_occurrence(rule,1,override_due_date='2026-10-05'),oid)
    elif feature=='deudas':
        from repositories.debts_repo import list_debt_installments,register_debt_installment_payment
        amount=100000+v;did=debt(amount);inst=list_debt_installments(did)
        check('principal no duplicado',sum(D(i['capital']) for i in inst),D(amount))
        first=inst[0];paid=1 if v==3 else D(first['total_amount']) if v==4 else 10000
        result=register_debt_installment_payment(first['id'],paid,'2026-10-20',bank_account_id=bank(),payment_method='Efectivo')
        check('pago deuda válido',result[0],True)
        changed=query('SELECT balance FROM debt_installments WHERE id=%s',(first['id'],))[0]
        check('saldo cuota',changed['balance'],D(first['total_amount'])-D(paid))
        if v==5:check('sobrepago cuota rechazado',register_debt_installment_payment(first['id'],D(amount)*2,'2026-10-20',None)[0],False)
    elif feature=='bancos':
        from repositories.cash_flow_repo import get_bank_initial_balances
        account=bank();statement(account,1000000,'2026-09-30');statement(account,10000*v);statement(account,-3000*v)
        check('saldo contable banco',get_bank_initial_balances('2026-10-21',account)[account],D(1000000+7000*v))
        if v==5:
            from repositories.bank_reconciliation_repo import reconcile_transaction
            other=bank();out,_=statement(account,-50000);inc,_=statement(other,50000)
            check('transferencia enlazada',reconcile_transaction(out['id'],'INTERNAL_TRANSFER',inc['id'],'CERT')[0],True)
            check('transferencia consolidada neutra',get_bank_initial_balances('2026-10-21',account)[account]+get_bank_initial_balances('2026-10-21',other)[other],D(1000000+7000*v))
    elif feature=='conciliacion':
        from repositories.bank_reconciliation_repo import reconcile_transaction,unreconcile_transaction
        account=bank();sale=quote(client,product(),1,10000,0,convert=True);items=payment(client,sale['id'],11900,account=account)
        check('transferencia ERP persistida',len(items),1)
        tx,_=statement(account,11900 if v!=3 else 11901)
        before=query('SELECT count(*) n FROM sale_payment_items')[0]['n'];ok,msg=reconcile_transaction(tx['id'],'SALE_PAYMENT',items[0]['id'],'CERT')
        check('conciliación monto compatible',ok,v!=3)
        check('sin pagos extra',query('SELECT count(*) n FROM sale_payment_items')[0]['n'],before)
        if v==4:check('desconciliar autorizado',unreconcile_transaction(tx['id'],'CERT')[0],True)
        if v==5:check('conciliación no duplicada',reconcile_transaction(tx['id'],'SALE_PAYMENT',items[0]['id'],'CERT')[0],False)
    elif feature=='flujo_caja':
        from repositories.cash_flow_repo import calculate_cash_flow_consolidation
        account=bank();statement(account,100000,'2026-09-30');statement(account,11900*v);statement(account,-2380*v)
        report=calculate_cash_flow_consolidation('2026-10-01','2026-10-31',bank_account_id=account,filter_type='real')
        check('saldo inicial',report['kpis']['initial_balance'],D(100000))
        check('saldo final real',report['kpis']['current_balance'],D(100000+(11900-2380)*v))
        check('ingresos reales',report['kpis']['real_inflows'],D(11900*v))
    elif feature=='reportes':
        from repositories.reporting_repo import get_sales_report_data
        before=get_sales_report_data();pid=product();row=quote(client,pid,v+1,1234+v,10,convert=True);expected=invoice([(v+1,1234+v,10)])
        after=get_sales_report_data();check('reporte total bruto',D(after['total_income'])-D(before['total_income']),expected['total'])
        check('reporte neto',D(after['total_net'])-D(before['total_net']),expected['net'])
        check('reporte IVA',D(after['total_vat'])-D(before['total_vat']),expected['vat'])
        check('distribución concilia',sum(D(p['revenue']) for p in after['products']),D(after['total_income']))
        if v==5:
            response=client.get('/reporteria/cuentas-por-cobrar/exportar-excel?search='+row['sale_number'])
            check('Excel válido',response.data[:2],b'PK')
    elif feature=='seguridad':
        routes=['/usuarios','/administracion/informacion','/administracion/cuentas-bancarias','/reporteria/conciliacion-bancaria','/inventario/ajustes']
        with client.session_transaction() as s:s.update(role_name='CERT Sin Permisos',permissions={})
        response=client.get(routes[v-1],follow_redirects=False)
        check('endpoint protegido',response.status_code in [302,403],True)
    elif feature=='ajustes':
        from repositories.inventory_adjustments_repo import create_adjustment,approve_adjustment
        pid=product();purchase(pid,10,1000,receive=True)
        if v==3:
            with pytest.raises(ValueError):create_adjustment(product_id=pid,warehouse='Principal',counted_quantity=-1,reason='CERT',observation='',requested_by=1,requested_by_name='CERT')
            return
        req=create_adjustment(product_id=pid,warehouse='Principal',counted_quantity=10+v,reason='CERT Conteo sintético',observation='',requested_by=1,requested_by_name='CERT')
        check('solicitud sin stock',physical(pid),D(10))
        approve_adjustment(req['id'],actor_id=1,actor_name='CERT',approver_may_self_approve=True)
        check('ajuste aprobado',physical(pid),D(10+v))
        if v==5:
            with pytest.raises(ValueError):approve_adjustment(req['id'],actor_id=1,actor_name='CERT',approver_may_self_approve=True)
            check('sin duplicado',physical(pid),D(15))
    elif feature=='precios':
        from repositories.kardex_repo import get_current_ppp
        from services.pricing import net_price
        pid=product();purchase(pid,10,1000,receive=True);purchase(pid,10,1500,receive=True)
        markup=[0,15,40,25,100][v-1];expected=(D(1250)*(D(1)+D(markup)/100)).quantize(D('.01'),rounding=ROUND_HALF_UP)
        check('precio neto por PPP y recargo',net_price(get_current_ppp(pid),markup),expected)
    elif feature=='operario':
        from repositories.production_repo import create_production_order
        raw=product(raw=True,lot=v!=3);finished=product(cost=0,lot=True);lot_number=tag();purchase(raw,20,1000+v*100,lot=lot_number,receive=True)
        oid,_=create_production_order(finished,v,status='Aprobada',items=[{'input_product_id':raw,'quantity_required':1}])
        if v!=3:
            from services.operario_service import OperarioService
            ok,msg,_=OperarioService.validate_and_record_consumption(oid,raw,lot_number,v)
            check('consumo móvil registrado',ok,True)
        with client.session_transaction() as s:s['permissions']['operario_bodega']=True
        client.post(f'/operario/ot/{oid}/finalizar',data={'output_lot_number':tag(),'actual_quantity':v})
        check('operario salida PT',physical(finished),D(0 if v==3 else v))
        if v!=3:check('operario costo producción',query('SELECT unit_cost FROM production_orders WHERE id=%s',(oid,))[0]['unit_cost'],D(1000+v*100))
        else:check('rechazo no crea salida valorada',query("SELECT count(*) n FROM inventory_movements WHERE reference_id=%s AND reference_type='production_order' AND movement_type='PRODUCTION_OUTPUT'",(oid,))[0]['n'],0)
    elif feature=='agenda':
        from repositories.production_repo import create_production_order,set_production_order_schedule
        pid=product();oid,_=create_production_order(pid,v,status='Borrador',items=[])
        ok,msg,details=set_production_order_schedule(oid,'2026-11-0'+str(v))
        check('programación válida',ok,True);check('agenda no consume',physical(pid),D(0))
        if v==5:
            set_production_order_schedule(oid,None)
            check('desprogramar',query('SELECT scheduled_date FROM production_orders WHERE id=%s',(oid,))[0]['scheduled_date'],None)
    elif feature=='excel_productos':
        from openpyxl import load_workbook
        pid=product(cost=1234+v);sku=query('SELECT sku FROM products WHERE id=%s',(pid,))[0]['sku']
        response=client.get('/productos/exportar?search='+sku)
        check('Excel productos válido',response.data[:2],b'PK')
        workbook=load_workbook(io.BytesIO(response.data),data_only=True)
        values=[cell for row in workbook.active.iter_rows(values_only=True) for cell in row]
        check('SKU exportado',sku in values,True);check('costo exacto en Excel',1234+v in values,True)
    elif feature=='excel_bancos':
        from services.bank_reconciliation_excel_service import export_bank_transactions_to_excel,parse_and_preview_bank_statement
        from openpyxl import load_workbook
        account=bank();tx,_=statement(account,11900+v)
        stream=export_bank_transactions_to_excel(bank_account_id=account)
        raw=stream.getvalue() if hasattr(stream,'getvalue') else stream
        workbook=load_workbook(io.BytesIO(raw),data_only=True)
        values=[cell for row in workbook.active.iter_rows(values_only=True) for cell in row]
        check('monto bancario en Excel',11900+v in values,True)
        preview=parse_and_preview_bank_statement(raw,account)
        check('roundtrip sin nuevas filas',preview['summary']['new_rows'],0)
    elif feature=='excel_deudas':
        from repositories.debts_repo import get_debt_detail,list_debt_installments
        from services.debt_excel_service import export_debt_schedule_excel,parse_and_validate_debt_schedule_excel
        did=debt(300000+v);detail=get_debt_detail(did);installments=list_debt_installments(did)
        raw=export_debt_schedule_excel(detail,installments)
        ok,msg,lines=parse_and_validate_debt_schedule_excel(raw)
        check('Excel cuotas parseable',ok,True)
        check('cuotas sin duplicados',len(lines),3)
        check('principal exportado exacto',sum(D(x['capital']) for x in lines),D(300000+v))
    elif feature=='usuarios_roles':
        from repositories.auth_repo import insert_role,insert_user,get_user
        from werkzeug.security import check_password_hash
        name=tag();rid=insert_role({'name':name,'description':'CERT','permissions':json.dumps({'ventas':True}),'created_at':datetime.now(timezone.utc).isoformat()})
        uid=insert_user({'username':name,'email':name+'@cert.invalid','password':'CERT-safe-synthetic-password','full_name':name,'role_id':rid,'is_active':True,'created_at':datetime.now(timezone.utc).isoformat()})
        user=get_user(uid);check('rol asignado',user['role_id'],rid)
        password_hash=query('SELECT password FROM users WHERE id=%s',(uid,))[0]['password']
        check('contraseña no almacenada en claro',check_password_hash(password_hash,'CERT-safe-synthetic-password'),True)
    elif feature=='informacion_empresa':
        from PIL import Image
        from db import get_page_data
        before=get_page_data('company_information') or {}
        stream=io.BytesIO();Image.new('RGB',(v+1,v+1),(20,100,40)).save(stream,format='PNG');stream.seek(0)
        if v==3:
            client.post('/administracion/informacion',data={'company_logo':(io.BytesIO(b'CERT no es imagen'),'cert.png')},content_type='multipart/form-data')
            check('imagen inválida no reemplaza',get_page_data('company_information') or {},before)
        else:
            client.post('/administracion/informacion',data={'company_logo':(stream,'cert.png')},content_type='multipart/form-data')
            check('logo configurado',bool(get_page_data('company_information').get('quotation_logo')),True)
            response=client.get('/empresa/logo-cotizacion')
            check('logo decodificable',response.data[:8],b'\x89PNG\r\n\x1a\n')
    else:pytest.skip('Funcionalidad sin adaptador seguro disponible')
