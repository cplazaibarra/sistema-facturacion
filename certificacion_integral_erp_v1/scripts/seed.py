import os,sys,json
from pathlib import Path
from psycopg2 import sql
from core.test_database_guard import assert_current_test_database_authorized
assert_current_test_database_authorized()
from app import app
from core.database import get_connection
from repositories.products_repo import create_product
from repositories.suppliers_repo import insert_supplier
from repositories.clients_repo import insert_client
from repositories.purchases_repo import create_purchase_order
from repositories.inventory_repo import register_inventory_entry
from db import insert_bank_account,set_page_data,insert_sale
from repositories.production_repo import create_production_order
from repositories.purchases_repo import create_purchase_invoice
from datetime import datetime,timezone
from werkzeug.security import generate_password_hash

out=Path(os.environ['CERTIFICATION_OUT'])
with get_connection() as c,c.cursor() as cur:
    keep=['schema_migrations','roles','users','page_data','expense_categories','debt_types','bank_transaction_categories']
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>ALL(%s)",(keep,))
    names=[r['tablename'] for r in cur.fetchall()]
    cur.execute(sql.SQL('TRUNCATE {} RESTART IDENTITY CASCADE').format(sql.SQL(',').join(sql.Identifier(t) for t in names)))
    cur.execute("INSERT INTO debt_types(name) VALUES ('CERT Crédito Sintético'),('CERT Leasing Sintético') ON CONFLICT(name) DO NOTHING")
    cur.execute("INSERT INTO bank_transaction_categories(name,flow_type) VALUES ('CERT Ingreso','INGRESO'),('CERT Egreso','EGRESO'),('CERT Transferencia','AMBOS') ON CONFLICT(name) DO NOTHING")
    cur.execute("INSERT INTO expense_categories(name) VALUES ('CERT Gastos Sintéticos') ON CONFLICT DO NOTHING")
    for uid in range(2,7):
        cur.execute("INSERT INTO users(id,username,email,password,full_name,role_id,is_active,created_at) VALUES (%s,%s,%s,%s,%s,1,TRUE,NOW()::text) ON CONFLICT DO NOTHING",(uid,f'cert_user_{uid}',f'usuario{uid}@cert.invalid',generate_password_hash('CERT-synthetic-only-password'),f'CERT Usuario Ficticio {uid}'))
    cur.execute("SELECT setval(pg_get_serial_sequence('users','id'),(SELECT max(id) FROM users),TRUE)")
    c.commit()
clients=[insert_client({'rut':str(91000000+i),'dv':'K','razon_social':f'CERT Cliente Ficticio {i:02}','email':f'cliente{i}@cert.invalid','direccion':f'Calle Sintética {i}','delivery_address':f'Bodega Ficticia {i}','category_id':'cat_0'}) for i in range(1,11)]
suppliers=[insert_supplier({'name':f'CERT Proveedor Ficticio {i:02}','rut':str(92000000+i),'email':f'proveedor{i}@cert.invalid','payment_terms':'NET_30'}) for i in range(1,11)]
products=[create_product(sku='PRD001' if i==1 else f'CERT-BASE-{i:02}',name=f'CERT Producto Ficticio {i:02}',product_type='Insumo' if i>10 else 'Final',cost=1000+i*100,requires_lot=i%2==0) for i in range(1,21)]
banks=[insert_bank_account({'bank_name':f'Banco Ficticio {i}','account_number':f'CERT-CTA-{i}','account_type':'Cuenta Corriente','holder_name':'Empresa Ficticia CERT SpA','holder_rut':'99000000-K','status':'Activa'}) for i in [1,2]]
set_page_data('inventory_items',[{'code':f'CERT-BASE-{i:02}','name':f'CERT Producto Ficticio {i:02}','stock':0,'price':0} for i in range(1,21)])
set_page_data('price_list_config',{'categories':[{'id':'cat_0','name':'CERT Retail','margin':40},{'id':'cat_1','name':'CERT Mayorista','margin':15}]})
set_page_data('company_information',{})
# A synthetic cancelled sentinel prevents legacy demo seeding on the next app import.
insert_sale({'sale_number':'CERT-SEED-CANCELADA','customer_name':'Empresa Ficticia CERT','sale_date':'2026-10-01','sale_time':'00:00','products':[],'total_amount':0,'status':'Cancelada','created_at':datetime.now(timezone.utc).isoformat()})
for pid,cost in [(products[0],1000),(products[1],1500)]:
    items=[{'product_id':pid,'quantity':100,'unit_price':cost,'lot_number':f'CERT-INITIAL-{pid}'}]
    number=create_purchase_order(suppliers[0],'2026-10-01','CERT inventario inicial documentado',items)
    with get_connection() as c,c.cursor() as cur:
        cur.execute('SELECT id FROM purchase_orders WHERE oc_number=%s',(number,));po=cur.fetchone()['id']
    register_inventory_entry(po,number,'2026-10-01','Principal','CERT inventario inicial',items)
manifest={'company':'Empresa Ficticia CERT SpA','clients':clients,'suppliers':suppliers,'products':products,'banks':banks,'initial_stock':{str(products[0]):100,str(products[1]):100},'all_other_stock':0,'initial_stock_net_value':250000,'scope':'synthetic only'}
# Explicit synthetic volume for the existing SQL pagination contracts (25/50/100).
# Draft orders consume no stock; standalone invoices represent known opening payables.
for n in range(120):
    create_production_order(products[2],1,notes=f'CERT Volumen sintético {n}',status='Borrador',items=[])
for n in range(60):
    create_purchase_invoice({'supplier_id':suppliers[n%10],'invoice_number':f'CERT-APERTURA-{n:03}','invoice_amount':11900,'invoice_date':'2026-10-01','due_date':'2026-11-01','payment_status':'Pendiente'})
manifest.update(initial_draft_orders=120,initial_standalone_invoices=60,initial_payables_gross=714000)
(out/'evidencia/datos_sinteticos.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest))
