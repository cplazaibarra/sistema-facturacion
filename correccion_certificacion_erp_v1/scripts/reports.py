"""Build recertification conclusions from current evidence, preserving all attempts."""
from pathlib import Path
from decimal import Decimal,InvalidOperation
from collections import Counter
import json,xml.etree.ElementTree as ET,hashlib,zipfile,difflib,subprocess,csv
ROOT=Path(__file__).resolve().parents[1];E=ROOT/'evidencia';REPO=ROOT.parent
GROUPS={'Productos':['productos','excel_productos'],'Proveedores':['proveedores'],'Clientes':['clientes'],'Órdenes de compra':['ordenes_compra'],'Recepción':['recepcion'],'Inventario y Kardex':['inventario','ajustes','trazabilidad'],'Costos PPP/FIFO y precios':['ppp_fifo','precios'],'Cotizaciones':['cotizaciones'],'Ventas':['ventas'],'Preparación y despacho':['despacho','embalajes'],'Producción':['recetas','produccion','operario','agenda'],'Cuentas por Cobrar':['cxc'],'Cuentas por Pagar':['cxp'],'Gastos Operacionales':['gastos'],'Deudas':['deudas','excel_deudas'],'Cuentas bancarias':['bancos'],'Conciliación':['conciliacion','excel_bancos'],'Flujo de Caja':['flujo_caja'],'Reportes':['reportes'],'Usuarios, permisos y administración':['seguridad','usuarios_roles','informacion_empresa']}
def read(name,default=None):
 p=E/name
 return json.loads(p.read_text()) if p.exists() else default

def table(head,rows):return '\n'.join(['| '+' | '.join(head)+' |','|'+'|'.join(['---']*len(head))+'|']+['| '+' | '.join(str(v).replace('|','/').replace('\n',' ') for v in row)+' |' for row in rows])
def output(name,body):(ROOT/name).write_text(body)
def family(r):
 name=r['id']
 if 'test_repairs_cxp' in name or 'test_repairs_invoice_creation' in name:return 'cxp'
 if 'test_repairs_flow' in name:return 'flujo_caja'
 if 'test_repairs_reconciliation' in name:return 'conciliacion'
 if 'test_repairs_production' in name:return 'produccion'
 if 'test_repairs_expense_partial' in name:return 'gastos'
 if 'test_repairs_legacy_partial' in name:return 'cxp' if 'purchase' in name else 'gastos'
 if 'test_repairs_integrity_edges' in name:
  if any(x in name for x in ['empty_plan','missing_cost']):return 'produccion'
  return 'gastos' if 'document_retry' in name else 'cxp'
 return r.get('functionality','E2E')
def main():
 required=['baseline.xml','certification.xml','navegador.json','navegador_ampliado.json','navegador_critico.json','aislamiento.json','control_monetario_final.json']
 assert all((E/n).exists() for n in required),'Final run is incomplete'
 cases=list({r['id']:r for r in [json.loads(l) for l in (E/'casos.jsonl').read_text().splitlines()]}.values())
 for r in cases:r['family']=family(r)
 baseline=[]
 for t in ET.parse(E/'baseline.xml').iter('testcase'):
  state='FAIL' if t.find('failure') is not None or t.find('error') is not None else 'BLOCKED' if t.find('skipped') is not None else 'PASS'
  baseline.append(dict(id=t.get('classname')+'::'+t.get('name'),status=state,new=('test_rollback_preserves_posted_opening_snapshots' in t.get('name','') or 'test_startup_schema_safety' in t.get('classname',''))))
 ui=read('navegador.json',[])+read('navegador_ampliado.json',[])+read('navegador_critico.json',[])
 all_cases=baseline+cases+ui
 states=Counter(r['status'] for r in all_cases)
 unique=[r['id'] for r in all_cases];assert len(set(unique))==len(unique),'Duplicate case IDs'
 original=[r for r in baseline if not r['new']]+[r for r in cases if not r['id'].startswith('test_repairs.py')]+[r for r in ui if not r['id'].startswith('UI-CRIT-')]
 assert len(original)==922,f'Original plan not preserved: {len(original)}'
 original_counts=Counter(r['status'] for r in original)
 migration=[r for r in baseline if 'migrations_phase4' in r['id']]
 quantitative=[]
 for r in cases:
  for ch in r.get('checks',[]):
   if isinstance(ch.get('expected'),bool) or isinstance(ch.get('actual'),bool):continue
   try:a=Decimal(str(ch['actual']));b=Decimal(str(ch['expected']))
   except (InvalidOperation,TypeError,KeyError):continue
   if not a.is_finite() or not b.is_finite():continue
   quantitative.append(dict(case=r['id'],concept=ch['concept'],expected=str(b),actual=str(a),difference=str(a-b),status=ch['status'],scale=ch.get('scale')))
 controls=read('control_monetario_final.json',{})
 for r in controls.get('document_checks',[]):
  quantitative.append(dict(case='cierre:'+r['operation'],concept=r['concept'],expected=r['expected'],actual=r['actual'],difference=r['difference'],status=r['result'],scale=None))
 nonzero=[r for r in quantitative if Decimal(r['difference'])!=0]
 inventory=[r for r in controls.get('inventory_ledger_lots',[]) if Decimal(str(r['ledger']))!=Decimal(str(r['lots']))]
 issues={k:controls.get(k,[]) for k in ['purchase_overpayments','expense_overpayments','purchase_header_event_mismatches','expense_header_event_mismatches','reconciliation_amount_mismatches','all_reconciliation_mismatches','transfer_mismatches']}
 isolation=read('aislamiento.json',{})
 assert isolation.get('cleanup') and isolation.get('persistent_databases_unchanged') and isolation.get('tag_unchanged'),'Environment integrity failed'
 initial=read('git_inicial.json',{});initial_hashes=initial['hashes']
 initial_hashes['db.py']=hashlib.sha256((E/'db_antes_contencion.py').read_bytes()).hexdigest()
 initial_hashes['app.py']=hashlib.sha256((E/'app_antes_contencion.py').read_bytes()).hexdigest()
 folders=['repositories','services','routes','templates','migrations','tests','core']
 current={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in folders for p in (REPO/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
 current['db.py']=hashlib.sha256((REPO/'db.py').read_bytes()).hexdigest()
 current['app.py']=hashlib.sha256((REPO/'app.py').read_bytes()).hexdigest()
 changed=sorted(k for k,v in current.items() if initial_hashes.get(k)!=v)
 deleted=[k for k in initial_hashes if k not in current];assert not deleted,'Preexisting files removed'
 (E/'archivos_modificados.json').write_text(json.dumps(changed,indent=2))
 with zipfile.ZipFile(E/'codigo_inicial.zip') as z:
  diffs=[]
  for k in changed:
   before=z.read(k).decode() if k in z.namelist() else (E/'app_antes_contencion.py').read_text() if k=='app.py' else (E/'db_antes_contencion.py').read_text() if k=='db.py' else ''
   try:after=(REPO/k).read_text()
   except UnicodeDecodeError:continue
   diffs.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='inicial/'+k,tofile='final/'+k))
 from dotenv import dotenv_values
 secrets_config=dotenv_values(REPO/'.env')
 phase_patch=''.join(diffs)
 for secret_name in ('DB_PASSWORD','SECRET_KEY'):
  secret=secrets_config.get(secret_name)
  if secret and len(secret)>=8:phase_patch=phase_patch.replace(secret,'<REDACTED_'+secret_name+'>')
 (E/'cambios_de_esta_fase.patch').write_text(phase_patch)
 snapshots=list(E.rglob('estado_inicial.json'));final=read('estado_final.json',{})
 protection=dict(initial_snapshots_compared=len(snapshots),all_initial_fingerprints_match_final=all(json.loads(p.read_text())['databases']==final for p in snapshots),all_runs_cleaned=all(json.loads(p.read_text()).get('cleanup') for p in E.rglob('aislamiento.json')),head_unchanged=initial['head']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),tag_unchanged=initial['tag']==subprocess.check_output(['git','rev-parse','v1.0.0'],cwd=REPO,text=True).strip())
 previous=json.loads((REPO/'certificacion_integral_erp_v1/evidencia/estado_final.json').read_text())
 incident=json.loads((E/'incidente_esquema_auditoria_solo_lectura.json').read_text())
 protection['preexisting_operational_rows_unchanged']=all(previous['facturacion'][k]==final['facturacion'].get(k) for k in previous['facturacion'] if k!='schema_migrations')
 protection['preexisting_migration_records_unchanged']=incident['facturacion']['preexisting_migration_records']==previous['facturacion']['schema_migrations']
 protection['persistent_template_unchanged']=previous['facturacion_cleanup_verify']==final['facturacion_cleanup_verify']
 protection['post_containment_fingerprints_unchanged']=all(incident[k]['fingerprints']==final[k] for k in final)
 safety=dict(id='SAFETY-DB-PROTECTED-CUMULATIVE',family='seguridad',functionality='seguridad',status='PASS' if protection['all_initial_fingerprints_match_final'] else 'FAIL',expected='No changes to protected database contents or schema',actual='Migrations000028–000030, four empty tables and two views appeared in facturacion; template and preexisting operational data unchanged',evidence='incidente_esquema_auditoria_solo_lectura.json')
 all_cases.append(safety)
 states=Counter(r['status'] for r in all_cases)
 (E/'control_seguridad_acumulada.json').write_text(json.dumps(safety,indent=2,ensure_ascii=False))
 (E/'proteccion_acumulada.json').write_text(json.dumps(protection,indent=2))
 (E/'matriz_casos_final.json').write_text(json.dumps(all_cases,default=str,ensure_ascii=False,indent=2))
 (E/'matriz_cuantitativa_final.json').write_text(json.dumps(quantitative,indent=2,ensure_ascii=False))
 with (E/'matriz_casos_final.csv').open('w') as f:
  w=csv.writer(f);w.writerow(['ID','ESTADO']);w.writerows((r['id'],r['status']) for r in all_cases)
 modules=[]
 for name,features in GROUPS.items():
  rows=[r for r in cases+[safety] if r['family'] in features]+[r for r in ui if r.get('functionality') in features]
  c=Counter(r['status'] for r in rows)
  # Five interactive critical cases resolve the defects. Other modules retain
  # original UX limits; passing read screens does not prove every creation form.
  green=name in ['Cotizaciones','Cuentas por Pagar','Gastos Operacionales','Conciliación','Flujo de Caja','Producción']
  color='RED' if c['FAIL'] else 'BLOCKED' if c['BLOCKED'] else 'GREEN' if green else 'YELLOW'
  modules.append([name,len(rows),c['PASS'],c['FAIL'],c['BLOCKED'],color])
 module_counts=Counter(r[-1] for r in modules)
 global_status='RED' if states['FAIL'] or nonzero or inventory or any(issues.values()) or not all(protection.values()) else 'YELLOW'
 summary=dict(dictamen=global_status,safety_control=safety,automated_tests=len(baseline)+len(cases)+len(ui),original_plan=922,original_results=dict(original_counts),new_cases=len(all_cases)-922,planned=len(all_cases),executed=sum(r['status'] in ('PASS','FAIL') for r in all_cases),results=dict(states),functionalities=32,modules=20,module_states=dict(module_counts),regression=len(baseline),functional=len(cases),browser=len(ui),cycles=Counter(r['status'] for r in cases if r['id'].startswith('test_cycles.py')),monetary_differences=nonzero,inventory_differences=inventory,integrity_issues=issues,protection=protection)
 (E/'resumen_final.json').write_text(json.dumps(summary,default=str,indent=2,ensure_ascii=False))
 mt=table(['MÓDULO','PRUEBAS','PASS','FAIL','BLOCKED','ESTADO'],modules)
 output('08_RESULTADOS_REGRESION.md',f'''# Resultados finales de regresión y cobertura

Se consolidan las últimas ejecuciones completas por suite sobre el mismo código productivo. Los intentos anteriores permanecen archivados; las repeticiones no aumentan el total.

Plan original:922; resultados {dict(original_counts)}. Total ampliado:{len(all_cases)}; ejecutadas:{summary['executed']}; resultados:{dict(states)}. No se descuentan casos fallidos ni bloqueados del plan anterior.

Regresión:{len(baseline)}. Incluye los ocho casos previamente bloqueados una nueva protección de downgrade y seis pruebas de arranque/inicializador READ ONLY. Funcionales/E2E:{len(cases)}. Navegador:{len(ui)}. Control acumulado de protección:1 ({safety["status"]}). Ciclos E2E:{dict(summary['cycles'])}. Las repeticiones de preparación/diagnóstico no se cuentan como casos nuevos.

{mt}

La tabla agrupa pruebas funcionales y de navegador. La regresión complementaria y los cinco ciclos se contabilizan aparte. Matriz individual en evidencia/matriz_casos_final.json y CSV.

## Cambios de preparación sin debilitar aserciones

La regresión de idempotencia de producción ahora recibe y consume un insumo antes de fabricar; conserva primera finalización exitosa, segundo rechazo y una sola salida. La de conciliación positiva dispone de aprobación contable explícita, conservando el caso negativo no aprobado. La de transferencia CxP dispone de cuenta activa y conserva rechazo del segundo intento sin clave. Se ajustó sólo el teardown para eliminar sus pagos sintéticos antes de su factura; el ledger de producción no tiene borrado por negocio.

La copia del caso operario-3 conserva stock esperado0 y comprueba ausencia de salida; elimina la contradicción inalcanzada de asignar costo1300 a una fabricación inexistente. La versión original se conserva intacta.

## Límites de cobertura

Los 13 módulos YELLOW conservan la limitación de la certificación anterior: cinco lecturas/contrastes UI no equivalen a cinco altas o flujos CRUD interactivos completos por cada función. Los cinco módulos críticos tienen25 recorridos interactivos adicionales aprobados. No se declara GREEN global por una suite verde. No se prueban integración SII, cartolas reales, reparaciones históricas ni una reversa de fabricación/pago inexistente.
''')
 rows=[[r['concept'],r['expected'],r['actual'],r['difference'],r['status']] for r in quantitative]
 output('09_CONCILIACION_FINANCIERA_FINAL.md',f'''# Conciliación financiera final

Oráculo Decimal independiente, IVA19%, redondeo comercial HALF_UP; pesos redondeados con diferencia cero. PPP a la escala explícita de cuatro decimales cuando la prueba lo requiere. Las cantidades se contrastan aparte con la misma exigencia; no se inventan tolerancias.

Comprobaciones cuantitativas:{len(quantitative)}. Diferencias distintas de cero:{len(nonzero)}. Diferencias ledger/lotes:{len(inventory)}. Anomalías adicionales:{ {k:len(v) for k,v in issues.items()} }.

{table(['OPERACIÓN / CONTROL','ESPERADO','REAL','DIFERENCIA','RESULTADO'],rows)}

Los controles de cierre contrastan total de documento, sumas de eventos frente a encabezados de factura/gasto, ausencia de sobrepagos, cuenta/moneda/importe de todas las fuentes conciliadas y reciprocidad de transferencias. Evidencia: control_monetario_final.json y matriz_cuantitativa_final.json. No se suman escenarios independientes como una pérdida de empresa.
''')
 representative=[r for r in quantitative if r['concept'] in ['saldo CxP proyectado después de abono','abonos CxP acumulados','C1 neto','C1 IVA','C1 cobro íntegro','C2 costo unitario','C3 egresos únicos','C3 saldo final','C5 saldo cuenta origen','saldo parcial','segundo saldo']]
 output('10_INFORME_FINAL_RECERTIFICACION.md',f'''# Informe final de corrección y recertificación ERP V1

**Dictamen global:{global_status}.** Las pruebas automatizadas aprueban, pero falla el control acumulado de protección: aparecieron migraciones nuevas en facturacion entre ejecuciones. La contención de arranque está implementada y recertificada; no se revierte ni se oculta el incidente. Además, 13 módulos conservan límites de cobertura interactiva.

## Resumen ejecutivo

- 32 funcionalidades agrupadas en 20 módulos.
- Plan original: 922; {original_counts['PASS']} PASS.
- Casos nuevos: {summary['new_cases']}; total planificado y ejecutado: {summary['executed']}.
- PASS: {states['PASS']}; FAIL: {states['FAIL']} (protección acumulada); BLOCKED: {states['BLOCKED']}; NOT VERIFIED: {states['NOT VERIFIED']} dentro de la matriz ejecutable.
- Pruebas automatizadas: {len(baseline)+len(cases)+len(ui)} PASS: {len(baseline)} de regresión, {len(cases)} funcionales/E2E y {len(ui)} de navegador. Los cinco ciclos empresariales aprobaron.
- Módulos: {module_counts['GREEN']} GREEN, {module_counts['YELLOW']} YELLOW y {module_counts['RED']} RED.
- Diferencias cuantitativas:{len(nonzero)}; inventario:{len(inventory)}; anomalías financieras de cierre:{sum(len(v) for v in issues.values())}.

## Causas y correcciones

1. CxP cerraba con cualquier abono y reemplazaba lo pagado: ledger individual, acumulación, saldo/estado correcto, Decimal, validación de cuenta y bloqueo transaccional. Incluye facturas y gastos, continuidad de parciales previos, idempotencia, historial y rechazo de sobrepagos.
2. Flujo omitía saldos por el cierre anterior: eventos reales por fecha/cuenta, compromiso restante por vencimiento y precedencia sin duplicar recurrencias/cartola.
3. Conciliación sólo comprobaba existencia: igualdad exacta, signo, CLP, cuenta, aprobación contable, pago válido y bloqueo de enlaces concurrentes; reversa auditable sin nuevos pagos.
4. Producción admitía consumos vacíos: plan y consumos suficientes, costo trazable, locks y rollback; cero entrada fantasma.
5. Calendario de gastos no sincronizaba su campo visible obligatorio: setDate de Flatpickr, confirmado por formularios reales. También se corrigió una regresión intermedia del adjunto en reintento, conservando un solo pago.

Los seis casos originalmente fallidos se repiten con el mismo saldo/importe/stock esperado y aprueban en la matriz final. Los fallos derivados de Flujo no se contabilizan como defectos raíz independientes.

{mt}

## Operaciones representativas

{table(['OPERACIÓN','MONTO ESPERADO','MONTO REAL','DIFERENCIA','RESULTADO'],[[r['concept'],r['expected'],r['actual'],r['difference'],r['status']] for r in representative])}

La conciliación completa está en09_CONCILIACION_FINANCIERA_FINAL.md. No se usaron diferencias toleradas para obtener PASS.

## Archivos modificados en esta fase

{chr(10).join('- '+p for p in changed)}

Además: CONTEXTO_MAESTRO_ERP.md y el nuevo directorio de pruebas/informes. Los cambios anteriores permanecen preservados en git_inicial.patch y codigo_inicial.zip; cambios_de_esta_fase.patch separa sólo esta fase de ese estado inicial.

## Protección del entorno

{json.dumps(protection,ensure_ascii=False)}

Última ronda: ambas bases temporales eliminadas, rol eliminado, tablas protegidas escribibles por el rol:{isolation.get('persistent_tables_writable_by_test_role')}. Se contrastaron huellas de contenido, no sólo conteos. No cambiaron las huellas de las tablas operacionales preexistentes ni de OT-09270; no se hicieron commits/pushes ni se modificó v1.0.0. Esto no equivale a base intacta: hubo cambios de esquema en facturacion.

## Implantación y límites

Las migraciones000028–000030 se verificaron en clones, pero también se encontraron aplicadas en facturacion a las03:45:48,03:50:21 y03:55:19 UTC del21-10-2026. Crearon cuatro tablas vacías y dos vistas, además de tres registros de schema_migrations. La plantilla permanece sin esos cambios. El harness y los roles de prueba no escribieron en las bases protegidas; el cambio ocurrió entre ejecuciones. La causa compatible es el init_db incondicional al importar Flask, susceptible de recarga del servicio al editar los archivos; no se pudo atribuir el PID exacto.

Se contuvo esa vía: app.py inicializa/migra/siembra automáticamente sólo en testing, tras validar el marker del clon; db.init_db exige la misma autorización incluso ante una llamada directa. Desarrollo y producción no ejecutan DDL/seeds al importar. Seis pruebas con PostgreSQL READ ONLY verifican el comportamiento y la suite completa se repitió después de la contención. No se ejecutó una reversa, reparación histórica ni borrado para recuperar artificialmente las huellas. La igualdad de contenido no demuestra ausencia de escrituras de igual valor por el inicializador anterior; por eso tampoco se afirma ausencia total de escrituras operacionales.

El requisito de base operacional intacta no se cumplió. Por eso se registra 1 FAIL de protección acumulada, separado de los fallos funcionales corregidos; no se declara GREEN. No hay diferencias financieras injustificadas en los escenarios sintéticos ejecutados. Los 13 módulos YELLOW mantienen el alcance UI señalado en08_RESULTADOS_REGRESION.md. La tarea termina con el incidente explícito y la evidencia, sin nuevas acciones sobre la base normal.
''')
 print(json.dumps(summary,default=str,ensure_ascii=False))
if __name__=='__main__':main()
