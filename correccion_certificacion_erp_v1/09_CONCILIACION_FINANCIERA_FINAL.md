# Conciliación financiera final

Oráculo Decimal independiente, IVA19%, redondeo comercial HALF_UP; pesos redondeados con diferencia cero. PPP a la escala explícita de cuatro decimales cuando la prueba lo requiere. Las cantidades se contrastan aparte con la misma exigencia; no se inventan tolerancias.

Comprobaciones cuantitativas:655. Diferencias distintas de cero:0. Diferencias ledger/lotes:0. Anomalías adicionales:{'purchase_overpayments': 0, 'expense_overpayments': 0, 'purchase_header_event_mismatches': 0, 'expense_header_event_mismatches': 0, 'reconciliation_amount_mismatches': 0, 'all_reconciliation_mismatches': 0, 'transfer_mismatches': 0}.

| OPERACIÓN / CONTROL | ESPERADO | REAL | DIFERENCIA | RESULTADO |
|---|---|---|---|---|
| costo persistido | 1235 | 1235.0 | 0.0 | PASS |
| sin stock creado | 0 | 0.0 | 0.0 | PASS |
| OC neta | 3375 | 3375.0 | 0.0 | PASS |
| OC no crea stock | 0.0 | 0.0 | 0.0 | PASS |
| stock recibido | 3 | 3.0 | 0.0 | PASS |
| CxP bruta | 3838 | 3838.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| reserva global | 2 | 2.0 | 0.0 | PASS |
| disponible | 18 | 18.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| stock de capas | 20 | 20.0 | 0.0 | PASS |
| total persistido | 32130 | 32130.0 | 0.0 | PASS |
| subtotal neto | 27000.00 | 27000.0 | 0.00 | PASS |
| neto servidor | 27000 | 27000.0 | 0.0 | PASS |
| IVA servidor | 5130 | 5130.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 18 | 18.0 | 0.0 | PASS |
| costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 18 | 18.0 | 0.0 | PASS |
| costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| receta creada | 42 | 42 | 0 | PASS |
| fabricación o bloqueo | 2 | 2.0 | 0.0 | PASS |
| costo unitario fabricación | 1250 | 1250.0 | 0.0 | PASS |
| MP consumida | 18 | 18.0 | 0.0 | PASS |
| cobro persistido | 2000 | 2000.0 | 0.0 | PASS |
| saldo CxC | 9900 | 9900.0 | 0.0 | PASS |
| abono CxP aplicado | 2000 | 2000.0 | 0.0 | PASS |
| saldo CxP proyectado después de abono | 9900 | 9900.00 | 0.00 | PASS |
| importe real del mes | 15111 | 15111.00 | 0.00 | PASS |
| regla mensual intacta | 12000 | 12000.00 | 0.00 | PASS |
| principal no duplicado | 100001 | 100001.00 | 0.00 | PASS |
| saldo cuota | 23333.67 | 23333.67 | 0.00 | PASS |
| saldo contable banco | 1007000 | 1007000.00 | 0.00 | PASS |
| transferencia ERP persistida | 1 | 1 | 0 | PASS |
| sin pagos extra | 9 | 9 | 0 | PASS |
| saldo inicial | 100000 | 100000.00 | 0.00 | PASS |
| saldo final real | 109520 | 109520.00 | 0.00 | PASS |
| ingresos reales | 11900 | 11900.00 | 0.00 | PASS |
| reporte total bruto | 2645 | 2645.0 | 0.0 | PASS |
| reporte neto | 2223 | 2223.0 | 0.0 | PASS |
| reporte IVA | 422 | 422.0 | 0.0 | PASS |
| distribución concilia | 6919245.0 | 6919245.0 | 0.0 | PASS |
| solicitud sin stock | 10 | 10.0 | 0.0 | PASS |
| ajuste aprobado | 11 | 11.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 18 | 18.0 | 0.0 | PASS |
| costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| costo embalaje | 100 | 100.0 | 0.0 | PASS |
| precio neto por PPP y recargo | 1250.00 | 1250.0 | 0.00 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 18 | 18.0 | 0.0 | PASS |
| costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| operario salida PT | 1 | 1.0 | 0.0 | PASS |
| operario costo producción | 1100 | 1100.0 | 0.0 | PASS |
| agenda no consume | 0 | 0.0 | 0.0 | PASS |
| roundtrip sin nuevas filas | 0 | 0 | 0 | PASS |
| cuotas sin duplicados | 3 | 3 | 0 | PASS |
| principal exportado exacto | 300001 | 300001.00 | 0.00 | PASS |
| rol asignado | 40 | 40 | 0 | PASS |
| costo persistido | 1236 | 1236.0 | 0.0 | PASS |
| sin stock creado | 0 | 0.0 | 0.0 | PASS |
| OC neta | 5000 | 5000.0 | 0.0 | PASS |
| OC no crea stock | 0.0 | 0.0 | 0.0 | PASS |
| stock recibido | 4 | 4.0 | 0.0 | PASS |
| CxP bruta | 5474 | 5474.0 | 0.0 | PASS |
| recepción parcial | 3 | 3 | 0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| reserva global | 3 | 3.0 | 0.0 | PASS |
| disponible | 17 | 17.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| stock de capas | 20 | 20.0 | 0.0 | PASS |
| total persistido | 8742 | 8742.0 | 0.0 | PASS |
| subtotal neto | 7345.57 | 7345.57 | 0.00 | PASS |
| neto servidor | 7346 | 7346.0 | 0.0 | PASS |
| IVA servidor | 1396 | 1396.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 17 | 17.0 | 0.0 | PASS |
| costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 17 | 17.0 | 0.0 | PASS |
| costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| receta creada | 43 | 43 | 0 | PASS |
| fabricación o bloqueo | 3 | 3.0 | 0.0 | PASS |
| costo unitario fabricación | 1250 | 1250.0 | 0.0 | PASS |
| MP consumida | 17 | 17.0 | 0.0 | PASS |
| cobro persistido | 5900 | 5900.0 | 0.0 | PASS |
| saldo CxC | 6000 | 6000.0 | 0.0 | PASS |
| abono CxP aplicado | 5900 | 5900.0 | 0.0 | PASS |
| saldo CxP proyectado después de abono | 6000 | 6000.00 | 0.00 | PASS |
| importe real del mes | 15222 | 15222.00 | 0.00 | PASS |
| regla mensual intacta | 12100 | 12100.00 | 0.00 | PASS |
| principal no duplicado | 100002 | 100002.00 | 0.00 | PASS |
| saldo cuota | 23334.00 | 23334.00 | 0.00 | PASS |
| saldo contable banco | 1014000 | 1014000.00 | 0.00 | PASS |
| transferencia ERP persistida | 1 | 1 | 0 | PASS |
| sin pagos extra | 11 | 11 | 0 | PASS |
| saldo inicial | 100000 | 100000.00 | 0.00 | PASS |
| saldo final real | 119040 | 119040.00 | 0.00 | PASS |
| ingresos reales | 23800 | 23800.00 | 0.00 | PASS |
| reporte total bruto | 3971 | 3971.0 | 0.0 | PASS |
| reporte neto | 3337 | 3337.0 | 0.0 | PASS |
| reporte IVA | 634 | 634.0 | 0.0 | PASS |
| distribución concilia | 6994616.0 | 6994616.0 | 0.0 | PASS |
| solicitud sin stock | 10 | 10.0 | 0.0 | PASS |
| ajuste aprobado | 12 | 12.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 17 | 17.0 | 0.0 | PASS |
| costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| costo embalaje | 200 | 200.0 | 0.0 | PASS |
| precio neto por PPP y recargo | 1437.50 | 1437.5 | 0.00 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 17 | 17.0 | 0.0 | PASS |
| costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| operario salida PT | 2 | 2.0 | 0.0 | PASS |
| operario costo producción | 1200 | 1200.0 | 0.0 | PASS |
| agenda no consume | 0 | 0.0 | 0.0 | PASS |
| roundtrip sin nuevas filas | 0 | 0 | 0 | PASS |
| cuotas sin duplicados | 3 | 3 | 0 | PASS |
| principal exportado exacto | 300002 | 300002.00 | 0.00 | PASS |
| rol asignado | 41 | 41 | 0 | PASS |
| costo persistido | 1237 | 1237.0 | 0.0 | PASS |
| sin stock creado | 0 | 0.0 | 0.0 | PASS |
| OC neta | 6875 | 6875.0 | 0.0 | PASS |
| OC no crea stock | 0.0 | 0.0 | 0.0 | PASS |
| cantidad inválida no persistida | 0 | 0 | 0 | PASS |
| stock recibido | 5 | 5.0 | 0.0 | PASS |
| CxP bruta | 7289 | 7289.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| reserva global | 30 | 30.0 | 0.0 | PASS |
| disponible | 0 | 0.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| stock de capas | 20 | 20.0 | 0.0 | PASS |
| total persistido | 60 | 60.0 | 0.0 | PASS |
| subtotal neto | 50.00 | 50.0 | 0.00 | PASS |
| neto servidor | 50 | 50.0 | 0.0 | PASS |
| IVA servidor | 10 | 10.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 20 | 20.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 20 | 20.0 | 0.0 | PASS |
| receta creada | 44 | 44 | 0 | PASS |
| fabricación o bloqueo | 0 | 0.0 | 0.0 | PASS |
| sobrepago rechazado | 0 | 0 | 0 | PASS |
| sobrepago CxP rechazado | 0 | 0 | 0 | PASS |
| importe real del mes | 15333 | 15333.00 | 0.00 | PASS |
| regla mensual intacta | 12200 | 12200.00 | 0.00 | PASS |
| principal no duplicado | 100003 | 100003.00 | 0.00 | PASS |
| saldo cuota | 33333.33 | 33333.33 | 0.00 | PASS |
| saldo contable banco | 1021000 | 1021000.00 | 0.00 | PASS |
| transferencia ERP persistida | 1 | 1 | 0 | PASS |
| sin pagos extra | 12 | 12 | 0 | PASS |
| saldo inicial | 100000 | 100000.00 | 0.00 | PASS |
| saldo final real | 128560 | 128560.00 | 0.00 | PASS |
| ingresos reales | 35700 | 35700.00 | 0.00 | PASS |
| reporte total bruto | 5299 | 5299.0 | 0.0 | PASS |
| reporte neto | 4453 | 4453.0 | 0.0 | PASS |
| reporte IVA | 846 | 846.0 | 0.0 | PASS |
| distribución concilia | 7398565.0 | 7398565.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 20 | 20.0 | 0.0 | PASS |
| precio neto por PPP y recargo | 1750.00 | 1750.0 | 0.00 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 20 | 20.0 | 0.0 | PASS |
| operario salida PT | 0 | 0.0 | 0.0 | PASS |
| rechazo no crea salida valorada | 0 | 0 | 0 | PASS |
| agenda no consume | 0 | 0.0 | 0.0 | PASS |
| roundtrip sin nuevas filas | 0 | 0 | 0 | PASS |
| cuotas sin duplicados | 3 | 3 | 0 | PASS |
| principal exportado exacto | 300003 | 300003.00 | 0.00 | PASS |
| rol asignado | 42 | 42 | 0 | PASS |
| costo persistido | 1238 | 1238.0 | 0.0 | PASS |
| sin stock creado | 0 | 0.0 | 0.0 | PASS |
| SKU único | 1 | 1 | 0 | PASS |
| relación OC | 166 | 166 | 0 | PASS |
| OC neta | 9000 | 9000.0 | 0.0 | PASS |
| OC no crea stock | 0.0 | 0.0 | 0.0 | PASS |
| recepción ligada | 6 | 6.0 | 0.0 | PASS |
| stock recibido | 6 | 6.0 | 0.0 | PASS |
| CxP bruta | 9282 | 9282.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| reserva global | 5 | 5.0 | 0.0 | PASS |
| disponible | 15 | 15.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 15 | 15.0 | 0.0 | PASS |
| costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| FIFO capa antigua agotada | 0 | 0 | 0 | PASS |
| total persistido | 0 | 0.0 | 0.0 | PASS |
| subtotal neto | 0.00 | 0.0 | 0.00 | PASS |
| neto servidor | 0 | 0.0 | 0.0 | PASS |
| IVA servidor | 0 | 0.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 15 | 15.0 | 0.0 | PASS |
| costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 15 | 15.0 | 0.0 | PASS |
| costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| receta creada | 45 | 45 | 0 | PASS |
| fabricación o bloqueo | 5 | 5.0 | 0.0 | PASS |
| costo unitario fabricación | 1250 | 1250.0 | 0.0 | PASS |
| MP consumida | 15 | 15.0 | 0.0 | PASS |
| cobro persistido | 11900 | 11900.0 | 0.0 | PASS |
| saldo CxC | 0 | 0 | 0 | PASS |
| abono CxP aplicado | 11900 | 11900.0 | 0.0 | PASS |
| importe real del mes | 15444 | 15444.00 | 0.00 | PASS |
| regla mensual intacta | 12300 | 12300.00 | 0.00 | PASS |
| otro período diferente | 16444 | 16444.00 | 0.00 | PASS |
| principal no duplicado | 100004 | 100004.00 | 0.00 | PASS |
| saldo cuota | 0.00 | 0.00 | 0.00 | PASS |
| saldo contable banco | 1028000 | 1028000.00 | 0.00 | PASS |
| transferencia ERP persistida | 1 | 1 | 0 | PASS |
| sin pagos extra | 14 | 14 | 0 | PASS |
| saldo inicial | 100000 | 100000.00 | 0.00 | PASS |
| saldo final real | 138080 | 138080.00 | 0.00 | PASS |
| ingresos reales | 47600 | 47600.00 | 0.00 | PASS |
| reporte total bruto | 6629 | 6629.0 | 0.0 | PASS |
| reporte neto | 5571 | 5571.0 | 0.0 | PASS |
| reporte IVA | 1058 | 1058.0 | 0.0 | PASS |
| distribución concilia | 7696744.0 | 7696744.0 | 0.0 | PASS |
| solicitud sin stock | 10 | 10.0 | 0.0 | PASS |
| ajuste aprobado | 14 | 14.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 15 | 15.0 | 0.0 | PASS |
| costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| costo embalaje | 400 | 400.0 | 0.0 | PASS |
| precio neto por PPP y recargo | 1562.50 | 1562.5 | 0.00 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 15 | 15.0 | 0.0 | PASS |
| costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| operario salida PT | 4 | 4.0 | 0.0 | PASS |
| operario costo producción | 1400 | 1400.0 | 0.0 | PASS |
| agenda no consume | 0 | 0.0 | 0.0 | PASS |
| roundtrip sin nuevas filas | 0 | 0 | 0 | PASS |
| cuotas sin duplicados | 3 | 3 | 0 | PASS |
| principal exportado exacto | 300004 | 300004.00 | 0.00 | PASS |
| rol asignado | 43 | 43 | 0 | PASS |
| costo persistido | 1239 | 1239.0 | 0.0 | PASS |
| sin stock creado | 0 | 0.0 | 0.0 | PASS |
| relación OC | 192 | 192 | 0 | PASS |
| RUT no duplica | 34 | 34 | 0 | PASS |
| OC neta | 11375 | 11375.0 | 0.0 | PASS |
| OC no crea stock | 0.0 | 0.0 | 0.0 | PASS |
| OC anulada no consume | 0 | 0.0 | 0.0 | PASS |
| stock recibido | 7 | 7.0 | 0.0 | PASS |
| CxP bruta | 11454 | 11454.0 | 0.0 | PASS |
| sin sobre-recepción | 7 | 7.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| reserva global | 6 | 6.0 | 0.0 | PASS |
| disponible | 14 | 14.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 14 | 14.0 | 0.0 | PASS |
| costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| PPP revaluado independiente | 1400.0000 | 1400.0 | 0.0000 | PASS |
| costo congelado histórico conservado | 1250 | 1250.0 | 0.0 | PASS |
| total persistido | 3213000000 | 3213000000.0 | 0.0 | PASS |
| subtotal neto | 2700000000.00 | 2700000000.0 | 0.00 | PASS |
| neto servidor | 2700000000 | 2700000000.0 | 0.0 | PASS |
| IVA servidor | 513000000 | 513000000.0 | 0.0 | PASS |
| cotización modificada | 3213000004 | 3213000004.0 | 0.0 | PASS |
| conversión mismo bruto | 3213000004 | 3213000004.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 14 | 14.0 | 0.0 | PASS |
| costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| reversa stock | 20 | 20.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 14 | 14.0 | 0.0 | PASS |
| costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| receta creada | 46 | 46 | 0 | PASS |
| fabricación o bloqueo | 6 | 6.0 | 0.0 | PASS |
| costo unitario fabricación | 1250 | 1250.0 | 0.0 | PASS |
| MP consumida | 14 | 14.0 | 0.0 | PASS |
| cobro persistido | 3000 | 3000.0 | 0.0 | PASS |
| saldo CxC | 8900 | 8900.0 | 0.0 | PASS |
| pago idempotente | 1 | 1 | 0 | PASS |
| abono CxP aplicado | 3000 | 3000.0 | 0.0 | PASS |
| abonos CxP acumulados | 11900 | 11900.0 | 0.0 | PASS |
| importe real del mes | 15555 | 15555.00 | 0.00 | PASS |
| regla mensual intacta | 12400 | 12400.00 | 0.00 | PASS |
| otro período diferente | 16555 | 16555.00 | 0.00 | PASS |
| período idempotente | 42 | 42 | 0 | PASS |
| principal no duplicado | 100005 | 100005.00 | 0.00 | PASS |
| saldo cuota | 23335.00 | 23335.00 | 0.00 | PASS |
| saldo contable banco | 1035000 | 1035000.00 | 0.00 | PASS |
| transferencia consolidada neutra | 1035000 | 1035000.00 | 0.00 | PASS |
| transferencia ERP persistida | 1 | 1 | 0 | PASS |
| sin pagos extra | 16 | 16 | 0 | PASS |
| saldo inicial | 100000 | 100000.00 | 0.00 | PASS |
| saldo final real | 147600 | 147600.00 | 0.00 | PASS |
| ingresos reales | 59500 | 59500.00 | 0.00 | PASS |
| reporte total bruto | 7962 | 7962.0 | 0.0 | PASS |
| reporte neto | 6691 | 6691.0 | 0.0 | PASS |
| reporte IVA | 1271 | 1271.0 | 0.0 | PASS |
| distribución concilia | 3220811810.0 | 3220811810.0 | 0.0 | PASS |
| solicitud sin stock | 10 | 10.0 | 0.0 | PASS |
| ajuste aprobado | 15 | 15.0 | 0.0 | PASS |
| sin duplicado | 15 | 15.0 | 0.0 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 14 | 14.0 | 0.0 | PASS |
| costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| costo embalaje | 500 | 500.0 | 0.0 | PASS |
| precio neto por PPP y recargo | 2500.00 | 2500.0 | 0.00 | PASS |
| PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| salida o bloqueo por insuficiencia | 14 | 14.0 | 0.0 | PASS |
| costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| operario salida PT | 5 | 5.0 | 0.0 | PASS |
| operario costo producción | 1500 | 1500.0 | 0.0 | PASS |
| agenda no consume | 0 | 0.0 | 0.0 | PASS |
| roundtrip sin nuevas filas | 0 | 0 | 0 | PASS |
| cuotas sin duplicados | 3 | 3 | 0 | PASS |
| principal exportado exacto | 300005 | 300005.00 | 0.00 | PASS |
| rol asignado | 44 | 44 | 0 | PASS |
| C1 compra bruta | 11900 | 11900.0 | 0.0 | PASS |
| C1 reserva sin salida | 10 | 10.0 | 0.0 | PASS |
| C1 stock final | 7 | 7.0 | 0.0 | PASS |
| C1 neto | 27000 | 27000.0 | 0.0 | PASS |
| C1 IVA | 5130 | 5130.0 | 0.0 | PASS |
| C1 costo vendido | 3000 | 3000.0 | 0.0 | PASS |
| C1 utilidad | 24000 | 24000.0 | 0.0 | PASS |
| C1 cobro íntegro | 32130 | 32130.0 | 0.0 | PASS |
| C1 ingreso único | 32130 | 32130.00 | 0.00 | PASS |
| C1 banco final | 1032130 | 1032130.00 | 0.00 | PASS |
| C2 receta persiste | 1 | 1 | 0 | PASS |
| C2 MP remanente | 5 | 5.0 | 0.0 | PASS |
| C2 PT fabricado | 15 | 15.0 | 0.0 | PASS |
| C2 costo unitario | 1250 | 1250.0 | 0.0 | PASS |
| C2 valor transferido | 18750 | 18750.0 | 0.0 | PASS |
| C2 costo vendido | 6250 | 6250.0 | 0.0 | PASS |
| C2 utilidad neta | 6250 | 6250.0 | 0.0 | PASS |
| C2 IVA | 2375 | 2375.0 | 0.0 | PASS |
| C2 PT final | 10 | 10.0 | 0.0 | PASS |
| C3 regla recurrente inmutable | 11900 | 11900.00 | 0.00 | PASS |
| C3 egresos únicos | 32130 | 32130.00 | 0.00 | PASS |
| C3 saldo final | 967870 | 967870.00 | 0.00 | PASS |
| C4 reserva mayor al físico | 13 | 13.0 | 0.0 | PASS |
| C4 disponible cero | 0 | 0.0 | 0.0 | PASS |
| C4 operador elige B | 5 | 5.0 | 0.0 | PASS |
| C4 no segunda salida | 5 | 5.0 | 0.0 | PASS |
| C5 saldo cuenta origen | 838100 | 838100.00 | 0.00 | PASS |
| saldo parcial | 9900 | 9900 | 0 | PASS |
| segundo saldo | 5900 | 5900 | 0 | PASS |
| sobrepago sin escritura | 0 | 0 | 0 | PASS |
| concurrencia un ganador | 1 | 1 | 0 | PASS |
| concurrencia importe | 7000 | 7000.00 | 0.00 | PASS |
| reintento único | 1 | 1 | 0 | PASS |
| gasto real único | 11900 | 11900.00 | 0.00 | PASS |
| regla intacta | 11900 | 11900.00 | 0.00 | PASS |
| invalidos sin escritura | 0 | 0 | 0 | PASS |
| banco sin duplicar abono | 2000 | 2000.00 | 0.00 | PASS |
| compromiso original | 11900 | 11900.00 | 0.00 | PASS |
| real sólo pagado | 2000 | 2000.00 | 0.00 | PASS |
| pendiente sólo saldo | 9900 | 9900.00 | 0.00 | PASS |
| real sólo pagado | 11900 | 11900.00 | 0.00 | PASS |
| pendiente sólo saldo | 0 | 0.00 | 0.00 | PASS |
| real sólo pagado | 2000 | 2000.00 | 0.00 | PASS |
| pendiente sólo saldo | 9900 | 9900.00 | 0.00 | PASS |
| precedencia gasto período | 23800 | 23800.00 | 0.00 | PASS |
| precedencia gasto período | 26900 | 26900.00 | 0.00 | PASS |
| transferencia neutra | 0 | 0.00 | 0.00 | PASS |
| pago futuro no efectivo octubre | 0 | 0.00 | 0.00 | PASS |
| pago noviembre | 2000 | 2000.00 | 0.00 | PASS |
| vencido conserva saldo | 11900 | 11900.00 | 0.00 | PASS |
| real sólo pagado | 2000 | 2000.00 | 0.00 | PASS |
| pendiente sólo saldo | 9900 | 9900.00 | 0.00 | PASS |
| no crea pagos | 1 | 1 | 0 | PASS |
| no crea pagos | 1 | 1 | 0 | PASS |
| no crea pagos | 1 | 1 | 0 | PASS |
| no crea pagos | 1 | 1 | 0 | PASS |
| no crea pagos | 1 | 1 | 0 | PASS |
| no crea pagos | 1 | 1 | 0 | PASS |
| no crea pagos | 1 | 1 | 0 | PASS |
| destino único concurrente | 1 | 1 | 0 | PASS |
| no crea pagos | 1 | 1 | 0 | PASS |
| pago conservado | 11900 | 11900.0 | 0.0 | PASS |
| no crea pagos | 1 | 1 | 0 | PASS |
| sin doble ingreso | 11900 | 11900.00 | 0.00 | PASS |
| no crea pagos | 1 | 1 | 0 | PASS |
| salida legítima | 4 | 4.0 | 0.0 | PASS |
| costo PPP transferido | 1000 | 1000.0 | 0.0 | PASS |
| MP remanente | 6 | 6.0 | 0.0 | PASS |
| entrada única | 1 | 1 | 0 | PASS |
| sin entrada fantasma | 0 | 0.0 | 0.0 | PASS |
| salida legítima | 4 | 4.0 | 0.0 | PASS |
| costo PPP transferido | 1000 | 1000.0 | 0.0 | PASS |
| MP remanente | 6 | 6.0 | 0.0 | PASS |
| entrada única | 1 | 1 | 0 | PASS |
| salida legítima | 4 | 4.0 | 0.0 | PASS |
| costo PPP transferido | 1000 | 1000.0 | 0.0 | PASS |
| MP remanente | 6 | 6.0 | 0.0 | PASS |
| entrada única | 1 | 1 | 0 | PASS |
| salida legítima | 2 | 2.0 | 0.0 | PASS |
| costo PPP transferido | 1000 | 1000.0 | 0.0 | PASS |
| MP remanente | 8 | 8.0 | 0.0 | PASS |
| entrada única | 1 | 1 | 0 | PASS |
| salida legítima | 4 | 4.0 | 0.0 | PASS |
| costo PPP transferido | 1000 | 1000.0 | 0.0 | PASS |
| MP remanente | 6 | 6.0 | 0.0 | PASS |
| entrada única | 1 | 1 | 0 | PASS |
| rollback lotes | 189 | 189 | 0 | PASS |
| rollback output | 0 | 0.0 | 0.0 | PASS |
| finalización concurrente única | 1 | 1 | 0 | PASS |
| salida legítima | 4 | 4.0 | 0.0 | PASS |
| costo PPP transferido | 1000 | 1000.0 | 0.0 | PASS |
| MP remanente | 6 | 6.0 | 0.0 | PASS |
| entrada única | 1 | 1 | 0 | PASS |
| cancelada sin entrada | 0 | 0.0 | 0.0 | PASS |
| salida legítima | 4 | 4.0 | 0.0 | PASS |
| costo PPP transferido | 1000 | 1000.0 | 0.0 | PASS |
| MP remanente | 6 | 6.0 | 0.0 | PASS |
| entrada única | 1 | 1 | 0 | PASS |
| gasto saldo parcial | 9900 | 9900.00 | 0.00 | PASS |
| gasto egreso real | 2000 | 2000.00 | 0.00 | PASS |
| gasto sobrepago sin escritura | 0 | 0 | 0 | PASS |
| gasto concurrente único | 1 | 1 | 0 | PASS |
| gasto reintento único | 1 | 1 | 0 | PASS |
| gasto conciliado único | 2000 | 2000.00 | 0.00 | PASS |
| snapshot inicial preservado | 2000 | 2000.00 | 0.00 | PASS |
| nuevo abono | 3900 | 3900.00 | 0.00 | PASS |
| parciales reales sin duplicar | 5900 | 5900.00 | 0.00 | PASS |
| snapshot inicial preservado | 2000 | 2000.00 | 0.00 | PASS |
| nuevo abono | 3900 | 3900.00 | 0.00 | PASS |
| parciales reales sin duplicar | 5900 | 5900.00 | 0.00 | PASS |
| no reducir debajo de abonos | 11900 | 11900.0 | 0.0 | PASS |
| historial accesible | 200 | 200 | 0 | PASS |
| histórico conserva dos pagos | 2 | 2 | 0 | PASS |
| sin cuenta sin escritura | 0 | 0 | 0 | PASS |
| no genera stock sin respaldo | 0 | 0.0 | 0.0 | PASS |
| no genera stock sin respaldo | 0 | 0.0 | 0.0 | PASS |
| adjunto no duplica pago | 1 | 1 | 0 | PASS |
| factura pagada tiene abono | 11900 | 11900.00 | 0.00 | PASS |
| importe inválido sin obligación | 0 | 0 | 0 | PASS |
| importe inválido sin obligación | 0 | 0 | 0 | PASS |
| importe inválido sin obligación | 0 | 0 | 0 | PASS |
| importe inválido sin obligación | 0 | 0 | 0 | PASS |
| total neto + IVA | 5950 | 5950.0 | 0.0 | PASS |
| total neto + IVA | 5950 | 5950.0 | 0.0 | PASS |
| total neto + IVA | 5950 | 5950.0 | 0.0 | PASS |
| total neto + IVA | 5950 | 5950.0 | 0.0 | PASS |
| total neto + IVA | 32130 | 32130.0 | 0.0 | PASS |
| total neto + IVA | 5950 | 5950.0 | 0.0 | PASS |
| total neto + IVA | 5950 | 5950.0 | 0.0 | PASS |
| total neto + IVA | 5950 | 5950.0 | 0.0 | PASS |
| total neto + IVA | 5950 | 5950.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 2645 | 2645.0 | 0.0 | PASS |
| total neto + IVA | 2645 | 2645.0 | 0.0 | PASS |
| total neto + IVA | 5950 | 5950.0 | 0.0 | PASS |
| total neto + IVA | 5950 | 5950.0 | 0.0 | PASS |
| total neto + IVA | 5950 | 5950.0 | 0.0 | PASS |
| total neto + IVA | 5950 | 5950.0 | 0.0 | PASS |
| total neto + IVA | 8925 | 8925.0 | 0.0 | PASS |
| total neto + IVA | 8925 | 8925.0 | 0.0 | PASS |
| total neto + IVA | 8925 | 8925.0 | 0.0 | PASS |
| total neto + IVA | 8925 | 8925.0 | 0.0 | PASS |
| total neto + IVA | 8742 | 8742.0 | 0.0 | PASS |
| total neto + IVA | 8925 | 8925.0 | 0.0 | PASS |
| total neto + IVA | 8925 | 8925.0 | 0.0 | PASS |
| total neto + IVA | 8925 | 8925.0 | 0.0 | PASS |
| total neto + IVA | 8925 | 8925.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 3971 | 3971.0 | 0.0 | PASS |
| total neto + IVA | 3971 | 3971.0 | 0.0 | PASS |
| total neto + IVA | 8925 | 8925.0 | 0.0 | PASS |
| total neto + IVA | 8925 | 8925.0 | 0.0 | PASS |
| total neto + IVA | 8925 | 8925.0 | 0.0 | PASS |
| total neto + IVA | 8925 | 8925.0 | 0.0 | PASS |
| total neto + IVA | 89250 | 89250.0 | 0.0 | PASS |
| total neto + IVA | 89250 | 89250.0 | 0.0 | PASS |
| total neto + IVA | 89250 | 89250.0 | 0.0 | PASS |
| total neto + IVA | 89250 | 89250.0 | 0.0 | PASS |
| total neto + IVA | 60 | 60.0 | 0.0 | PASS |
| total neto + IVA | 89250 | 89250.0 | 0.0 | PASS |
| total neto + IVA | 89250 | 89250.0 | 0.0 | PASS |
| total neto + IVA | 89250 | 89250.0 | 0.0 | PASS |
| total neto + IVA | 89250 | 89250.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 5299 | 5299.0 | 0.0 | PASS |
| total neto + IVA | 5299 | 5299.0 | 0.0 | PASS |
| total neto + IVA | 89250 | 89250.0 | 0.0 | PASS |
| total neto + IVA | 89250 | 89250.0 | 0.0 | PASS |
| total neto + IVA | 89250 | 89250.0 | 0.0 | PASS |
| total neto + IVA | 89250 | 89250.0 | 0.0 | PASS |
| total neto + IVA | 32130 | 32130.0 | 0.0 | PASS |
| total neto + IVA | 14875 | 14875.0 | 0.0 | PASS |
| total neto + IVA | 14875 | 14875.0 | 0.0 | PASS |
| total neto + IVA | 14875 | 14875.0 | 0.0 | PASS |
| total neto + IVA | 14875 | 14875.0 | 0.0 | PASS |
| total neto + IVA | 29750 | 29750.0 | 0.0 | PASS |
| total neto + IVA | 29750 | 29750.0 | 0.0 | PASS |
| total neto + IVA | 0 | 0.0 | 0.0 | PASS |
| total neto + IVA | 14875 | 14875.0 | 0.0 | PASS |
| total neto + IVA | 14875 | 14875.0 | 0.0 | PASS |
| total neto + IVA | 14875 | 14875.0 | 0.0 | PASS |
| total neto + IVA | 14875 | 14875.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 6629 | 6629.0 | 0.0 | PASS |
| total neto + IVA | 6629 | 6629.0 | 0.0 | PASS |
| total neto + IVA | 14875 | 14875.0 | 0.0 | PASS |
| total neto + IVA | 14875 | 14875.0 | 0.0 | PASS |
| total neto + IVA | 14875 | 14875.0 | 0.0 | PASS |
| total neto + IVA | 14875 | 14875.0 | 0.0 | PASS |
| total neto + IVA | 32130 | 32130.0 | 0.0 | PASS |
| total neto + IVA | 17850 | 17850.0 | 0.0 | PASS |
| total neto + IVA | 17850 | 17850.0 | 0.0 | PASS |
| total neto + IVA | 17850 | 17850.0 | 0.0 | PASS |
| total neto + IVA | 17850 | 17850.0 | 0.0 | PASS |
| total neto + IVA | 3213000004 | 3213000004.0 | 0.0 | PASS |
| total neto + IVA | 3213000004 | 3213000004.0 | 0.0 | PASS |
| total neto + IVA | 17850 | 17850.0 | 0.0 | PASS |
| total neto + IVA | 17850 | 17850.0 | 0.0 | PASS |
| total neto + IVA | 17850 | 17850.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 7962 | 7962.0 | 0.0 | PASS |
| total neto + IVA | 7962 | 7962.0 | 0.0 | PASS |
| total neto + IVA | 17850 | 17850.0 | 0.0 | PASS |
| total neto + IVA | 17850 | 17850.0 | 0.0 | PASS |
| total neto + IVA | 17850 | 17850.0 | 0.0 | PASS |
| total neto + IVA | 17850 | 17850.0 | 0.0 | PASS |
| total neto + IVA | 32130 | 32130.0 | 0.0 | PASS |
| total neto + IVA | 32130 | 32130.0 | 0.0 | PASS |
| total neto + IVA | 14875 | 14875.0 | 0.0 | PASS |
| total neto + IVA | 14875 | 14875.0 | 0.0 | PASS |
| total neto + IVA | 19040 | 19040.0 | 0.0 | PASS |
| total neto + IVA | 19040 | 19040.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 32130 | 32130.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 32130 | 32130.0 | 0.0 | PASS |
| total neto + IVA | 23800 | 23800.0 | 0.0 | PASS |
| total neto + IVA | 23800 | 23800.0 | 0.0 | PASS |
| total neto + IVA | 32130 | 32130.0 | 0.0 | PASS |
| total neto + IVA | 35700 | 35700.0 | 0.0 | PASS |
| total neto + IVA | 35700 | 35700.0 | 0.0 | PASS |
| total neto + IVA | 32130 | 32130.0 | 0.0 | PASS |
| total neto + IVA | 47600 | 47600.0 | 0.0 | PASS |
| total neto + IVA | 47600 | 47600.0 | 0.0 | PASS |
| total neto + IVA | 32130 | 32130.0 | 0.0 | PASS |
| total neto + IVA | 59500 | 59500.0 | 0.0 | PASS |
| total neto + IVA | 59500 | 59500.0 | 0.0 | PASS |
| total neto + IVA | 32130 | 32130.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 32130 | 32130.0 | 0.0 | PASS |
| total neto + IVA | 23800 | 23800.0 | 0.0 | PASS |
| total neto + IVA | 23800 | 23800.0 | 0.0 | PASS |
| total neto + IVA | 32130 | 32130.0 | 0.0 | PASS |
| total neto + IVA | 35700 | 35700.0 | 0.0 | PASS |
| total neto + IVA | 35700 | 35700.0 | 0.0 | PASS |
| total neto + IVA | 32130 | 32130.0 | 0.0 | PASS |
| total neto + IVA | 47600 | 47600.0 | 0.0 | PASS |
| total neto + IVA | 47600 | 47600.0 | 0.0 | PASS |
| total neto + IVA | 32130 | 32130.0 | 0.0 | PASS |
| total neto + IVA | 59500 | 59500.0 | 0.0 | PASS |
| total neto + IVA | 59500 | 59500.0 | 0.0 | PASS |
| total neto + IVA | 32130 | 32130.0 | 0.0 | PASS |
| total neto + IVA | 8742 | 8742.0 | 0.0 | PASS |
| total neto + IVA | 60 | 60.0 | 0.0 | PASS |
| total neto + IVA | 0 | 0.0 | 0.0 | PASS |
| total neto + IVA | 3213000000 | 3213000000.0 | 0.0 | PASS |
| total neto + IVA | 3570 | 3570.0 | 0.0 | PASS |
| total neto + IVA | 3570 | 3570.0 | 0.0 | PASS |
| total neto + IVA | 7140 | 7140.0 | 0.0 | PASS |
| total neto + IVA | 7140 | 7140.0 | 0.0 | PASS |
| total neto + IVA | 10710 | 10710.0 | 0.0 | PASS |
| total neto + IVA | 10710 | 10710.0 | 0.0 | PASS |
| total neto + IVA | 14280 | 14280.0 | 0.0 | PASS |
| total neto + IVA | 14280 | 14280.0 | 0.0 | PASS |
| total neto + IVA | 17850 | 17850.0 | 0.0 | PASS |
| total neto + IVA | 17850 | 17850.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |
| total neto + IVA | 11900 | 11900.0 | 0.0 | PASS |

Los controles de cierre contrastan total de documento, sumas de eventos frente a encabezados de factura/gasto, ausencia de sobrepagos, cuenta/moneda/importe de todas las fuentes conciliadas y reciprocidad de transferencias. Evidencia: control_monetario_final.json y matriz_cuantitativa_final.json. No se suman escenarios independientes como una pérdida de empresa.
