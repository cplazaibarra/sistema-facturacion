# Diagnóstico inicial de causas raíz

Estado inicial: HEAD y tag en evidencia/git_inicial.json; cambios anteriores preservados en git_inicial.patch y codigo_inicial.zip. El harness no importa Flask contra bases protegidas. La comparación acumulada posterior detectó una vía separada de inicialización normal y se documenta abajo.

| Fallo original | Entrada / esperado / observado | Ruta y función | Tablas | Causa raíz y propuesta |
|---|---|---|---|---|
| cxp-1 | 11900, abono2000; saldo9900 / 0 | POST /compras/facturas/<id>/registrar-pago → finance_repo.register_purchase_payment | purchase_invoices | UPDATE marca Pagada sin contrastar saldo. Acumular bajo FOR UPDATE y conservar pagos individuales. |
| cxp-2 | 11900, abono5900; saldo6000 / 0 | misma función | mismas tablas; cash_flow_repo | Misma causa. Proyección sólo saldo y egreso real por fecha del abono. |
| cxp-3 | obligación11900, pago11901; rechazo / aceptado | misma función | mismas tablas | No valida signo, finitud ni límite. Decimal y validación atómica antes de escribir. |
| cxp-5 | abonos3000+8900;11900 /3000 | misma función | mismas tablas | Rechaza segundo abono tras cerrar indebidamente. Estados derivados y claves de idempotencia. |
| conciliacion-3 | ERP11900, banco11901;rechazo / aceptado | POST /reporteria/conciliacion-bancaria/movimientos/<id>/conciliar → bank_reconciliation_repo.reconcile_transaction | bank_transactions,sale_payment_items,bank_reconciliation_audit | Sólo existencia/estado. Comparar importe exacto, signo, cuenta y moneda; serializar destino para impedir doble enlace concurrente. |
| operario-3 | OT3, sin consumos;salida0 /3 costo0 | POST /operario/ot/<id>/finalizar → OperarioService.finalize_production | production_orders,production_order_items,inventory_movements,production_lot_consumptions,production_lot_outputs,lot_stock,lots | No comprueba plan vs consumos; sumar vacío produce costo0. Exigir consumos proporcionales completos y costo trazable bajo lock OT, sin entradas parciales. |

Riesgos: obligaciones omitidas, sobrepagos, conciliaciones falsas y stock fabricado sin respaldo. Los dos errores de Flujo de Caja son derivados de CxP, no nuevas causas independientes.

Se necesita un ledger de abonos CxP: la única fila actual sólo guarda el último pago y no permite distintas fechas/cuentas ni idempotencia de parciales. Se añadirá una migración aditiva sin reescribir historia; compatibilidad de lectura para documentos anteriores sin abonos nuevos. Sólo se aplicará en clones efímeros.

Las ocho pruebas de migración usan un nombre auxiliar fijo y permisos CREATE DATABASE; se sustituirá su fixture por un esquema vacío único dentro del clon autorizado, conservando migraciones reales y comprobaciones. No se otorgarán permisos sobre postgres ni bases protegidas.

Observación del test original operario-3: tras exigir ausencia de fabricación contiene una aserción posterior de costo unitario1300 que nunca se alcanzó. Se conservará el original y se verificará que un rechazo no modifique el costo anterior, en vez de atribuir costo de fabricación a una operación inexistente; el resultado esperado de stock0 se mantiene.


## Hallazgos adicionales durante la corrección

- Interfaz de ocurrencias: asignar `input.value` no sincronizaba el altInput requerido de Flatpickr. El vencimiento visible quedaba vacío y el navegador bloqueaba el envío. Se corrige con setDate sobre la instancia real y se comprueba mediante pago interactivo.
- Regresión introducida y corregida: un reintento de pago de gasto retornaba antes de actualizar un adjunto nuevo. Se conserva el abono único y se permite continuar la actualización documental; el ciclo E2E3 y un test dedicado lo verifican.
- Registro de factura inicialmente pagada: la ruta creaba el encabezado Pagada antes de llamar al registrador que lo rechazaba. Ahora crea pendiente y registra el pago por el mismo flujo transaccional de abonos.
- La edición de factura no comprobaba el límite de abonos bajo lock. Se impide reducir el importe por debajo de lo pagado y se recalcula el estado consistente sin reescribir pagos.
- Preparaciones antiguas incompatibles con los invariantes requeridos: OT vacía y transferencia sin cuenta. Se preservaron todas las aserciones y se prepararon insumos/consumos y cuenta válidos; se agregan casos negativos explícitos. No se desactivaron validaciones ni se cambiaron importes esperados para ocultar diferencias.

- Otra preparación de conciliación construía un pago con aprobación contable por defecto0 y esperaba una conciliación válida. Se marca aprobado explícitamente en la preparación positiva; se conserva la aserción de conciliación exitosa y existe una prueba negativa dedicada que exige rechazar un pago no aprobado. No se relaja la validación.


## Incidente crítico de protección — FAIL

Los controles por ejecución resultaron estables, pero comparar todas las huellas detectó cambios entre ejecuciones: las migraciones000028/000029/000030 se registraron en facturacion a las03:45:48/03:50:21/03:55:19 UTC del21-10-2026. Las cuatro tablas nuevas están vacías y se añadieron dos vistas; todas las tablas operacionales preexistentes y la plantilla conservan su huella.

Causa técnica comprobada: app.py ejecutaba init_db (migraciones y seeds) incondicionalmente al importar. Ese mecanismo permite que editar archivos de migración active DDL a través de la recarga de un servicio vivo; no se pudo identificar el PID responsable desde el entorno de herramientas. El harness usa roles sin privilegios sobre las tablas protegidas y cada conexión de tests queda limitada a clones. Esa protección no contenía otro proceso de Flask ya activo.

Corrección: el arranque inicializa exclusivamente en testing, validando marker de clon antes de llamar init_db. Desarrollo/producción no ejecutan DDL/seeds por importación. Seis pruebas PostgreSQL READ ONLY verifican esa barrera y se repite toda la suite. No se revierte el esquema normal, no se ocultan registros de migración y no se reparan históricos. El control acumulado queda FAIL aunque las pruebas funcionales aprueben. Evidencia: incidente_esquema_auditoria_solo_lectura.json y control_seguridad_acumulada.json.
