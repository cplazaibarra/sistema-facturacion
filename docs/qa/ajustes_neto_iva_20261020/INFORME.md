# Correcciones de valores netos, IVA, precios y costos

Fecha: 20 de octubre de 2026.

## Regla monetaria implementada

- Los precios unitarios ingresados en cotizaciones y registro manual son **netos**, antes de IVA.
- Cada línea aplica el descuento a `cantidad × precio neto`, con cálculo Decimal y redondeo comercial a centavos.
- El neto del documento se redondea al peso; el IVA es 19% de ese neto, redondeado al peso con `ROUND_HALF_UP`.
- El total guardado para venta/cotización es **neto + IVA**. La conversión a venta conserva ese total y CxC utiliza el mismo importe.
- Impresión y detalle de venta reciben un desglose calculado en servidor; ya no vuelven a agregar IVA a un total que lo incluye.
- Ejemplo comprobado: 3 unidades a $10.000 netos, 10% de descuento → neto $27.000, IVA $5.130, total $32.130.
- Los costos de inventario, PPP, fabricación y embalaje se comparan con ingresos netos para calcular utilidad; el IVA no se usa como utilidad.

Archivos centrales: `services/money.py`, `services/pricing.py`, rutas de ventas/recepción y repositorios de ventas/inventario/reportes.

## Documentos históricos

Los 47 documentos existentes conservan **exactamente el total y las líneas originales almacenadas**; los 10 pagos por ítem permanecen iguales. No se incrementaron cuentas por cobrar antiguas para resolver una ambigüedad de visualización.

Cuando las líneas antiguas equivalen al total registrado, la vista las desglosa a neto a partir de ese total. Cuando las líneas ya son netas y el total contiene IVA, se utiliza esa base neta. Los datos originales no se reescriben. Al editar o clonar un histórico, el formulario recibe líneas netas compatibles con el total, para evitar aplicar IVA por segunda vez.

Ejemplo histórico verificado en navegador: COT-04213 conserva total $300.000 y ahora muestra neto $252.101 + IVA $47.899. Antes la plantilla mostraba $357.000 al agregar un impuesto que no estaba incorporado al importe registrado como total. Si una factura externa o acuerdo comercial de un histórico establece otro importe, debe conciliarse con ese documento externo; no se infiere una deuda adicional mediante esta corrección.

## Costos y precios sugeridos

- Cotizaciones y lista de precios usan la misma fuente: **PPP del ledger**, incluyendo revaluaciones, con costo maestro cuando no existen movimientos.
- Se eliminó el uso de `inventory_items.price` como costo y el desacuerdo entre promedio histórico de recepciones y compras de los últimos 30 días.
- La consulta por lote reproduce el algoritmo de PPP vigente con dos consultas SQL, sin una consulta por cada producto.
- El porcentaje comercial se denomina **recargo sobre costo neto**. Se conserva la fórmula comercial existente: `precio neto = costo × (1 + recargo/100)`.
- Los productos sin costo muestran la advertencia correspondiente; el servidor exige un precio neto positivo para cotizar. No se inventan costos para completar maestros vacíos.
- Se conserva la precisión del costo al recalcular precios en pantalla, evitando usar el costo previamente redondeado para visualización.
- La rentabilidad distingue costo `frozen`, `estimated` e `incomplete`: costo congelado de despacho, estimación PPP actual o costo incompleto. La pantalla oculta el margen numérico cuando faltan costos.

PRD001 dejó de usar $15 del catálogo legacy como base comercial. Tras la corrección histórica descrita abajo, su costo PPP vigente es $1.066,6667. Las sugerencias aplican el recargo comercial a este costo.

## Validación y reportería

- Se rechazan precios cero/negativos/no finitos, cantidades no positivas/no enteras, descuentos fuera de 0–100% y arrays de líneas incompletos.
- Se valida que los recargos sean números finitos no negativos.
- El descuento de 100% mantiene el subtotal cero; ya no se sustituye por el subtotal sin descuento en la vista de venta.
- Se excluyen `Cancelada`, `Cancelado`, `Anulada`, `Anulado`, `Cotización` y `Borrador` del universo comercial correspondiente de reportes.
- El reporte de ventas presenta total con IVA, neto e IVA por separado. Su distribución por producto se asigna al mismo total bruto con reparto de centavos; los históricos sin detalle se identifican, en lugar de quedar fuera de la conciliación.
- Recepción y detalle de recepción utilizan la misma regla de neto/IVA y redondeo.

## Corrección de la OT histórica

Se ejecutó `tools/repair_legacy_production_valuation.py` para OT-09270. Se calculó el PPP histórico inmediatamente anterior a sus consumos: costo de insumos $3.200 para 3 unidades producidas; costo unitario $1.066,666667.

Se añadió una revaluación inmutable del movimiento de salida, encadenada a la revaluación anterior, y se completaron el costo de la OT y el costo faltante de su línea de insumo. Los movimientos originales (incluidos los costos cero históricos registrados en las salidas de insumos) permanecen intactos: la valoración contable de esas salidas se reconstruye con PPP. No se registró una revaluación directa de salidas, prohibida por el mecanismo existente.

El plan y respaldo de los registros previos están en `../auditoria_erp_20261020/reparacion_ot_plan.json` y `reparacion_ot_aplicada.json`. La herramienta valida la forma de la OT auditada y rechaza su ejecución si existen ventas con costo congelado del producto final, para evitar alterar rentabilidades históricas sin revisar su impacto.

## Evidencia de validación

- **Suite completa final: 592 pruebas aprobadas, 0 fallidas, en 224,76 segundos.** Sus resultados se conservan en `pytest_final.log`. Incluye pruebas nuevas de valores inválidos, descuentos, redondeos, coherencia de cotización/conversión/CxC/rentabilidad, paridad del costo PPP y exclusión de anuladas.
- `../auditoria_erp_20261020/navegador.json`: navegador real contra puerto 5001, logo cargado, barra lateral oculta al imprimir, neto/IVA/total correctos y 0 errores JavaScript. Todas las peticiones de escritura fueron bloqueadas por el verificador.
- `../auditoria_erp_20261020/cotizacion_imprimible_validada.pdf` y `formulario_neto_iva.png`: muestras visuales.
- `../auditoria_erp_20261020/verificacion_final.json`: 47 documentos con desglose consistente; igualdad exacta de sus totales/líneas originales, 42 movimientos originales, 12 filas de lotes y 10 pagos por ítem.
- `../auditoria_erp_20261020/inventario_despues.json`: integridad operacional **OK**, sin diferencias ledger/lotes, reservas inconsistentes ni referencias huérfanas.

Las pruebas se ejecutaron en clones PostgreSQL efímeros eliminados al terminar, con comprobación de conteos persistentes. Las modificaciones a la base operacional fueron únicamente la corrección trazable de valoración y cabecera de la OT auditada.

## Datos operativos que siguen requiriendo gestión

Los maestros sin costo necesitan documentos de compra o costos reales para completarse. La demanda pendiente sin existencias requiere abastecimiento o gestión comercial; no se crearon existencias para cubrirla. El reconciliador conserva advertencias del snapshot legacy, que ya no se utiliza para sugerir precios. Los importes externos de facturas/cartolas y costos no registrados de mano de obra, energía o fletes no se pueden certificar con las pruebas internas.
