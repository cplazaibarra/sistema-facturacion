# Flujo de ajuste de inventario

## Arquitectura y fuente de verdad

La solicitud se persiste en `inventory_adjustment_requests`. Mientras está en
`PENDING` no escribe `inventory_movements`, `page_data.inventory_items`, lotes,
PPP ni Kardex. El stock físico se toma del saldo de `inventory_movements` para
el producto y la bodega registrada; el disponible y reservado se muestran con
las reglas operativas actuales (ventas pendientes y órdenes de producción
aprobadas).

La tabla guarda el snapshot del conteo (`stock_snapshot`,
`available_snapshot`, `reserved_snapshot`) y un `movement_watermark`. La
diferencia es una columna generada por PostgreSQL:

`diferencia = cantidad_fisica_contada - stock_snapshot`.

## Estados y permisos

Los estados son `PENDING`, `APPLIED` y `REJECTED`. Los permisos RBAC son
`inventory_adjustment_request` y `inventory_adjustment_approve`; los roles
administrativos conservan acceso total. El solicitante no puede aprobar su
propia solicitud. Un rechazo exige comentario y no genera movimiento.

## Aprobación, concurrencia e idempotencia

La aprobación bloquea la solicitud y el producto en una única transacción,
comprueba que siga pendiente, compara stock y watermark contra el snapshot,
genera un único movimiento `inventory_adjustment`, actualiza el snapshot
legacy usado por las pantallas existentes y registra auditoría. El índice único
por `(reference_type, reference_id)` y el bloqueo de fila impiden doble
aplicación. Si el inventario cambió, la solicitud queda pendiente y se muestra
que requiere revisión.

## Kardex, lotes, PPP y reservas

El movimiento aprobado se registra mediante `record_inventory_movement`, por lo
que aparece en Kardex y conserva la trazabilidad al ajuste. Los productos que
requieren lote quedan bloqueados para aprobación hasta que exista una política
explícita de asignación de lote; no se altera FIFO ni se inventa genealogía.

El ERP no tenía una política contable definida para valorizar sobrantes. Por
eso los ajustes positivos quedan rechazados con un mensaje funcional y deben
definirse antes de habilitarse. Los ajustes negativos usan el PPP vigente. No
se eliminan reservas; si el conteo es menor que lo reservado, la aprobación se
bloquea para evitar disponible negativo.

La arquitectura actual no posee una clave de bodega en el saldo legacy: la
bodega se conserva como dimensión del movimiento y la solicitud, pero el saldo
global del producto es la referencia disponible para verificar concurrencia.
Una futura política de stock por bodega deberá definir esa separación antes de
permitir conciliaciones independientes por almacén.

## Auditoría y pruebas

Cada solicitud registra actor, fecha, snapshot, conteo, motivo, observación,
decisión y movimiento relacionado en `inventory_adjustment_audit`. La UI está
disponible desde **Inventario → Ajustes de Inventario**, con formularios,
detalle, filtros y protección contra doble envío.

La migración es `000015_inventory_adjustments.up.sql`. Se verificaron creación
sin movimiento y rechazo transaccional contra la base de pruebas. La suite
existente tenía un fallo previo en la paginación de ventas; permanece separado
de este flujo y debe resolverse antes de declarar GREEN global.

## Requerimientos funcionales pendientes

1. Definir costo contable para sobrantes (ajustes positivos).
2. Definir selección/creación de lote para productos con `requires_lot`.
3. Definir stock físico realmente independiente por bodega, si se requiere
   conciliación por almacén y no sólo trazabilidad del movimiento.
