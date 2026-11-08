# Bancos, conciliación y Flujo de Caja

Las cartolas se crean en cuentas ficticias. Se comparan saldo inicial + abonos − cargos, transferencias internas y precedencia ERP/banco para evitar duplicaciones. La aceptación de una conciliación por la API no certifica igualdad de importes; se prueba explícitamente.

| CASO | ESTADO | EXPECTATIVA / REAL |
|---|---|---|
| test_certification.py::test_business_feature[1-bancos] | PASS | saldo contable banco: esperado 1007000, real 1007000.00, diferencia 0.00 |
| test_certification.py::test_business_feature[1-conciliacion] | PASS | transferencia ERP persistida: esperado 1, real 1, diferencia None; conciliación monto compatible: esperado True, real True, diferencia None; sin pagos extra: esperado 9, real 9, diferencia None |
| test_certification.py::test_business_feature[1-flujo_caja] | PASS | saldo inicial: esperado 100000, real 100000.00, diferencia 0.00; saldo final real: esperado 109520, real 109520.00, diferencia 0.00; ingresos reales: esperado 11900, real 11900.00, diferencia 0.00 |
| test_certification.py::test_business_feature[1-excel_bancos] | PASS | monto bancario en Excel: esperado True, real True, diferencia None; roundtrip sin nuevas filas: esperado 0, real 0, diferencia None |
| test_certification.py::test_business_feature[2-bancos] | PASS | saldo contable banco: esperado 1014000, real 1014000.00, diferencia 0.00 |
| test_certification.py::test_business_feature[2-conciliacion] | PASS | transferencia ERP persistida: esperado 1, real 1, diferencia None; conciliación monto compatible: esperado True, real True, diferencia None; sin pagos extra: esperado 11, real 11, diferencia None |
| test_certification.py::test_business_feature[2-flujo_caja] | PASS | saldo inicial: esperado 100000, real 100000.00, diferencia 0.00; saldo final real: esperado 119040, real 119040.00, diferencia 0.00; ingresos reales: esperado 23800, real 23800.00, diferencia 0.00 |
| test_certification.py::test_business_feature[2-excel_bancos] | PASS | monto bancario en Excel: esperado True, real True, diferencia None; roundtrip sin nuevas filas: esperado 0, real 0, diferencia None |
| test_certification.py::test_business_feature[3-bancos] | PASS | saldo contable banco: esperado 1021000, real 1021000.00, diferencia 0.00 |
| test_certification.py::test_business_feature[3-conciliacion] | FAIL | transferencia ERP persistida: esperado 1, real 1, diferencia None; conciliación monto compatible: esperado False, real True, diferencia None |
| test_certification.py::test_business_feature[3-flujo_caja] | PASS | saldo inicial: esperado 100000, real 100000.00, diferencia 0.00; saldo final real: esperado 128560, real 128560.00, diferencia 0.00; ingresos reales: esperado 35700, real 35700.00, diferencia 0.00 |
| test_certification.py::test_business_feature[3-excel_bancos] | PASS | monto bancario en Excel: esperado True, real True, diferencia None; roundtrip sin nuevas filas: esperado 0, real 0, diferencia None |
| test_certification.py::test_business_feature[4-bancos] | PASS | saldo contable banco: esperado 1028000, real 1028000.00, diferencia 0.00 |
| test_certification.py::test_business_feature[4-conciliacion] | PASS | transferencia ERP persistida: esperado 1, real 1, diferencia None; conciliación monto compatible: esperado True, real True, diferencia None; sin pagos extra: esperado 14, real 14, diferencia None; desconciliar autorizado: esperado True, real True, diferencia None |
| test_certification.py::test_business_feature[4-flujo_caja] | PASS | saldo inicial: esperado 100000, real 100000.00, diferencia 0.00; saldo final real: esperado 138080, real 138080.00, diferencia 0.00; ingresos reales: esperado 47600, real 47600.00, diferencia 0.00 |
| test_certification.py::test_business_feature[4-excel_bancos] | PASS | monto bancario en Excel: esperado True, real True, diferencia None; roundtrip sin nuevas filas: esperado 0, real 0, diferencia None |
| test_certification.py::test_business_feature[5-bancos] | PASS | saldo contable banco: esperado 1035000, real 1035000.00, diferencia 0.00; transferencia enlazada: esperado True, real True, diferencia None; transferencia consolidada neutra: esperado 1035000, real 1035000.00, diferencia 0.00 |
| test_certification.py::test_business_feature[5-conciliacion] | PASS | transferencia ERP persistida: esperado 1, real 1, diferencia None; conciliación monto compatible: esperado True, real True, diferencia None; sin pagos extra: esperado 16, real 16, diferencia None; conciliación no duplicada: esperado False, real False, diferencia None |
| test_certification.py::test_business_feature[5-flujo_caja] | PASS | saldo inicial: esperado 100000, real 100000.00, diferencia 0.00; saldo final real: esperado 147600, real 147600.00, diferencia 0.00; ingresos reales: esperado 59500, real 59500.00, diferencia 0.00 |
| test_certification.py::test_business_feature[5-excel_bancos] | PASS | monto bancario en Excel: esperado True, real True, diferencia None; roundtrip sin nuevas filas: esperado 0, real 0, diferencia None |

Los detalles completos y acciones están en `evidencia/casos.jsonl`. Los resultados de ciclos integrados se documentan por separado.
