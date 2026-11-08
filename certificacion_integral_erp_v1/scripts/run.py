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
OUT=ROOT/'certificacion_integral_erp_v1'
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
    global WORK
    parser=argparse.ArgumentParser();parser.add_argument('--targeted',action='store_true');parser.add_argument('--browser-only',action='store_true');parser.add_argument('--cycle3',action='store_true');args=parser.parse_args()
    (OUT/'evidencia').mkdir(parents=True,exist_ok=True)
    initial={'at':datetime.now(timezone.utc).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'tag':subprocess.check_output(['git','rev-parse','v1.0.0'],cwd=ROOT,text=True).strip(),'git_status':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),'source':source_state()}
    before={name:fingerprint(name) for name in ['facturacion','facturacion_cleanup_verify']}
    (OUT/'evidencia/estado_inicial.json').write_text(json.dumps({'git':initial,'databases':before},indent=2))
    rid=secrets.token_hex(6); db='facturacion_test_run_'+rid; role='cert_v1_'+rid; password=secrets.token_hex(24)
    state={'database':db,'role':role,'started_at':datetime.now(timezone.utc).isoformat(),'runs':{},'cleanup':False}
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
                cur.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public' AND (has_table_privilege(%s,quote_ident(schemaname)||'.'||quote_ident(tablename),'INSERT') OR has_table_privilege(%s,quote_ident(schemaname)||'.'||quote_ident(tablename),'UPDATE') OR has_table_privilege(%s,quote_ident(schemaname)||'.'||quote_ident(tablename),'DELETE') OR has_table_privilege(%s,quote_ident(schemaname)||'.'||quote_ident(tablename),'TRUNCATE'))",(role,)*4)
                forbidden[target]=cur.fetchone()[0]
        state['persistent_tables_writable_by_test_role']=forbidden
        if any(forbidden.values()):raise RuntimeError('Unsafe inherited table privileges')
        url=f"postgresql://{quote(role)}:{password}@{CFG['DB_HOST']}:{CFG['DB_PORT']}/{db}"
        env=os.environ.copy();env.update(APP_ENV='testing',ERP_TEST_MODE='1',ERP_TEST_RUN_ID=rid,DB_NAME=db,DB_USER=role,DB_PASSWORD=password,DATABASE_URL=url,TEST_DATABASE_URL=url,CERTIFICATION_BOUNDARY='1',CERTIFICATION_OUT=str(OUT),CERTIFICATION_WORK=str(WORK),PYTHONPATH=str(OUT/'scripts')+':'+str(WORK),PYTHONUNBUFFERED='1')
        py=sys.executable
        if command([py,str(OUT/'scripts/seed.py')],env,'seed.log')!=0:raise RuntimeError('Synthetic seed failed; see seed.log')
        if not args.targeted and not args.browser_only:
            state['runs']['baseline']=command([py,'-m','pytest','-q','-c',str(WORK/'pytest.ini'),'--rootdir='+str(WORK),'tests','--ignore=tests/integration/test_migrations_phase4.py','--junitxml='+str(OUT/'evidencia/baseline.xml')],env,'baseline.log')
        selection=['-k','deudas or operario or cxp'] if args.targeted else []
        if args.cycle3:selection=['-k','test_complete_business_cycle and 3']
        if not args.browser_only:
            state['runs']['certification']=command([py,'-m','pytest','-q','-c',str(WORK/'pytest.ini'),'--rootdir='+str(WORK),str(OUT/'tests'),*selection,'--junitxml='+str(OUT/'evidencia'/('retest.xml' if args.targeted else 'certification.xml'))],env,'retest.log' if args.targeted else 'certification.log')
        if not args.targeted:
            state['runs']['browser_seed']=command([py,str(OUT/'scripts/browser_seed.py')],env,'browser_seed.log')
            server_log=(OUT/'evidencia/server.log').open('w')
            server=subprocess.Popen([py,str(OUT/'scripts/server.py')],cwd=WORK,env=env,stdout=server_log,stderr=subprocess.STDOUT)
            browser_env=env.copy();browser_env['CERTIFICATION_BASE']='http://127.0.0.1:15021'
            state['runs']['browser']=command(['/home/cplaza/.cache/ms-playwright-go/1.57.0/node',str(OUT/'scripts'/('browser_extended.cjs' if args.browser_only else 'browser.cjs'))],browser_env,'browser_extended.log' if args.browser_only else 'browser.log',timeout=1200)
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
                if created:
                    cur.execute(sql.SQL('DROP DATABASE IF EXISTS {} WITH (FORCE)').format(sql.Identifier(db)))
                if role_created:cur.execute(sql.SQL('DROP ROLE IF EXISTS {}').format(sql.Identifier(role)))
                cur.execute('SELECT count(*) FROM pg_database WHERE datname=%s',(db,));state['remaining_database']=cur.fetchone()[0]
                cur.execute('SELECT count(*) FROM pg_roles WHERE rolname=%s',(role,));state['remaining_role']=cur.fetchone()[0]
        after={name:fingerprint(name) for name in before}
        state['persistent_databases_unchanged']=before==after
        state['source_unchanged']=initial['source']==source_state()
        state['tag_unchanged']=initial['tag']==subprocess.check_output(['git','rev-parse','v1.0.0'],cwd=ROOT,text=True).strip()
        state['cleanup']=state['remaining_database']==0 and state['remaining_role']==0
        shutil.rmtree(workspace)
        state['isolated_filesystem_removed']=not workspace.exists()
        state['ended_at']=datetime.now(timezone.utc).isoformat()
        (OUT/'evidencia/aislamiento.json').write_text(json.dumps(state,indent=2))
        (OUT/'evidencia/estado_final.json').write_text(json.dumps(after,indent=2))
        print(json.dumps(state,indent=2))
if __name__=='__main__':main()
