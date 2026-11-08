# Informe final de corrección y recertificación ERP V1

**Dictamen global:RED.** Las pruebas automatizadas aprueban, pero falla el control acumulado de protección: aparecieron migraciones nuevas en facturacion entre ejecuciones. La contención de arranque está implementada y recertificada; no se revierte ni se oculta el incidente. Además, 13 módulos conservan límites de cobertura interactiva.

## Resumen ejecutivo

- 32 funcionalidades agrupadas en 20 módulos.
- Plan original: 922; 922 PASS.
- Casos nuevos: 96; total planificado y ejecutado: 1018.
- PASS: 1017; FAIL: 1 (protección acumulada); BLOCKED: 0; NOT VERIFIED: 0 dentro de la matriz ejecutable.
- Pruebas automatizadas: 1017 PASS: 599 de regresión, 228 funcionales/E2E y 190 de navegador. Los cinco ciclos empresariales aprobaron.
- Módulos: 6 GREEN, 13 YELLOW y 1 RED.
- Diferencias cuantitativas:0; inventario:0; anomalías financieras de cierre:0.

## Causas y correcciones

1. CxP cerraba con cualquier abono y reemplazaba lo pagado: ledger individual, acumulación, saldo/estado correcto, Decimal, validación de cuenta y bloqueo transaccional. Incluye facturas y gastos, continuidad de parciales previos, idempotencia, historial y rechazo de sobrepagos.
2. Flujo omitía saldos por el cierre anterior: eventos reales por fecha/cuenta, compromiso restante por vencimiento y precedencia sin duplicar recurrencias/cartola.
3. Conciliación sólo comprobaba existencia: igualdad exacta, signo, CLP, cuenta, aprobación contable, pago válido y bloqueo de enlaces concurrentes; reversa auditable sin nuevos pagos.
4. Producción admitía consumos vacíos: plan y consumos suficientes, costo trazable, locks y rollback; cero entrada fantasma.
5. Calendario de gastos no sincronizaba su campo visible obligatorio: setDate de Flatpickr, confirmado por formularios reales. También se corrigió una regresión intermedia del adjunto en reintento, conservando un solo pago.

Los seis casos originalmente fallidos se repiten con el mismo saldo/importe/stock esperado y aprueban en la matriz final. Los fallos derivados de Flujo no se contabilizan como defectos raíz independientes.

| MÓDULO | PRUEBAS | PASS | FAIL | BLOCKED | ESTADO |
|---|---|---|---|---|---|
| Productos | 20 | 20 | 0 | 0 | YELLOW |
| Proveedores | 10 | 10 | 0 | 0 | YELLOW |
| Clientes | 10 | 10 | 0 | 0 | YELLOW |
| Órdenes de compra | 10 | 10 | 0 | 0 | YELLOW |
| Recepción | 10 | 10 | 0 | 0 | YELLOW |
| Inventario y Kardex | 30 | 30 | 0 | 0 | YELLOW |
| Costos PPP/FIFO y precios | 20 | 20 | 0 | 0 | YELLOW |
| Cotizaciones | 15 | 15 | 0 | 0 | GREEN |
| Ventas | 10 | 10 | 0 | 0 | YELLOW |
| Preparación y despacho | 20 | 20 | 0 | 0 | YELLOW |
| Producción | 57 | 57 | 0 | 0 | GREEN |
| Cuentas por Cobrar | 10 | 10 | 0 | 0 | YELLOW |
| Cuentas por Pagar | 34 | 34 | 0 | 0 | GREEN |
| Gastos Operacionales | 23 | 23 | 0 | 0 | GREEN |
| Deudas | 20 | 20 | 0 | 0 | YELLOW |
| Cuentas bancarias | 10 | 10 | 0 | 0 | YELLOW |
| Conciliación | 39 | 39 | 0 | 0 | GREEN |
| Flujo de Caja | 25 | 25 | 0 | 0 | GREEN |
| Reportes | 10 | 10 | 0 | 0 | YELLOW |
| Usuarios, permisos y administración | 31 | 30 | 1 | 0 | RED |

## Operaciones representativas

| OPERACIÓN | MONTO ESPERADO | MONTO REAL | DIFERENCIA | RESULTADO |
|---|---|---|---|---|
| saldo CxP proyectado después de abono | 9900 | 9900.00 | 0.00 | PASS |
| saldo CxP proyectado después de abono | 6000 | 6000.00 | 0.00 | PASS |
| abonos CxP acumulados | 11900 | 11900.0 | 0.0 | PASS |
| C1 neto | 27000 | 27000.0 | 0.0 | PASS |
| C1 IVA | 5130 | 5130.0 | 0.0 | PASS |
| C1 cobro íntegro | 32130 | 32130.0 | 0.0 | PASS |
| C2 costo unitario | 1250 | 1250.0 | 0.0 | PASS |
| C3 egresos únicos | 32130 | 32130.00 | 0.00 | PASS |
| C3 saldo final | 967870 | 967870.00 | 0.00 | PASS |
| C5 saldo cuenta origen | 838100 | 838100.00 | 0.00 | PASS |
| saldo parcial | 9900 | 9900 | 0 | PASS |
| segundo saldo | 5900 | 5900 | 0 | PASS |

La conciliación completa está en09_CONCILIACION_FINANCIERA_FINAL.md. No se usaron diferencias toleradas para obtener PASS.

## Archivos modificados en esta fase

- app.py
- db.py
- migrations/000028_purchase_payment_items.down.sql
- migrations/000028_purchase_payment_items.up.sql
- migrations/000029_expense_payment_items.down.sql
- migrations/000029_expense_payment_items.up.sql
- migrations/000030_payment_opening_snapshots.down.sql
- migrations/000030_payment_opening_snapshots.up.sql
- repositories/bank_reconciliation_repo.py
- repositories/cash_flow_repo.py
- repositories/finance_repo.py
- repositories/operational_expenses_repo.py
- repositories/purchases_repo.py
- repositories/reporting_repo.py
- routes/compras.py
- routes/usuarios.py
- services/operario_service.py
- templates/compras_cuentas_pagar.html
- templates/compras_historial_pagos.html
- templates/reporte_cuentas_por_pagar.html
- tests/integration/test_bank_reconciliation.py
- tests/integration/test_inventory_valuation_and_reconciler.py
- tests/integration/test_migrations_phase4.py
- tests/integration/test_transactions_phase3.py
- tests/security/test_startup_schema_safety.py

Además: CONTEXTO_MAESTRO_ERP.md y el nuevo directorio de pruebas/informes. Los cambios anteriores permanecen preservados en git_inicial.patch y codigo_inicial.zip; cambios_de_esta_fase.patch separa sólo esta fase de ese estado inicial.

## Protección del entorno

{"initial_snapshots_compared": 22, "all_initial_fingerprints_match_final": false, "all_runs_cleaned": true, "head_unchanged": true, "tag_unchanged": true, "preexisting_operational_rows_unchanged": true, "preexisting_migration_records_unchanged": true, "persistent_template_unchanged": true, "post_containment_fingerprints_unchanged": true}

Última ronda: ambas bases temporales eliminadas, rol eliminado, tablas protegidas escribibles por el rol:{'facturacion': 0, 'facturacion_cleanup_verify': 0}. Se contrastaron huellas de contenido, no sólo conteos. No cambiaron las huellas de las tablas operacionales preexistentes ni de OT-09270; no se hicieron commits/pushes ni se modificó v1.0.0. Esto no equivale a base intacta: hubo cambios de esquema en facturacion.

## Implantación y límites

Las migraciones000028–000030 se verificaron en clones, pero también se encontraron aplicadas en facturacion a las03:45:48,03:50:21 y03:55:19 UTC del21-10-2026. Crearon cuatro tablas vacías y dos vistas, además de tres registros de schema_migrations. La plantilla permanece sin esos cambios. El harness y los roles de prueba no escribieron en las bases protegidas; el cambio ocurrió entre ejecuciones. La causa compatible es el init_db incondicional al importar Flask, susceptible de recarga del servicio al editar los archivos; no se pudo atribuir el PID exacto.

Se contuvo esa vía: app.py inicializa/migra/siembra automáticamente sólo en testing, tras validar el marker del clon; db.init_db exige la misma autorización incluso ante una llamada directa. Desarrollo y producción no ejecutan DDL/seeds al importar. Seis pruebas con PostgreSQL READ ONLY verifican el comportamiento y la suite completa se repitió después de la contención. No se ejecutó una reversa, reparación histórica ni borrado para recuperar artificialmente las huellas. La igualdad de contenido no demuestra ausencia de escrituras de igual valor por el inicializador anterior; por eso tampoco se afirma ausencia total de escrituras operacionales.

El requisito de base operacional intacta no se cumplió. Por eso se registra 1 FAIL de protección acumulada, separado de los fallos funcionales corregidos; no se declara GREEN. No hay diferencias financieras injustificadas en los escenarios sintéticos ejecutados. Los 13 módulos YELLOW mantienen el alcance UI señalado en08_RESULTADOS_REGRESION.md. La tarea termina con el incidente explícito y la evidencia, sin nuevas acciones sobre la base normal.
