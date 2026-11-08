# Correcciones de producción

La finalización móvil sumaba consumos vacíos, calculaba costo0 y creaba existencias sin exigir el plan. Ahora exige OT habilitada, cantidad finita positiva no superior a la planificada, plan no vacío y consumos de todos los insumos suficientes para la cantidad declarada. Los costos transferidos deben ser positivos y trazables; no se reemplaza un costo faltante con el PPP actual.

Se conservan bloqueo de OT y producto, transacción única de salida y reintento sin duplicación. El consumo móvil bloquea producto/lote, congela PPP y no admite consumir por encima del plan. Un fallo intermedio de PostgreSQL después de crear el lote revierte el lote y todos los efectos de salida; los consumos previamente confirmados siguen trazables en la OT sin finalización.

No se alteró FIFO físico + PPP contable, precios, IVA ni históricos. Se verifican fabricación completa/parcial, insuficiencia, costo, reintento, concurrencia, cancelación e integridad. La fabricación sin consumos genera cero productos, no3. No se inventó una reversa de fabricación inexistente.

Una regresión antigua de idempotencia creaba una OT vacía y esperaba fabricación. Se conservan sus aserciones de primera fabricación y reintento, pero ahora se prepara una operación legítima con recepción y consumo real de insumo. El caso vacío se verifica adicionalmente como rechazo, sin eliminar la prueba anterior.
