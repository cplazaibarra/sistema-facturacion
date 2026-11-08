import os, json, sys
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
import psycopg2, psycopg2.extras
from dotenv import load_dotenv

ROOT=Path('/home/cplaza/Desarrollo/Proeycto-Gestion-Negocio/sistema-facturacion')
sys.path.insert(0,str(ROOT))
load_dotenv(ROOT/'.env')
conn=psycopg2.connect(host=os.getenv('DB_HOST','localhost'),port=os.getenv('DB_PORT','5432'),dbname=os.getenv('DB_NAME','postgres'),user=os.getenv('DB_USER','postgres'),password=os.getenv('DB_PASSWORD'),cursor_factory=psycopg2.extras.RealDictCursor,options='-c default_transaction_read_only=on -c statement_timeout=45000')
conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
def query(q,args=None):
    with conn.cursor() as cur:
        cur.execute(q,args)
        return [dict(r) for r in cur.fetchall()]
out={'date':datetime.now(timezone.utc).isoformat(),'database':query('select current_database() as name, current_setting(\'transaction_read_only\') as readonly')[0]}
out['columns']=query("select table_name,column_name,data_type from information_schema.columns where table_schema='public' order by table_name,ordinal_position")
tables=sorted(set(r['table_name'] for r in out['columns']))
out['counts']={t:query('select count(*) as n from "'+t+'"')[0]['n'] for t in tables}
out['invalid_constraints']=query("select conrelid::regclass::text as table_name,conname from pg_constraint where connamespace='public'::regnamespace and not convalidated")
out['config']=query("select key,json from page_data where key in ('price_list_config','inventory_items')")
out['products']=query('select id,sku,name,cost,product_type,requires_lot,is_deleted from products order by id')
out['entries']=query('select * from inventory_entry_items order by id')
out['margins']=query('select * from product_margins')
out['sales']=query('select id,sale_number,total_amount,status,payment_status,delivery_status,products_json from sales order by id')
for table in ['sale_items','sale_payment_items','sale_payments','purchase_orders','purchase_order_items','purchase_invoices','production_orders','production_order_items','inventory_movements','inventory_cost_revaluations','lot_stock']:
    rows=query('select * from '+table+' order by id')
    # Only persist fields needed for numerical audits, avoiding names, contacts and free text.
    sensitive={'customer_name','customer_email','notes','observations','description','supplier_name','payment_proof_file','invoice_file','created_by_name','seller_name','seller_initials','customer_initials'}
    out[table]=[{k:v for k,v in r.items() if k not in sensitive} for r in rows]
from repositories.kardex_repo import get_current_ppp
from repositories.products_repo import get_products_batch_calculated_cost
out['price_list_costs']=get_products_batch_calculated_cost([p['id'] for p in out['products']],conn=conn)
out['ppp']={str(p['id']):get_current_ppp(p['id'],conn=conn) for p in out['products'] if not p['is_deleted']}
for table in ['debts','debt_installments','debt_payments','operational_expense_occurrences','bank_transactions','bank_accounts']:
    fields=[c['column_name'] for c in out['columns'] if c['table_name']==table and (c['data_type'] in ['numeric','double precision','integer','boolean','date'] or c['column_name']=='status')]
    out[table]=query('select '+','.join('"'+f+'"' for f in fields)+' from '+table)
conn.rollback();conn.close()
target=ROOT/'docs/qa/auditoria_erp_20261020'
target.mkdir(parents=True,exist_ok=True)
(target/'datos_lectura.json').write_text(json.dumps(out,default=str,ensure_ascii=False,indent=2))
print(json.dumps({'database':out['database'],'counts':out['counts'],'invalid_constraints':out['invalid_constraints']},ensure_ascii=False))
