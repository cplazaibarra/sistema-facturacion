# Recetas y fabricación

Se comprueban receta, cantidades de materias primas, costo PPP, costo del producto terminado y ausencia de duplicaciones. Se cubren ruta administrativa, operario y agenda. Los consumos no crean existencias artificiales y los pedidos sin cobertura se mantienen bloqueados.

| CASO | ESTADO | EXPECTATIVA / REAL |
|---|---|---|
| test_certification.py::test_business_feature[1-recetas] | PASS | receta creada: esperado 42, real 42, diferencia None |
| test_certification.py::test_business_feature[1-produccion] | PASS | fabricación o bloqueo: esperado 2, real 2.0, diferencia 0.0; costo unitario fabricación: esperado 1250, real 1250.0, diferencia 0.0; MP consumida: esperado 18, real 18.0, diferencia 0.0 |
| test_certification.py::test_business_feature[1-operario] | PASS | consumo móvil registrado: esperado True, real True, diferencia None; operario salida PT: esperado 1, real 1.0, diferencia 0.0; operario costo producción: esperado 1100, real 1100.0, diferencia 0.0 |
| test_certification.py::test_business_feature[1-agenda] | PASS | programación válida: esperado True, real True, diferencia None; agenda no consume: esperado 0, real 0.0, diferencia 0.0 |
| test_certification.py::test_business_feature[2-recetas] | PASS | receta creada: esperado 43, real 43, diferencia None |
| test_certification.py::test_business_feature[2-produccion] | PASS | fabricación o bloqueo: esperado 3, real 3.0, diferencia 0.0; costo unitario fabricación: esperado 1250, real 1250.0, diferencia 0.0; MP consumida: esperado 17, real 17.0, diferencia 0.0 |
| test_certification.py::test_business_feature[2-operario] | PASS | consumo móvil registrado: esperado True, real True, diferencia None; operario salida PT: esperado 2, real 2.0, diferencia 0.0; operario costo producción: esperado 1200, real 1200.0, diferencia 0.0 |
| test_certification.py::test_business_feature[2-agenda] | PASS | programación válida: esperado True, real True, diferencia None; agenda no consume: esperado 0, real 0.0, diferencia 0.0 |
| test_certification.py::test_business_feature[3-recetas] | PASS | receta creada: esperado 44, real 44, diferencia None |
| test_certification.py::test_business_feature[3-produccion] | PASS | fabricación o bloqueo: esperado 0, real 0.0, diferencia 0.0 |
| test_certification.py::test_business_feature[3-operario] | FAIL | operario salida PT: esperado 0, real 3.0, diferencia 3.0 |
| test_certification.py::test_business_feature[3-agenda] | PASS | programación válida: esperado True, real True, diferencia None; agenda no consume: esperado 0, real 0.0, diferencia 0.0 |
| test_certification.py::test_business_feature[4-recetas] | PASS | receta creada: esperado 45, real 45, diferencia None |
| test_certification.py::test_business_feature[4-produccion] | PASS | fabricación o bloqueo: esperado 5, real 5.0, diferencia 0.0; costo unitario fabricación: esperado 1250, real 1250.0, diferencia 0.0; MP consumida: esperado 15, real 15.0, diferencia 0.0 |
| test_certification.py::test_business_feature[4-operario] | PASS | consumo móvil registrado: esperado True, real True, diferencia None; operario salida PT: esperado 4, real 4.0, diferencia 0.0; operario costo producción: esperado 1400, real 1400.0, diferencia 0.0 |
| test_certification.py::test_business_feature[4-agenda] | PASS | programación válida: esperado True, real True, diferencia None; agenda no consume: esperado 0, real 0.0, diferencia 0.0 |
| test_certification.py::test_business_feature[5-recetas] | PASS | receta creada: esperado 46, real 46, diferencia None |
| test_certification.py::test_business_feature[5-produccion] | PASS | fabricación o bloqueo: esperado 6, real 6.0, diferencia 0.0; costo unitario fabricación: esperado 1250, real 1250.0, diferencia 0.0; MP consumida: esperado 14, real 14.0, diferencia 0.0; fabricación no duplicada: esperado [{'id': 552}, {'id': 553}], real [{'id': 552}, {'id': 553}], diferencia None |
| test_certification.py::test_business_feature[5-operario] | PASS | consumo móvil registrado: esperado True, real True, diferencia None; operario salida PT: esperado 5, real 5.0, diferencia 0.0; operario costo producción: esperado 1500, real 1500.0, diferencia 0.0 |
| test_certification.py::test_business_feature[5-agenda] | PASS | programación válida: esperado True, real True, diferencia None; agenda no consume: esperado 0, real 0.0, diferencia 0.0; desprogramar: esperado None, real None, diferencia None |

Los detalles completos y acciones están en `evidencia/casos.jsonl`. Los resultados de ciclos integrados se documentan por separado.
