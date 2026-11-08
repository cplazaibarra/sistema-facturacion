# Correcciones de conciliación

Antes se validaban existencia y estado sin comparar importes. Ahora se exigen importe exacto, signo compatible, misma cuenta, CLP y pago efectivo válido; los cobros necesitan aprobación contable. Se rechaza una diferencia de1 peso, sin tolerancias inventadas. El rechazo no cambia el pago ni genera vínculos parciales.

Un lock transaccional PostgreSQL común serializa conciliación/desconciliación y las filas involucradas se bloquean. Dos cartolas concurrentes no pueden vincular el mismo pago. Una transferencia requiere cuentas distintas, importes opuestos iguales, moneda compatible y contraparte pendiente. La reversa de conciliación conserva el pago y registra auditoría.

Se agregaron PURCHASE_PAYMENT_ITEM y EXPENSE_PAYMENT_ITEM para abonos individuales. Los vínculos heredados se conservan; un documento con un único abono nuevo puede resolverse sin ambigüedad, pero varios abonos requieren escoger el individual. Las capturas de apertura conservan la identidad histórica del enlace.

Evidencia: diez test_repairs_reconciliation y cuatro test_repairs_reconciliation_identity, originales conciliacion, bancos y deudas, pruebas existentes de banco y navegador. Escenarios: igualdad, diferencia1, diferencia mayor, parcial, total, duplicado, reintento, concurrencia, reversa, saldo, moneda, cuenta, signo y aprobación.
