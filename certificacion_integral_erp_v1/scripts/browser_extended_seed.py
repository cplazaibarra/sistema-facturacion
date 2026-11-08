import os,sys,json,io
from pathlib import Path
OUT=Path(os.environ['CERTIFICATION_OUT']);sys.path.insert(0,str(OUT/'tests'))
from test_certification import product,purchase,query,bank,debt,statement,tag,quote,prepare
from app import app
from repositories.production_repo import create_production_order,set_production_order_schedule
from repositories.inventory_adjustments_repo import create_adjustment
from PIL import Image
data=[]
app.config.update(TESTING=True,WTF_CSRF_ENABLED=False)
with app.test_client() as client:
    with client.session_transaction() as s:s.update(user_id=1,username='admin',role_name='Administrativo',permissions={'administracion':True,'productos':True,'inventario':True,'ventas':True,'reportes':True})
    logo=io.BytesIO();Image.new('RGB',(20,20),'green').save(logo,format='PNG');logo.seek(0)
    client.post('/administracion/informacion',data={'company_logo':(logo,'cert.png')},content_type='multipart/form-data')
    for v in range(1,6):
        pid=product(cost=1000+v*100,lot=True,raw=True);lot=tag();purchase(pid,20,1000+v*100,lot=lot,receive=True)
        finished=product(cost=0);ot,num=create_production_order(finished,v,status='Aprobada',items=[{'input_product_id':pid,'quantity_required':1}])
        set_production_order_schedule(ot,'2026-10-'+str(21+v))
        code=tag();client.post('/produccion/recetas/nueva',data={'final_product_id':finished,'recipe_code':code,'input_product_id[]':[pid],'quantity_required[]':['1'],'unit[]':['UN']})
        adj=create_adjustment(product_id=pid,warehouse='Principal',counted_quantity=20+v,reason='CERT Conteo navegador',observation='',requested_by=1,requested_by_name='CERT')
        account=bank();did=debt(100000+v,account);tx,_=statement(account,11900+v)
        pdata=query('SELECT sku,name FROM products WHERE id=%s',(pid,))[0]
        lotid=query('SELECT id FROM lots WHERE lot_number=%s',(lot,))[0]['id']
        customer=query('SELECT razon_social FROM clients ORDER BY id OFFSET %s LIMIT 1',(v-1,))[0]['razon_social']
        sold=product(cost=2000);purchase(sold,10,2000,receive=True);sale=quote(client,sold,v,3000,0,convert=True);prepare(client,sale['id'])
        box=product(cost=100);purchase(box,10,100,receive=True)
        from repositories.sales_repo import record_sale_packaging
        record_sale_packaging(sale['id'],[{'product_id':box,'quantity':v}])
        data.append({'v':v,'raw_id':pid,'product':pdata,'sold_sku':query('SELECT sku FROM products WHERE id=%s',(sold,))[0]['sku'],'cost':1000+v*100,'price_cost':2000,'lot':lot,'lot_id':lotid,'order_id':ot,'order':num,'recipe':code,'adjustment_id':adj['id'],'account':account,'transaction':tx,'debt_id':did,'debt_name':query('SELECT name FROM debts WHERE id=%s',(did,))[0]['name'],'principal':100000+v,'customer':customer,'sale':sale['sale_number']})
(OUT/'evidencia/browser_extended_manifest.json').write_text(json.dumps(data,default=str,ensure_ascii=False,indent=2))
