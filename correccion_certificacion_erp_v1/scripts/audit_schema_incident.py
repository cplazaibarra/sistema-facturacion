"""Read-only attribution of schema drift. Never repair the protected databases."""
import importlib.util,json
from pathlib import Path
spec=importlib.util.spec_from_file_location('recert_run',Path(__file__).with_name('run.py'))
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
import tools.migrate as migrate
source={m['version']:m['name'] for m in migrate.get_migration_files()}
result={}
for name in ('facturacion','facturacion_cleanup_verify'):
 with r.admin(name,True) as conn,conn.cursor() as cur:
  cur.execute("SELECT version,name,applied_at FROM schema_migrations ORDER BY version")
  versions=[dict(zip(['version','name','applied_at'],x)) for x in cur.fetchall()]
  cur.execute("SELECT viewname,definition FROM pg_views WHERE schemaname='public' AND viewname IN ('purchase_payment_events','expense_payment_events') ORDER BY viewname")
  views=[]
  for view,definition in cur.fetchall():
   cur.execute('SELECT * FROM public.'+view+' LIMIT 0')
   views.append({'name':view,'valid':True,'columns':[d.name for d in cur.description],'definition':definition})
  cur.execute("SELECT count(*),md5(COALESCE(string_agg(h,'' ORDER BY h),'')) FROM (SELECT md5(to_jsonb(t)::text) AS h FROM schema_migrations t WHERE version NOT IN ('000028','000029','000030')) s")
  count,digest=cur.fetchone()
  result[name]={'preexisting_migration_records':{'count':count,'hash':digest},'migrations':versions,'views':views,'fingerprints':r.fingerprint(name)}
  applied={m['version']:m['name'] for m in versions}
  result[name]['migration_file_comparison']={
   'source_file_count':len(source),
   'source_without_applied_record':[{'version':v,'name':n} for v,n in source.items() if applied.get(v)!=n],
   'applied_without_matching_source':[{'version':v,'name':n} for v,n in applied.items() if source.get(v)!=n],
  }
out=r.OUT/'evidencia/incidente_esquema_auditoria_solo_lectura.json';out.write_text(json.dumps(result,default=str,indent=2))
print(json.dumps({k:{'migrations':v['migrations'],'views':v['views']} for k,v in result.items()},default=str,indent=2))
