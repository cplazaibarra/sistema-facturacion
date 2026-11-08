# Informe final de certificación ERP V1

**Dictamen global: RED. No puede responderse afirmativamente que todos los valores y procesos sean confiables sin restricciones.** Existen fallos financieros confirmados y límites de interfaz/cobertura.

- Funcionalidades agrupadas: 32, en 20 módulos.
- Pruebas planificadas/individualizadas: 922.
- Pruebas ejecutadas en la ronda final: 914 (sin contar como nuevas las repeticiones de preparación/fixtures).
- PASS: 908; FAIL: 6; BLOCKED: 8; NOT VERIFIED: 0.
- Estados de módulos: {'YELLOW': 15, 'GREEN': 1, 'RED': 4}.
- Comprobaciones cuantitativas con diferencia explícita: 196; diferencias distintas de cero: 7.
- Diferencias de cantidades en escenarios negativos: 1; consultar matriz_cantidades.json. La igualdad ledger/lotes no valida por sí sola la legitimidad de una fabricación.
- Cinco ciclos integrados: Counter({'PASS': 5}).

Las cifras anteriores incluyen regresión complementaria y certificación nueva, distinguidas en sus XML/logs. No se asume que una regresión verde sea certificación financiera. Los resultados por módulo de la siguiente tabla corresponden a casos nuevos y navegador; el resto está en baseline_casos.json.

| MÓDULO | PRUEBAS | PASS | FAIL | BLOCKED | NOT VERIFIED | ESTADO |
|---|---|---|---|---|---|---|
| Productos | 20 | 20 | 0 | 0 | 0 | YELLOW |
| Proveedores | 10 | 10 | 0 | 0 | 0 | YELLOW |
| Clientes | 10 | 10 | 0 | 0 | 0 | YELLOW |
| Órdenes de compra | 10 | 10 | 0 | 0 | 0 | YELLOW |
| Recepción | 10 | 10 | 0 | 0 | 0 | YELLOW |
| Inventario y Kardex | 30 | 30 | 0 | 0 | 0 | YELLOW |
| Costos PPP/FIFO y precios | 20 | 20 | 0 | 0 | 0 | YELLOW |
| Cotizaciones | 15 | 15 | 0 | 0 | 0 | GREEN |
| Ventas | 10 | 10 | 0 | 0 | 0 | YELLOW |
| Preparación y despacho | 20 | 20 | 0 | 0 | 0 | YELLOW |
| Producción | 40 | 39 | 1 | 0 | 0 | RED |
| Cuentas por Cobrar | 10 | 10 | 0 | 0 | 0 | YELLOW |
| Cuentas por Pagar | 10 | 6 | 4 | 0 | 0 | RED |
| Gastos Operacionales | 10 | 10 | 0 | 0 | 0 | YELLOW |
| Deudas | 20 | 20 | 0 | 0 | 0 | YELLOW |
| Cuentas bancarias | 10 | 10 | 0 | 0 | 0 | YELLOW |
| Conciliación | 20 | 19 | 1 | 0 | 0 | RED |
| Flujo de Caja | 10 | 10 | 0 | 0 | 0 | RED |
| Reportes | 10 | 10 | 0 | 0 | 0 | YELLOW |
| Usuarios, permisos y administración | 30 | 30 | 0 | 0 | 0 | YELLOW |

## Operaciones monetarias relevantes

| OPERACIÓN | MONTO ESPERADO | MONTO REAL | DIFERENCIA | RESULTADO |
|---|---|---|---|---|
| saldo CxP proyectado después de abono | 9900 | 0.00 | -9900.00 | FAIL |
| saldo CxP proyectado después de abono | 6000 | 0.00 | -6000.00 | FAIL |
| sobrepago CxP rechazado | 0 | 11901.0 | 11901.0 | FAIL |
| abonos CxP acumulados | 11900 | 3000.0 | -8900.0 | FAIL |
| Importe bancario frente a cobro ERP conciliado | 11900.0 | 11901.00 | 1.00 | FAIL |
| Exceso pagado sobre obligación CxP | 0 | 1.0 | 1.0 | FAIL |
| Exceso pagado sobre obligación CxP | 0 | 1.0 | 1.0 | FAIL |
| C1 compra bruta | 11900 | 11900.0 | 0.0 | PASS |
| C1 neto | 27000 | 27000.0 | 0.0 | PASS |
| C1 IVA | 5130 | 5130.0 | 0.0 | PASS |
| C1 costo vendido | 3000 | 3000.0 | 0.0 | PASS |
| C1 utilidad | 24000 | 24000.0 | 0.0 | PASS |
| C1 cobro íntegro | 32130 | 32130.0 | 0.0 | PASS |
| C1 ingreso único | 32130 | 32130.00 | 0.00 | PASS |
| C1 banco final | 1032130 | 1032130.00 | 0.00 | PASS |
| C2 costo unitario | 1250 | 1250.0 | 0.0 | PASS |
| C2 valor transferido | 18750 | 18750.0 | 0.0 | PASS |
| C2 costo vendido | 6250 | 6250.0 | 0.0 | PASS |
| C2 utilidad neta | 6250 | 6250.0 | 0.0 | PASS |
| C2 IVA | 2375 | 2375.0 | 0.0 | PASS |
| C3 regla recurrente inmutable | 11900 | 11900.00 | 0.00 | PASS |
| C3 egresos únicos | 32130 | 32130.00 | 0.00 | PASS |
| C3 saldo final | 967870 | 967870.00 | 0.00 | PASS |
| C5 saldo cuenta origen | 838100 | 838100.00 | 0.00 | PASS |

La tabla completa está en 10_CONCILIACION_MATEMATICA.md. Inventario y diferencias de conciliación/pagos están individualizados en control_monetario_final.json.

## Protección del entorno

Flujo de Caja se clasifica RED por los fallos integrados de CxP-1 y CxP-2: omite $9.900 y $6.000 pendientes. Sus diez comprobaciones directas pasan; estos dos casos se cuentan una sola vez, en CxP. No sumar las diferencias como pérdida real: son verificaciones sintéticas, algunas repetidas en clones distintos.

Bases protegidas con huellas íntegras antes/después: **True**. Código productivo idéntico: **True**. Tag idéntico: **True**. Eliminación de DB/rol temporal: **True**. Usuario temporal: permisos de escritura en tablas protegidas {'facturacion': 0, 'facturacion_cleanup_verify': 0}. No se ejecutaron migraciones ni operaciones mutables en facturacion o su plantilla; no se modificó OT-09270 ni otros documentos reales.

## Condición de cierre

La certificación termina con este informe y la evidencia. No se corrigieron funciones ni se realizaron commits o pushes. Se requiere autorización separada para reparar defectos. Las limitaciones de datos y de interfaz quedan explícitas; no se transforma NOT VERIFIED en GREEN.
