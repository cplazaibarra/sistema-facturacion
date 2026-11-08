import sys,os,json
from pathlib import Path
OUT=Path(os.environ['CERTIFICATION_OUT']);sys.path.insert(0,str(OUT/'tests'))
from test_certification import product,supplier,bank,purchase,quote,expense,query,tag
from app import app
from reference import invoice
from repositories.production_repo import create_production_order
from repositories.operational_expenses_repo import materialize_next_occurrence
app.config.update(TESTING=True,WTF_CSRF_ENABLED=False)
data=[]
with app.test_client() as c:
    with c.session_transaction() as s:s.update(user_id=1,username='admin',full_name='CERT Administrador',role_name='Administrativo',permissions={k:True for k in ['dashboard','usuarios','ventas','inventario','productos','administracion','reportes','configuracion','crear_registros','aprobar_registros','produccion','compras']})
    for v in range(1,6):
        pid=product(cost=1000+v*100);sid=supplier();account=bank();po,entry=purchase(pid,10+v,1000+v*100,receive=True,client=c)
        q=quote(c,pid,3,10000,10);sale=quote(c,pid,v,10000,0,convert=True)
        expected=invoice([(v,10000,0)]);inv=query('SELECT id,invoice_amount,invoice_number FROM purchase_invoices WHERE inventory_entry_id=%s',(entry,))[0]
        rule=expense(11900+119*v,account);oid=materialize_next_occurrence(rule,1,override_due_date='2026-10-25')
        ot,num=create_production_order(product(cost=0),v,status='Borrador',items=[{'input_product_id':pid,'quantity_required':1}])
        pdata=query('SELECT sku,name,cost FROM products WHERE id=%s',(pid,))[0]
        entry_number=query('SELECT order_number FROM inventory_entries WHERE id=%s',(entry,))[0]['order_number']
        data.append({'variant':v,'product':pdata,'supplier':query('SELECT name FROM suppliers WHERE id=%s',(sid,))[0]['name'],'bank':query('SELECT bank_name FROM bank_accounts WHERE id=%s',(account,))[0]['bank_name'],'account_id':account,'oc':po['oc_number'],'entry':entry,'entry_number':entry_number,'quote':q['sale_number'],'quote_total':32130,'sale':sale['sale_number'],'sale_total':str(expected['total']),'invoice_id':inv['id'],'invoice_doc':inv['invoice_number'],'invoice_total':inv['invoice_amount'],'expense':query('SELECT name,amount FROM operational_expenses WHERE id=%s',(rule,))[0],'production':num,'stock':10+v})
(OUT/'evidencia/browser_manifest.json').write_text(json.dumps(data,default=str,ensure_ascii=False,indent=2))
print('Escenarios sintéticos de interfaz preparados:',len(data))
