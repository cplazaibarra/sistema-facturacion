# Informe de normalización del modelo de stock

**Alcance:** normalización de lecturas y diagnósticos. No se reconstruyeron históricos ni se modificaron cantidades, movimientos, lotes, productos, ventas, compras, producción o PPP. `page_data.inventory_items` y su compatibilidad de escritura permanecen; no se eliminó ni migró.

## Semántica antes y después

| Concepto | Antes | Después |
|---|---|---|
| Stock físico | Dependía de la pantalla: getter mezclaba `MAX(lotes, snapshot, ledger)` para productos sin lote; algunas vistas trataban el snapshot como disponible y le sumaban reserva. | Fuente operacional explícita: `SUM(lot_stock.available_qty)` con `requires_lot=true`; `SUM(inventory_movements.quantity)` sin control de lote. |
| Reservado | Mapeo de ventas por ID/nombre exacto/primera coincidencia parcial; a veces se sumaba al snapshot para inferir físico. | Se mantiene como compromiso separado: ventas `Pendiente` y consumos de OT `Aprobada` en el contexto compartido; no incrementa físico. Identidad: `product_id`, SKU exacto, nombre exacto, y fragmento legacy sólo si queda un candidato único. Ambigüedades se omiten del saldo y se diagnostican como `RESERVA_AMBIGUA`. |
| Disponible | El getter llamado `get_product_available_stock` devolvía el saldo físico/ledger y distintas rutas lo mostraban como disponible; otras sumaban reserva para rotular físico. | Balance central: `available=max(physical-reserved, 0)`. Si reserva supera físico, el disponible se satura en cero y la sobre-reserva queda como excepción; la igualdad física = disponible + reservado se cumple para balances no sobre-reservados. |
| Fuente con lote | El getter ya usaba lotes, pero otras llamadas y pantallas comparaban o mostraban ledger/snapshot. | El getter y lectura batch usan el saldo remanente de lotes. `consume_fifo_lots` reduce `lot_stock.available_qty` al despachar; ese campo es saldo remanente, no una reserva anticipada. |
| Fuente sin lote | Getter usaba máximo de snapshot, lotes y ledger; ausencia de snapshot activaba fallback, pero snapshot existente podía dominar. | Ledger relacional es la fuente física. Snapshot legacy no se consulta como fuente primaria por estos getters. |
| Fallback legacy | `page_data.inventory_items` influía en getters globales y batch, y sus escrituras siguen en algunos flujos. | Clasificado como LEGACY SNAPSHOT/compatibilidad; no se borra. La lectura física ya no depende de su cobertura. Las escrituras duales históricas siguen activas en flujos identificados y deben retirarse en migración separada para evitar divergencia futura. |
| Filas repetidas por pago | `list_sales()` hacía `LEFT JOIN sale_payments`, pudiendo producir una fila de venta por pago. | `LEFT JOIN LATERAL (... ORDER BY id DESC LIMIT 1)` mantiene máximo una fila por venta para sus campos heredados de factura/pago. Las agregaciones de dinero no se sustituyeron ni se ocultaron con `DISTINCT`. |

## Fuentes y mapa auditado

| Archivo / función | Lectura/fuente ahora | Semántica / observación |
|---|---|---|
| `repositories/inventory_repo.py:get_product_physical_stock` | Lotes o movimientos | Fuente física central; acepta conexión existente para respetar la transacción llamadora. |
| `repositories/inventory_repo.py:get_product_available_stock` | Alias compatible del getter físico | El nombre histórico es engañoso; se conserva para no alterar validaciones protegidas. Nuevos consumidores de disponible deben usar StockContext. |
| `repositories/inventory_repo.py:get_batch_products_available_stock` | Agregados batch de lotes/ledger | Ahora devuelve fuente física por ID, sin `page_data` ni `MAX`. Conserva nombre por compatibilidad. |
| `services/stock_context.py:calculate_stock_balance` | Valor físico y reserva recibidos | Única fórmula pura para físico/reservado/disponible. |
| `services/stock_context.py:get_reserved_stock_by_sku` | JSON de ventas pendientes + líneas de OTs aprobadas | Identidad priorizada; diagnósticos sin asociación arbitraria. La política existente de qué estados reservan no se amplió en esta fase. |
| `services/stock_context.py:get_product_stock_balance` / `get_operational_balance` | Getter físico + contexto reservado | Lectura unitaria reutilizable; hace lecturas de repositorio separadas, por lo que no representa una reserva transaccional ni cambia el mecanismo de concurrencia. |
| `routes/inventario.py:inventario` | Proyección de filas legacy para catálogo; cantidades recalculadas desde batch físico | Presenta disponible, reserva y físico como campos separados; alerta `RESERVA_AMBIGUA`. Kardex/PPP permanecen en consulta batch. |
| `routes/inventario.py:nuevo_ajuste_inventario` | Catálogo, batch físico, reservas | Selector distingue `physical_stock`, `reserved_stock`, `available_stock`; sólo presenta, no cambia el ajuste. |
| `routes/ventas.py:cotizaciones` / `/api/producto/<id>/stock` | Agregado físico + reserva del contexto | El stock disponible presentado descuenta reserva; crear una venta/cotización sin stock sigue permitido. |
| `repositories/sales_repo.py:list_sales` | Sales + lateral a un pago heredado | Evita filas duplicadas por cantidad de pagos sin afectar sumas financieras. |
| `services/inventory_service.py:get_stock_overview` | StockContext + lecturas ledger/legacy/lotes/PPP | Incluye físico, reservado y disponible; dual-read sigue siendo diagnóstico legacy. |
| `repositories/reporting_repo.py:get_sales_metrics` y notificaciones de stock crítico | Agregados previos por fuente; lote si `requires_lot`, ledger en caso contrario | Quitado fallback del KPI a `page_data`; productos eliminados excluidos. El join no multiplica movimientos por lotes. |
| `repositories/production_repo.py` y `routes/produccion.py` | Parte de disponibilidad protegida consulta ledger en la transacción | Se conserva en esta fase para no cambiar el mecanismo de bloqueo/reserva de producción. Requiere una siguiente migración transaccional de validación por lotes que preserve locks. Queda como excepción documentada al uso del getter compartido. |
| Reportes/plantillas | Búsqueda por nombres de campo en `templates/`, `routes/`, `repositories/`, `services/` | Se normalizaron las vistas operacionales identificadas; cantidades históricas en reportes de valoración/Kardex conservan las fuentes propias del reporte. Revisar al migrar cada reporte a un contrato explícito. |

## Pago duplicado

Una reserva se deriva de una fila de venta. El query de `list_sales()` ahora entrega una fila por `sales.id` independientemente de que existan dos o más filas en `sale_payments`; por tanto, la iteración de `products_json` no suma una reserva por pago. Las sumas financieras agregadas continúan usando sus propias consultas y no se alteraron con `DISTINCT`. Validación específica en `tests/unit/test_stock_context_semantics.py` y tests de flujo de ventas.

## Ambigüedades y compatibilidad

En la nueva captura read-only del reconciliador: **32** líneas se resolvieron por `product_id`, **384** coincidencias parciales fueron ambiguas y no se asignaron, y **1** línea quedó sin resolver. La captura anterior tenía 350 coincidencias parciales asignadas por primera coincidencia; no son comparables como reservas válidas, porque V2 ahora aplica unicidad y no elige arbitrariamente. La diferencia cuantitativa pasa de **221 a 219** candidatos; cambian también los casos de reserva inconsistente de 6 a 4. Los grupos ledger/lotes (174), snapshots (86/43) y productos no cambiaron. Ninguna cifra almacenada fue escrita por el reconciliador.

En ejecución operativa, las líneas ambiguas incluyen ID de documento y lista de candidatos en diagnósticos; se registran como warning y se muestran en las vistas de inventario/ajustes. La tolerancia de coincidencia parcial queda sólo para compatibilidad legacy con candidato único.

## Concurrencia y límites

- `get_product_physical_stock(..., conn=...)` permite que validadores existentes lean desde la transacción que ya bloqueó producto/documento. La modificación no escribe ni crea una reserva nueva.
- `list_sales()` no introduce un lock ni una nueva condición de carrera; sólo selecciona una fila lateral determinística por venta.
- Los helpers StockContext de lectura unitaria agregan reserva por llamadas existentes y no sustituyen las transiciones operacionales protegidas. Las pruebas mantienen que crear una venta sin stock se permite y que las transiciones protegidas continúan validando stock.
- Las validaciones y disponibilidades de producción basadas en ledger conservan actualmente su mecanismo transaccional. No se cambió aquí porque el saldo de lotes necesitaría integrar los locks de `lot_stock` con la transacción de aprobación/consumo; cambiar sólo la consulta podría introducir carreras.
- Para reserva mayor que físico, la presentación indica disponible cero; no “arregla” ni oculta la inconsistencia reservada.

## Reconciliador V2 después del cambio

Captura read-only contra la base disponible, idéntica en cantidad de productos/fuentes a la captura previa:

| Medida | Antes | Después |
|---|---:|---:|
| Productos activos | 14.379 | 14.379 |
| Snapshot presente / ausente | 911 / 13.468 | 911 / 13.468 |
| Candidatos cuantitativos | 221 | 219 |
| Ledger vs lotes | 174 | 174 |
| Snapshot vs ledger | 86 | 86 |
| Snapshot vs lotes | 43 | 43 |
| Reservas inconsistentes | 6 | 4 |
| Ambiguas detectadas | No se separaban; 350 parciales asignadas | 384 no asignadas |
| Correcciones automáticas | 0 | 0 |

El delta de dos candidatos y dos reservas incompatibles resulta de no reservar nombres parciales ambiguos. No cambió ninguna cantidad guardada. La salida completa está en `INFORME_LEDGER_VS_LOTES.md` y el análisis costo-cantidad en `INFORME_AUDITORIA_PPP.md`.

## Validación

- Bloque específico de semántica stock, reconciliador V2, inventario y flujo de ventas: **46 passed**.
- Tests específicos de recepción/salida y referencias documentales, repetidos tras añadir sus aserciones: **2 passed**.
- Suite completa contra `facturacion_cleanup_verify`: **472 passed, 0 failed**.
- `py_compile` de los módulos modificados: correcto.
- Reconciliador V2 ejecutado contra la base de datos en modo de solo lectura; cero correcciones automáticas.
