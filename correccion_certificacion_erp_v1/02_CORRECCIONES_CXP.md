# Correcciones de Cuentas por Pagar

## Causa y solución

La función anterior guardaba el último importe y marcaba Pagada en cualquier abono. Ahora bloquea `purchase_invoices` con FOR UPDATE, valida Decimal finito/positivo con dos decimales, fecha, cuenta activa y saldo; después agrega un abono inmutable por interfaz y actualiza el acumulado compatible. Pagada sólo corresponde a saldo cero; un parcial conserva Pendiente/Vencida. No se modifica el IVA ni el importe original al registrar pagos.

`purchase_payment_items` conserva importe, fecha, cuenta, método, comprobante, notas, clave de idempotencia y fecha de creación. Un reintento con clave explícita no crea otro pago; una clave con importe diferente se rechaza. El caller heredado sin clave conserva su retorno defensivo False ante una repetición. Un intento rechazado no modifica pagos ni acumulados. Dos pagos concurrentes se serializan sobre la factura y no pueden exceder el saldo.

Las ocurrencias de gastos tienen su propio ledger `expense_payment_items`, sin fusionarlas con facturas ni cuotas. El parcial conserva el estado pendiente del esquema, Proyectado; pago total cierra en Pagado. Se conservan la regla recurrente, documentos y auditoría. Un reintento puede agregar metadata documental sin repetir el pago.

Las tablas de apertura de la migración 000030 capturan la metadata anterior sólo al continuar un parcial heredado. Las vistas de eventos evitan sumar apertura, encabezado y ledger dos veces. No se ejecutó backfill ni reparación histórica.

## Interfaz y protección

- El modal de factura propone y limita el saldo, muestra abonado/saldo y genera una clave por operación.
- El modal de gasto permite indicar el abono parcial y su clave.
- Historial de factura: `/compras/facturas/<id>/pagos`, con importes, fechas, cuentas y comprobantes.
- Los comprobantes nuevos tienen nombres únicos, evitando sobrescribir el de otro abono.
- Editar una factura no permite reducir el importe por debajo de lo pagado; se comprueba bajo el mismo bloqueo de factura.
- No se implementaron reversas de pagos ni reparaciones históricas inexistentes en el flujo autorizado.

Archivos: repositories/finance_repo.py, repositories/operational_expenses_repo.py, repositories/purchases_repo.py, routes/compras.py, routes/usuarios.py, templates/compras_cuentas_pagar.html, templates/compras_historial_pagos.html, templates/reporte_cuentas_por_pagar.html, migraciones 000028–000030.

Evidencia: test_repairs_cxp, test_repairs_expense_partial, test_repairs_legacy_partial_preserved, test_repairs_integrity_edges; casos originales cxp-1..5; pruebas de concurrencia sobre PostgreSQL real. Consulte el informe final para los conteos de la ronda vigente.
