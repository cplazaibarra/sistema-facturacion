# Informe de limpieza de datos de prueba

**Fecha:** 2026-09-27 13:28 (America/Santiago)  
**Estado final:** RED — se alcanzaron los objetivos de cuentas bancarias y cotizaciones, pero no es seguro reducir ventas/OC a 30 y la reconciliación de inventario detecta diferencias.

## Backup

| Archivo | Tamaño | Fecha | Estado |
|---|---:|---|---|
| `backup_pre_limpieza_datos_prueba_20260927_1510.sql` | 6.572.872 bytes | 2026-09-27 12:11 -0300 | pg_dump terminó con código 0 y marcador de dump completo; previo al primer DELETE. |
| `backup_pre_limpieza_revalidacion_20260927_1325.sql` | 6.187.126 bytes | 2026-09-27 13:28 -0300 | No vacío, marcador final verificado; previo a la segunda transacción de limpieza. |

## Cantidades

La segunda ejecución incluyó los datos de prueba adicionales presentes al momento de revalidar. Las cantidades finales son posteriores a esa transacción. “Ventas” excluye cotizaciones según la regla real del sistema (`status='Cotización' OR sale_number LIKE 'COT-%'`).

| Entidad | Antes de la revalidación | Después | Eliminados en la revalidación |
|---|---:|---:|---:|
| Ventas | 1.712 | 1.700 | 12 sin dependencias financieras ni de stock |
| Cotizaciones | 32 | 30 | 2 sin linaje |
| Órdenes de compra | 1.607 | 1.607 | 0 |
| Cuentas bancarias | 98 | 10 | 88 |
| Productos | 13.712 | 13.712 | 0 |
| Proveedores | 1.609 | 1.587 | 22 marcados como prueba y sin referencias |
| Movimientos bancarios | 42 | 9 | 33 |
| Deudas | 26 | 8 | 18 vinculadas a cuentas eliminadas |
| Cuotas de deuda | 83 | 27 | 56 |
| Pagos de deuda | 20 | 6 | 14 |
| Entradas de inventario | 1.989 | 1.989 | 0 |
| Movimientos de inventario | 7.653 | 7.653 | 0 |
| Lotes | 1.823 | 1.823 | 0 |
| Órdenes de producción | 1.925 | 1.925 | 0 |
| Recetas de producto | 1.676 | 1.676 | 0 |

En la limpieza inicial también se eliminaron 270 ventas `VTA-TEST-%` sin dependencias y 35 cotizaciones antiguas sin dependencias. En total, respecto de la primera auditoría, se eliminaron 282 ventas elegibles y 37 cotizaciones; permanecen 1.700 ventas ordinarias y 30 cotizaciones.

## Dependencias y criterios

- Las cuentas conservadas son la cuenta histórica ID 1 (referenciada por movimientos/documentos que se preservaron) y las nueve cuentas más recientes. No se reasignaron pagos. Las claves foráneas configuradas como `ON DELETE SET NULL` conservaron el documento y su importe/método/fecha, dejando nula solamente la cuenta bancaria; las FK restrictivas se resolvieron eliminando únicamente deudas de prueba asociadas y sus cuotas/pagos.
- Se eliminaron movimientos bancarios, importaciones y auditorías dependientes de las cuentas descartadas. Permanecen 9 movimientos, 1 importación y 3 auditorías en la primera comprobación; la segunda limpieza retiró movimientos y auditorías adicionales que dependían de las cuentas nuevas de prueba.
- Las ventas con pagos, reserva pendiente, artículos, embalajes, lotes o movimientos de inventario se conservaron. Las ventas de prueba restantes tienen dependencias; no se borraron ni se alteró stock/Kardex para forzar el número 30.
- No se borraron OC: las candidatas antiguas están relacionadas con artículos, recepciones, facturas, lotes y movimientos de inventario. Borrarlas rompería el historial/costeo que se debe conservar.
- No se borraron productos. La simulación de la política existente de conservar los 70 más antiguos habría tocado miles de relaciones de stock, lotes, recetas, producción, ventas y movimientos. Se conserva el catálogo íntegro para no alterar inventario ni genealogía.
- Se eliminaron únicamente proveedores de prueba sin referencias. Los proveedores usados por compras, facturas, entradas o lotes permanecieron.
- Las dos ejecuciones de limpieza fueron transaccionales. La segunda fue respaldada por el segundo dump indicado arriba.

## Integridad y reconciliación

| Área | Estado | Resultado |
|---|---|---|
| FK bancaria/deuda/documentos | GREEN en comprobaciones explícitas | 0 movimientos bancarios sin cuenta; 0 cuotas/pagos de deuda sin padre; 0 auditorías conciliatorias sin movimiento; 0 movimientos de venta sin venta. |
| CxC / CxP | GREEN en integridad referencial | Se conservaron documentos relacionados; no se ejecutó una reconstrucción financiera. |
| Conciliación bancaria | GREEN en integridad referencial | Sin referencias huérfanas; permanecen 9 movimientos al cierre. |
| Flujo de caja | GREEN en pruebas | Suite completa en copia de verificación: 455 passed, 0 failed. |
| Deudas | GREEN en integridad referencial | 8 deudas, 27 cuotas y 6 pagos al cierre. |
| Inventario físico / reservado / disponible | RED preexistente y requiere investigación | `tools/reconcile_inventory.py --check`: 13.711 productos incluidos, 4.445 diferencias, diferencia absoluta 225.464,0; 0 referencias huérfanas, 0 lotes inválidos, 0 movimientos en cero. No se ejecutó `--fix` ni se actualizaron saldos directamente. |
| Kardex / PPP | RED para certificación completa | Se conservaron íntegros sus movimientos y lotes; la discrepancia del reconciliador impide declarar consistencia GREEN. No se recalcularon costos. |

La auditoría de inventario anterior a la limpieza ya reportaba 4.231 diferencias y diferencia absoluta 214.604,0. Por lo tanto, no se atribuye la discrepancia al borrado; sin embargo, la comprobación final detectó un valor mayor en la base existente y no se declara GREEN.

## Validación

- Baseline ejecutada antes de limpiar: **455 passed, 0 failed**.
- Suite completa en la copia de verificación posterior a la primera limpieza: **455 passed, 0 failed**. Se corrigió la prioridad de resultados sugeridos con `NULLS LAST` y desempate por ID; se ajustaron dos aserciones de pruebas que dependían de datos globales específicos.
- E2E autenticado: las 15 rutas visitadas respondieron HTTP 200; sin errores JavaScript ni respuestas HTTP fallidas de recursos/API registradas por el navegador. Las vistas de productos, conciliación bancaria, productos comprados, CxP y cuentas bancarias mostraron sus controles de paginación; la prueba avanzó y volvió de página donde había enlace. Ventas/OC y otras pantallas muestran filas, pero no todas exponen el mismo control de paginación; esto pertenece al trabajo de optimización de listados y no se considera resuelto por esta limpieza.
- La prueba autenticada no cubre todas las reglas de negocio ni demuestra que cada listado esté limitado en SQL. Los objetivos de limpieza y las conclusiones de inventario se informan separadamente.

## Estado de objetivos

| Objetivo | Resultado |
|---|---|
| 10 cuentas bancarias | GREEN — exactamente 10 |
| 30 cotizaciones recientes | GREEN — exactamente 30 |
| 30 ventas recientes | RED — 1.700 permanecen por dependencias financieras/inventario; no se sacrificó trazabilidad |
| 30 órdenes de compra recientes | RED — 1.607 permanecen por dependencias de recepción, factura, lotes y Kardex/costeo |
| Inventario / Kardex / PPP | RED — diferencias detectadas por el reconciliador; no se introdujeron ajustes automáticos |
| Tests | GREEN — 455 passed, 0 failed en copia de verificación |
| Estado final global | **RED** — los límites de ventas/OC e inventario impiden declarar completa la limpieza solicitada |
