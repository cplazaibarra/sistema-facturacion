#!/usr/bin/env python3
"""Certification orchestration; admin only creates/drops disposable resources."""
import os, sys, json, secrets, subprocess, hashlib, signal, time, shutil, tempfile, argparse
from pathlib import Path
from urllib.parse import quote
from datetime import datetime, timezone
from contextlib import closing
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'correccion_certificacion_erp_v1'
WORK=ROOT
sys.path.insert(0,str(ROOT))
load_dotenv(ROOT/'.env')
CFG={k:os.environ[k] for k in ['DB_HOST','DB_PORT','DB_USER','DB_PASSWORD']}
def admin(db='postgres',readonly=False):
    c=psycopg2.connect(host=CFG['DB_HOST'],port=CFG['DB_PORT'],user=CFG['DB_USER'],password=CFG['DB_PASSWORD'],dbname=db,connect_timeout=8)
    if readonly:c.set_session(readonly=True)
    return c
def fingerprint(db):
    result={}
    with admin(db,True) as conn,conn.cursor() as cur:
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
        for (table,) in cur.fetchall():
            cur.execute(sql.SQL("SELECT count(*),md5(COALESCE(string_agg(h,'' ORDER BY h),'')) FROM (SELECT md5(to_jsonb(t)::text) AS h FROM public.{} t) s").format(sql.Identifier(table)))
            count,digest=cur.fetchone();result[table]={'count':count,'hash':digest}
        schema={}
        queries={
            'relations':"SELECT c.relname,c.relkind,pg_get_userbyid(c.relowner),CASE WHEN c.relkind IN ('v','m') THEN pg_get_viewdef(c.oid,true) END FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S','i','I','f') ORDER BY c.relname",
            'columns':"SELECT table_name,column_name,ordinal_position,data_type,udt_name,is_nullable,column_default,character_maximum_length,numeric_precision,numeric_scale FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position",
            'constraints':"SELECT conrelid::regclass::text,conname,contype,pg_get_constraintdef(oid,true) FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY 1,2",
            'triggers':"SELECT event_object_table,trigger_name,event_manipulation,action_timing,action_statement FROM information_schema.triggers WHERE trigger_schema='public' ORDER BY event_object_table,trigger_name,event_manipulation",
            'functions':"SELECT p.proname,pg_get_function_identity_arguments(p.oid),pg_get_function_result(p.oid),p.prokind,pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.prokind <> 'a' ORDER BY p.proname,2",
            'extensions':"SELECT extname,extversion FROM pg_extension ORDER BY extname",
        }
        for name,query in queries.items():
            cur.execute(query);schema[name]=cur.fetchall()
        result['__schema__']=hashlib.sha256(json.dumps(schema,default=str,sort_keys=True).encode()).hexdigest()
    return result
def source_state():
    paths=[p for folder in ['routes','services','repositories','core','templates','static','migrations'] for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in str(p) and 'uploads' not in p.parts]
    paths += [ROOT/'app.py',ROOT/'db.py',ROOT/'security.py']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
def command(args,env,log,timeout=1200):
    with (OUT/'evidencia'/log).open('w') as f:
        result=subprocess.run(args,cwd=WORK,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
    return result.returncode
def main():
    global WORK,OUT
    parser=argparse.ArgumentParser();parser.add_argument('--targeted',action='store_true');parser.add_argument('--browser-only',action='store_true');parser.add_argument('--cycle3',action='store_true');parser.add_argument('--new-only',action='store_true');parser.add_argument('--functional-only',action='store_true');parser.add_argument('--critical-only',action='store_true');parser.add_argument('--cycles-only',action='store_true');parser.add_argument('--baseline-only',action='store_true');parser.add_argument('--output-name');parser.add_argument('--startup-only',action='store_true');args=parser.parse_args()
    if args.startup_only:args.baseline_only=True
    if args.output_name:
        import re
        if not re.fullmatch('[a-z0-9_]+',args.output_name):raise ValueError('Invalid evidence namespace')
        original_out=OUT
        OUT=OUT/'evidencia'/args.output_name;OUT.mkdir(parents=True,exist_ok=True)
        for folder in ('scripts','tests'):
            target=OUT/folder
            if not target.exists():target.symlink_to(original_out/folder,target_is_directory=True)
    if args.cycles_only:args.targeted=True
    if args.critical_only:args.browser_only=True
    (OUT/'evidencia').mkdir(parents=True,exist_ok=True)
    initial={'at':datetime.now(timezone.utc).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'tag':subprocess.check_output(['git','rev-parse','v1.0.0'],cwd=ROOT,text=True).strip(),'git_status':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),'source':source_state()}
    before={name:fingerprint(name) for name in ['facturacion','facturacion_cleanup_verify']}
    (OUT/'evidencia/estado_inicial.json').write_text(json.dumps({'git':initial,'databases':before},indent=2))
    rid=secrets.token_hex(6); db='facturacion_test_run_'+rid; role='cert_v1_'+rid; password=secrets.token_hex(24)
    state={'database':db,'role':role,'started_at':datetime.now(timezone.utc).isoformat(),'runs':{},'cleanup':False}
    migration_db='facturacion_test_run_'+secrets.token_hex(6)
    migration_created=False
    server=None;created=False;role_created=False
    workspace=Path(tempfile.mkdtemp(prefix='erp_v1_cert_'))
    WORK=workspace/'app';WORK.mkdir()
    for p in ROOT.glob('*.py'):shutil.copy2(p,WORK/p.name)
    shutil.copy2(ROOT/'pytest.ini',WORK/'pytest.ini')
    for folder in ['routes','services','repositories','core','templates','static','migrations','tools','tests']:
        shutil.copytree(ROOT/folder,WORK/folder,ignore=shutil.ignore_patterns('__pycache__','uploads'))
    try:
        with closing(admin()) as c:
            c.autocommit=True
            with c.cursor() as cur:
                cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname='facturacion_cleanup_verify'")
                if cur.fetchone()[0]!='ERP_TEST_DATABASE_TEMPLATE:v1':raise RuntimeError('Template marker invalid')
                cur.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT').format(sql.Identifier(role)),(password,));role_created=True
                cur.execute(sql.SQL('CREATE DATABASE {} WITH TEMPLATE facturacion_cleanup_verify OWNER {}').format(sql.Identifier(db),sql.Identifier(role)));created=True
                cur.execute(sql.SQL('COMMENT ON DATABASE {} IS %s').format(sql.Identifier(db)),('ERP_TEST_DATABASE_RUN:v1:'+rid,))
                cur.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(migration_db),sql.Identifier(role)));migration_created=True
                cur.execute(sql.SQL('COMMENT ON DATABASE {} IS %s').format(sql.Identifier(migration_db)),('ERP_TEST_DATABASE_RUN:v1:'+migration_db.rsplit('_',1)[1],))
        with admin(db) as c,c.cursor() as cur:
            # All destructive preparation is on the disposable clone, before test connections.
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'schema_migrations'")
            names=[r[0] for r in cur.fetchall()]
            cur.execute(sql.SQL('TRUNCATE {} RESTART IDENTITY CASCADE').format(sql.SQL(',').join(sql.Identifier(t) for t in names)))
            cur.execute(sql.SQL('GRANT ALL ON SCHEMA public TO {}').format(sql.Identifier(role)))
            cur.execute(sql.SQL('GRANT ALL ON ALL TABLES IN SCHEMA public TO {}').format(sql.Identifier(role)))
            cur.execute(sql.SQL('GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO {}').format(sql.Identifier(role)))
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            for (table,) in cur.fetchall():
                cur.execute(sql.SQL('ALTER TABLE {} OWNER TO {}').format(sql.Identifier(table),sql.Identifier(role)))
            cur.execute("SELECT sequencename FROM pg_sequences WHERE schemaname='public'")
            for (sequence,) in cur.fetchall():
                cur.execute(sql.SQL('ALTER SEQUENCE {} OWNER TO {}').format(sql.Identifier(sequence),sql.Identifier(role)))
            c.commit()
        # Database-level privileges independently prove writes to persistent DBs are denied.
        forbidden={}
        for target in ['facturacion','facturacion_cleanup_verify']:
            with admin(target,True) as c,c.cursor() as cur:
                cur.execute("""SELECT
                    (SELECT count(*) FROM pg_tables WHERE schemaname='public' AND
                      (has_table_privilege(%s,quote_ident(schemaname)||'.'||quote_ident(tablename),'INSERT') OR
                       has_table_privilege(%s,quote_ident(schemaname)||'.'||quote_ident(tablename),'UPDATE') OR
                       has_table_privilege(%s,quote_ident(schemaname)||'.'||quote_ident(tablename),'DELETE') OR
                       has_table_privilege(%s,quote_ident(schemaname)||'.'||quote_ident(tablename),'TRUNCATE'))),
                    has_schema_privilege(%s,'public','CREATE'),
                    (SELECT count(*) FROM information_schema.sequences WHERE sequence_schema='public' AND
                      (has_sequence_privilege(%s,quote_ident(sequence_schema)||'.'||quote_ident(sequence_name),'USAGE') OR
                       has_sequence_privilege(%s,quote_ident(sequence_schema)||'.'||quote_ident(sequence_name),'UPDATE'))),
                    has_database_privilege(%s,current_database(),'CREATE'),
                    (SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=%s))
                    """,(role,role,role,role,role,role,role,role,role))
                table_writes,schema_create,sequence_writes,db_create,members=cur.fetchone()
                forbidden[target]={'table_write_objects':table_writes,'public_schema_create':schema_create,
                    'sequence_write_objects':sequence_writes,'database_create':db_create,'role_memberships':members}
        state['persistent_tables_writable_by_test_role']=forbidden
        if any(any(value for value in privileges.values()) for privileges in forbidden.values()):
            raise RuntimeError('Test role has effective write, create, or inherited role privileges on a protected database')
        url=f"postgresql://{quote(role)}:{password}@{CFG['DB_HOST']}:{CFG['DB_PORT']}/{db}"
        env=os.environ.copy()
        for key in list(env):
            if key.startswith('PG'):
                env.pop(key,None)
        env.update(APP_ENV='testing',ERP_TEST_MODE='1',ERP_TEST_RUN_ID=rid,DB_NAME=db,DB_USER=role,DB_PASSWORD=password,DATABASE_URL=url,TEST_DATABASE_URL=url,CERTIFICATION_BOUNDARY='1',CERTIFICATION_OUT=str(OUT),CERTIFICATION_WORK=str(WORK),PYTHONPATH=str(OUT/'scripts')+':'+str(OUT/'tests')+':'+str(WORK),PYTHONUNBUFFERED='1',CERTIFICATION_PYTHON=sys.executable,MIGRATION_TEST_DB=migration_db)
        py=sys.executable
        if command([py,str(OUT/'scripts/seed.py')],env,'seed.log')!=0:raise RuntimeError('Synthetic seed failed; see seed.log')
        if not args.targeted and not args.browser_only and not args.new_only and not args.functional_only:
            state['runs']['baseline']=command([py,'-m','pytest','-q','-c',str(WORK/'pytest.ini'),'--rootdir='+str(WORK),'tests',*(['-k','startup_schema_safety'] if args.startup_only else []),'--junitxml='+str(OUT/'evidencia/baseline.xml')],env,'baseline.log')
        selection=['-k','deudas or operario or cxp or conciliacion'] if args.targeted else []
        if args.new_only:selection=['-k','test_repairs_']
        if args.cycles_only:selection=['-k','test_complete_business_cycle']
        if args.cycle3:selection=['-k','test_complete_business_cycle and 3']
        if not args.browser_only and not args.baseline_only:
            state['runs']['certification']=command([py,'-m','pytest','-q','-c',str(WORK/'pytest.ini'),'--rootdir='+str(WORK),str(OUT/'tests'),*selection,'--junitxml='+str(OUT/'evidencia'/('retest.xml' if args.targeted else 'certification.xml'))],env,'retest.log' if args.targeted else 'certification.log')
        if not args.targeted and not args.new_only and not args.functional_only and not args.baseline_only:
            state['runs']['browser_seed']=command([py,str(OUT/'scripts/browser_seed.py')],env,'browser_seed.log')
            server_log=(OUT/'evidencia/server.log').open('w')
            server=subprocess.Popen([py,str(OUT/'scripts/server.py')],cwd=WORK,env=env,stdout=server_log,stderr=subprocess.STDOUT)
            browser_env=env.copy();browser_env['CERTIFICATION_BASE']='http://127.0.0.1:15021'
            state['runs']['browser']=command(['/home/cplaza/.cache/ms-playwright-go/1.57.0/node',str(OUT/'scripts'/('browser_critical.cjs' if args.critical_only else 'browser_extended.cjs' if args.browser_only else 'browser.cjs'))],browser_env,'browser_extended.log' if args.browser_only else 'browser.log',timeout=1200)
            if not args.browser_only and not args.baseline_only:
                state['runs']['browser_extended']=command(['/home/cplaza/.cache/ms-playwright-go/1.57.0/node',str(OUT/'scripts/browser_extended.cjs')],browser_env,'browser_extended.log',timeout=1200)
                state['runs']['browser_critical']=command(['/home/cplaza/.cache/ms-playwright-go/1.57.0/node',str(OUT/'scripts/browser_critical.cjs')],browser_env,'browser_critical.log',timeout=1200)
        state['runs']['final_data']=command([py,str(OUT/'scripts/final_data.py')],env,'final_data.log')
    except Exception as exc:
        state['error']=f'{type(exc).__name__}: {exc}'
    finally:
        if server:
            server.terminate()
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill();server.wait()
        with closing(admin()) as c:
            c.autocommit=True
            with c.cursor() as cur:
                if migration_created:cur.execute(sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(migration_db)))
                if created:
                    cur.execute(sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(db)))
                if role_created:cur.execute(sql.SQL('DROP ROLE IF EXISTS {}').format(sql.Identifier(role)))
                cur.execute('SELECT count(*) FROM pg_database WHERE datname=%s',(db,));state['remaining_database']=cur.fetchone()[0]
                cur.execute('SELECT count(*) FROM pg_database WHERE datname=%s',(migration_db,));state['remaining_migration_database']=cur.fetchone()[0]
                cur.execute('SELECT count(*) FROM pg_roles WHERE rolname=%s',(role,));state['remaining_role']=cur.fetchone()[0]
        after={name:fingerprint(name) for name in before}
        state['persistent_databases_unchanged']=before==after
        state['source_unchanged']=initial['source']==source_state()
        state['tag_unchanged']=initial['tag']==subprocess.check_output(['git','rev-parse','v1.0.0'],cwd=ROOT,text=True).strip()
        state['cleanup']=state['remaining_database']==0 and state['remaining_migration_database']==0 and state['remaining_role']==0
        shutil.rmtree(workspace)
        state['isolated_filesystem_removed']=not workspace.exists()
        state['ended_at']=datetime.now(timezone.utc).isoformat()
        (OUT/'evidencia/aislamiento.json').write_text(json.dumps(state,indent=2))
        (OUT/'evidencia/estado_final.json').write_text(json.dumps(after,indent=2))
        print(json.dumps(state,indent=2))
if __name__=='__main__':main()
