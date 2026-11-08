# Conciliación matemática independiente

Oráculo: scripts/reference.py, Decimal y ROUND_HALF_UP. No importa services.money ni funciones de precios para producir los valores esperados. PPP se compara a su escala explícita de cuatro decimales. Los valores enteros ya redondeados requieren diferencia cero.

| OPERACIÓN / CASO | MONTO ESPERADO | MONTO REAL | DIFERENCIA | RESULTADO |
|---|---|---|---|---|
| test_certification.py::test_business_feature[1-productos] / costo persistido | 1235 | 1235.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-recepcion] / CxP bruta | 3838 | 3838.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-inventario] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[1-ppp_fifo] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[1-cotizaciones] / total persistido | 32130 | 32130.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-cotizaciones] / subtotal neto | 27000.00 | 27000.0 | 0.00 | PASS |
| test_certification.py::test_business_feature[1-cotizaciones] / neto servidor | 27000 | 27000.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-cotizaciones] / IVA servidor | 5130 | 5130.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-ventas] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[1-ventas] / costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-despacho] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[1-despacho] / costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-produccion] / costo unitario fabricación | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-cxc] / cobro persistido | 2000 | 2000.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-cxc] / saldo CxC | 9900 | 9900.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-cxp] / abono CxP aplicado | 2000 | 2000.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-cxp] / saldo CxP proyectado después de abono | 9900 | 0.00 | -9900.00 | FAIL |
| test_certification.py::test_business_feature[1-gastos] / importe real del mes | 15111 | 15111.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[1-gastos] / regla mensual intacta | 12000 | 12000.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[1-deudas] / principal no duplicado | 100001 | 100001.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[1-deudas] / saldo cuota | 23333.67 | 23333.67 | 0.00 | PASS |
| test_certification.py::test_business_feature[1-bancos] / saldo contable banco | 1007000 | 1007000.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[1-flujo_caja] / saldo inicial | 100000 | 100000.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[1-flujo_caja] / saldo final real | 109520 | 109520.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[1-flujo_caja] / ingresos reales | 11900 | 11900.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[1-reportes] / reporte total bruto | 2645 | 2645.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-reportes] / reporte neto | 2223 | 2223.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-reportes] / reporte IVA | 422 | 422.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-embalajes] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[1-embalajes] / costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-embalajes] / costo embalaje | 100 | 100.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-precios] / precio neto por PPP y recargo | 1250.00 | 1250.0 | 0.00 | PASS |
| test_certification.py::test_business_feature[1-trazabilidad] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[1-trazabilidad] / costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-operario] / operario costo producción | 1100 | 1100.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-excel_deudas] / principal exportado exacto | 300001 | 300001.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[2-productos] / costo persistido | 1236 | 1236.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-recepcion] / CxP bruta | 5474 | 5474.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-inventario] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[2-ppp_fifo] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[2-cotizaciones] / total persistido | 8742 | 8742.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-cotizaciones] / subtotal neto | 7345.57 | 7345.57 | 0.00 | PASS |
| test_certification.py::test_business_feature[2-cotizaciones] / neto servidor | 7346 | 7346.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-cotizaciones] / IVA servidor | 1396 | 1396.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-ventas] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[2-ventas] / costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-despacho] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[2-despacho] / costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-produccion] / costo unitario fabricación | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-cxc] / cobro persistido | 5900 | 5900.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-cxc] / saldo CxC | 6000 | 6000.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-cxp] / abono CxP aplicado | 5900 | 5900.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-cxp] / saldo CxP proyectado después de abono | 6000 | 0.00 | -6000.00 | FAIL |
| test_certification.py::test_business_feature[2-gastos] / importe real del mes | 15222 | 15222.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[2-gastos] / regla mensual intacta | 12100 | 12100.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[2-deudas] / principal no duplicado | 100002 | 100002.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[2-deudas] / saldo cuota | 23334.00 | 23334.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[2-bancos] / saldo contable banco | 1014000 | 1014000.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[2-flujo_caja] / saldo inicial | 100000 | 100000.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[2-flujo_caja] / saldo final real | 119040 | 119040.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[2-flujo_caja] / ingresos reales | 23800 | 23800.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[2-reportes] / reporte total bruto | 3971 | 3971.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-reportes] / reporte neto | 3337 | 3337.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-reportes] / reporte IVA | 634 | 634.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-embalajes] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[2-embalajes] / costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-embalajes] / costo embalaje | 200 | 200.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-precios] / precio neto por PPP y recargo | 1437.50 | 1437.5 | 0.00 | PASS |
| test_certification.py::test_business_feature[2-trazabilidad] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[2-trazabilidad] / costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-operario] / operario costo producción | 1200 | 1200.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-excel_deudas] / principal exportado exacto | 300002 | 300002.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[3-productos] / costo persistido | 1237 | 1237.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-recepcion] / CxP bruta | 7289 | 7289.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-inventario] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[3-ppp_fifo] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[3-cotizaciones] / total persistido | 60 | 60.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-cotizaciones] / subtotal neto | 50.00 | 50.0 | 0.00 | PASS |
| test_certification.py::test_business_feature[3-cotizaciones] / neto servidor | 50 | 50.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-cotizaciones] / IVA servidor | 10 | 10.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-ventas] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[3-despacho] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[3-cxp] / sobrepago CxP rechazado | 0 | 11901.0 | 11901.0 | FAIL |
| test_certification.py::test_business_feature[3-gastos] / importe real del mes | 15333 | 15333.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[3-gastos] / regla mensual intacta | 12200 | 12200.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[3-deudas] / principal no duplicado | 100003 | 100003.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[3-deudas] / saldo cuota | 33333.33 | 33333.33 | 0.00 | PASS |
| test_certification.py::test_business_feature[3-bancos] / saldo contable banco | 1021000 | 1021000.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[3-flujo_caja] / saldo inicial | 100000 | 100000.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[3-flujo_caja] / saldo final real | 128560 | 128560.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[3-flujo_caja] / ingresos reales | 35700 | 35700.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[3-reportes] / reporte total bruto | 5299 | 5299.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-reportes] / reporte neto | 4453 | 4453.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-reportes] / reporte IVA | 846 | 846.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-embalajes] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[3-precios] / precio neto por PPP y recargo | 1750.00 | 1750.0 | 0.00 | PASS |
| test_certification.py::test_business_feature[3-trazabilidad] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[3-excel_deudas] / principal exportado exacto | 300003 | 300003.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[4-productos] / costo persistido | 1238 | 1238.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-recepcion] / CxP bruta | 9282 | 9282.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-inventario] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[4-ppp_fifo] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[4-ppp_fifo] / costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-cotizaciones] / total persistido | 0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-cotizaciones] / subtotal neto | 0.00 | 0.0 | 0.00 | PASS |
| test_certification.py::test_business_feature[4-cotizaciones] / neto servidor | 0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-cotizaciones] / IVA servidor | 0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-ventas] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[4-ventas] / costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-despacho] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[4-despacho] / costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-produccion] / costo unitario fabricación | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-cxc] / cobro persistido | 11900 | 11900.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-cxc] / saldo CxC | 0 | 0 | 0 | PASS |
| test_certification.py::test_business_feature[4-cxp] / abono CxP aplicado | 11900 | 11900.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-gastos] / importe real del mes | 15444 | 15444.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[4-gastos] / regla mensual intacta | 12300 | 12300.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[4-gastos] / otro período diferente | 16444 | 16444.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[4-deudas] / principal no duplicado | 100004 | 100004.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[4-deudas] / saldo cuota | 0.00 | 0.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[4-bancos] / saldo contable banco | 1028000 | 1028000.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[4-flujo_caja] / saldo inicial | 100000 | 100000.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[4-flujo_caja] / saldo final real | 138080 | 138080.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[4-flujo_caja] / ingresos reales | 47600 | 47600.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[4-reportes] / reporte total bruto | 6629 | 6629.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-reportes] / reporte neto | 5571 | 5571.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-reportes] / reporte IVA | 1058 | 1058.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-embalajes] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[4-embalajes] / costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-embalajes] / costo embalaje | 400 | 400.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-precios] / precio neto por PPP y recargo | 1562.50 | 1562.5 | 0.00 | PASS |
| test_certification.py::test_business_feature[4-trazabilidad] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[4-trazabilidad] / costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-operario] / operario costo producción | 1400 | 1400.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-excel_deudas] / principal exportado exacto | 300004 | 300004.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[5-productos] / costo persistido | 1239 | 1239.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-recepcion] / CxP bruta | 11454 | 11454.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-inventario] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[5-ppp_fifo] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[5-ppp_fifo] / costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-ppp_fifo] / PPP revaluado independiente | 1400.0000 | 1400.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[5-ppp_fifo] / costo congelado histórico conservado | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-cotizaciones] / total persistido | 3213000000 | 3213000000.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-cotizaciones] / subtotal neto | 2700000000.00 | 2700000000.0 | 0.00 | PASS |
| test_certification.py::test_business_feature[5-cotizaciones] / neto servidor | 2700000000 | 2700000000.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-cotizaciones] / IVA servidor | 513000000 | 513000000.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-cotizaciones] / conversión mismo bruto | 3213000004 | 3213000004.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-ventas] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[5-ventas] / costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-despacho] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[5-despacho] / costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-produccion] / costo unitario fabricación | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-cxc] / cobro persistido | 3000 | 3000.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-cxc] / saldo CxC | 8900 | 8900.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-cxp] / abono CxP aplicado | 3000 | 3000.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-cxp] / abonos CxP acumulados | 11900 | 3000.0 | -8900.0 | FAIL |
| test_certification.py::test_business_feature[5-gastos] / importe real del mes | 15555 | 15555.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[5-gastos] / regla mensual intacta | 12400 | 12400.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[5-gastos] / otro período diferente | 16555 | 16555.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[5-deudas] / principal no duplicado | 100005 | 100005.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[5-deudas] / saldo cuota | 23335.00 | 23335.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[5-bancos] / saldo contable banco | 1035000 | 1035000.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[5-flujo_caja] / saldo inicial | 100000 | 100000.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[5-flujo_caja] / saldo final real | 147600 | 147600.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[5-flujo_caja] / ingresos reales | 59500 | 59500.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[5-reportes] / reporte total bruto | 7962 | 7962.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-reportes] / reporte neto | 6691 | 6691.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-reportes] / reporte IVA | 1271 | 1271.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-embalajes] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[5-embalajes] / costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-embalajes] / costo embalaje | 500 | 500.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-precios] / precio neto por PPP y recargo | 2500.00 | 2500.0 | 0.00 | PASS |
| test_certification.py::test_business_feature[5-trazabilidad] / PPP independiente | 1250.0000 | 1250.0 | 0.0000 | PASS |
| test_certification.py::test_business_feature[5-trazabilidad] / costo congelado | 1250 | 1250.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-operario] / operario costo producción | 1500 | 1500.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-excel_deudas] / principal exportado exacto | 300005 | 300005.00 | 0.00 | PASS |
| test_cycles.py::test_complete_business_cycle[1] / C1 compra bruta | 11900 | 11900.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[1] / C1 neto | 27000 | 27000.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[1] / C1 IVA | 5130 | 5130.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[1] / C1 costo vendido | 3000 | 3000.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[1] / C1 utilidad | 24000 | 24000.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[1] / C1 cobro íntegro | 32130 | 32130.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[1] / C1 ingreso único | 32130 | 32130.00 | 0.00 | PASS |
| test_cycles.py::test_complete_business_cycle[1] / C1 banco final | 1032130 | 1032130.00 | 0.00 | PASS |
| test_cycles.py::test_complete_business_cycle[2] / C2 costo unitario | 1250 | 1250.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[2] / C2 valor transferido | 18750 | 18750.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[2] / C2 costo vendido | 6250 | 6250.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[2] / C2 utilidad neta | 6250 | 6250.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[2] / C2 IVA | 2375 | 2375.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[3] / C3 regla recurrente inmutable | 11900 | 11900.00 | 0.00 | PASS |
| test_cycles.py::test_complete_business_cycle[3] / C3 egresos únicos | 32130 | 32130.00 | 0.00 | PASS |
| test_cycles.py::test_complete_business_cycle[3] / C3 saldo final | 967870 | 967870.00 | 0.00 | PASS |
| test_cycles.py::test_complete_business_cycle[5] / C5 saldo cuenta origen | 838100 | 838100.00 | 0.00 | PASS |
| cierre-1-conciliacion-223 / Importe bancario frente a cobro ERP conciliado | 11900.0 | 11901.00 | 1.00 | FAIL |
| cierre-1-sobrepago-155 / Exceso pagado sobre obligación CxP | 0 | 1.0 | 1.0 | FAIL |
| cierre-2-sobrepago-63 / Exceso pagado sobre obligación CxP | 0 | 1.0 | 1.0 | FAIL |

## Cantidades e inventario (unidades, no pesos)

| CASO / OPERACIÓN | ESPERADO | REAL | DIFERENCIA | ESTADO |
|---|---|---|---|---|
| test_certification.py::test_business_feature[1-productos] / sin stock creado | 0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-ordenes_compra] / OC neta | 3375 | 3375.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-ordenes_compra] / OC no crea stock | 0.0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-recepcion] / stock recibido | 3 | 3.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-inventario] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-inventario] / reserva global | 2 | 2.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-inventario] / disponible | 18 | 18.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-ppp_fifo] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-ppp_fifo] / stock de capas | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-ventas] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-ventas] / salida o bloqueo por insuficiencia | 18 | 18.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-despacho] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-despacho] / salida o bloqueo por insuficiencia | 18 | 18.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-produccion] / fabricación o bloqueo | 2 | 2.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-produccion] / MP consumida | 18 | 18.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-reportes] / distribución concilia | 6919245.0 | 6919245.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-ajustes] / solicitud sin stock | 10 | 10.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-ajustes] / ajuste aprobado | 11 | 11.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-embalajes] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-embalajes] / salida o bloqueo por insuficiencia | 18 | 18.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-trazabilidad] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-trazabilidad] / salida o bloqueo por insuficiencia | 18 | 18.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-operario] / operario salida PT | 1 | 1.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[1-agenda] / agenda no consume | 0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-productos] / sin stock creado | 0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-ordenes_compra] / OC neta | 5000 | 5000.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-ordenes_compra] / OC no crea stock | 0.0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-recepcion] / stock recibido | 4 | 4.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-recepcion] / recepción parcial | 3 | 3 | 0 | PASS |
| test_certification.py::test_business_feature[2-inventario] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-inventario] / reserva global | 3 | 3.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-inventario] / disponible | 17 | 17.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-ppp_fifo] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-ppp_fifo] / stock de capas | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-ventas] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-ventas] / salida o bloqueo por insuficiencia | 17 | 17.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-despacho] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-despacho] / salida o bloqueo por insuficiencia | 17 | 17.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-produccion] / fabricación o bloqueo | 3 | 3.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-produccion] / MP consumida | 17 | 17.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-reportes] / distribución concilia | 6994616.0 | 6994616.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-ajustes] / solicitud sin stock | 10 | 10.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-ajustes] / ajuste aprobado | 12 | 12.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-embalajes] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-embalajes] / salida o bloqueo por insuficiencia | 17 | 17.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-trazabilidad] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-trazabilidad] / salida o bloqueo por insuficiencia | 17 | 17.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-operario] / operario salida PT | 2 | 2.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[2-agenda] / agenda no consume | 0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-productos] / sin stock creado | 0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-ordenes_compra] / OC neta | 6875 | 6875.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-ordenes_compra] / OC no crea stock | 0.0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-recepcion] / stock recibido | 5 | 5.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-inventario] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-inventario] / reserva global | 30 | 30.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-inventario] / disponible | 0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-ppp_fifo] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-ppp_fifo] / stock de capas | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-ventas] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-ventas] / salida o bloqueo por insuficiencia | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-despacho] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-despacho] / salida o bloqueo por insuficiencia | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-produccion] / fabricación o bloqueo | 0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-reportes] / distribución concilia | 7398565.0 | 7398565.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-embalajes] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-embalajes] / salida o bloqueo por insuficiencia | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-trazabilidad] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-trazabilidad] / salida o bloqueo por insuficiencia | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[3-operario] / operario salida PT | 0 | 3.0 | 3.0 | FAIL |
| test_certification.py::test_business_feature[3-agenda] / agenda no consume | 0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-productos] / sin stock creado | 0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-ordenes_compra] / OC neta | 9000 | 9000.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-ordenes_compra] / OC no crea stock | 0.0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-ordenes_compra] / recepción ligada | 6 | 6.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-recepcion] / stock recibido | 6 | 6.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-inventario] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-inventario] / reserva global | 5 | 5.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-inventario] / disponible | 15 | 15.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-ppp_fifo] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-ppp_fifo] / salida o bloqueo por insuficiencia | 15 | 15.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-ppp_fifo] / FIFO capa antigua agotada | 0 | 0 | 0 | PASS |
| test_certification.py::test_business_feature[4-ventas] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-ventas] / salida o bloqueo por insuficiencia | 15 | 15.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-despacho] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-despacho] / salida o bloqueo por insuficiencia | 15 | 15.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-produccion] / fabricación o bloqueo | 5 | 5.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-produccion] / MP consumida | 15 | 15.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-reportes] / distribución concilia | 7696744.0 | 7696744.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-ajustes] / solicitud sin stock | 10 | 10.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-ajustes] / ajuste aprobado | 14 | 14.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-embalajes] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-embalajes] / salida o bloqueo por insuficiencia | 15 | 15.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-trazabilidad] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-trazabilidad] / salida o bloqueo por insuficiencia | 15 | 15.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-operario] / operario salida PT | 4 | 4.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[4-agenda] / agenda no consume | 0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-productos] / sin stock creado | 0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-ordenes_compra] / OC neta | 11375 | 11375.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-ordenes_compra] / OC no crea stock | 0.0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-ordenes_compra] / OC anulada no consume | 0 | 0.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-recepcion] / stock recibido | 7 | 7.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-recepcion] / sin sobre-recepción | 7 | 7.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-inventario] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-inventario] / reserva global | 6 | 6.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-inventario] / disponible | 14 | 14.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-ppp_fifo] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-ppp_fifo] / salida o bloqueo por insuficiencia | 14 | 14.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-cotizaciones] / cotización modificada | 3213000004 | 3213000004.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-ventas] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-ventas] / salida o bloqueo por insuficiencia | 14 | 14.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-ventas] / reversa stock | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-despacho] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-despacho] / salida o bloqueo por insuficiencia | 14 | 14.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-produccion] / fabricación o bloqueo | 6 | 6.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-produccion] / MP consumida | 14 | 14.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-bancos] / transferencia consolidada neutra | 1035000 | 1035000.00 | 0.00 | PASS |
| test_certification.py::test_business_feature[5-reportes] / distribución concilia | 3220811810.0 | 3220811810.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-ajustes] / solicitud sin stock | 10 | 10.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-ajustes] / ajuste aprobado | 15 | 15.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-ajustes] / sin duplicado | 15 | 15.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-embalajes] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-embalajes] / salida o bloqueo por insuficiencia | 14 | 14.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-trazabilidad] / venta pendiente sin salida | 20 | 20.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-trazabilidad] / salida o bloqueo por insuficiencia | 14 | 14.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-operario] / operario salida PT | 5 | 5.0 | 0.0 | PASS |
| test_certification.py::test_business_feature[5-agenda] / agenda no consume | 0 | 0.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[1] / C1 reserva sin salida | 10 | 10.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[1] / C1 stock final | 7 | 7.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[2] / C2 MP remanente | 5 | 5.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[2] / C2 PT fabricado | 15 | 15.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[2] / C2 PT final | 10 | 10.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[4] / C4 reserva mayor al físico | 13 | 13.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[4] / C4 disponible cero | 0 | 0.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[4] / C4 operador elige B | 5 | 5.0 | 0.0 | PASS |
| test_cycles.py::test_complete_business_cycle[4] / C4 no segunda salida | 5 | 5.0 | 0.0 | PASS |

Controles de cierre: `evidencia/control_monetario_final.json` y versiones de cada ronda. Los sobrepagos y diferencias de conciliación se registran aunque el ERP los acepte. Los indicadores booleanos fallidos no se convierten artificialmente en diferencias monetarias cero.
