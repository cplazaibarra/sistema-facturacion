# Auditoría forense del inventario

**Fecha de consulta:** 2026-09-27  
**Modo:** consultas PostgreSQL `READ ONLY`; no se ejecutó `--fix`, no se modificaron cantidades, productos ni movimientos.  
**Backup verificado:** `backup_pre_limpieza_revalidacion_20260927_1325.sql` (6.187.126 bytes; dump finalizado). No se modificó.

## Conclusión ejecutiva

El reconciliador reproduce exactamente **13.711 productos analizados, 4.445 diferencias y 225.464,0 de diferencia absoluta**. Sin embargo, esa cifra **no equivale a 4.445 errores demostrados de stock**: en **4.444** productos que tienen movimientos no existe fila correspondiente en `page_data.inventory_items`. El reconciliador sustituye esa ausencia por cero. La lógica de lectura de stock de la aplicación, en cambio, recurre al ledger y/o a lotes cuando falta la fila legacy. Para esos 4.444 productos, la comparación actual no compara las mismas fuentes.

Las diferencias de productos sin fila legacy suman **224.579,0** (99,6% del delta absoluto reportado). Queda **885,0** de delta absoluto en productos con fila legacy; la consulta encuentra un producto con fila presente en cero y movimientos. Ese caso sí requiere rastrear los documentos antes de calificarlo.

La auditoría encuentra además brechas de trazabilidad real: referencias históricas genéricas o nulas, 26 movimientos con referencia previamente normalizada a `reconciliation_orphan`, líneas de entrada sin vínculo explícito a un movimiento y órdenes finalizadas sin la referencia de salida esperada. Son alertas de procedencia; por sí solas no prueban que falte o sobre cantidad, pues existen flujos legacy que escriben a través de otros tipos de movimiento.

**No es seguro corregir cantidades todavía.** El número de productos corregibles automáticamente con alta confianza es **0** en esta fase. Sí hay una corrección de alta confianza pendiente en el diagnóstico: el reconciliador debe tratar la ausencia de snapshot según la misma regla de fuente efectiva que usa el lector del ERP, no como cero.

## Fuente de verdad y modelo observado

Las tablas y columnas comprobadas en el esquema real son:

| Concepto | Tabla/columnas | Uso observado |
|---|---|---|
| Catálogo | `products(id, sku, name, cost, requires_lot, is_deleted)` | Identidad, unidad de control de lote y costo fallback. El reconciliador excluye productos soft-deleted. |
| Proyección legacy de stock | `page_data(key='inventory_items', json)`; elementos con `code`, `stock` | Snapshot JSON parcial por SKU. Solo 869 de los 13.711 productos analizados tienen una fila; no es cobertura completa. |
| Libro de movimientos / Kardex | `inventory_movements(product_id, movement_type, quantity, unit_cost, created_at, reference_type, reference_id, lot_id, lot_number)` | Kardex y saldo relacional por producto se calculan como suma de `quantity`; Kardex/PPP ordena cronológicamente por `created_at`, con `id` como desempate. El propio repositorio lo describe como fuente relacional oficial. |
| Disponibilidad por lote | `lot_stock(product_id, initial_qty, available_qty, lot_id, entry_id, lot_number)` | Saldo operacional por lote. `initial_qty` es saldo inicial del registro de lote; no equivale a saldo disponible actual. |
| Genealogía | `lots(product_id, origin_type, origin_id, purchase_order_id, inventory_entry_id, production_order_id, initial_quantity, status)` | Origen del lote y trazabilidad compra/producción. |
| Recepciones | `inventory_entries`; líneas `inventory_entry_items(inventory_entry_id, product_id, quantity, unit_price, lot_number, lot_id)` | Documento/recepción y cantidades recibidas. |
| Venta/reserva | `sales(status, products_json)` | `services.stock_context` suma como reservado los productos JSON de ventas `Pendiente`; la reserva no está materializada en una tabla de reservas independiente. |
| Reserva de producción | `production_orders(status)`, `production_order_items(quantity_required)`, `production_order_additional_items(quantity)` | El código reserva consumos de OTs `Aprobada`. En los datos actuales no existe ninguna OT con ese estado. |
| Ajustes | `inventory_adjustment_requests`, `inventory_adjustment_audit` | Solicitud/aprobación. Solo una aprobación con diferencia no nula debe crear movimiento. |

La regla de lectura efectiva observada en `get_product_available_stock()` es distinta según producto:

- Si `requires_lot=true`, retorna `SUM(lot_stock.available_qty)`.
- Si no requiere lote, retorna el máximo entre stock en lotes, `page_data` y suma del ledger, con fallback al ledger cuando no hay proyección.
- La vista de inventario agrega las reservas al stock que llama disponible y muestra `físico = disponible + reservado`.
- `get_current_ppp()` y el Kardex valorizado recorren `inventory_movements` por orden cronológico. Los movimientos entrantes sin costo positivo afectan la reconstrucción de valor.

Por tanto, el sistema **no mantiene una única fórmula uniforme de disponibilidad**: coexisten un snapshot JSON parcial, un ledger relacional, saldos de lotes y reservas calculadas por estado. La fórmula correcta de saldo físico por producto no puede verificarse sólo sumando las tres fuentes como si fueran snapshots intercambiables.

### Flujos documentados desde el código

- **Compra:** OC → recepción (`inventory_entries` + líneas) → actualización legacy/lotes → movimiento `PURCHASE_RECEIPT` u otros movimientos legacy → Kardex. La escritura nueva puede referenciar `inventory_entry_item`; se encontraron numerosos movimientos históricos con `reference_type='purchase_order'` o nulo.
- **Producción:** aprobación reserva insumos; finalización consume lotes/insumos (`PRODUCTION_INPUT`), registra salida `PRODUCTION_OUTPUT`, crea OT/lote de producto terminado y actualiza `page_data`/entrada. Hay órdenes antiguas que no tienen todo este linaje explícito.
- **Venta:** `Pendiente` aporta reserva calculada desde `products_json`; los movimientos de salida y reversiones quedan en el ledger al avanzar/cancelar la operación. Se encontraron salidas con referencia a venta existente; el emparejamiento cuantitativo exacto de salidas y reversas requiere revisión por documento.
- **Ajuste:** solicitud no toca stock; aprobación valida snapshot/watermark y agrega un movimiento `ADJUSTMENT_IN/OUT` con referencia `inventory_adjustment`. Un ajuste aplicado con diferencia cero no necesita movimiento.

## Reconciliador auditado

En `tools/reconcile_inventory.py`, para cada producto activo se define:

```text
A = SUM(inventory_movements.quantity) por product_id
L = SUM(page_data.inventory_items[*].stock) por SKU; si no hay fila, L=0
Rs = SUM(quantity de products_json) para sales.status='Pendiente'
Rp = SUM(quantity_required y quantity adicional) de OTs status='Aprobada'
B = L + Rs + Rp
diferencia firmada = A - B
producto marcado = ABS(A - B) > 0,001
diferencia absoluta total = SUM(ABS(A - B)) solo para productos marcados
```

El contador `orphan_references` valida únicamente referencias de cuatro tipos (`production_order`, `production_order_item`, `production_order_add_item`, `purchase_order`). No detecta todas las referencias polimórficas. El chequeo de lotes inválidos solo cuenta `lot_stock.available_qty<0` o `initial_qty<0`; no verifica la igualdad entre lotes, ledger y stock operativo.

**Juicio matemático:** la suma firmada del ledger es razonable para calcular el saldo Kardex, pero `A` contra `L+reservas` solo es una comparación válida cuando existe una proyección legacy completa, consistente y definida como stock disponible para ese producto. No se cumple esa precondición: 12.842 productos no tienen fila legacy. Además, el lector usa fallback a ledger/lotes, pero el reconciliador los interpreta como cero. Por eso el conteo global no es una prueba válida de stock erróneo.

## Diferencias y distribución

| Clase | Productos | % del catálogo analizado |
|---|---:|---:|
| Diferencia ≤ 0,001 | 9.266 | 67,58% |
| Diferencia exacta ±1 | 0 | 0,00% |
| Diferencia absoluta >1 a 10 | 339 | 2,47% |
| Diferencia absoluta >10 a 100 | 4.026 | 29,36% |
| Diferencia absoluta >100 a 1.000 | 80 | 0,58% |
| Diferencia absoluta >1.000 | 0 | 0,00% |
| **Productos marcados** | **4.445** | **32,42%** |

Entre los marcados, 4.441 tienen delta positivo y 4 negativo. El total absoluto reproduce 225.464,0. Los grupos de causa se solapan; no deben sumarse como categorías mutuamente excluyentes.

| Causa/condición observada | Productos | Diferencia absoluta asociada | Interpretación |
|---|---:|---:|---|
| Sin fila `inventory_items` y con movimientos | 4.444 | 224.579,0 | Comparación con cero por ausencia de snapshot; candidato fuerte a falso positivo del reconciliador, no cantidad demostrada a corregir. |
| Fila legacy presente con stock cero y ledger no cero | 1 | 885,0 | Candidato real a revisar contra movimientos/documentos. |
| Reserva de venta/producción no nula y producto marcado | 6 | 66,0 | Subconjunto de los grupos anteriores; no explica por sí solo el conjunto. |
| SKU/nombre con marcadores `TEST`, `HIST-`, `E2E` o `FIXTURE` | 655 | No separado en esta ejecución | Evidencia directa de datos de prueba en parte del universo; no implica que sea seguro borrar sus movimientos. |

La consulta produjo **12.842** productos sin fila legacy y **869** con fila. La condición `page_stock=0` y “tiene movimientos” se cumple para las 4.445 discrepancias; no significa que la aplicación vea esos productos con stock cero, porque su lector recurre a otras fuentes.

## Top 50 por diferencia absoluta

La columna “disponible calculado” aplica la rama de lectura de la aplicación (`lot_stock` si exige lote; para los demás el máximo de snapshot, lotes y ledger). No constituye una validación independiente del stock físico. El detalle completo solicitado está en la tabla siguiente.

| ID | SKU | Producto | Stock físico calculado* | Reservado | Disponible calculado* | Stock ledger | Stock lotes | Diferencia A-B | Movs. | Último movimiento | Causa probable |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| 17972 | HIST-COST-838663 | Test Product HIST-COST-838663 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-23 01:08:06+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 18350 | HIST-COST-308274 | Test Product HIST-COST-308274 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-23 01:24:09+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 18728 | HIST-COST-13C4FC | Test Product HIST-COST-13C4FC | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-23 01:25:30+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 19106 | HIST-COST-0B8935 | Test Product HIST-COST-0B8935 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-23 01:46:39+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 19484 | HIST-COST-F043E0 | Test Product HIST-COST-F043E0 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-23 02:03:36+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 19862 | HIST-COST-CA7673 | Test Product HIST-COST-CA7673 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-23 02:11:19+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 20240 | HIST-COST-C78BF7 | Test Product HIST-COST-C78BF7 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-23 02:15:34+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 20618 | HIST-COST-3311D9 | Test Product HIST-COST-3311D9 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-23 02:16:47+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 20996 | HIST-COST-F22A46 | Test Product HIST-COST-F22A46 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-23 02:24:32+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 21374 | HIST-COST-BA25C3 | Test Product HIST-COST-BA25C3 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-26 02:08:53+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 21752 | HIST-COST-54B844 | Test Product HIST-COST-54B844 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-26 02:23:41+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 22130 | HIST-COST-921344 | Test Product HIST-COST-921344 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-26 02:50:26+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 22508 | HIST-COST-4164F1 | Test Product HIST-COST-4164F1 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-26 02:52:26+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 22886 | HIST-COST-64B59D | Test Product HIST-COST-64B59D | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-26 04:17:00+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 23264 | HIST-COST-91DE72 | Test Product HIST-COST-91DE72 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-26 04:36:14+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 24005 | HIST-COST-A80D9E | Test Product HIST-COST-A80D9E | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-26 17:37:25+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 24411 | HIST-COST-D25827 | Test Product HIST-COST-D25827 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-26 19:48:34+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 24817 | HIST-COST-276A6C | Test Product HIST-COST-276A6C | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-26 20:29:13+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 25223 | HIST-COST-1607DD | Test Product HIST-COST-1607DD | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-26 20:43:26+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 25665 | HIST-COST-250EDC | Test Product HIST-COST-250EDC | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-26 20:52:41+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 26071 | HIST-COST-D0517E | Test Product HIST-COST-D0517E | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-26 21:10:40+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 26477 | HIST-COST-C656C0 | Test Product HIST-COST-C656C0 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-26 21:59:49+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 26883 | HIST-COST-FCD922 | Test Product HIST-COST-FCD922 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-26 22:16:53+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 27289 | HIST-COST-A3D248 | Test Product HIST-COST-A3D248 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-26 22:26:36+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 27695 | HIST-COST-F9E73C | Test Product HIST-COST-F9E73C | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-26 23:30:42+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 28101 | HIST-COST-8A02F7 | Test Product HIST-COST-8A02F7 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-26 23:44:28+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 28507 | HIST-COST-0F56B5 | Test Product HIST-COST-0F56B5 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-27 01:17:59+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 28913 | HIST-COST-4C6C72 | Test Product HIST-COST-4C6C72 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-27 01:56:27+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 29319 | HIST-COST-FB1879 | Test Product HIST-COST-FB1879 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-27 02:52:54+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 29678 | HIST-COST-61C460 | Test Product HIST-COST-61C460 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-27 02:54:06+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 29982 | HIST-COST-60BC8A | Test Product HIST-COST-60BC8A | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-27 02:55:02+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 30597 | HIST-COST-0F6BD1 | Test Product HIST-COST-0F6BD1 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-27 03:00:55+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 31003 | HIST-COST-358A22 | Test Product HIST-COST-358A22 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-27 03:09:36+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 31958 | HIST-COST-57465B | Test Product HIST-COST-57465B | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-27 03:31:27+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 32730 | HIST-COST-61D39B | Test Product HIST-COST-61D39B | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-27 03:35:13+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 34051 | HIST-COST-239E56 | Test Product HIST-COST-239E56 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-27 14:31:48+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 34862 | HIST-COST-D2F196 | Test Product HIST-COST-D2F196 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-27 14:39:07+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 35668 | HIST-COST-7B55B2 | Test Product HIST-COST-7B55B2 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-27 15:01:49+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 36257 | HIST-COST-727889 | Test Product HIST-COST-727889 | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-27 16:05:33+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 36846 | HIST-COST-05904D | Test Product HIST-COST-05904D | 196 | 0 | 196 | 196 | 0 | 196 | 3 | 2026-09-27 16:19:47+00:00 | Fixture HIST-COST, sin snapshot; validar documentos |
| 18141 | E2E-SCHED-MPA-1790125701939 | Materia Prima A 1790125701939 | 110 | 0 | 110 | 110 | 110 | 110 | 2 | 2026-09-23 01:08:22.493233+00:00 | Fixture E2E de producción, sin snapshot |
| 18519 | E2E-SCHED-MPA-1790126665311 | Materia Prima A 1790126665311 | 110 | 0 | 110 | 110 | 110 | 110 | 2 | 2026-09-23 01:24:25.789474+00:00 | Fixture E2E de producción, sin snapshot |
| 18897 | E2E-SCHED-MPA-1790126746531 | Materia Prima A 1790126746531 | 110 | 0 | 110 | 110 | 110 | 110 | 2 | 2026-09-23 01:25:47.028123+00:00 | Fixture E2E de producción, sin snapshot |
| 19275 | E2E-SCHED-MPA-1790128017053 | Materia Prima A 1790128017053 | 110 | 0 | 110 | 110 | 110 | 110 | 2 | 2026-09-23 01:46:57.603992+00:00 | Fixture E2E de producción, sin snapshot |
| 19653 | E2E-SCHED-MPA-1790129033683 | Materia Prima A 1790129033683 | 110 | 0 | 110 | 110 | 110 | 110 | 2 | 2026-09-23 02:03:54.277376+00:00 | Fixture E2E de producción, sin snapshot |
| 20031 | E2E-SCHED-MPA-1790129497159 | Materia Prima A 1790129497159 | 110 | 0 | 110 | 110 | 110 | 110 | 2 | 2026-09-23 02:11:37.749935+00:00 | Fixture E2E de producción, sin snapshot |
| 20409 | E2E-SCHED-MPA-1790129752431 | Materia Prima A 1790129752431 | 110 | 0 | 110 | 110 | 110 | 110 | 2 | 2026-09-23 02:15:53.049135+00:00 | Fixture E2E de producción, sin snapshot |
| 20787 | E2E-SCHED-MPA-1790129826493 | Materia Prima A 1790129826493 | 110 | 0 | 110 | 110 | 110 | 110 | 2 | 2026-09-23 02:17:07.114190+00:00 | Fixture E2E de producción, sin snapshot |
| 21165 | E2E-SCHED-MPA-1790130291389 | Materia Prima A 1790130291389 | 110 | 0 | 110 | 110 | 110 | 110 | 2 | 2026-09-23 02:24:52.016730+00:00 | Fixture E2E de producción, sin snapshot |
| 21543 | E2E-SCHED-MPA-1790388552771 | Materia Prima A 1790388552771 | 110 | 0 | 110 | 110 | 110 | 110 | 2 | 2026-09-26 02:09:13.319713+00:00 | Fixture E2E de producción, sin snapshot |

## Hallazgos por dominio

### Productos sin movimientos / movimientos con stock cero

- **1 producto** tiene stock legacy no cero sin movimientos: ID 16, SKU `INS-ENV-002`, “Envase 260 g”, snapshot 41, ledger 0, lote 0. Esto es compatible con saldo de carga/manual antiguo, pero no se puede asignar la causa sin registro fuente.
- **4.445 productos** tienen movimientos históricos y `page_data` ausente/cero. De ellos, 4.444 carecen de fila y uno tiene fila explícita en cero. La etiqueta “stock actual cero” solo describe el snapshot legacy; no describe necesariamente el stock efectivo del ERP.

### Reservas

- Hay 354 ventas en estado `Pendiente`; su cantidad reservada se calcula recorriendo `products_json`.
- No hay órdenes de producción en estado `Aprobada` (estados presentes: Borrador, Finalizada, Solicitada y Cancelada), por lo que `Rp=0` hoy.
- Seis productos marcados tienen reserva calculada no nula, con 66,0 de delta absoluto combinado; ese dato se solapa con las discrepancias de proyección ausente.
- No se encontró una tabla independiente que materialice reservas de venta. El código que mapea nombres de productos puede usar coincidencia parcial cuando falta `product_id`; esto puede asociar reservas ambiguamente y debe medirse en una auditoría de líneas.
- Esta fase no reconstruyó reservas ligadas a ventas canceladas/completadas: sólo el estado actual `Pendiente` participa en la fórmula auditada.

### Lotes

- 5.668 productos activos están marcados `requires_lot`.
- En ese grupo, 1.296 difieren entre saldo de lote y snapshot legacy; 166 difieren entre saldo de lote y ledger. La suma absoluta lote-vs-ledger para productos con lote es 3.173,0. La discrepancia lote-vs-snapshot no es concluyente porque el snapshot falta para casi todo el catálogo.
- 121 productos que actualmente no requieren lote tienen filas en `lot_stock`; requieren revisar historial de configuración y si el saldo fue transferido al ledger.
- No hay lotes negativos/ inválidos según el chequeo anterior, pero ello no demuestra igualdad de genealogía y existencias.

### Ventas

- 1.275 movimientos con `reference_type='sale'` apuntan a ventas existentes (0 referencias a ventas inexistentes en ese subconjunto).
- 242 de esos movimientos pertenecen a ventas cuyo estado actual es `Cancelada`; coexisten con 120 `SALE_REVERSAL` y 202 `SALE_PACKAGING_REVERSAL`. No se probó que cada salida esté compensada por documento/línea/lote ni que toda venta despachada tenga exactamente un movimiento; no se deben borrar/recalcular aún.
- Las 354 ventas pendientes alimentan la reserva calculada. No se detectó una tabla de reservas dedicada.

### Compras y recepciones

- Hay 1.989 cabeceras de entrada según la medición previa de limpieza y 968 líneas `inventory_entry_items` en la consulta relacional actual.
- De esas 968 líneas, 936 no tienen un movimiento enlazado explícitamente mediante `reference_type='inventory_entry_item'`; no hay duplicados por esa referencia ni diferencias de cantidad dentro del pequeño grupo directamente vinculado. Esto **no prueba 936 recepciones sin movimiento**: el ledger contiene 814 `PURCHASE_RECEIPT` con referencia a OC y 735 con referencia nula, flujos legacy que pueden representar esos ingresos pero no se pueden emparejar de forma inequívoca con línea/documento usando solo `reference_id`.
- Total de movimientos `PURCHASE_RECEIPT`: 1.581, neto +85.551.0. Hace falta reconstruir correspondencia por OC, producto, cantidad, fecha y lote para distinguir backfill faltante de duplicación.

### Producción

- Hay 282 OTs `Finalizada`; solo 162 tienen movimiento `PRODUCTION_OUTPUT` referenciado directamente a `production_order`. **120 no tienen esa referencia explícita**.
- 122 finalizadas tienen una entrada cuyo `order_number` coincide con el número de OT; 160 no. 242 tienen lote vinculado por `production_order_id`; 40 no.
- El ledger contiene 269 movimientos `PRODUCTION_INPUT` (neto -6.717,0), pero 26 movimientos de producción quedaron con `reference_type='reconciliation_orphan'` (22 entradas y 4 salidas según agregación por tipo). Las referencias originales ya no están disponibles en ese campo; la causa histórica no puede recuperarse de esa tabla sola.
- Los faltantes de referencia no son prueba de cantidad ausente: la ruta de producción actual también genera entradas/lotes/movimientos, mientras que los registros antiguos pueden representar etapas distintas. Se necesita el cruce por OT/producto/cantidad.

### Ajustes

- Se observaron 4 solicitudes: 2 `APPLIED`, 1 `PENDING`, 1 `REJECTED`. Solo una aplicada tiene movimiento relacionado; una aprobación con delta cero puede legítimamente no crear movimiento. La otra aplicada sin movimiento debe cotejarse con `difference` antes de declararla irregular.
- El ledger incluye 4 movimientos de ajuste tipados (3 `ADJUSTMENT_IN`, 1 `ADJUSTMENT_OUT`); uno está referenciado a `inventory_adjustment`, tres a `reconciliation`. No se identificaron duplicados automáticamente en esta fase.

### Kardex y referencias

Tipos y cantidades agregadas: `IN` 3.989 movimientos (+205.705,0); `PURCHASE_RECEIPT` 1.581 (+85.551,0); `SALE_PACKAGING` 998 (-3.081,0); `SALE` 317 (-2.265,0); `PRODUCTION_INPUT` 269 (-6.717,0); `SALE_PACKAGING_REVERSAL` 202 (+609,0); `PRODUCTION_OUTPUT` 166 (+3.240,0); `SALE_REVERSAL` 120 (+720,0); `INITIAL_BALANCE` 7 (+3.345,0). Hay además 4 ajustes tipados. `IN` incluye 2.772 movimientos sin referencia y 1.217 `MANUAL_ENTRY`; la suma simple es válida como ledger, pero la falta de origen reduce auditabilidad.

El chequeo acotado del reconciliador informa cero huérfanos en cuatro tipos, pero el ledger polimórfico tiene 26 referencias explícitamente degradadas a `reconciliation_orphan` y otros tipos sin referencia. El cero reportado **no equivale a integridad completa del linaje**.

### PPP y valorización

- El PPP calculado por código recorre movimientos en orden `created_at, id`; las cantidades positivas se valorizan a `unit_cost` y las salidas al PPP acumulado.
- 1.300 de 7.653 movimientos tienen costo nulo/cero; 1.259 son movimientos entrantes con costo nulo/cero. Esto puede distorsionar el PPP de los productos con esas entradas, independientemente de que el saldo cuantitativo sea correcto.
- No se recalculó PPP. El análisis disponible no cuantifica qué parte del error de valor es imputable a datos cero frente a un costo de producto fallback; se debe separar esa auditoría de la conciliación de unidades.

### Datos de prueba

Hay evidencia directa: 655 discrepancias tienen SKU o nombre con marcador de prueba (`HIST-COST`, `E2E`, `TEST`, `FIXTURE`). Los primeros lugares de diferencia absoluta incluyen productos `HIST-COST-*` con 3 movimientos y saldo neto +196, y productos `E2E-SCHED-MPA-*` con 2 movimientos y saldo +110, todos sin fila legacy. La huella temporal/determinística es compatible con fixtures o scripts de generación. No hay evidencia suficiente para atribuir las restantes discrepancias a pruebas, ni para borrar productos/movimientos de ese grupo sin cruzar relaciones con ventas, OTs, recetas, lotes y compras.

## Plan de remediación propuesto (no ejecutado)

| Clase | Alcance observado | Riesgo | Estrategia futura | Rollback / pruebas |
|---|---|---|---|---|
| **A — corrección automática con alta confianza** | 0 cantidades identificadas. | Alto si se cambia stock antes de resolver fuentes. | No autoajustar unidades. Mantener sólo la consulta diagnóstica read-only y exigir documento fuente para cada ajuste. | No aplica todavía; cualquier operación posterior requerirá backup completo y transacción reversible. |
| **B — reconstrucción desde movimientos/documentos oficiales** | 936 líneas de recepción sin enlace directo al ledger; 120 OTs finalizadas sin referencia directa de salida; 26 movimientos de producción con referencia previamente degradada. | Alto: datos legacy pueden estar representados por referencias genéricas, y backfill puede duplicar stock si no se reconcilia por documento/producto/cantidad/lote. | Crear una conciliación candidato-a-candidato usando OC/entrada/OT, tipo, cantidad, tiempo, lote y movimiento; generar informe de matches exactos/ambiguos antes de cualquier backfill. | Tabla temporal de mapeo, unique/idempotency guard, transacción por documento y rollback probado; tests de recepción, FIFO/lotes, producción, Kardex y PPP. |
| **C — requiere decisión de fuente de verdad** | 13.711 productos; solo 869 snapshots legacy; 5.668 con control de lote; 354 ventas pendientes. | Muy alto: las rutas usan distintas ramas para snapshot/ledger/lote/reserva. | Acordar definición de físico/disponible por producto y de reserva. Unificar lectura y reconciliador; tratar “sin proyección” distinto de “stock cero”. Medir primero los 869 productos con snapshot y lote/ledger. | Migración reversible de proyección, comparativa de lectura anterior/nueva, invariantes por lote y tests de venta/reserva. |
| **D — datos históricos de prueba potencialmente eliminables** | 655 discrepancias con marcador de prueba; muchos top50 son fixtures. | Alto hasta verificar dependencias y si su movimiento participa en cantidades de productos conservados. | Inventariar prefijos/creador/fecha y cerrar grafo de dependencias por producto; clasificar documentos completos de prueba. Borrar sólo en una futura limpieza respaldada y después de preservar saldos objetivo. | Dump verificado; dry-run de tablas dependientes; transacción; conteos y reconciliación antes/después. |
| **E — posible error del reconciliador** | 4.444 discrepancias sin fila legacy (224.579,0 de delta absoluto); 1 discrepancia con fila explícita en cero (885,0). | Bajo para cambiar la métrica; alto si se confunde la métrica con autorización de ajustar stock. | Corregir el auditor para comparar contra la misma fuente efectiva que usa el ERP (incluyendo lotes y fallback); publicar separadamente cobertura/proyección y discrepancia física. No convertir una fila ausente en stock cero sin una regla explícita. | Tests SQL sintéticos: fila faltante con ledger, fila cero con ledger, requires_lot, reservas pendientes, OT aprobada, producto soft-deleted y movimientos sin referencia; validar que `--check` no escriba. |

## Respuestas a los objetivos

1. **Por qué aparecen 4.445:** 4.444 (224.579,0 de delta absoluto) carecen de fila `page_data` aunque tienen ledger, y el reconciliador toma la ausencia como cero; la aplicación consulta ledger/lote en esa situación. Hay además un producto con snapshot cero y ledger no cero (885,0). Reservas intervienen en seis productos y se solapan.
2. **Causa identificada:** la causa de la diferencia del cálculo está identificada para 4.444 como brecha de cobertura/proyección; no equivale a certificar el saldo verdadero. La causa documental exacta de todos los movimientos legacy no está identificada.
3. **Corrección automática de cantidades segura:** 0 demostrada. No se recomienda ejecutar `--fix`.
4. **Datos claramente marcados como prueba:** 655 productos dentro del conjunto discrepante; solo esos están identificados por patrón en esta consulta. Su porcentaje del total de diferencias es 14,7%.
5. **Intervención requerida:** al menos el producto ID 16 con stock legacy 41 sin movimiento; el producto con fila cero y delta 885; la correspondencia de entradas/OTs/movimientos y la semántica de reservas/lotes.
6. **Validez del reconciliador:** la aritmética de su fórmula es reproducible, pero la comparación no es válida para el catálogo completo porque el snapshot es parcial y el fallback del lector difiere. El contador de huérfanos también es incompleto por diseño.
7. **Limpieza futura de ventas/OC/productos:** no es posible declarar seguro eliminar grandes cantidades con esta evidencia. Las ventas/OC deben ser analizadas junto con movimientos/documentos conservados; borrar productos con ledger, lotes, receta o producción altera trazabilidad y puede cambiar stock/costo histórico. Primero se debe identificar el stock objetivo y sanear/probar el mapa de linaje.

## Validación de esta fase

- Backup reciente existe, tamaño y estado verificados; no fue modificado.
- Consultas sobre la base se ejecutaron en transacción PostgreSQL `READ ONLY`.
- Reproducción de `--check`: **13.711 productos / 4.445 diferencias / 225.464,0 absoluta**.
- Suite conocida del proyecto: **455 PASSED / 0 FAILED** (no se volvió a ejecutar para mantener esta fase diagnóstica y evitar crear fixtures; no hubo cambios de código de negocio).
- **No se ejecutaron** `--fix`, UPDATE, DELETE, backfill, limpieza, ni modificación de stock, lote, movimiento o PPP.
