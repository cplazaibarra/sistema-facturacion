import os,json,traceback
from pathlib import Path
import pytest
from core.test_database_guard import assert_current_test_database_authorized
assert_current_test_database_authorized()
OUT=Path(os.environ['CERTIFICATION_OUT'])

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item,call):
    outcome=yield
    report=outcome.get_result()
    if report.when=='call' or (report.when=='setup' and report.failed):
        module=getattr(item,'callspec',None)
        params=module.params if module else {}
        record={'id':item.nodeid,'functionality':params.get('feature','E2E'),'variant':params.get('variant',params.get('cycle')),'initial_data':'Empresa Ficticia CERT; datos exclusivos por escenario; véanse parámetros, peticiones y script reproducible','action':item.function.__doc__ or item.name,'requests':getattr(item,'cert_actions',[]),'checks':getattr(item,'cert_checks',[]),'status':'PASS' if report.passed else 'BLOCKED' if report.skipped or report.when=='setup' else 'FAIL','actual':str(report.longrepr) if not report.passed else 'Persistencia y aserciones verificadas','impact':'Consultar fallo y diferencias de checks' if report.failed else 'Sin diferencia en controles ejecutados'}
        with (OUT/'evidencia/casos.jsonl').open('a') as f:f.write(json.dumps(record,default=str,ensure_ascii=False)+'\n')

@pytest.fixture
def check(request):
    request.node.cert_checks=[]
    def verify(label,actual,expected,scale=None):
        from decimal import Decimal,ROUND_HALF_UP
        money=isinstance(expected,Decimal)
        diff=None
        if money:
            actual=Decimal(str(actual))
            if scale:actual=actual.quantize(Decimal(scale),rounding=ROUND_HALF_UP)
            diff=actual-expected
        request.node.cert_checks.append({'concept':label,'expected':expected,'actual':actual,'difference':diff,'scale':scale,'status':'PASS' if actual==expected else 'FAIL'})
        assert actual==expected,f'{label}: expected={expected}, actual={actual}, delta={diff}'
    return verify

@pytest.fixture
def client(request):
    from app import app
    old=dict(TESTING=app.config.get('TESTING'),WTF_CSRF_ENABLED=app.config.get('WTF_CSRF_ENABLED'))
    app.config.update(TESTING=True,WTF_CSRF_ENABLED=False)
    with app.test_client() as c:
        request.node.cert_actions=[]
        original=c.open
        def traced(*args,**kwargs):
            request.node.cert_actions.append({'path':str(args[0]) if args else kwargs.get('path'),'method':kwargs.get('method','GET'),'data':str(kwargs.get('data',kwargs.get('json','')))[:5000]})
            return original(*args,**kwargs)
        c.open=traced
        with c.session_transaction() as s:
            s.update(user_id=1,username='admin',full_name='Administrador Ficticio CERT',role_name='Administrativo',permissions={k:True for k in ['dashboard','usuarios','ventas','inventario','productos','administracion','reportes','configuracion','crear_registros','aprobar_registros','produccion','compras','inventory_adjustment_request','inventory_adjustment_approve']})
        yield c
    app.config.update(old)
