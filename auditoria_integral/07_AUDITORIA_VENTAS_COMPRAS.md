# 07. AUDITORÍA DE VENTAS Y COMPRAS — CICLOS COMERCIALES Y DOCUMENTALES

**Fecha de Auditoría:** 17 de Octubre de 2026  
**Módulos Evaluados:** Cotizaciones, Ventas, Despachos, Cobranza, Órdenes de Compra y Recepción de Mercaderías.

---

## 1. CICLO DE COMPRAS Y CUENTAS POR PAGAR (CxP)

### 1.1 Invariante de la Orden de Compra (`PAR-PUR-01`)
- **Regla Estricta:** La creación, edición o aprobación formal de una Orden de Compra (OC) tiene impacto financiero/compromiso, pero **NO incrementa el stock físico ni altera el Kardex de inventario**.
- El inventario físico se actualiza exclusivamente cuando se registra una **Recepción de Mercaderías** (`purchase_receipts`), generando los lotes correspondientes y recalculando el PPP del producto.

### 1.2 Recepciones Parciales y Totales
- Una Orden de Compra puede recibirse en múltiples entregas.
- El sistema controla el saldo pendiente por línea de producto (`quantity_ordered - quantity_received`).
- Cuando todas las líneas alcanzan la cantidad pedida, la OC pasa automáticamente a estado `RECIBIDA`.

### 1.3 Facturación de Compra y Obligación de Pago (`PAR-PUR-02`)
- La factura del proveedor genera el registro en Cuentas por Pagar (`accounts_payable`).
- Toda amortización o abono se registra en `accounts_payable_payments`, descontando el saldo insoluto.
- Se previene estrictamente el sobrepago: un pago por un valor superior al saldo remanente es rechazado con error transaccional.

---

## 2. CICLO DE VENTAS Y CUENTAS POR COBRAR (CxC)

### 2.1 Neutralidad de la Cotización (`PAR-SAL-01`)
- Una cotización (`quotations`) es un documento de propuesta comercial. No reserva stock físico ni genera compromisos de bodega.
- Al convertirse en Orden de Venta (`sales_orders`), adquiere estado *Pendiente* y es en ese instante cuando se valida la disponibilidad y se registra el compromiso de stock (`stock_commitments`).

### 2.2 Despacho y Consumo Físico (`PAR-INV-03`)
- El consumo físico del inventario se materializa una sola vez cuando el pedido es preparado y despachado (`sales_dispatches`).
- Al realizar el despacho, se libera el compromiso de stock y se emiten los movimientos de salida del Kardex vinculando los lotes exactos seleccionados mediante FIFO.

### 2.3 Estado Terminal de Venta Cancelada (`PAR-INV-04`)
- Una venta en estado `CANCELADA` es un estado terminal definitivo.
- El sistema no permite reactivar o reabrir una venta cancelada: si el cliente decide retomar la compra, las reglas de negocio exigen generar una nueva cotización u orden de venta.
- Si una venta se cancela antes de ser despachada, se libera automáticamente la reserva global de stock sin alterar el stock físico.

---

## 3. HALLAZGOS Y RECOMENDACIONES EN VENTAS Y COMPRAS

| ID Hallazgo | Módulo | Descripción | Severidad | Recomendación |
|---|---|---|:---:|---|
| **COM-01** | Compras / Facturas | En V1 la interfaz de usuario permitía crear recepciones sin ingresar factura, y la subida de la factura PDF se realizaba en un paso posterior que a veces quedaba inconcluso. | **P2** | Establecer un indicador de estado "Pendiente de Factura" visible en el listado para auditoría rápida. |
| **VEN-01** | Ventas / Documentos | No existe integración electrónica directa con el SII (Servicio de Impuestos Internos de Chile) para emisión automática de DTEs (Facturas y Boletas Electrónicas). Opera mediante adjuntos manuales. | **P1 (para fase comercial)** | Diseñar un conector / micro-servicio de firma electrónica y facturación DTE con un proveedor autorizado o conexión directa SOAP/REST. |
| **VEN-02** | Ventas / Clientes | Al momento de crear una cotización, no se realiza una comprobación de riesgo crediticio o límite de crédito concedido al cliente. | **P2** | Agregar en `customers` un campo `credit_limit` y alertar al vendedor si el saldo pendiente en CxC supera dicho límite. |
