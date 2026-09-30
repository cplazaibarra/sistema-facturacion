# Informe de reconciliación de inventario

Fecha: 22-09-2026
Base: `facturacion` (datos de prueba)

## Causa raíz

Se eliminaron manualmente documentos comerciales y de producción que todavía
tenían movimientos en `inventory_movements`. Además, `page_data.inventory_items`
era un saldo operativo legacy que no se había actualizado junto al Kardex, y
existían proyecciones de lotes para productos que no requieren lote.

La alerta de `/inventario` usa la fórmula existente:

```text
diferencia = Σ inventory_movements.quantity
             - (page_data.stock + reservas)
```

Las reservas son ventas `Pendiente` más insumos de órdenes de producción
`Aprobada`. El Kardex y el PPP se reconstruyen desde `inventory_movements`; los
lotes son una proyección de disponibilidad por lote.

## Backup

Se generó y verificó antes de modificar datos:

`backups/facturacion_pre_reconciliacion_20260922T205049Z.dump`

El dump es PostgreSQL custom, pesa 728.555 bytes y su catálogo contiene 392
entradas. Se restauró temporalmente para comparar PPP y luego se eliminó la
base temporal.

## Estado BEFORE / AFTER

| Métrica | Antes | Después |
|---|---:|---:|
| Productos activos auditados | 12.937 | 13.605* |
| Productos con diferencia | 4.766 | 0 |
| Diferencia absoluta acumulada | 255.771 un. | 0 un. |
| Referencias de movimientos huérfanas | 424 | 0 |
| Lotes con cantidad negativa | 0 | 0 |
| Movimientos con cantidad cero | 0 | 0 |
| Diferencias por lote | 106 proyecciones residuales | 0 |
| Alertas en `/inventario` | — | 0 |

## Correcciones realizadas

- Se preservaron todos los movimientos históricos.
- Se agregaron asientos técnicos `ADJUSTMENT_IN`/`ADJUSTMENT_OUT` con
  referencia `reconciliation` y notas `AJUSTE DE CONCILIACIÓN`.
- Se respaldaron reservas sin saldo ledger mediante 3 entradas técnicas.
- Se transfirieron saldos entre lotes y ledger general mediante pares
  compensados, sin cambiar el total físico.
- Se crearon 165 lotes técnicos para asignar saldos que requerían lote y no
  tenían proyección trazable.
- Se eliminaron las proyecciones residuales de `lot_stock` en productos que no
  requieren lote mediante transferencias compensadas.
- Se actualizaron los saldos `page_data.inventory_items` desde el ledger y las
  reservas. Tras las pruebas contiene 5.773 productos con existencia o saldo
  reconciliado.
- Las 424 referencias a documentos eliminados se conservaron como movimientos,
  pero se normalizaron a `reconciliation_orphan` con `reference_id = NULL` y
  nota auditable.
- No se crearon compras, ventas, recepciones ni órdenes ficticias.

## Productos solicitados

| SKU | Producto | Antes físico | Antes disponible | Antes reservado | Antes movimientos | Antes lotes | Antes diferencia | Después físico | Después disponible | Después reservado | Después movimientos | Después lotes | Después diferencia |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| PRD001 | Miel Pura 1kg | 454 | 450 | 4 | 450 | 0 | -4 | 450 | 446 | 4 | 450 | 0 | 0 |
| PRD002 | Miel Pura 500g | 705 | 701 | 4 | 829 | 0 | 124 | 829 | 825 | 4 | 829 | 0 | 0 |

El stock disponible se redujo en PRD001 y aumentó en PRD002 porque ahora se
calcula correctamente como físico menos reservas pendientes. No se alteraron
ventas ni reservas.

## PPP y costos

El PPP se calculó antes y después desde todos los movimientos, aplicando el
mismo algoritmo del repositorio Kardex. Los asientos compensados utilizaron el
PPP vigente capturado antes de cada ajuste. Comparación final: **0 productos
con cambio de PPP** usando el fallback existente de `products.cost` para
productos sin movimientos previos. No se modificaron `products.cost`, compras,
recepciones ni ventas.

*La suite de pruebas generó productos adicionales después de la primera
reconciliación; esos datos también se reconciliaron antes del cierre.*

## Validaciones

- Auditoría SQL completa: 13.605 productos al cierre, 0 diferencias.
- Huérfanos de producto, lote, entrada y movimiento: 0.
- Referencias documentales huérfanas: 0.
- Lotes negativos: 0.
- Movimientos cero: 0.
- Consistencia `lot_stock` para productos con lote: 0 diferencias.
- Proyecciones `lot_stock` en productos sin requisito de lote: 0.
- `/inventario`: 0 textos `Pendiente de conciliación`; PRD001 y PRD002 visibles.
- `python3 -m py_compile tools/reconcile_inventory.py`: correcto.
- `git diff --check`: correcto.
- Suite completa con `venv/bin/pytest -q`: **271 passed, 1 failed**.
  El único fallo está fuera del flujo de inventario, en
  `test_sales_pagination_cases_a_to_u`: el test suma solo estados
  `Completada`/`Pendiente`, mientras la base de prueba contiene además 818
  ventas `En Preparación` y 128 `Para Despacho`. No se alteraron ventas para
  maquillar ese fallo.
- Después de la suite se ejecutó `tools/reconcile_inventory.py --fix` para
  reconciliar sus datos de prueba: 13.605 productos auditados y 0 diferencias.

## Herramienta reutilizable

Se dejó `tools/reconcile_inventory.py`:

```bash
python tools/reconcile_inventory.py --check
python tools/reconcile_inventory.py --fix
```

`--check` solo diagnostica. `--fix` muestra el estado, exige escribir
`RECONCILIAR`, ejecuta la corrección en una transacción y hace rollback ante
cualquier error. El SQL transaccional queda en
`tools/reconcile_inventory_fix.sql`.

## Resultado

Inventario, reservas, lotes, movimientos y Kardex quedan conciliados. La
condición frontend de alerta se mantuvo intacta y desapareció por consistencia
de datos, no por ocultamiento.
