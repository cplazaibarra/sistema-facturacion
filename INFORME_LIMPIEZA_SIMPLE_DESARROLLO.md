# Informe de limpieza simple de la base de desarrollo

**Fecha:** 2026-09-27 (America/Santiago)  
**Base intervenida:** `facturacion` (`SELECT current_database()` comprobó el nombre antes de operar).  
**Estado:** GREEN.

## Backups

| Tipo | Archivo | Resultado |
|---|---|---|
| Previo | `backup_pre_limpieza_simple_20260927_2306.sql` | `pg_dump` terminó con código 0; archivo no vacío, 6.794.969 bytes; 2026-09-27 20:07 -0300. |
| Final | `backup_base_desarrollo_limpia_20260927_2026.sql` | `pg_dump` terminó con código 0; archivo no vacío, 203.912 bytes; 2026-09-27 20:28 -0300. |

## Conteos antes y después

| Entidad | Antes | Después |
|---|---:|---:|
| Productos | 15.048 | 68 |
| Ventas (sin cotizaciones) | 1.904 | 0 |
| Cotizaciones | 34 | 0 |
| Órdenes de compra | 1.715 | 0 |
| Entradas/recepciones | 2.077 | 0 |
| Ítems de entradas | 1.060 | 0 |
| Movimientos de inventario | 8.389 | 0 |
| Lotes / existencias de lote | 2.003 / 2.003 | 0 / 0 |
| Órdenes de producción | 2.105 | 0 |
| Clientes | 10 | 10 |
| Proveedores | 1.711 | 10 |
| Cuentas bancarias | 186 | 10 |
| Deudas | 44 | 0 |
| Cuotas / pagos de deuda | 139 / 34 | 0 / 0 |
| Facturas de compra | 518 | 0 |
| Pagos de venta | 723 | 0 |
| Movimientos bancarios / importaciones | 77 / 5 | 0 / 0 |
| Gastos operacionales / ocurrencias | 29 / 28 | 0 / 0 |

La tabla `sales` contenía 1.938 filas: 1.904 ventas y 34 cotizaciones. Se eliminaron ambas clases de documentos y sus dependencias. También se eliminaron historiales y acciones asociadas, ajustes transaccionales, consumos y salidas de producción, conciliaciones y demás hijos alcanzados por el orden seguro de borrado.

## Maestros y configuración

- Se conservaron 68 productos maestros completos y útiles. El catálogo limpio disponible tras excluir las familias de fixtures identificadas contenía 68 candidatos; se mantuvo ese conjunto cercano al objetivo de 70 en lugar de añadir productos `TEST`, `E2E`, `FIXTURE`, `DBG`, `MP-A`, `SEMI-A`, `FINAL-A`, `MP-OT` o `PT-OT`.
- Se conservaron los 10 clientes actuales, 10 proveedores seleccionados y 10 cuentas bancarias seleccionadas.
- Se conservaron usuarios, roles, permisos, categorías, tipos, unidades y configuración. No se reiniciaron secuencias.
- `page_data` conserva sus 25 claves. Sólo se actualizó `inventory_items`: ahora contiene 68 productos con stock y porcentaje de stock en cero; las otras 24 claves JSON permanecieron intactas.
- Se descartó la valorización histórica de los productos retenidos poniendo `products.cost` en cero; no se recalculó PPP ni se inventaron costos de apertura. El costo se formará con compras/recepciones futuras.

## Integridad e inventario

El script corrió primero íntegro en una transacción de ensayo que terminó en `ROLLBACK`; las mismas validaciones se ejecutaron después en la transacción aplicada. La validación recorrió las 82 FK reales del esquema y no detectó referencias huérfanas. No se deshabilitaron restricciones, no se añadió `CASCADE`, y no se ejecutó `TRUNCATE` ni se reiniciaron IDs.

Estado de los 68 productos conservados:

| Medida | Resultado |
|---|---:|
| Físico / reservado / disponible | 0 / 0 / 0 |
| Ledger (movimientos) | 0 |
| Existencia en lotes | 0 |
| Costo histórico almacenado | 0 |
| Snapshots `inventory_items` con stock distinto de cero | 0 |

`tools/reconcile_inventory.py --check --json` analizó 68 productos: 68 snapshots presentes, 0 diferencias ledger-vs-lotes, 0 diferencias snapshot-vs-ledger, 0 diferencias snapshot-vs-lotes, 0 reservas inconsistentes, 0 referencias huérfanas y 0 candidatos de investigación/corrección.

## Pruebas

- Login servido por el ERP: HTTP 200 en `/login`.
- Pasada autenticada de sólo lectura contra `facturacion` con Flask test client, sin invocar la inicialización/seed de la aplicación: HTTP 200 en las 18 rutas principales revisadas: dashboard, productos, inventario, Kardex, ventas, cotizaciones, compras, recepciones, producción, CxC, CxP, deudas, conciliación bancaria, flujo de caja, reportería y cuentas bancarias.
- Las pruebas autenticadas de smoke routes forman parte de la suite completa: dashboard, productos, proveedores, clientes, compras, inventario, cotizaciones, ventas, producción, CxP, CxC y cuentas bancarias respondieron según sus asserts HTTP 200 usando el cliente autenticado de integración.
- Suite completa aislada #1: **484 passed, 0 failed**.
- Suite completa aislada #2: **484 passed, 0 failed**.
- El runner clonó y eliminó sus bases efímeras; confirmó `NORMAL DATABASE DELTA: 0` y `TEST TEMPLATE DELTA: 0`. La suite no escribió en `facturacion`.

No se ejecutó un recorrido manual de interfaz con navegador. La validación funcional directa corresponde a los 18 GET autenticados de sólo lectura contra `facturacion`, además de las pruebas autenticadas de rutas dentro de ambas ejecuciones completas.

## Estado final

| Gate | Estado |
|---|---|
| Backup previo | GREEN |
| Base objetivo verificada | GREEN (`facturacion`) |
| Limpieza transaccional | GREEN |
| Maestros conservados | GREEN (68 productos, 10 clientes, 10 proveedores, 10 cuentas) |
| Integridad FK | GREEN (82 FK revisadas; 0 huérfanos) |
| Inventario / lotes / reservas / ledger | GREEN (cero) |
| PPP histórico | GREEN para esta limpieza (sin reconstrucción ni movimientos pendientes) |
| Rutas autenticadas de smoke | GREEN |
| Suites aisladas | GREEN (484 passed en cada ejecución) |
| Delta de `facturacion` causado por pytest | GREEN (0) |
| Backup final | GREEN |

La base `facturacion` queda como nuevo baseline pequeño de desarrollo. No se modificaron `facturacion_cleanup_verify` ni bases `facturacion_test_run_*` de forma persistente.
