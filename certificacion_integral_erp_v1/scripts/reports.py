"""Render the certification dossier strictly from recorded results, never invent PASS."""
import json,collections,xml.etree.ElementTree as ET,re
from pathlib import Path
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[1]; E=ROOT/'evidencia'
GROUPS={
'Productos':['productos','excel_productos'],'Proveedores':['proveedores'],'Clientes':['clientes'],
'Órdenes de compra':['ordenes_compra'],'Recepción':['recepcion'],'Inventario y Kardex':['inventario','ajustes','trazabilidad'],
'Costos PPP/FIFO y precios':['ppp_fifo','precios'],'Cotizaciones':['cotizaciones'],'Ventas':['ventas'],
'Preparación y despacho':['despacho','embalajes'],'Producción':['recetas','produccion','operario','agenda'],
'Cuentas por Cobrar':['cxc'],'Cuentas por Pagar':['cxp'],'Gastos Operacionales':['gastos'],
'Deudas':['deudas','excel_deudas'],'Cuentas bancarias':['bancos'],'Conciliación':['conciliacion','excel_bancos'],
'Flujo de Caja':['flujo_caja'],'Reportes':['reportes'],'Usuarios, permisos y administración':['seguridad','usuarios_roles','informacion_empresa']}
def read(name,default):
    p=E/name
    return json.loads(p.read_text()) if p.exists() else default
def write(name,text): (ROOT/name).write_text(text,encoding='utf-8')
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(str(v).replace('|','/').replace('\n',' ') for v in row)+' |'for row in rows])
def main():
    cases=[json.loads(s) for s in (E/'casos.jsonl').read_text().splitlines()] if (E/'casos.jsonl').exists() else []
    # Unique final outcomes; previous attempts are kept in separate directories.
    cases=list({r['id']:r for r in cases}.values())
    ui=read('navegador.json',[])+read('navegador_ampliado.json',[])
    isolation=read('aislamiento.json',{})
    controls=read('control_monetario_final.json',{})
    baseline=[]
    if (E/'baseline.xml').exists():
        for tc in ET.parse(E/'baseline.xml').getroot().iter('testcase'):
            failed=tc.find('failure');error=tc.find('error');skipped=tc.find('skipped')
            baseline.append({'id':tc.attrib['classname']+'::'+tc.attrib['name'],'status':'FAIL' if failed is not None or error is not None else 'BLOCKED' if skipped is not None else 'PASS','detail':(failed.text or '') if failed is not None else ''})
    (E/'baseline_casos.json').write_text(json.dumps(baseline,indent=2,ensure_ascii=False))
    excluded=[]
    text=(ROOT.parents[0]/'tests/integration/test_migrations_phase4.py').read_text()
    for name in re.findall(r'^def (test_\w+)\(',text,re.M):excluded.append({'id':name,'status':'BLOCKED','reason':'Fixture heredada crea base auxiliar fija fuera del namespace protegido; no se ejecutó.'})
    all_results=cases+ui+baseline+excluded
    counts=collections.Counter(r['status'] for r in all_results)
    # Complete UI workflow verification remains stricter than viewing a table.
    # Only quotations have 5 interactive write/form + persistence cases here.
    modules=[]
    for name,features in GROUPS.items():
        back=[r for r in cases if r['functionality'] in features]
        front=[r for r in ui if r['functionality'] in features]
        records=back+front; counter=collections.Counter(r['status'] for r in records)
        if counter['FAIL']:status='RED'
        elif not back or all(r['status'] in ['BLOCKED','NOT VERIFIED'] for r in records):status='BLOCKED'
        elif name=='Cotizaciones' and len(back)>=5 and counter['BLOCKED']==0 and counter['NOT VERIFIED']==0 and sum(r['id'].startswith('UI-FORM-COT-') and r['status']=='PASS'for r in front)==5:status='GREEN'
        else:status='YELLOW'
        if name=='Flujo de Caja' and any(r['functionality']=='cxp' and any(c['status']=='FAIL' and 'proyectado' in c['concept'] for c in r.get('checks',[])) for r in cases):
            status='RED'
        modules.append({'module':name,'features':features,'tests':len(records),'pass':counter['PASS'],'fail':counter['FAIL'],'blocked':counter['BLOCKED'],'not_verified':counter['NOT VERIFIED'],'status':status})
    table_modules=table(['MÓDULO','PRUEBAS','PASS','FAIL','BLOCKED','NOT VERIFIED','ESTADO'],[[m[k] for k in ['module','tests','pass','fail','blocked','not_verified','status']] for m in modules])
    monetary=[];quantities=[]
    for c in cases:
        for check in c.get('checks',[]):
            if check.get('difference') is not None:
                record={'id':c['id'],'operation':check['concept'],'expected':check['expected'],'actual':check['actual'],'difference':check['difference'],'result':check['status']}
                financial=bool(re.search(r'costo|PPP|neto|IVA|total|importe|monto|saldo|precio|banco|principal|utilidad|ingreso|egreso|CxP|CxC|abono|pago|cobro|brut|valor|regla|período',check['concept'],re.I))
                (monetary if financial else quantities).append(record)
    control_sets=[controls]
    for folder in ['ronda_integral','ronda_dirigida']:
        p=E/folder/'control_monetario_final.json'
        if p.exists():control_sets.append(json.loads(p.read_text()))
    for num,control in enumerate(control_sets):
        for row in control.get('reconciliation_amount_mismatches',[]):
            expected=Decimal(str(row['payment_amount']));actual=Decimal(str(row['amount']))
            monetary.append({'id':f'cierre-{num}-conciliacion-{row["id"]}','operation':'Importe bancario frente a cobro ERP conciliado','expected':str(expected),'actual':str(actual),'difference':str(actual-expected),'result':'FAIL'})
        for row in control.get('purchase_overpayments',[]):
            excess=Decimal(str(row['payment_amount']))-Decimal(str(row['invoice_amount']))
            monetary.append({'id':f'cierre-{num}-sobrepago-{row["id"]}','operation':'Exceso pagado sobre obligación CxP','expected':'0','actual':str(excess),'difference':str(excess),'result':'FAIL'})
    (E/'matriz_cantidades.json').write_text(json.dumps(quantities,indent=2,ensure_ascii=False))
    (E/'matriz_monetaria.json').write_text(json.dumps(monetary,indent=2,ensure_ascii=False))
    moneytable=table(['OPERACIÓN / CASO','MONTO ESPERADO','MONTO REAL','DIFERENCIA','RESULTADO'],[[r['id']+' / '+r['operation'],r['expected'],r['actual'],r['difference'],r['result']]for r in monetary])
    failed=[r for r in cases+ui if r['status']=='FAIL']
    baseline_failed=[r for r in baseline if r['status']=='FAIL']
    cycle_rows=[r for r in cases if r['functionality']=='E2E']
    final={'functionalities':sum(len(v)for v in GROUPS.values()),'modules':20,'planned':len(all_results),'executed':len(cases)+len(ui)+len(baseline),'counts':dict(counts),'module_states':dict(collections.Counter(m['status']for m in modules)),'cycles':{r['id']:r['status']for r in cycle_rows},'isolation':isolation,'global':'RED' if counts['FAIL'] else 'YELLOW','monetary_checks':len(monetary),'monetary_differences':[r for r in monetary if Decimal(str(r['difference']))!=0],'inventory_differences':[r for r in quantities if Decimal(str(r['difference']))!=0]}
    (E/'resumen.json').write_text(json.dumps(final,ensure_ascii=False,indent=2))
    write('01_PLAN_PRUEBAS.md',f'''# Plan de certificación ERP V1

Alcance: versión de trabajo Python/Flask, Jinja/JavaScript y PostgreSQL monotenant, con modificaciones previas sin commit. HEAD y tag exactos se conservan en `evidencia/estado_inicial.json`. No se equipara el tag v1.0.0 a este árbol modificado.

Se identificaron {final['functionalities']} familias funcionales agrupadas en 20 módulos. Se planificaron cinco escenarios nuevos por familia, cinco ciclos empresariales completos, cinco comprobaciones de navegador por familia y cinco formularios adicionales de cotización, y la regresión existente como soporte, no como sustituto de un oráculo financiero independiente. Ocho pruebas heredadas de migración se planifican BLOCKED por incompatibilidad con el namespace de aislamiento.

Método: operación normal, valores diferentes, límite/validación, integración y repetición/reversa/complejidad. Los detalles ejecutables son `tests/test_certification.py` y `tests/test_cycles.py`; `scripts/reference.py` calcula importes independientemente de servicios monetarios productivos. No se aceptan tolerancias de pesos: Decimal ROUND_HALF_UP, subtotal a 0,01, neto/IVA a 1 peso; PPP a 0,0001 conforme al valor expuesto por el repositorio.

La preparación usa una copia de archivos fuera del workspace productivo y una base efímera marcada, vaciada dentro del clon. El usuario de pruebas carece de permisos de escritura en las dos bases protegidas y no puede crear bases ni roles. `sitecustomize.py` rechaza conexiones externas al clon. Las migraciones pendientes y uploads sólo ocurren dentro de ese entorno. `run.py` limpia base, rol, procesos y filesystem en finally, también al fallar pruebas.

Datos iniciales: 10 clientes, 10 proveedores, 20 productos, lotes, materias primas, terminados y stock cero; dos bancos ficticios. Los datos de volumen adicionales para paginación son explícitamente sintéticos. Inventario inicial y obligaciones de apertura están cuantificados en `datos_sinteticos.json`. Catálogos, usuarios y secuencias son fixtures; sus ajustes durante la preparación no modifican el ERP.

Los fallos originales de preparación y de adaptadores se conservan en carpetas de intentos. Los resultados finales se contabilizan una vez por identificador; los intentos previos no se suman como nuevas funcionalidades aprobadas.

Comando reproducible: `venv/bin/python certificacion_integral_erp_v1/scripts/run.py`. Herramientas instaladas existentes; no se instalaron dependencias. Ninguna corrección productiva, commit, push, modificación de tag o de OT reales forma parte de la certificación.
''')
    matrix=table(['ID','FUNCIÓN','VARIANTE','ESTADO','EVIDENCIA'],[[r['id'],r['functionality'],r.get('variant'),r['status'],'casos.jsonl / navegador.json']for r in cases+ui])
    write('02_MATRIZ_FUNCIONAL.md','# Matriz funcional ejecutada\n\n'+table_modules+'\n\n## Casos individuales\n\n'+matrix+'\n\nLa regresión complementaria está individualizada en `evidencia/baseline_casos.json`; las exclusiones de migración se explican en el informe final. Cada caso JSON conserva datos iniciales, peticiones, expectativas, resultados, diferencia y traceback cuando corresponde. Una pantalla disponible o HTTP 200 por sí solos no otorgan PASS.\n')
    def section(filename,title,features,notes):
        selected=[r for r in cases if r['functionality'] in features]
        details=[]
        for r in selected:
            checks='; '.join(f"{c['concept']}: esperado {c['expected']}, real {c['actual']}, diferencia {c.get('difference')}"for c in r.get('checks',[]))
            details.append([r['id'],r['status'],checks or r.get('actual','')[-700:]])
        write(filename,'# '+title+'\n\n'+notes+'\n\n'+table(['CASO','ESTADO','EXPECTATIVA / REAL'],details)+'\n\nLos detalles completos y acciones están en `evidencia/casos.jsonl`. Los resultados de ciclos integrados se documentan por separado.\n')
    section('03_RESULTADOS_COMPRAS_INVENTARIO.md','Compras, recepción e inventario',['productos','proveedores','ordenes_compra','recepcion','inventario','ppp_fifo','ajustes','trazabilidad'],'Se comprueban cantidades persistidas, costo de entrada, creación de obligación, stock antes/después, costo promedio, reservas, control de faltantes y capas FIFO. FIFO físico no se interpreta como costo específico: las salidas contables usan PPP. Los controles finales de lotes/ledger están en control_monetario_final.json.')
    section('04_RESULTADOS_COTIZACIONES_VENTAS.md','Cotizaciones, ventas, despacho y cobros',['clientes','cotizaciones','ventas','despacho','embalajes','cxc','precios'],'Ejemplo obligatorio: 3 × 10.000, descuento 10%, neto 27.000, IVA 5.130, total 32.130. Se contrastan persistencia, formulario, impresión y conversión. Se incluyen descuento 100%, valores grandes, faltantes, selección manual de pedido, congelación de costo y reintentos.')
    section('05_RESULTADOS_PRODUCCION.md','Recetas y fabricación',['recetas','produccion','operario','agenda'],'Se comprueban receta, cantidades de materias primas, costo PPP, costo del producto terminado y ausencia de duplicaciones. Se cubren ruta administrativa, operario y agenda. Los consumos no crean existencias artificiales y los pedidos sin cobertura se mantienen bloqueados.')
    section('06_RESULTADOS_FINANZAS.md','CxC, CxP, gastos y deudas',['cxc','cxp','gastos','deudas','excel_deudas'],'Gastos Operacionales se mantiene donde está en el ERP; no se modificó su navegación ni lógica. La certificación distingue importe de la regla y monto real del período. Se contrastan obligaciones, abonos, cierre y saldos; ningún pago se considera correcto sólo por una redirección.')
    section('07_RESULTADOS_BANCOS_FLUJO_CAJA.md','Bancos, conciliación y Flujo de Caja',['bancos','conciliacion','excel_bancos','flujo_caja'],'Las cartolas se crean en cuentas ficticias. Se comparan saldo inicial + abonos − cargos, transferencias internas y precedencia ERP/banco para evitar duplicaciones. La aceptación de una conciliación por la API no certifica igualdad de importes; se prueba explícitamente.')
    section('08_RESULTADOS_REPORTERIA.md','Reportes y exportaciones',['reportes','excel_productos','excel_bancos','excel_deudas'],'Se verifican registros persistidos, lectura de Excel con openpyxl y presencia de montos/identificadores propios. La regresión aporta controles de filtros/paginación. No todas las combinaciones API/pantalla/Excel de todos los reportes se consideran certificadas: se limita cada afirmación a los casos registrados.')
    write('09_RESULTADOS_UX_NAVEGADOR.md','# Validación real en navegador aislado\n\nPlaywright y Chromium existentes, puerto 15021, cuenta sintética y mismo usuario PostgreSQL restringido. El proceso verifica que app.root_path corresponde a la copia temporal; se bloquean accesos locales a otros puertos, incluido el ERP normal.\n\n'+table(['CASO','FUNCIÓN','ESTADO','RESULTADO'],[[r['id'],r['functionality'],r['status'],r.get('error',str(r.get('actual','')))[:500]]for r in ui])+'\n\nSe prueban cinco formularios interactivos de cotización con persistencia y cinco visualizaciones por pantalla cubierta. Las demás comprobaciones de pantalla son lecturas/contrastes, no cinco altas interactivas completas de cada módulo. Esa limitación mantiene módulos YELLOW y no se sustituye con un PASS de API. Las capturas, PDF y manifiesto identifican los datos sintéticos.\n')
    write('10_CONCILIACION_MATEMATICA.md','# Conciliación matemática independiente\n\nOráculo: scripts/reference.py, Decimal y ROUND_HALF_UP. No importa services.money ni funciones de precios para producir los valores esperados. PPP se compara a su escala explícita de cuatro decimales. Los valores enteros ya redondeados requieren diferencia cero.\n\n'+moneytable+'\n\n## Cantidades e inventario (unidades, no pesos)\n\n'+table(['CASO / OPERACIÓN','ESPERADO','REAL','DIFERENCIA','ESTADO'],[[r['id']+' / '+r['operation'],r['expected'],r['actual'],r['difference'],r['result']]for r in quantities])+'\n\nControles de cierre: `evidencia/control_monetario_final.json` y versiones de cada ronda. Los sobrepagos y diferencias de conciliación se registran aunque el ERP los acepte. Los indicadores booleanos fallidos no se convierten artificialmente en diferencias monetarias cero.\n')
    write('11_RESULTADOS_E2E.md','# Cinco ciclos empresariales independientes\n\n'+table(['CICLO','ESTADO','COMPROBACIONES'],[[r['id'],r['status'],'; '.join(f"{c['concept']}: {c['actual']} (esperado {c['expected']})" for c in r.get('checks',[]))] for r in cycle_rows])+'\n\nC1 compra/recepción/venta/cobro/banco; C2 compra/receta/fabricación/venta; C3 dos períodos recurrentes/pagos/banco; C4 dos ventas con demanda conjunta superior al físico y selección manual; C5 deuda, gasto, compra, venta, pagos, transferencia y conciliación. Un ciclo aprobado no invalida las pruebas negativas fallidas del mismo módulo.\n')
    defects='''# Defectos y límites encontrados

**No se aplicó ninguna corrección productiva.** Los defectos se registran para autorización posterior.

## Hallazgos prioritarios confirmados

- CxP admite un pago superior a la obligación: prueba de $11.901 frente a factura de $11.900. Impacto: exceso de $1 aceptado; revisar validación transaccional y límites del saldo en registrar_pago_factura/register_purchase_payment. Propuesta: validar importe finito/positivo y no superior al saldo bajo bloqueo, sin modificar documentos históricos durante la certificación.
- Conciliación admite asociar abono bancario de $11.901 con cobro ERP de $11.900. Impacto: diferencia de $1 se considera conciliada. Causa probable: reconcile_transaction verifica existencia/estado, sin contrastar importe/signo/cuenta como condición de conciliación. Propuesta: validar correspondencia y definir explícitamente el flujo de diferencias bancarias legítimas.
- CxP marca como Pagada una factura abonada parcialmente y rechaza el abono posterior. Impacto: omisión de saldo proyectado y bloqueo del cierre legítimo; escenarios de $2.000/$5.900/$3.000 sobre $11.900. Propuesta: registrar y acumular pagos transaccionales, derivar estado del saldo y conservar historial.
- Operario permite finalizar una OT sin consumo de materias primas registrado: el escenario negativo genera 3 unidades terminadas cuando debía bloquearse, con costo 0. Los cuatro recorridos con consumo previo se ejecutan aparte. Propuesta: validar cumplimiento de consumos y costo positivo/trazable antes del ingreso final, dentro de una única transacción. No se ejecutó reparación.

## Todos los casos finales fallidos

'''
    for i,r in enumerate(failed,1):defects+=f"### F{i:03} — {r['id']}\n\nEstado FAIL. Función {r['functionality']}. Resultado: `{r.get('error',r.get('actual',''))[-1400:]}`\n\nEvidencia completa: casos.jsonl o navegador.json. Las aserciones anteriores al fallo se conservan y no se presentan como aprobación del resto del escenario.\n\n"
    defects+='## Regresión complementaria fallida\n\n'+table(['CASO','RESULTADO'],[[r['id'],r['detail'][-900:]]for r in baseline_failed])
    defects+='\n\nLos intentos previos incluyen errores de fixtures/adaptadores (catálogos ausentes, secuencia de usuarios, campos obligatorios, parser de miles y uso incorrecto de contratos Python). Se corrigieron exclusivamente pruebas y preparación, y se repitieron en clones nuevos; no son defectos productivos confirmados. La falta de datos suficientes para una aserción de paginación histórica no certifica un fallo del paginador.\n'
    defects+='\n## Alcance no verificado\n\nNo se certifican cartolas externas, SII, contratos reales ni costos no registrados. Tampoco cinco formularios interactivos de alta para cada módulo ni todas las combinaciones de filtros, concurrencia y reversas. Las pruebas de migración auxiliares fijas están BLOCKED por seguridad. No declarar GREEN global.\n'
    write('12_DEFECTOS_ENCONTRADOS.md',defects)
    summary=f'''# Informe final de certificación ERP V1

**Dictamen global: {final['global']}. No puede responderse afirmativamente que todos los valores y procesos sean confiables sin restricciones.** Existen fallos financieros confirmados y límites de interfaz/cobertura.

- Funcionalidades agrupadas: {final['functionalities']}, en 20 módulos.
- Pruebas planificadas/individualizadas: {final['planned']}.
- Pruebas ejecutadas en la ronda final: {final['executed']} (sin contar como nuevas las repeticiones de preparación/fixtures).
- PASS: {counts['PASS']}; FAIL: {counts['FAIL']}; BLOCKED: {counts['BLOCKED']}; NOT VERIFIED: {counts['NOT VERIFIED']}.
- Estados de módulos: {dict(final['module_states'])}.
- Comprobaciones cuantitativas con diferencia explícita: {len(monetary)}; diferencias distintas de cero: {len(final['monetary_differences'])}.
- Diferencias de cantidades en escenarios negativos: {len(final['inventory_differences'])}; consultar matriz_cantidades.json. La igualdad ledger/lotes no valida por sí sola la legitimidad de una fabricación.
- Cinco ciclos integrados: {collections.Counter(r['status']for r in cycle_rows)}.

Las cifras anteriores incluyen regresión complementaria y certificación nueva, distinguidas en sus XML/logs. No se asume que una regresión verde sea certificación financiera. Los resultados por módulo de la siguiente tabla corresponden a casos nuevos y navegador; el resto está en baseline_casos.json.

{table_modules}

## Operaciones monetarias relevantes

'''
    chosen=[r for r in monetary if r['result']=='FAIL']+[r for r in monetary if 'C1 'in r['operation'] or 'C2 'in r['operation'] or 'C3 'in r['operation'] or 'C5 'in r['operation']]
    summary+=table(['OPERACIÓN','MONTO ESPERADO','MONTO REAL','DIFERENCIA','RESULTADO'],[[r['operation'],r['expected'],r['actual'],r['difference'],r['result']]for r in chosen])
    summary+='\n\nLa tabla completa está en 10_CONCILIACION_MATEMATICA.md. Inventario y diferencias de conciliación/pagos están individualizados en control_monetario_final.json.\n\n## Protección del entorno\n\n'
    summary+='Flujo de Caja se clasifica RED por los fallos integrados de CxP-1 y CxP-2: omite $9.900 y $6.000 pendientes. Sus diez comprobaciones directas pasan; estos dos casos se cuentan una sola vez, en CxP. No sumar las diferencias como pérdida real: son verificaciones sintéticas, algunas repetidas en clones distintos.\n\n'
    summary+=f"Bases protegidas con huellas íntegras antes/después: **{isolation.get('persistent_databases_unchanged')}**. Código productivo idéntico: **{isolation.get('source_unchanged')}**. Tag idéntico: **{isolation.get('tag_unchanged')}**. Eliminación de DB/rol temporal: **{isolation.get('cleanup')}**. Usuario temporal: permisos de escritura en tablas protegidas {isolation.get('persistent_tables_writable_by_test_role')}. No se ejecutaron migraciones ni operaciones mutables en facturacion o su plantilla; no se modificó OT-09270 ni otros documentos reales.\n"
    summary+='\n## Condición de cierre\n\nLa certificación termina con este informe y la evidencia. No se corrigieron funciones ni se realizaron commits o pushes. Se requiere autorización separada para reparar defectos. Las limitaciones de datos y de interfaz quedan explícitas; no se transforma NOT VERIFIED en GREEN.\n'
    write('13_INFORME_FINAL_CERTIFICACION.md',summary)
    print(json.dumps({k:v for k,v in final.items() if k not in ['isolation','monetary_differences','cycles']},ensure_ascii=False))
if __name__=='__main__':main()
