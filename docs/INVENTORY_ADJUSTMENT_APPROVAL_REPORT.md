# Informe de aprobación de ajustes de inventario

## Arquitectura encontrada

El flujo usa `inventory_adjustment_requests` para la solicitud, `inventory_movements`
como fuente de saldo/Kardex, `record_inventory_movement()` como mecanismo oficial
de escritura y `get_current_ppp()` para el costo vigente. La UI existente está en
`ajustes_inventario.html` y `detalle_ajuste_inventario.html`; las rutas viven en
`routes/inventario.py` y la persistencia en
`repositories/inventory_adjustments_repo.py`.

## Flujo implementado

`PENDING` es una solicitud abierta. Crear una solicitud sólo guarda snapshot,
conteo, diferencia, motivo, actor y watermark; no modifica stock ni Kardex.

Al aprobar se bloquean la solicitud y el producto, se valida que siga pendiente,
se comprueba el snapshot/watermark y las reservas, y se registra un movimiento
`inventory_adjustment` dentro de la misma transacción. El movimiento actualiza el
saldo legacy y la solicitud pasa a `APPLIED`. Si falla cualquier paso se hace
rollback. El índice único de referencia y el lock de fila impiden una segunda
aplicación.

Al rechazar se exige comentario, la solicitud pasa a `REJECTED` y no se genera
movimiento. El solicitante no puede aprobar su propia solicitud.

## Delta, Kardex y PPP

La solicitud guarda cantidad física contada; PostgreSQL calcula
`difference = counted_quantity - stock_snapshot`. La aprobación aplica ese delta
sobre el saldo vigente después de validar que no hubo movimientos posteriores.
Los ajustes positivos usan el PPP actual obtenido por el repositorio oficial; al
valorizar al PPP vigente no se introduce una política de costo nueva ni se altera
arbitrariamente el PPP.

## Lotes y reservas

Los productos con `requires_lot` se bloquean en aprobación porque el modelo actual
no define selección de lote de origen para una salida ni lote explícito para un
sobrante. No se inventa genealogía FIFO. Si el conteo queda por debajo de las
reservas operativas, la aprobación se rechaza para evitar disponible negativo.

## UX y RBAC

El listado permite filtrar `PENDIENTE`, `APROBADO/APLICADO` y `RECHAZADO`. El
detalle muestra stock solicitado, stock actual, delta y stock resultante. Aprobar
requiere confirmación contextual y protege el doble submit; el backend sigue
siendo la autoridad. Se mantienen los permisos RBAC
`inventory_adjustment_request` e `inventory_adjustment_approve`.

## Validación

Se agregaron pruebas de rechazo sin movimiento, aprobación positiva con movimiento
único y referencia, segunda aprobación bloqueada, POST persistente y protección
contra el interceptor global de doble envío. La suite focalizada debe ejecutarse
contra PostgreSQL de pruebas; el conjunto focalizado ejecutado quedó en **5
passed, 0 failed**. La suite completa se interrumpió tras crear datos de prueba
adicionales y mostró fallos previos/no relacionados; la base fue restaurada al
KEEP SET de 70 productos mediante la herramienta de purga. Los productos con
lote quedan documentados como requerimiento funcional hasta definir la política
explícita de lotes.
