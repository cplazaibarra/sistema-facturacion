import json,os
from pathlib import Path
from app import app
from test_certification import bank,supplier,tag,expense,product,purchase,quote,payment,statement,query
from repositories.purchases_repo import create_purchase_invoice
from repositories.operational_expenses_repo import materialize_next_occurrence
from repositories.production_repo import create_production_order
from services.operario_service import OperarioService
app.config.update(TESTING=True,WTF_CSRF_ENABLED=False)
rows=[]
with app.test_client() as c:
 with c.session_transaction() as s:s.update(user_id=1,username='admin',role_name='Administrativo',permissions={'ventas':True,'crear_registros':True,'administracion':True,'reportes':True})
 for v in range(1,6):
  a=bank();doc=tag();inv=create_purchase_invoice(dict(supplier_id=supplier(),invoice_number=doc,invoice_amount=11900,invoice_date='2026-10-05',due_date='2026-11-05',bank_account_id=a,payment_status='Pendiente'))
  e=expense(account=a);occ=materialize_next_occurrence(e,1,override_due_date='2026-10-05')
  raw=product(lot=True,raw=True);pt=product(cost=0,lot=True);lot=tag();purchase(raw,10,1000,lot=lot,receive=True)
  oid,num=create_production_order(pt,2,status='Aprobada',items=[{'input_product_id':raw,'quantity_required':1}])
  if v!=3:assert OperarioService.validate_and_record_consumption(oid,raw,lot,1 if v in (2,4) else 2)[0]
  sale=quote(c,product(),1,10000,0,convert=True);amt=2000 if v==4 else 11900;item=payment(c,sale['id'],amt,account=a)[0];tx,_=statement(a,11901 if v==2 else 15000 if v==3 else amt)
  account=query('SELECT * FROM bank_accounts WHERE id=%s',(a,))[0]
  rows.append(dict(v=v,invoice_id=inv,invoice_doc=doc,account=account,expense_id=e,occurrence_id=occ,order_id=oid,order=num,finished=pt,payment_id=item['id'],tx_id=tx['id'],paid=amt))
Path(os.environ['CERTIFICATION_OUT'],'evidencia/critical_manifest.json').write_text(json.dumps(rows,default=str,indent=2))
