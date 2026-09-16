# Auditoría de Trazabilidad Actual de Lotes (Fase 5B)

**Fecha:** 15 de Septiembre de 2026  
**Sistema:** ERP Facturación & Gestión de Negocio  

---

## 1. ¿Qué información ya existe actualmente?

En la base de datos PostgreSQL existen los siguientes registros relacionados con lotes:

1. **`inventory_entries` e `inventory_entry_items`:**
   - Registra recepciones de mercadería (`order_number`, `entry_date`, `warehouse`, `supplier_id`, `purchase_order_id`).
   - `inventory_entry_items` cuenta con columna `lot_number` (texto opcional) y `quantity`.
2. **`lot_stock`:**
   - Tabla que representa el saldo de stock disponible por lote y producto (`product_id`, `lot_number`, `entry_id`, `entry_date`, `initial_qty`, `available_qty`, `warehouse`).
   - Se actualiza al ingresar mercadería (`register_inventory_entry`) y al vender mediante FIFO (`consume_fifo_lots` / `consume_lots_for_sale`).
3. **`sale_lot_movements`:**
   - Tabla que registra los lotes consumidos por ventas emitidas (`sale_id`, `product_id`, `lot_number`, `quantity`, `moved_at`).
4. **`inventory_movements`:**
   - Kardex universal con columna `lot_number` (texto opcional). Registra compras (`PURCHASE_ENTRY`), ventas (`SALE_OUT`), y producción (`PRODUCTION_INPUT`, `PRODUCTION_OUTPUT`).
5. **`production_orders` e items:**
   - `production_orders`: `id`, `ot_number`, `final_product_id`, `quantity`, `status`, `completed_at`, `unit_cost`.
   - `production_order_items`: `production_order_id`, `input_product_id`, `quantity_required`, `unit_cost`.
   - `production_order_additional_items`: insumos adicionales sin lote.

---

## 2. ¿Qué relaciones históricas ya existen?

- **Recepción → Lote:** Vinculada parcialmente a través de `inventory_entry_items.lot_number` y `lot_stock.entry_id -> inventory_entries.id`. Permite conocer la OC y el Proveedor si el lote vino de una compra.
- **Venta → Lote:** Vinculada en `sale_lot_movements` (`sale_id -> sales.id`, `product_id`, `lot_number`, `quantity`). Permite conocer qué lote se despachó al cliente.

---

## 3. ¿Qué información se pierde actualmente?

1. **Insumos de Producción sin Lote:**
   - Al finalizar una OT (`routes/produccion.py:finalizar_ot`), los insumos se descuentan únicamente de `page_data.inventory_items` y se asientan en `inventory_movements` con `lot_number = NULL`.
   - No se descuentan de `lot_stock` ni se registra qué lote específico de materia prima fue consumido.
2. **Producto Terminado sin Lote:**
   - La OT incrementa el stock de producto terminado en `inventory_movements` con `lot_number = NULL`.
   - No se crea una fila en `lot_stock` ni se emite un lote formal de producto terminado.
3. **Pérdida de Genealogía (Ruptura del Hilo Trazable):**
   - No existe relación entre los lotes de insumos que entraron a la OT y el producto terminado que salió.
   - Es imposible vincular una venta de producto terminado con las materias primas que lo originaron.
4. **Dependencia de cadenas de texto (`lot_number`):**
   - Las relaciones actuales usan texto plano `lot_number`, que no es único entre diferentes productos o proveedores. No existe un `lot_id` primario inmutable.
5. **Pérdida al Agotar Stock:**
   - Si un lote llega a `available_qty = 0`, la historia detallada de sus transformaciones no cuenta con una entidad permanente de ciclo de vida.

---

## 4. Respuestas a las Preguntas Clave

| Pregunta de Auditoría | Respuesta Actual | Detalle Técnico |
|---|---|---|
| **¿Podemos identificar qué lote de materia prima fue utilizado en cada OT?** | **NO** | `production_order_items` solo tiene `input_product_id` y `quantity_required`. No guarda lote. En `routes/produccion.py` no se invoca FIFO de lotes. |
| **¿Podemos identificar qué lote de producto terminado generó una OT?** | **NO** | `production_orders` no tiene campo `lot_number` ni genera registro en `lot_stock`. |
| **¿Podemos identificar qué lote terminado salió en una venta?** | **SÍ (Parcial)** | `sale_lot_movements` guarda `lot_number` como texto, pero si el producto terminado no tenía lote al producirse, no se descuenta lote real. |
| **¿Podemos recorrer toda la cadena automáticamente?** | **NO** | La cadena está rota en el eslabón de producción. No hay unión entre `inventory_entry_items` (entrada MP) y `sale_lot_movements` (salida PT). |

---

## 5. Requerimientos de Diseño para Fase 5B

1. Crear tabla central de identidad inmutable de lotes: `lots` con PK `id` entero.
2. Crear tabla de consumos de lotes en producción: `production_lot_consumptions` (`production_order_id`, `lot_id`, `product_id`, `quantity_consumed`).
3. Crear tabla de producción de lotes terminados: `production_lot_outputs` (`production_order_id`, `lot_id`, `product_id`, `quantity_produced`).
4. Vincular `sale_lot_movements` con `lot_id` (conservando `lot_number` por compatibilidad).
5. Vincular `inventory_entry_items` con `lot_id`.
6. Conectar `lot_stock` con `lot_id`.
7. Implementar recorrido recursivo en PostgreSQL (`WITH RECURSIVE`) para forward trace, backward trace y cálculo de impacto de Recall.
