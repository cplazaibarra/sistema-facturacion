"""Run from project root with PYTHONPATH=. and the configured test database.

Writes read-only SQL profiling evidence for the migrated P0 subset.
"""
import json, time, re
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from app import app

queries=[]
class Cursor(RealDictCursor):
    def execute(self, query, vars=None):
        started=time.perf_counter()
        result=super().execute(query,vars)
        self.entry={'sql':self.query.decode(), 'ms':round((time.perf_counter()-started)*1000,3),'fetched':0}
        queries.append(self.entry)
        return result
    def fetchall(self):
        rows=super().fetchall();self.entry['fetched']+=len(rows);return rows
    def fetchone(self):
        row=super().fetchone();self.entry['fetched']+=int(row is not None);return row
original=psycopg2.connect
def connect(*args,**kwargs):
    kwargs['cursor_factory']=Cursor
    return original(*args,**kwargs)
psycopg2.connect=connect
paths=['/dashboard','/reporteria/conciliacion-bancaria','/ventas/cotizaciones','/compras/productos-comprados','/administracion/cuentas-bancarias','/compras/cuentas-por-pagar']
results=[]
with app.test_client() as client:
    with client.session_transaction() as sess:
        sess.update(user_id=1,username='admin',role_name='Administrativo',permissions={k:True for k in ['dashboard','reportes','administracion','ventas','inventario','productos','configuracion','usuarios','crear_registros','aprobar_registros']})
    for path in paths:
        queries.clear();started=time.perf_counter();r=client.get(path);elapsed=(time.perf_counter()-started)*1000
        html=r.get_data(as_text=True)
        tbody=re.search(r'<tbody[^>]*>(.*?)</tbody>',html,re.S)
        details=[q for q in queries if ' LIMIT 30 OFFSET ' in q['sql'] or ('FROM sales s' in q['sql'] and ' LIMIT 5' in q['sql'])]
        # Store structural evidence, not client or account data from SELECT results.
        results.append(dict(route=path,http=r.status_code,backend_ms=round(elapsed,2),payload_bytes=len(r.data),queries=len(queries),fetched_rows_all_queries=sum(q['fetched'] for q in queries),html_first_table_rows=len(re.findall(r'<tr\b',tbody.group(1))) if tbody else 0,detail_queries=[dict(fetched=q['fetched'],ms=q['ms'],sql=q['sql']) for q in details]))
Path('docs/pagination_evidence/measurements.json').write_text(json.dumps(results,indent=2,ensure_ascii=False))
print(json.dumps([{k:v for k,v in r.items() if k!='detail_queries'} for r in results],indent=2))
# Representative real plans, first/deep page. Counts and plans reflect this local dataset.
plans=[]
from core.database import get_connection
with get_connection() as conn:
    with conn.cursor() as cur:
        for table,order in [('bank_transactions','transaction_date DESC,id DESC'),('bank_accounts','id DESC')]:
            cur.execute('SELECT count(*) AS n FROM '+table);n=cur.fetchone()['n']
            for offset in (0,max(0,((n-1)//30)*30)):
                cur.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT * FROM '+table+' ORDER BY '+order+' LIMIT 30 OFFSET %s',(offset,))
                plans.append(dict(table=table,count=n,offset=offset,plan=cur.fetchone()['QUERY PLAN']))
Path('docs/pagination_evidence/explain.json').write_text(json.dumps(plans,indent=2))
