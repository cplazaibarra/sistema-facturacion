# Auditoría numérica del ERP V1

**Fecha:** 26 de octubre de 2026  
**Dictamen:** **YELLOW — hay cálculos que cuadran, pero no se puede certificar que todo esté correcto.**  
**Alcance:** revisión de solo lectura de `facturacion`, validación de cálculos financieros e inventario, y ejecución de la suite automatizada en una copia efímera.

## Resumen

Las comprobaciones independientes de compras, recepciones, facturas vinculadas, cuotas y sobrepagos no encontraron diferencias en las muestras verificadas. El Kardex y las existencias por lote también coinciden entre sí. Sin embargo, hay una diferencia confirmada en la proyección de ingresos del flujo de caja: las vistas mensual y semanal cuentan el total de ventas parcialmente pagadas, en vez del saldo pendiente. En dos ventas con abonos aprobados por un total de $200.000, la proyección incluye $476.000 en lugar de $276.000; la sobreestimación es **$200.000**.

La auditoría también detectó registros de venta sin detalle de líneas y dos facturas de proveedor con abonos heredados sin fecha ni evento de pago trazable. No se modificaron ni repararon registros.

## Alcance y seguridad

- La inspección de datos operacionales se ejecutó sobre `facturacion` con transacción de solo lectura (`READ ONLY`). No se ejecutaron escrituras, DDL ni reparaciones.
- La suite se ejecutó mediante `tools/run_isolated_tests.py` contra una base efímera `facturacion_test_run_*`; el harness no reportó diferencias de huellas protegidas y completó su limpieza.
- Las cifras y filas de `facturacion` reflejan el estado observado al momento de la consulta. Algunos documentos tienen identificadores con apariencia de datos de prueba; no se asumió que fueran operaciones comerciales reales ni se eliminaron.
- Las comprobaciones monetarias se calcularon independientemente con `Decimal` y redondeo `ROUND_HALF_UP`, conforme a los importes persistidos y al IVA del 19%.

## Comprobaciones que cuadran

| Área | Muestra | Resultado |
|---|---:|---|
| Órdenes de compra | 9 órdenes, 12 líneas | 0 diferencias entre cantidad × precio unitario, total de línea y total de cabecera |
| Recepciones | 15 líneas | 0 diferencias entre cantidad × precio unitario y total de línea |
| Facturas de compra vinculadas | 2 | 0 diferencias entre neto, IVA 19% y total: $100.000 + $19.000 = $119.000; $62.000 + $11.780 = $73.780 |
| Cuotas de deuda | 8 | 0 diferencias entre componentes, total, pagos relacionados y saldo registrado |
| Pagos de ventas | 10 ítems aprobados | No se encontraron pagos acumulados superiores al total de sus ventas |
| Integridad referencial de movimientos | 42 movimientos | 42 referencias válidas; sin huérfanos ni movimientos de cantidad cero |
| Restricciones inválidas | — | 0 detectadas |

Estas verificaciones cubren las filas disponibles y no prueban por sí solas todos los flujos de la aplicación ni todos los datos históricos.

## Inventario

El verificador oficial se ejecutó en modo `--check --json`, sin correcciones automáticas:

- 82 productos; 77 tienen snapshot de inventario (93,90%), 5 no tienen snapshot.
- Ledger frente a lotes: diferencia absoluta **0 unidades**.
- Snapshot frente a ledger: 6 productos con diferencia, diferencia absoluta acumulada de **20 unidades**.
- Snapshot frente a lotes: 3 productos con diferencia, diferencia absoluta acumulada de **11 unidades**.
- No se detectaron inconsistencias de reservas ni referencias de movimientos inválidas.
- Se identificaron 4 productos con demanda no cubierta (8 unidades) y 11 advertencias de legado.
- El informe del verificador clasifica la integridad operacional como `OK` y el estado legado como `LEGACY_WARNING`.

Ledger y lotes coinciden entre sí, pero los snapshots no coinciden en todos los casos. Como hay snapshots ausentes y advertencias de legado, esas diferencias requieren revisión por producto antes de concluir que el saldo visible es correcto en todos los reportes.

## Hallazgo: proyección de caja sobreestima ventas parcialmente cobradas

En `repositories/reporting_repo.py`, las consultas de `get_cash_flow_data()` y `get_cash_flow_data_weekly()` agrupan `sales.total_amount` para documentos cuyo estado no es `Pagado`. No descuentan los pagos parciales. En contraste, el detalle de CxC/flujo de caja calcula el saldo pendiente a partir de pagos registrados.

En los datos observados hay dos ventas pendientes de $238.000 cada una, con abonos aprobados de $100.000 cada una:

| Concepto | Venta A | Venta B | Total |
|---|---:|---:|---:|
| Total de documentos | $238.000 | $238.000 | $476.000 |
| Abonos registrados | $100.000 | $100.000 | $200.000 |
| Saldo pendiente correcto | $138.000 | $138.000 | $276.000 |
| Sobreestimación de proyección | $100.000 | $100.000 | **$200.000** |

**Estado: FAIL confirmado en la lógica de agregación.** La proyección semanal y mensual puede contar otra vez importes ya cobrados. Los dos registros concretos parecen asociados a escenarios de prueba; la falla lógica afecta cualquier venta parcialmente pagada que entre en esas consultas. No se alteró código en esta auditoría.

## Hallazgos que requieren conciliación documental

1. **Ventas sin detalle persistido:** 9 de 47 ventas tienen `products_json` vacío. En esas filas no se puede recalcular el neto desde productos y cantidades. No se marcaron como error aritmético porque falta el detalle fuente; se clasifican `NOT VERIFIED`.
2. **Abonos de CxP sin evento trazable:** dos facturas pendientes registran `payment_amount = $38.000` y carecen de fecha de pago; no aparecen como eventos en `purchase_payment_events`. El saldo calculado por CxP descuenta esos montos, pero el flujo de caja no puede atribuirles una salida real fechada. Si fueron pagados, falta trazabilidad del egreso; si no, el saldo pendiente podría estar subestimado en $76.000. Requiere cotejo con comprobantes antes de cualquier corrección.
3. **Pagos de CxC con estado pagado sin ítems nuevos:** dos ventas con estado `Pagado` no tienen registros en `sale_payment_items`; podrían utilizar el mecanismo histórico. Su origen no se determinó y no se infirió un defecto sólo por esa ausencia.

## Pruebas automatizadas

Suite ejecutada en clon efímero: **630 PASS, 2 FAIL**, duración 259,72 segundos.

| Prueba fallida | Evaluación |
|---|---|
| `tests/integration/test_inventory_lots_pagination.py::test_inventory_lots_route_200` | La ruta respondió, pero el test exige el breadcrumb antiguo `Reportes > Inventario por Lotes y Bodega`. La página fue trasladada a Bodega; la expectativa del test parece obsoleta. Sigue siendo una prueba fallida que debe actualizarse y verificarse. |
| `tests/unit/test_repository_imports.py::test_facade_exposes_all_repository_functions` | Fallo real de integración: `db.py` no exporta `list_inventory_entries_page`, función nueva de `repositories.inventory_repo`. |

No se atribuyen estos fallos a errores de montos. Aun así, la suite actual no está completamente aprobada.

## Resultado por área

| Área | Resultado |
|---|---|
| Compras, recepciones, IVA y cuotas revisadas | PASS en las muestras consultadas |
| Sobrepagos de CxC revisados | PASS en 10 ítems aprobados |
| Inventario ledger ↔ lotes | PASS; diferencia 0 |
| Snapshots de inventario | YELLOW; diferencias y cobertura incompleta |
| Proyección mensual/semanal de CxC | FAIL; sobreestima $200.000 en dos ventas parciales observadas |
| Trazabilidad de dos abonos CxP | NOT VERIFIED; $76.000 sin fecha/evento trazable |
| Suite automatizada | FAIL; 630 PASS y 2 FAIL |
| Integridad de bases protegidas durante pruebas | Sin alerta de huellas en el harness; ejecución mutable sólo en clon efímero |

## Conclusión

**No se puede afirmar que todos los números del ERP estén cuadrando correctamente.** Varias sumas de compras, recepciones, IVA y cuotas coinciden exactamente, y ledger/lotes no presentan diferencia. Pero existe una sobreestimación reproducible de $200.000 en la proyección de caja para pagos parciales, quedan diferencias entre snapshots y movimientos por investigar y hay abonos de CxP sin trazabilidad fechada. La suite actual también tiene dos fallos.

El dictamen es **YELLOW**, con un defecto de proyección confirmado. Se recomienda corregir y probar la agregación de ventas parciales en flujo de caja, revisar las diferencias de inventario por SKU y conciliar los dos abonos de proveedor con sus comprobantes. Esta auditoría no modificó código ni datos operacionales.

## Evidencia reproducible

- Lectura sanitizada de solo lectura: `/tmp/erp-audit-now/datos_lectura.json`.
- Log de suite aislada: `/tmp/erp_isolated_pytest_1.log`.
- Verificador de inventario: ejecutar `venv/bin/python tools/inventory_integrity_check.py --check --json` en el entorno del proyecto, manteniendo el modo de solo comprobación.
- Código de agregación revisado: `repositories/reporting_repo.py`, funciones `get_cash_flow_data()` y `get_cash_flow_data_weekly()`.

