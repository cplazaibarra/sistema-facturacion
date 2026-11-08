# Informe de rediseño: Trazabilidad de Lotes — ERP V1

**Fecha:** 2026-10-23  
**Estado:** implementación funcional validada con pruebas aisladas; validación visual real pendiente.

## Resumen

Se reemplazó el timeline vertical de trazabilidad por una vista responsive basada en la referencia entregada: identificación compacta del lote, diagrama de entrada → transformaciones → movimientos de salida y resumen del lote consultado. La pantalla conserva la exploración de Recall y las exportaciones CSV/PDF.

Las salidas se obtienen de los registros físicos del ERP. Se toma el Kardex por `lot_id` y se usa `sale_lot_movements` como respaldo cuando un flujo registró el despacho allí sin una fila equivalente en Kardex. Una clave de coincidencia evita contar dos veces un despacho presente en ambas fuentes. Las ventas anuladas y sus reversiones no aparecen como despachos efectivos.

## Archivos modificados

- `templates/trazabilidad.html`: nuevo diseño adaptable, buscador y selector de lotes, tarjetas de origen, transformaciones y salidas, resumen, Kardex expandible y Recall secundario.
- `services/lot_traceability_service.py`: arma el conjunto de movimientos visibles, elimina duplicados, calcula resumen directo desde movimientos y saldo de `lot_stock`, y presenta el estado operativo del lote.
- `repositories/lot_genealogy_repo.py`: consulta movimientos por IDs de lote y agrega el estado de venta al árbol de trazabilidad para excluir ventas anuladas.
- `routes/trazabilidad.py`: protege la página, APIs y exportaciones con el permiso existente `inventario`.
- `tests/integration/test_lot_traceability_phase5b.py`: añade aserciones de movimientos, render de pantalla y escenarios de cobertura.

## Comportamiento de los datos

- El saldo mostrado sigue siendo el saldo actual asociado al lote en `lot_stock`; la interfaz no lo recalcula ni lo modifica.
- El total y número de salidas del resumen corresponden al lote consultado, no agregan unidades de productos derivados de otras transformaciones.
- La columna de movimientos muestra despachos de ventas, consumos productivos y ajustes negativos físicos. El historial expandible muestra también otros movimientos y reingresos con su signo.
- Las transformaciones provienen de las relaciones `production_lot_consumptions` y `production_lot_outputs`. Si no hay relaciones, aparece “Sin transformaciones”.
- Los despachos pendientes no se infieren desde ventas: sólo se usan `sale_lot_movements` creados por el flujo de despacho o movimientos físicos del Kardex.
- Los enlaces llevan a ventas filtradas, órdenes de trabajo filtradas y Kardex del producto. Se conserva la consulta de Recall con clientes y ventas afectados y sus descargas.
- El estado combina el estado vigente del lote con el saldo: disponible, agotado, cuarentena, vencido, retirado por Recall o inconsistencia de saldo.

No se alteraron FIFO, PPP, costos congelados, movimientos históricos ni cantidades de inventario. No se agregaron tablas ni migraciones.

## Pruebas

Comando ejecutado:

```text
venv/bin/python tools/run_isolated_tests.py --pytest-args tests/integration/test_lot_traceability_phase5b.py
```

Resultado final:

```text
SUITE 1: GREEN
10 passed in 8.08s
```

Cobertura añadida/verificada:

| Escenario | Resultado |
|---|---|
| Lote sin salidas, separado de otro lote del mismo producto | PASS |
| Dos salidas parciales y saldo agotado | PASS |
| 21 salidas; la pantalla representa todas y permite scroll | PASS |
| Lote consumido en genealogía de producción, con lotes derivados y ventas | PASS |
| Ajuste físico aplicado incluido como salida | PASS |
| Venta cancelada y reversión excluidas de las salidas efectivas | PASS |
| Impacto Recall con clientes y ventas | PASS |
| Usuario sin permiso `inventario` recibe 403 | PASS |
| Render Jinja de la página con datos integrados | PASS |

El archivo de pruebas de integración completo ejecutó 10 casos PASS en la copia PostgreSQL efímera. El runner ejecuta verificaciones de huellas de esquema y datos para `facturacion` y `facturacion_cleanup_verify`, y elimina la base y el rol efímeros en su bloque de limpieza. El runner finalizó con código cero.

La suite completa de regresión de 1.047 pruebas no se ejecutó en esta tarea.

## Validación visual

Se comprobó el HTML renderizado mediante el cliente Flask de integración y se comprobó que contuviera el diagrama, las salidas y el estado de agotamiento.

No se tomó captura de navegador ni se validó el layout en Chromium/Playwright. El entorno tiene el paquete cliente de Playwright para Node, pero no se encontró una instalación ejecutable de Playwright para Python ni Selenium, y el acceso al servidor local desde este entorno no está habilitado. Por ello la alineación final en navegador, resoluciones y captura quedan **NOT VERIFIED**. El CSS incluye reglas responsive para escritorio, tablet y móvil.

## Riesgos y limitaciones

1. Parte de la genealogía histórica puede estar representada sólo en `sale_lot_movements`; se soporta como respaldo. Las salidas sin `lot_id` quedan sin atribuir; no se relacionan solo por producto y código, para evitar mezclar lotes distintos.
2. La cobertura funcional del módulo aprobó, pero no se ejecutó la regresión global ni la validación visual de navegador. No debe interpretarse como una certificación GREEN integral del ERP.
3. El enlace de orden de trabajo abre el listado con el número de OT buscado; el enlace de Kardex abre el producto asociado y conserva el movimiento identificado en la pantalla.

## Dictamen

**YELLOW para el rediseño completo.** La implementación y sus pruebas de integración aisladas aprobaron; la validación en navegador y captura solicitada no pudo completarse, y la suite global no se repitió. No se detectaron cambios a las bases protegidas durante la suite aislada.
