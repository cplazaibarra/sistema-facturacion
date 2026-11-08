# Pruebas nuevas y metodología

Persistencia: PostgreSQL real efímero. No se utilizan mocks para sustituir escrituras, lectura, locks, concurrencia o rollback. El fallo intermedio de producción se inyecta mediante un trigger PostgreSQL temporal del clon; se retira después de la comprobación.

Oráculo: scripts/reference.py independiente de services.money, y constantes Decimal calculadas por los escenarios. Se mantienen netos, IVA19%, HALF_UP y escalas documentadas; pesos redondeados con diferencia exigida cero. No se aplican tolerancias nuevas.

Familias principales:

- CxP:10 escenarios (parcial, segundo parcial, total, sobrepago, dos pagos concurrentes, idempotencia, recurrencia, vencido, inválidos y banco).
- Flujo:10 (obligación, parcial, total, conciliación, recurrencia, materialización, transferencia, fecha futura, vencida y consolidación).
- Conciliación:10 (exacto, diferencia1, mayor, duplicado, parcial, completo, reintento, concurrencia, reversa y saldo), más moneda/cuenta/signo/aprobación.
- Producción:10 (normal, sin insumos, costo/movimientos, parcial, repetición, rollback intermedio, concurrencia, cancelación e integridad); FIFO multicapa y PPP cuentan además con regresiones específicas preexistentes y ciclo E2E2.
- Gastos parciales:6, incluyendo segundo pago, rechazo, concurrencia, reintento y conciliación.
- Aperturas heredadas sintéticas:2, factura y gasto. No son reparaciones de datos reales.
- Bordes de integridad: factura editada bajo abonos, historial, transferencia sin cuenta, plan vacío, costo faltante, adjunto en reintento y casos de creación de factura.
- Protección de rollback de snapshots: prueba nueva en el módulo de migraciones.
- Navegador:25 escenarios interactivos adicionales, cinco por CxP, gastos, flujo, conciliación y producción. Se utilizan formularios reales, CSRF activo, controles visibles de calendario, datalist de cuentas y PostgreSQL; los intentos de sobrepago también contrastan el rechazo backend desde el navegador.

Los intentos iniciales fallidos y adaptadores corregidos se conservan en evidencia/ronda_*. Las repeticiones no se cuentan como casos únicos adicionales. No se eliminaron pruebas ni se añadieron xfail/skip. Los conteos finales salen de JUnit y JSON, no de estimaciones.

La certificación anterior se conserva intacta en certificacion_integral_erp_v1/. Su caso operario-3 contenía un assert posterior inalcanzado que atribuía costo1300 a una fabricación que debía rechazarse. La copia de recertificación conserva stock esperado0 y exige ausencia de salida; el original queda preservado. No se inventa costo para una fabricación inexistente.

Se añaden seis pruebas de arranque/inicializador con PostgreSQL READ ONLY y un control acumulado de las bases protegidas. Este último es FAIL por el incidente de esquema, se contabiliza explícitamente y no se restablece su referencia para conseguir GREEN.
