import os,json,sys
from pathlib import Path
from dotenv import load_dotenv
import psycopg2,psycopg2.extras
root=Path('/home/cplaza/Desarrollo/Proeycto-Gestion-Negocio/sistema-facturacion')
sys.path.insert(0,str(root));load_dotenv(root/'.env')
from services.money import document_amounts
from repositories.kardex_repo import get_batch_current_ppp
out=root/'docs/qa/auditoria_erp_20261020'
before=json.loads((out/'datos_lectura.json').read_text())
conn=psycopg2.connect(host=os.getenv('DB_HOST'),port=os.getenv('DB_PORT'),dbname=os.getenv('DB_NAME'),user=os.getenv('DB_USER'),password=os.getenv('DB_PASSWORD'),cursor_factory=psycopg2.extras.RealDictCursor,options='-c default_transaction_read_only=on')
conn.set_session(readonly=True,isolation_level='REPEATABLE READ')
with conn.cursor() as cur:
    cur.execute('SELECT id,total_amount,products_json FROM sales ORDER BY id'); sales=cur.fetchall()
    expected={r['id']:(r['total_amount'],r['products_json']) for r in before['sales']}
    assert {r['id']:(r['total_amount'],r['products_json']) for r in sales}==expected
    documents=[]
    for sale in sales:
        amounts=document_amounts(json.loads(sale['products_json'] or '[]'),sale['total_amount'])
        assert abs(amounts['net']+amounts['vat']-amounts['total'])<.01
        assert amounts['total']==sale['total_amount']
        documents.append({'id':sale['id'],'net':amounts['net'],'vat':amounts['vat'],'total':amounts['total']})
    cur.execute('SELECT id,product_id,quantity,unit_cost FROM inventory_movements ORDER BY id'); movements=cur.fetchall()
    assert [dict(r) for r in movements]==[{k:r[k] for k in ['id','product_id','quantity','unit_cost']} for r in before['inventory_movements']]
    cur.execute('SELECT * FROM lot_stock ORDER BY id');lots=cur.fetchall()
    assert [json.loads(json.dumps(dict(r),default=str)) for r in lots]==before['lot_stock']
    cur.execute('SELECT id,payment_amount,accounting_approved FROM sale_payment_items ORDER BY id');payments=cur.fetchall()
    assert [dict(r) for r in payments]==[{k:r[k] for k in ['id','payment_amount','accounting_approved']} for r in before['sale_payment_items']]
    cur.execute("SELECT ot_number,unit_cost FROM production_orders WHERE ot_number='OT-09270'");order=dict(cur.fetchone())
    cur.execute('SELECT count(*) AS n FROM inventory_cost_revaluations');revals=cur.fetchone()['n']
    costs=get_batch_current_ppp([p['id'] for p in before['products']],conn=conn)
conn.rollback();conn.close()
inventory=json.loads((out/'inventario_despues.json').read_text())['summary']
result={'sales_totals_and_original_lines_unchanged':len(sales),'documents_with_consistent_tax_split':len(documents),'original_inventory_movements_unchanged':len(movements),'lot_rows_unchanged':len(lots),'payment_items_unchanged':len(payments),'revaluations':revals,'repaired_order':order,'prd001_net_cost':costs[1],'inventory_integrity':inventory['operational_integrity'],'legacy_status':inventory['legacy_status'],'documents':documents}
(out/'verificacion_final.json').write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='documents'},default=str,ensure_ascii=False))
