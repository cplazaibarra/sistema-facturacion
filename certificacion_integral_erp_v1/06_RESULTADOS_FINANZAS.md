# CxC, CxP, gastos y deudas

Gastos Operacionales se mantiene donde está en el ERP; no se modificó su navegación ni lógica. La certificación distingue importe de la regla y monto real del período. Se contrastan obligaciones, abonos, cierre y saldos; ningún pago se considera correcto sólo por una redirección.

| CASO | ESTADO | EXPECTATIVA / REAL |
|---|---|---|
| test_certification.py::test_business_feature[1-cxc] | PASS | cobro persistido: esperado 2000, real 2000.0, diferencia 0.0; saldo CxC: esperado 9900, real 9900.0, diferencia 0.0 |
| test_certification.py::test_business_feature[1-cxp] | FAIL | abono CxP aplicado: esperado 2000, real 2000.0, diferencia 0.0; saldo CxP proyectado después de abono: esperado 9900, real 0.00, diferencia -9900.00 |
| test_certification.py::test_business_feature[1-gastos] | PASS | importe real del mes: esperado 15111, real 15111.00, diferencia 0.00; regla mensual intacta: esperado 12000, real 12000.00, diferencia 0.00 |
| test_certification.py::test_business_feature[1-deudas] | PASS | principal no duplicado: esperado 100001, real 100001.00, diferencia 0.00; pago deuda válido: esperado True, real True, diferencia None; saldo cuota: esperado 23333.67, real 23333.67, diferencia 0.00 |
| test_certification.py::test_business_feature[1-excel_deudas] | PASS | Excel cuotas parseable: esperado True, real True, diferencia None; cuotas sin duplicados: esperado 3, real 3, diferencia None; principal exportado exacto: esperado 300001, real 300001.00, diferencia 0.00 |
| test_certification.py::test_business_feature[2-cxc] | PASS | cobro persistido: esperado 5900, real 5900.0, diferencia 0.0; saldo CxC: esperado 6000, real 6000.0, diferencia 0.0 |
| test_certification.py::test_business_feature[2-cxp] | FAIL | abono CxP aplicado: esperado 5900, real 5900.0, diferencia 0.0; saldo CxP proyectado después de abono: esperado 6000, real 0.00, diferencia -6000.00 |
| test_certification.py::test_business_feature[2-gastos] | PASS | importe real del mes: esperado 15222, real 15222.00, diferencia 0.00; regla mensual intacta: esperado 12100, real 12100.00, diferencia 0.00 |
| test_certification.py::test_business_feature[2-deudas] | PASS | principal no duplicado: esperado 100002, real 100002.00, diferencia 0.00; pago deuda válido: esperado True, real True, diferencia None; saldo cuota: esperado 23334.00, real 23334.00, diferencia 0.00 |
| test_certification.py::test_business_feature[2-excel_deudas] | PASS | Excel cuotas parseable: esperado True, real True, diferencia None; cuotas sin duplicados: esperado 3, real 3, diferencia None; principal exportado exacto: esperado 300002, real 300002.00, diferencia 0.00 |
| test_certification.py::test_business_feature[3-cxc] | PASS | sobrepago rechazado: esperado 0, real 0, diferencia None |
| test_certification.py::test_business_feature[3-cxp] | FAIL | sobrepago CxP rechazado: esperado 0, real 11901.0, diferencia 11901.0 |
| test_certification.py::test_business_feature[3-gastos] | PASS | importe real del mes: esperado 15333, real 15333.00, diferencia 0.00; regla mensual intacta: esperado 12200, real 12200.00, diferencia 0.00 |
| test_certification.py::test_business_feature[3-deudas] | PASS | principal no duplicado: esperado 100003, real 100003.00, diferencia 0.00; pago deuda válido: esperado True, real True, diferencia None; saldo cuota: esperado 33333.33, real 33333.33, diferencia 0.00 |
| test_certification.py::test_business_feature[3-excel_deudas] | PASS | Excel cuotas parseable: esperado True, real True, diferencia None; cuotas sin duplicados: esperado 3, real 3, diferencia None; principal exportado exacto: esperado 300003, real 300003.00, diferencia 0.00 |
| test_certification.py::test_business_feature[4-cxc] | PASS | cobro persistido: esperado 11900, real 11900.0, diferencia 0.0; saldo CxC: esperado 0, real 0, diferencia 0 |
| test_certification.py::test_business_feature[4-cxp] | PASS | abono CxP aplicado: esperado 11900, real 11900.0, diferencia 0.0; obligación pagada: esperado Pagada, real Pagada, diferencia None |
| test_certification.py::test_business_feature[4-gastos] | PASS | importe real del mes: esperado 15444, real 15444.00, diferencia 0.00; regla mensual intacta: esperado 12300, real 12300.00, diferencia 0.00; otro período diferente: esperado 16444, real 16444.00, diferencia 0.00 |
| test_certification.py::test_business_feature[4-deudas] | PASS | principal no duplicado: esperado 100004, real 100004.00, diferencia 0.00; pago deuda válido: esperado True, real True, diferencia None; saldo cuota: esperado 0.00, real 0.00, diferencia 0.00 |
| test_certification.py::test_business_feature[4-excel_deudas] | PASS | Excel cuotas parseable: esperado True, real True, diferencia None; cuotas sin duplicados: esperado 3, real 3, diferencia None; principal exportado exacto: esperado 300004, real 300004.00, diferencia 0.00 |
| test_certification.py::test_business_feature[5-cxc] | PASS | cobro persistido: esperado 3000, real 3000.0, diferencia 0.0; saldo CxC: esperado 8900, real 8900.0, diferencia 0.0; pago idempotente: esperado 1, real 1, diferencia None |
| test_certification.py::test_business_feature[5-cxp] | FAIL | abono CxP aplicado: esperado 3000, real 3000.0, diferencia 0.0; abonos CxP acumulados: esperado 11900, real 3000.0, diferencia -8900.0 |
| test_certification.py::test_business_feature[5-gastos] | PASS | importe real del mes: esperado 15555, real 15555.00, diferencia 0.00; regla mensual intacta: esperado 12400, real 12400.00, diferencia 0.00; otro período diferente: esperado 16555, real 16555.00, diferencia 0.00; período idempotente: esperado 42, real 42, diferencia None |
| test_certification.py::test_business_feature[5-deudas] | PASS | principal no duplicado: esperado 100005, real 100005.00, diferencia 0.00; pago deuda válido: esperado True, real True, diferencia None; saldo cuota: esperado 23335.00, real 23335.00, diferencia 0.00; sobrepago cuota rechazado: esperado False, real False, diferencia None |
| test_certification.py::test_business_feature[5-excel_deudas] | PASS | Excel cuotas parseable: esperado True, real True, diferencia None; cuotas sin duplicados: esperado 3, real 3, diferencia None; principal exportado exacto: esperado 300005, real 300005.00, diferencia 0.00 |

Los detalles completos y acciones están en `evidencia/casos.jsonl`. Los resultados de ciclos integrados se documentan por separado.
