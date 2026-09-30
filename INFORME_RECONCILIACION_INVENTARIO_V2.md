# Informe de reconciliación de inventario V2

**Modo:** diagnóstico read-only (`REPEATABLE READ`, `READ ONLY`).  
**Captura final:** 2026-09-27.  
**Backup verificado, intacto:** `backup_pre_limpieza_revalidacion_20260927_1325.sql` (6.187.126 bytes).  
**Cambios permitidos realizados:** herramienta de diagnóstico, tests y este informe. No se ejecutó `--fix` ni se modificaron productos, stock, reservas persistidas, movimientos, lotes, ventas, compras, producción ni PPP.

## Resultado ejecutivo

La versión anterior informó **4.445 diferencias / 225.464,0 de delta absoluto** comparando el ledger contra `snapshot + reserva`, con snapshot ausente convertido en cero. V2 ya no presenta esa cifra como error físico. Separa presencia/cobertura de snapshot, diferencias entre fuentes, reservas y trazabilidad.

En la captura final había **14.379 productos activos analizados** (1 soft-deleted excluido), no 13.711 como en la auditoría anterior. La base cambió entre capturas: había 13.712 productos totales y 7.653 movimientos en el informe de limpieza; V2 observó 14.379 activos y 8.021 movimientos. La captura V2 es una sola instantánea transaccional; no atribuyo ese crecimiento a la herramienta, que conecta en solo lectura. La suite se ejecutó contra `facturacion_cleanup_verify`, la base temporal.

### Cifras V2

| Métrica | Resultado |
|---|---:|
| Productos analizados | 14.379 |
| Soft-deleted excluidos | 1 |
| Snapshot presente | 911 |
| Snapshot ausente | 13.468 |
| Cobertura legacy | 6,336% |
| Snapshot duplicado por SKU | 0 |
| Ledger vs lotes, en productos `requires_lot=true` | 174 productos; delta absoluto 3.329,0 |
| Snapshot vs ledger, en snapshots con valor válido | 86 productos; delta absoluto 929,0 |
| Snapshot vs lotes, donde lotes aplican | 43 productos; delta absoluto 1.683,0 |
| Reservas inconsistentes candidatas | 6 productos |
| Candidatos de cantidad a investigar (unión sin duplicados) | **221 productos** |
| Productos con alerta de trazabilidad | 4.715 |
| Unión de productos con revisión cuantitativa o de trazabilidad | 4.800 |
| Correcciones automáticas de cantidad identificadas | **0** |

La ausencia de snapshot aparece como `SNAPSHOT_AUSENTE` y **no** cuenta como inconsistencia cuantitativa por sí sola. Los 221 candidatos son diferencias entre fuentes o reservas que merecen cotejo documental; no son una instrucción de ajuste.

## Comparación V1 / V2

| Aspecto | V1 / auditoría anterior | V2 / captura final |
|---|---|---|
| Productos analizados | 13.711 en la captura reportada | 14.379 activos en esta captura |
| Regla para snapshot ausente | Lo convertía en stock 0 | Lo deja como `null`, estado `SNAPSHOT_AUSENTE`; no compara como cero |
| Métrica destacada | 4.445 diferencias / 225.464,0 absoluto | 221 candidatos cuantitativos; comparaciones fuente por fuente |
| Cobertura del snapshot | No estaba separada claramente | 911/14.379 = 6,336%; 13.468 ausentes |
| Ledger vs lotes | No era el eje principal | 174 productos `requires_lot`, delta absoluto 3.329,0 |
| Reservas | SQL propio parcial, no idéntico al resolver de stock del ERP | Se mide por separado replicando `stock_context`; líneas ID, nombre exacto y parcial quedan contadas |
| Referencias | Validaba unos pocos tipos | 8.021 movimientos clasificados por tipo, validez y trazabilidad |
| Efecto sobre datos | V1 tenía un modo de escritura `--fix` basado en la métrica antigua | `--fix` deshabilitado; el programa no permite modificar inventario |

La consulta V1 que producía el número de **4.444** en el desglose anterior contaba productos sin snapshot que tenían movimientos; esa condición no filtraba por delta no cero. Por ello ese 4.444 no debe presentarse como conteo exacto de productos discrepantes. Además, el conjunto creció entre capturas, por lo que los totales V1 y V2 no son una comparación sobre idéntico estado temporal. El criterio que sí queda corregido en V2 es que ausencia de snapshot ya no se imputa como stock cero.

## Fuente efectiva, cantidades y disponibilidad

V2 muestra cada fuente independientemente. Para el producto sin lotes toma el ledger como saldo físico diagnóstico; si exige lote, toma `SUM(lot_stock.available_qty)` como saldo físico operativo principal y muestra el ledger al lado. Calcula `disponible = físico - reservado`; nunca usa el máximo entre ledger, lotes y snapshot para declarar consistencia.

También reporta `erp_stock_lookup`, que replica como dato observacional la rama actual de `get_product_available_stock()` —incluido el `max()` que usa la aplicación para productos sin lote—, pero ese valor no entra en las comparaciones de consistencia. Los campos por producto en `--details --json` incluyen ID, SKU, nombre, `requires_lot`, presencia y valor del snapshot, ledger, lotes, reserva, físico, disponible diagnóstico, valor del getter ERP, deltas y clasificaciones.

Se confirma una inconsistencia conceptual de la aplicación que queda documentada y fuera de este cambio: si falta snapshot en un producto sin lote, `get_product_available_stock()` devuelve el ledger como “disponible”; la vista de inventario después suma la reserva para calcular “físico”. Eso puede presentar `ledger + reserva` como físico cuando la lectura diagnóstica interpreta que el ledger ya es físico y calcula disponible restando la reserva. El V2 expone ambos resultados para cotejo, pero no cambia la aplicación.

## Reservas

La semántica de reserva reutilizada es la de `services.stock_context.get_reserved_stock_by_sku()`:

- ventas con `status='Pendiente'`, usando `products_json`, primero por `product_id` y después nombre exacto o parcial;
- insumos de órdenes de producción con `status='Aprobada'`;
- líneas agrupadas por SKU. `list_sales()` actualmente hace `LEFT JOIN sale_payments`, así que sus filas pueden repetirse por pago; V2 refleja esa semántica actual y no corrige el posible doble conteo.

En la captura final: **6 productos** tienen reserva superior a la fuente física y 1 línea de venta no se pudo asociar a un producto. Los seis casos llevan SKU de prueba/diagnóstico, por ejemplo `TEST-CONC-DBG2`, `SKU-CONC-DBG-A` y `TEST-FLASH-MSG`; se reportan como candidatos, sin modificación. Hubo 32 líneas asociadas por ID, 34 por nombre exacto y 350 por coincidencia parcial. Las coincidencias parciales pueden ser ambiguas y deben investigarse antes de confiar en esos saldos.

## Trazabilidad de movimientos

| `reference_type` | Movimientos | Referencias válidas | ID/tipo ausente | Huérfanas | Legacy/genéricas | No verificables |
|---|---:|---:|---:|---:|---:|---:|
| Sin tipo (`NULL`) | 3.717 | 0 | 3.717 | 0 | 3.717 | 0 |
| `sale` | 1.337 | 1.337 | 0 | 0 | 0 | 0 |
| `MANUAL_ENTRY` | 1.277 | 0 | 0 | 0 | 1.277 | 0 |
| `purchase_order` | 854 | 854 | 0 | 0 | 0 | 0 |
| `production_order` | 429 | 429 | 0 | 0 | 0 | 0 |
| `sale_cancellation` | 338 | 338 | 0 | 0 | 0 | 0 |
| `inventory_entry_item` | 32 | 32 | 0 | 0 | 0 | 0 |
| `reconciliation_orphan` | 26 | 0 | 0 | 26 | 0 | 0 |
| `initial_seed` | 7 | 0 | 0 | 0 | 7 | 0 |
| `reconciliation` | 3 | 0 | 0 | 0 | 3 | 0 |
| `inventory_adjustment` | 1 | 1 | 0 | 0 | 0 | 0 |
| **Total** | **8.021** | **2.991** | **3.717** | **26** | **5.004** | **0** |

“Sin tipo/ID” y “legacy/genérica” se solapan para `reference_type=NULL`; por eso sus columnas no se suman. Hay **26 movimientos huérfanos** previamente normalizados como `reconciliation_orphan` y **5.004 movimientos** genéricos o sin tipo; ninguno se reparó. A nivel de producto, 4.715 tienen alguna alerta de trazabilidad y 4.708 quedan clasificados `MOVIMIENTOS_SIN_ORIGEN`.

## Lectura de las categorías

- `SNAPSHOT_AUSENTE`: 13.468; cobertura, no inconsistencia de cantidad.
- `LEDGER_VS_LOTES`: 174 productos con lote controlado; total absoluto 3.329,0. Este es el grupo más claro para investigación posterior. Los mayores casos observados son productos `MP-A-*` con ledger 100 y lotes 60 (delta 40), con patrón repetido de fixtures; no se ajustó ninguno.
- `SNAPSHOT_VS_LEDGER`: 86 snapshots presentes, con comparación de stock físico esperado como `snapshot + reservado` contra ledger; delta absoluto 929,0.
- `SNAPSHOT_VS_LOTES`: 43; delta absoluto 1.683,0.
- `RESERVA_INCONSISTENTE`: 6; todos requieren comprobar líneas `products_json` y asociación por nombre parcial.
- `SIN_MOVIMIENTOS_CON_STOCK`: 43. Contrasta snapshots/lotes con ausencia de movimiento; es candidato de procedencia, no justifica crear asientos automáticamente.
- `OK`: 769 productos que no presentan alertas en las comparaciones ejecutadas. La falta de snapshot puede coexistir con `OK` cuantitativo, y se informa como clasificación adicional.
- `REFERENCIAS_HUERFANAS`: 26 movimientos en total y 11 productos afectados.
- Lotes negativos/filas inválidas: 0. Movimientos con cantidad cero: 0.

Las clasificaciones se solapan; el total de candidatos cuantitativos (221) es la unión sin duplicados de `LEDGER_VS_LOTES`, snapshots incompatibles, reservas negativas/disponibilidad negativa y stock de snapshot/lote sin movimientos. Los 4.800 que requieren alguna revisión añaden trazabilidad; no significan 4.800 errores físicos.

## Comandos disponibles

```bash
python tools/reconcile_inventory.py --check
python tools/reconcile_inventory.py --check --details
python tools/reconcile_inventory.py --check --json
python tools/reconcile_inventory.py --check --details --json
```

`--fix` queda rechazado por el CLI y termina antes de conectarse a PostgreSQL. Las conexiones de auditoría son `READ ONLY` y `REPEATABLE READ` para mantener consistentes conteos, clasificación y referencias dentro de una captura.

## Tests y estado

- Tests sintéticos del reconciliador: **11 passed**. Cubren snapshot ausente, snapshot cero, igualdad/diferencia ledger-lotes, stock físico/reservado/disponible, soft-delete y referencias sin origen/huérfanas.
- Suite completa: **466 passed, 0 failed** en `facturacion_cleanup_verify`.
- V2 `--check --details --json`: **14.379 filas de producto**, salida JSON parseada correctamente; conexión en solo lectura.
- No se ejecutó `--fix`; **0 correcciones de cantidad**.

**Estado de esta fase: GREEN para el diagnóstico V2; inventario aún NO declarado reconciliado.** Los 221 candidatos cuantitativos y las alertas de linaje quedan para un plan posterior; no se realizó ninguna reparación.
