# Auditoría funcional y coherencia de costos y precios del ERP

Fecha: 20 de octubre de 2026. Aplicación evaluada: Flask/PostgreSQL de este repositorio, usada en el puerto 5001.

**Dictamen: funcionamiento automatizado estable, pero coherencia económica NO certificable.** La suite disponible aprueba; existen diferencias comprobadas entre cotización impresa, importe de venta, costo comercial y costo de inventario. Deben resolverse antes de considerar correctos todos los precios finales.

## Alcance y método

- Suite completa existente ejecutada con `venv/bin/python tools/run_isolated_tests.py --pytest-args tests`: **565 passed en 215,93 segundos**, sin fallos ni omisiones reportadas. La herramienta crea una copia efímera de la plantilla marcada y la elimina al terminar; terminó con código 0, incluidas las comprobaciones de igualdad de conteos de las bases persistentes.
- Lectura de `facturacion` con transacción PostgreSQL `READ ONLY`, aislamiento `REPEATABLE READ`: 82 productos, 47 documentos de venta/cotización, 9 OC, 14 recepciones, 15 líneas recibidas, 4 facturas de compra, 4 OT finalizadas, 42 movimientos, 12 filas de existencias por lote, 12 líneas de costo vendido, 10 pagos por ítem, 4 deudas y 8 cuotas.
- Reconciliador existente en `--check --details --json`, sin correcciones.
- Revisión de código de cálculo de cotizaciones, listas de precios, costo promedio ponderado (PPP), conversión a venta, cobros, reportes y producción.
- No se cambiaron reglas, precios, stock, documentos ni pagos durante esta auditoría. Los archivos nuevos son evidencia y análisis.

Las pruebas cubren escenarios programados en una plantilla; no son una certificación de cada combinación posible ni una sesión nueva de navegador sobre todos los formularios. La lectura actual incluye registros con nombres E2E/TEST/auditoría; sus anomalías se informan, pero no se extrapolan a una pérdida comercial efectiva.

## Cobertura funcional

| Proceso | Evidencia actual | Resultado y límite |
|---|---|---|
| Acceso, roles, permisos y CSRF | Suites `tests/security`, pruebas de rutas | Aprobadas en aislamiento; no es una prueba de penetración |
| Productos, clientes, proveedores y Excel | Suites de maestros, importación y paginación | Aprobadas |
| Cotización y conversión a venta | Suites de cotización, clientes y ventas/stock | Flujos aprobados; IVA y costo sugerido presentan los hallazgos A01–A03 |
| Compras, recepción y CxP | Suites de OC, recepción, totales y CxP; aritmética de datos actuales | Aprobadas; dos facturas vinculadas a recepción cuadran con la regla implementada de IVA |
| Stock, lotes, FIFO, reservas y ajustes | Suites específicas y reconciliación actual | Integridad operacional OK; demanda descubierta y advertencias legacy descritas abajo |
| Producción administrativa y operario | Suites de FIFO multicapa, producción y operario; 4 OT actuales | Flujos aprobados; una OT histórica tiene valoración incompleta |
| Despacho, cancelación, embalajes e idempotencia | Suites de despacho y embalajes | Aprobadas en aislamiento; no hay embalajes persistidos actualmente para contrastar un caso real |
| Cobros y CxC | Suites de pagos/CxC y pagos aprobados actuales | Aprobadas; dependen del importe erróneamente interpretado de A01 |
| Bancos y conciliación | Suites de ciclo de cuentas y conciliación | Aprobadas; no contrastado con cartolas externas |
| Deudas y gastos operacionales | Suites de deudas/gastos; revisión de 8 cuotas | Aprobadas; cuotas, pagos y saldos actuales cuadran |
| Reportería y flujo de caja | Suites específicas | Aprobadas; revisar IVA y exclusión de documentos anulados |

## Hallazgos priorizados

### A01 — Alta: el total impreso no coincide con el importe vendido y cobrado

**Comprobado en las 17 cotizaciones actuales.** El POST calcula `cantidad × precio × (1 − descuento/100)` y guarda la suma en `sales.total_amount`, sin sumar IVA. La impresión interpreta esa suma como neto y agrega 19%. La conversión copia el importe guardado a la venta; CxC resta los pagos a ese importe. A su vez, el cálculo de rentabilidad interpreta el importe guardado como IVA incluido y lo divide por 1,19.

Ejemplos:

| Cotización | Guardado / base de venta | Total mostrado por la fórmula de impresión | Diferencia |
|---|---:|---:|---:|
| COT-04208 | $30.000 | $35.700 | $5.700 |
| COT-04210 | $11.904 | $14.166 | $2.262 |
| COT-04212 | $8.680 | $10.329 | $1.649 |
| COT-04213 | $300.000 | $357.000 | $57.000 |

Son importes calculados reproduciendo la fórmula de la plantilla, no extraídos de un PDF nuevo. La diferencia agregada en las 17 cotizaciones es $92.546; **no equivale a una pérdida ni a deuda exigible**, porque incluye históricos/pruebas y no determina el acuerdo comercial real.

Fuentes: `routes/ventas.py:1591–1608`, conversión `:2050`; `templates/cotizaciones.html:616–628`; `repositories/sales_repo.py:932`; CxC en `repositories/reporting_repo.py:1944`.

Acción: definir una única representación explícita de neto, impuesto y total, calcularla en servidor y reutilizarla en impresión, venta, cobro y margen. Revisar históricos individualmente antes de recalcular importes ya cobrados.

### A02 — Alta: los precios sugeridos pueden quedar por debajo del costo o en cero

La cotización usa promedio histórico de recepciones; cuando no hay recepciones, usa `page_data.inventory_items.price`, un precio legacy, como si fuese costo. No recurre al PPP ni al costo maestro. La lista de precios usa compras de los últimos 30 días / última compra y después sí tiene fallback al maestro. Se identificaron **4 productos** con base de cotización 0 y base de lista/PPP positiva: IDs 39567 ($1.234), 39568 ($1.700), 39578 ($1.000) y 39579 ($1.000). Sus nombres indican registros de pruebas, pero el defecto de fallback es general.

Caso con stock valorizado: **PRD001 — Miel Pura 1kg** tiene PPP $1.016,6667 y base comercial $15 procedente del catálogo legacy. Con Retail 40%, el algoritmo sugiere $21 netos, por debajo del costo. La base $15 requiere revisar moneda/unidad/origen; no asumir que representa $15.000 ni corregirla automáticamente.

Además, 54 de 82 productos tienen base sugerida de cotización cero; muchos no tienen costo de referencia comprobable. No se clasifican automáticamente como 54 errores económicos, pero requieren control de completitud antes de vender.

Fuentes: `routes/ventas.py:1837–1883`; `routes/usuarios.py:489–506`; `repositories/products_repo.py:492–540`; PPP en `repositories/kardex_repo.py:29`.

Acción: acordar fuente de costo comercial (PPP, reposición u otra política explícita), usarla consistentemente y alertar o impedir sugerencias con costo no definido. No reutilizar un precio de venta legacy como costo.

### A03 — Media: el campo “margen” aplica recargo sobre costo

El algoritmo es `precio = costo × (1 + porcentaje/100)`. Es recargo: con costo $1.000 y 40%, precio neto $1.400, utilidad $400 y margen sobre venta **28,57%**. Si se pretendía un margen bruto de 40%, el precio sería $1.666,67 antes del impuesto. La aritmética implementada es consistente con recargo; el nombre puede inducir una expectativa comercial equivocada.

Acción: decidir si el negocio quiere recargo o margen sobre venta y ajustar etiqueta o fórmula según esa decisión; no incrementar precios automáticamente por esta auditoría.

### A04 — Alta para históricos: OT finalizada con costo original cero y revaluación parcial

OT-09270 (ID 6092) tiene dos consumos de insumo con costo registrado 0, una salida de producto terminado con costo original 0 y `production_orders.unit_cost = NULL`. Existe una revaluación del movimiento de salida 56163 a $1.000 por unidad, por $3.000. El PPP contempla esta revaluación, pero los consumos históricos siguen a cero; la conservación de costo documentada presenta diferencia efectiva de $3.000.

No es una nueva regresión demostrada del flujo vigente: es evidencia histórica que continúa en la base. Las otras **3 OT finalizadas** conservan costo insumido/valor producido sin diferencias: $1.066,6667, $16.500 y $31.000.

Acción: revisar la corrección histórica completa, incluyendo consumos y cabecera, mediante plan trazable; conservar el rastro de revaluación.

### A05 — Media: estados anulados no se excluyen de todos los reportes

Hay un documento `VTA-4-51C0E3`, estado `Anulada`, por $50.000. Consultas de dashboard, reporte de ventas y CxC excluyen `Cancelada`/`Cotización` (algunas también `Cancelado`), pero no `Anulada`. Por el predicado actual, este documento es elegible para sumarse en reportes cuyo resto de filtros lo incluya.

Fuentes: `repositories/reporting_repo.py:36`, `:1042`, `:1910`.

Acción: normalizar estados y centralizar la condición de documento comercial válido. El nombre del registro sugiere prueba; el impacto comercial real requiere distinguir sus datos de operación.

### A06 — Media: validación económica incompleta del POST de cotización

En `routes/ventas.py:1591–1608` se convierten cantidad a `int` y precio/descuento a `float` sin validar localmente cantidad positiva, precio finito no negativo y descuento entre 0 y 100. La interfaz restringe parte de esos campos, pero puede omitirse con una petición directa. Los arrays se recorren con `zip`, que puede truncar líneas si tienen longitudes diferentes.

No se encontraron líneas inválidas en los documentos actuales. Es un hallazgo de código; no se insertaron documentos malformados en la base operacional para demostrarlo. También conviene acordar si la cantidad debe admitir fracciones, ya que la conversión actual exige enteros.

Acción: validación en servidor y reglas de redondeo monetario uniformes; incorporar pruebas de límites junto a la futura corrección.

### A07 — Media: demanda pendiente sin cobertura y catálogo legacy desactualizado

El reconciliador informa **4 productos con 8 unidades de demanda sin cubrir**. Es una necesidad de abastecimiento o priorización, no una diferencia de stock ni un incumplimiento de la regla que permite ventas pendientes sin existencias.

Hay **11 productos con advertencias legacy**: 5 carecen de snapshot y 6 difieren del ledger; 3 de estos últimos también difieren de lotes. El inventario operacional no usa ese snapshot como verdad física, pero el módulo de precios todavía consulta su campo `price` (A02).

Acción: revisar cobertura de pedidos y retirar gradualmente dependencias económicas del catálogo legacy.

## Comprobaciones numéricas sin diferencias detectadas

- Reconciliación física: 0 diferencias ledger/lotes, 0 reservas inconsistentes, 0 lotes negativos, 0 movimientos de cantidad cero; 42/42 referencias válidas, ninguna huérfana ni genérica.
- Restricciones PostgreSQL: ninguna restricción pública marcada como no validada. Esto no reemplaza una auditoría contable externa.
- 15 líneas de recepción: cantidad × precio unitario coincide con total.
- 12 líneas de OC: cantidad pedida × precio unitario coincide con total de línea.
- 12 líneas de costo congelado de venta: cantidad × costo unitario coincide con costo total.
- Ningún sobrepago aprobado detectado respecto al total guardado de ventas activas; esta igualdad no valida el tratamiento de IVA de A01.
- Facturas vinculadas a recepción 3669 y 3686: netos $100.000 y $62.000, totales $119.000 y $73.780; coinciden con la regla del sistema. Las otras 2 facturas no tienen recepción vinculada y no permiten esta comprobación; no son diferencias de IVA demostradas.
- 8 cuotas de deuda: componentes del importe, pagos por cuota y saldo pendiente cuadran.

## Orden recomendado de corrección

1. Unificar neto/IVA/total en el flujo cotización → venta → cobro → rentabilidad, con tratamiento explícito de históricos.
2. Unificar la fuente de costo comercial y revisar PRD001, precios cero, moneda/unidades y productos fabricados.
3. Acordar recargo frente a margen sobre venta y validar límites/precisión en servidor.
4. Normalizar estados de anulación en reportes y revisar la OT histórica 6092.
5. Resolver abastecimiento y dependencias legacy; ejecutar escenarios adicionales que cubran los hallazgos.

## Evidencias y reproducibilidad

- `pytest.log`: salida de la suite completa.
- `inventario.json`: resultado CHECK del reconciliador.
- `datos_lectura.json`: extracción de soporte; no incluye credenciales. Es información interna y contiene identificadores/documentos, por lo que debe mantenerse en el repositorio privado.
- `resultados_numericos.json`: comparación por producto/documento y controles aritméticos.
- `lectura.py` y `analisis.py`: scripts utilizados; el primero fuerza solo lectura y el segundo procesa la extracción sin acceso a la base. Las rutas de salida están fijadas a este workspace.

**Límites:** no se compararon documentos con SII, facturas externas, cartolas ni costos reales de mano de obra, energía, flete o mermas; no se puede certificar rentabilidad completa ni razonabilidad de mercado con la información interna disponible. No se ejecutó un nuevo recorrido visual de todos los módulos ni restauración de respaldos. No se alteraron importes para ocultar diferencias.
