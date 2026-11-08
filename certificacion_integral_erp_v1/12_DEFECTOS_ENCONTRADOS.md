# Defectos y límites encontrados

**No se aplicó ninguna corrección productiva.** Los defectos se registran para autorización posterior.

## Hallazgos prioritarios confirmados

- CxP admite un pago superior a la obligación: prueba de $11.901 frente a factura de $11.900. Impacto: exceso de $1 aceptado; revisar validación transaccional y límites del saldo en registrar_pago_factura/register_purchase_payment. Propuesta: validar importe finito/positivo y no superior al saldo bajo bloqueo, sin modificar documentos históricos durante la certificación.
- Conciliación admite asociar abono bancario de $11.901 con cobro ERP de $11.900. Impacto: diferencia de $1 se considera conciliada. Causa probable: reconcile_transaction verifica existencia/estado, sin contrastar importe/signo/cuenta como condición de conciliación. Propuesta: validar correspondencia y definir explícitamente el flujo de diferencias bancarias legítimas.
- CxP marca como Pagada una factura abonada parcialmente y rechaza el abono posterior. Impacto: omisión de saldo proyectado y bloqueo del cierre legítimo; escenarios de $2.000/$5.900/$3.000 sobre $11.900. Propuesta: registrar y acumular pagos transaccionales, derivar estado del saldo y conservar historial.
- Operario permite finalizar una OT sin consumo de materias primas registrado: el escenario negativo genera 3 unidades terminadas cuando debía bloquearse, con costo 0. Los cuatro recorridos con consumo previo se ejecutan aparte. Propuesta: validar cumplimiento de consumos y costo positivo/trazable antes del ingreso final, dentro de una única transacción. No se ejecutó reparación.

## Todos los casos finales fallidos

### F001 — test_certification.py::test_business_feature[1-cxp]

Estado FAIL. Función cxp. Resultado: `n('2026-10-01','2026-11-30',bank_account_id=account)
>                   check('saldo CxP proyectado después de abono',flow['kpis']['projected_outflows'],D(11900-amount))

/home/cplaza/Desarrollo/Proeycto-Gestion-Negocio/sistema-facturacion/certificacion_integral_erp_v1/tests/test_certification.py:253: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

label = 'saldo CxP proyectado después de abono', actual = Decimal('0.00')
expected = Decimal('9900'), scale = None

    def verify(label,actual,expected,scale=None):
        from decimal import Decimal,ROUND_HALF_UP
        money=isinstance(expected,Decimal)
        diff=None
        if money:
            actual=Decimal(str(actual))
            if scale:actual=actual.quantize(Decimal(scale),rounding=ROUND_HALF_UP)
            diff=actual-expected
        request.node.cert_checks.append({'concept':label,'expected':expected,'actual':actual,'difference':diff,'scale':scale,'status':'PASS' if actual==expected else 'FAIL'})
>       assert actual==expected,f'{label}: expected={expected}, actual={actual}, delta={diff}'
E       AssertionError: saldo CxP proyectado después de abono: expected=9900, actual=0.00, delta=-9900.00
E       assert Decimal('0.00') == Decimal('9900')

/home/cplaza/Desarrollo/Proeycto-Gestion-Negocio/sistema-facturacion/certificacion_integral_erp_v1/tests/conftest.py:30: AssertionError`

Evidencia completa: casos.jsonl o navegador.json. Las aserciones anteriores al fallo se conservan y no se presentan como aprobación del resto del escenario.

### F002 — test_certification.py::test_business_feature[2-cxp]

Estado FAIL. Función cxp. Resultado: `n('2026-10-01','2026-11-30',bank_account_id=account)
>                   check('saldo CxP proyectado después de abono',flow['kpis']['projected_outflows'],D(11900-amount))

/home/cplaza/Desarrollo/Proeycto-Gestion-Negocio/sistema-facturacion/certificacion_integral_erp_v1/tests/test_certification.py:253: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

label = 'saldo CxP proyectado después de abono', actual = Decimal('0.00')
expected = Decimal('6000'), scale = None

    def verify(label,actual,expected,scale=None):
        from decimal import Decimal,ROUND_HALF_UP
        money=isinstance(expected,Decimal)
        diff=None
        if money:
            actual=Decimal(str(actual))
            if scale:actual=actual.quantize(Decimal(scale),rounding=ROUND_HALF_UP)
            diff=actual-expected
        request.node.cert_checks.append({'concept':label,'expected':expected,'actual':actual,'difference':diff,'scale':scale,'status':'PASS' if actual==expected else 'FAIL'})
>       assert actual==expected,f'{label}: expected={expected}, actual={actual}, delta={diff}'
E       AssertionError: saldo CxP proyectado después de abono: expected=6000, actual=0.00, delta=-6000.00
E       assert Decimal('0.00') == Decimal('6000')

/home/cplaza/Desarrollo/Proeycto-Gestion-Negocio/sistema-facturacion/certificacion_integral_erp_v1/tests/conftest.py:30: AssertionError`

Evidencia completa: casos.jsonl o navegador.json. Las aserciones anteriores al fallo se conservan y no se presentan como aprobación del resto del escenario.

### F003 — test_certification.py::test_business_feature[3-cxp]

Estado FAIL. Función cxp. Resultado: `=%s',(inv['id'],))[0]
>           if v==3:check('sobrepago CxP rechazado',changed['payment_amount'] or 0,D(0))
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/cplaza/Desarrollo/Proeycto-Gestion-Negocio/sistema-facturacion/certificacion_integral_erp_v1/tests/test_certification.py:247: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

label = 'sobrepago CxP rechazado', actual = Decimal('11901.0')
expected = Decimal('0'), scale = None

    def verify(label,actual,expected,scale=None):
        from decimal import Decimal,ROUND_HALF_UP
        money=isinstance(expected,Decimal)
        diff=None
        if money:
            actual=Decimal(str(actual))
            if scale:actual=actual.quantize(Decimal(scale),rounding=ROUND_HALF_UP)
            diff=actual-expected
        request.node.cert_checks.append({'concept':label,'expected':expected,'actual':actual,'difference':diff,'scale':scale,'status':'PASS' if actual==expected else 'FAIL'})
>       assert actual==expected,f'{label}: expected={expected}, actual={actual}, delta={diff}'
E       AssertionError: sobrepago CxP rechazado: expected=0, actual=11901.0, delta=11901.0
E       assert Decimal('11901.0') == Decimal('0')

/home/cplaza/Desarrollo/Proeycto-Gestion-Negocio/sistema-facturacion/certificacion_integral_erp_v1/tests/conftest.py:30: AssertionError`

Evidencia completa: casos.jsonl o navegador.json. Las aserciones anteriores al fallo se conservan y no se presentan como aprobación del resto del escenario.

### F004 — test_certification.py::test_business_feature[3-conciliacion]

Estado FAIL. Función conciliacion. Resultado: `f v!=3 else 11901)
            before=query('SELECT count(*) n FROM sale_payment_items')[0]['n'];ok,msg=reconcile_transaction(tx['id'],'SALE_PAYMENT',items[0]['id'],'CERT')
>           check('conciliación monto compatible',ok,v!=3)

/home/cplaza/Desarrollo/Proeycto-Gestion-Negocio/sistema-facturacion/certificacion_integral_erp_v1/tests/test_certification.py:291: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

label = 'conciliación monto compatible', actual = True, expected = False
scale = None

    def verify(label,actual,expected,scale=None):
        from decimal import Decimal,ROUND_HALF_UP
        money=isinstance(expected,Decimal)
        diff=None
        if money:
            actual=Decimal(str(actual))
            if scale:actual=actual.quantize(Decimal(scale),rounding=ROUND_HALF_UP)
            diff=actual-expected
        request.node.cert_checks.append({'concept':label,'expected':expected,'actual':actual,'difference':diff,'scale':scale,'status':'PASS' if actual==expected else 'FAIL'})
>       assert actual==expected,f'{label}: expected={expected}, actual={actual}, delta={diff}'
E       AssertionError: conciliación monto compatible: expected=False, actual=True, delta=None
E       assert True == False

/home/cplaza/Desarrollo/Proeycto-Gestion-Negocio/sistema-facturacion/certificacion_integral_erp_v1/tests/conftest.py:30: AssertionError`

Evidencia completa: casos.jsonl o navegador.json. Las aserciones anteriores al fallo se conservan y no se presentan como aprobación del resto del escenario.

### F005 — test_certification.py::test_business_feature[3-operario]

Estado FAIL. Función operario. Resultado: `ermissions']['operario_bodega']=True
            client.post(f'/operario/ot/{oid}/finalizar',data={'output_lot_number':tag(),'actual_quantity':v})
>           check('operario salida PT',physical(finished),D(0 if v==3 else v))

/home/cplaza/Desarrollo/Proeycto-Gestion-Negocio/sistema-facturacion/certificacion_integral_erp_v1/tests/test_certification.py:350: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

label = 'operario salida PT', actual = Decimal('3.0'), expected = Decimal('0')
scale = None

    def verify(label,actual,expected,scale=None):
        from decimal import Decimal,ROUND_HALF_UP
        money=isinstance(expected,Decimal)
        diff=None
        if money:
            actual=Decimal(str(actual))
            if scale:actual=actual.quantize(Decimal(scale),rounding=ROUND_HALF_UP)
            diff=actual-expected
        request.node.cert_checks.append({'concept':label,'expected':expected,'actual':actual,'difference':diff,'scale':scale,'status':'PASS' if actual==expected else 'FAIL'})
>       assert actual==expected,f'{label}: expected={expected}, actual={actual}, delta={diff}'
E       AssertionError: operario salida PT: expected=0, actual=3.0, delta=3.0
E       assert Decimal('3.0') == Decimal('0')

/home/cplaza/Desarrollo/Proeycto-Gestion-Negocio/sistema-facturacion/certificacion_integral_erp_v1/tests/conftest.py:30: AssertionError`

Evidencia completa: casos.jsonl o navegador.json. Las aserciones anteriores al fallo se conservan y no se presentan como aprobación del resto del escenario.

### F006 — test_certification.py::test_business_feature[5-cxp]

Estado FAIL. Función cxp. Resultado: `        final=query('SELECT payment_amount,payment_status FROM purchase_invoices WHERE id=%s',(inv['id'],))[0]
>                   check('abonos CxP acumulados',final['payment_amount'],D(11900))

/home/cplaza/Desarrollo/Proeycto-Gestion-Negocio/sistema-facturacion/certificacion_integral_erp_v1/tests/test_certification.py:258: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

label = 'abonos CxP acumulados', actual = Decimal('3000.0')
expected = Decimal('11900'), scale = None

    def verify(label,actual,expected,scale=None):
        from decimal import Decimal,ROUND_HALF_UP
        money=isinstance(expected,Decimal)
        diff=None
        if money:
            actual=Decimal(str(actual))
            if scale:actual=actual.quantize(Decimal(scale),rounding=ROUND_HALF_UP)
            diff=actual-expected
        request.node.cert_checks.append({'concept':label,'expected':expected,'actual':actual,'difference':diff,'scale':scale,'status':'PASS' if actual==expected else 'FAIL'})
>       assert actual==expected,f'{label}: expected={expected}, actual={actual}, delta={diff}'
E       AssertionError: abonos CxP acumulados: expected=11900, actual=3000.0, delta=-8900.0
E       assert Decimal('3000.0') == Decimal('11900')

/home/cplaza/Desarrollo/Proeycto-Gestion-Negocio/sistema-facturacion/certificacion_integral_erp_v1/tests/conftest.py:30: AssertionError`

Evidencia completa: casos.jsonl o navegador.json. Las aserciones anteriores al fallo se conservan y no se presentan como aprobación del resto del escenario.

## Regresión complementaria fallida

| CASO | RESULTADO |
|---|---|

Los intentos previos incluyen errores de fixtures/adaptadores (catálogos ausentes, secuencia de usuarios, campos obligatorios, parser de miles y uso incorrecto de contratos Python). Se corrigieron exclusivamente pruebas y preparación, y se repitieron en clones nuevos; no son defectos productivos confirmados. La falta de datos suficientes para una aserción de paginación histórica no certifica un fallo del paginador.

## Alcance no verificado

No se certifican cartolas externas, SII, contratos reales ni costos no registrados. Tampoco cinco formularios interactivos de alta para cada módulo ni todas las combinaciones de filtros, concurrencia y reversas. Las pruebas de migración auxiliares fijas están BLOCKED por seguridad. No declarar GREEN global.
