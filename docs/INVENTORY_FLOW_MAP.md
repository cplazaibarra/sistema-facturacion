# Mapa de Operaciones y Flujos de Inventario
**Sistema de Facturación / Bodega Miel (ERP Single-Tenant)**  
**Fase 2 — Consistencia y Fuente de Verdad de Inventario**

---

## 1. Arquitectura Actual de Inventario y Flujo de Datos

El sistema convive actualmente con una arquitectura híbrida y fragmentada en tres mecanismos de almacenamiento:
1. **`page_data` (`key = 'inventory_items'`):** Cadena JSON desnormalizada que contiene una lista de diccionarios con stock físico agregado por producto (`code`, `name`, `stock`, `min_stock`, etc.).
2. **`lot_stock`:** Tabla relacional en PostgreSQL que almacena existencia física segregada por lote (`product_id`, `lot_number`, `entry_id`, `entry_date`, `initial_qty`, `available_qty`, `warehouse`).
3. **Documentos Históricos:** Tablas relacionales transaccionales (`inventory_entries`, `inventory_entry_items`, `sales`, `sale_lot_movements`, `production_orders`, `production_order_items`, `production_order_additional_items`).

---

## 2. Matriz Completa de Operaciones de Stock

A continuación se mapean todas las operaciones del sistema que leen, escriben, validan o calculan stock en el ERP:

| Operación | Archivo | Función | Estructura Leída | Estructura Escrita | Mutación | Transaccionalidad | Nivel de Riesgo |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| **Recepción de Compra (con lote)** | `db.py` | `register_inventory_entry()` | `purchase_order_items`, `products` | `inventory_entries`, `inventory_entry_items`, `lot_stock`, `page_data(inventory_items)` | Incrementa (+) | Mixta: SQL en transacción `conn`, pero `page_data` en bloque `try` posterior fuera de la transacción | **Alto** (Race Condition en `page_data` y desincronización si falla `page_data`) |
| **Recepción de Compra (sin lote)** | `db.py` | `register_inventory_entry()` | `purchase_order_items`, `products` | `inventory_entries`, `inventory_entry_items`, `page_data(inventory_items)` | Incrementa (+) | Mixta (no escribe en `lot_stock`) | **Crítico** (`lot_stock` queda en 0, solo existe en `page_data`) |
| **Validación de Stock para Venta** | `db.py` | `validate_stock_for_sale()` | `products`, `lot_stock`, `page_data(inventory_items)` | Ninguna (solo lectura) | N/A | Lectura no transaccional | **Medio** (Phantom Read: stock puede variar entre validación y emisión) |
| **Consulta Stock Disponible** | `db.py` | `get_product_available_stock()` | `products`, `lot_stock`, `page_data(inventory_items)` | Ninguna | N/A | Lectura | **Alto** (Lógica de fallback disyuntiva: si `requires_lot=True` lee `lot_stock`, si no, toma `max(lot_stock, page_data)`) |
| **Descuento de Stock por Venta** | `db.py` | `discount_stock_for_sale()` | `products`, `page_data(inventory_items)` | `lot_stock` (vía `consume_lots_for_sale`), `sale_lot_movements`, `page_data(inventory_items)` | Disminuye (-) | Desacoplada: `consume_lots` tiene commit propio; `set_page_data` no es transaccional | **Crítico** (Pérdida de consistencia por fallos intermedios o ventas simultáneas) |
| **Consumo de Lotes por Venta** | `db.py` | `consume_lots_for_sale()` | `lot_stock` | `lot_stock` (`available_qty`), `sale_lot_movements` | Disminuye (-) | SQL con commit propio | **Medio** (Usa `GREATEST(0, available_qty - qty)` silenciando sobregiro) |
| **Conversión Cotización → Venta** | `routes/ventas.py` | `_convert_quotation_to_sale()` | `sales`, `products`, `lot_stock`, `page_data` | `sales`, `sale_status_history`, `lot_stock`, `page_data` | Disminuye (-) | Múltiples commits separados + llamada a `discount_stock_for_sale()` | **Crítico** (No es atómica) |
| **Venta Directa (POS / Nueva Venta)** | `routes/ventas.py` | `ventas()` (POST) | Ninguna | `sales_entries` | Ninguna | Commit aislado en `sales_entries` | **Crítico** (Las ventas directas registradas en `sales_entries` históricamente NO descontaban inventario) |
| **Finalización de OT (Producción)** | `routes/produccion.py` | `finalizar_ot()` | `production_orders`, `production_order_items`, `production_order_additional_items`, `page_data` | `production_orders`, `inventory_entries`, `page_data(inventory_items)` | Insumos: (-)<br>PT: (+) | Mixta: SQL actualiza OT e inserta `inventory_entries`, pero stock se muta en JSON `page_data` | **Crítico** (No descuenta de `lot_stock` ni crea lotes para el producto terminado; depende 100% de `page_data`) |
| **Aprobación de OT** | `routes/produccion.py` | `aprobar_ot()` | `production_orders`, `production_order_items`, `page_data` | `production_orders` | Ninguna | Valida stock de insumos en `page_data`, no bloquea ni reserva | **Medio** (Puede autorizar OTs concurrentes para el mismo stock disponible) |
| **Adición de Insumos Extra en OT** | `routes/produccion.py` | `adicionar_insumo()` | `products` | `production_order_additional_items` | Ninguna (difiere descuento a la finalización) | SQL transaccional | **Bajo** |
| **Actualización Stock Mínimo** | `routes/inventario.py` | `update_product_min_stock()` | `page_data(inventory_items)` | `page_data(inventory_items)` | Modifica parámetro | No transaccional (reescribe todo el JSON de inventario) | **Alto** (Riesgo de revertir stock físico si hubo escrituras intermedias) |
| **Dashboard (Métricas de Stock)** | `db.py` | `get_sales_metrics()` | `page_data(inventory_items)` | Ninguna | N/A | Lectura de JSON | **Bajo** (Muestra stock de `page_data` ignorando `lot_stock`) |
| **Dashboard (Alertas de Stock)** | `db.py` | `get_system_notifications()` | `page_data(inventory_items)` | Ninguna | N/A | Lectura de JSON | **Bajo** |
| **Reporte de Lotes** | `routes/reportes.py` | `reportes_inventario_lotes()` | `lot_stock`, `products` | Ninguna | N/A | Lectura SQL | **Bajo** (Solo refleja los 2 lotes existentes, ignorando los otros 9 productos con stock en `page_data`) |
| **Cálculo de Costo VPP** | `db.py` | `get_product_calculated_cost()` | `inventory_entry_items`, `inventory_entries` | Ninguna | N/A | Lectura SQL pura relacional | **Bajo** (Excelente implementación basada en entradas reales) |
| **Creación Rápida de Producto** | `routes/produccion.py` | `crear_producto_rapido()` | `products` | `products`, `page_data(inventory_items)` | Inicializa en 0 | Inserta producto en DB y hace append en JSON `inventory_items` | **Medio** (Sobreescritura de JSON) |
| **Creación Estándar de Producto** | `routes/inventario.py` | `productos()` (POST) | `products` | `products` | Ninguna | SQL puro, NO crea entrada en `page_data` | **Medio** (Desalineación entre catálogo `products` y lista `inventory_items`) |

---

## 3. Principales Brechas y Factores de Inconsistencia Detectados

1. **Bifurcación de Canales de Entrada:**
   - Si una compra ingresa con número de lote (`iei.lot_number != ''`), se registra en `lot_stock` y en `page_data`.
   - Si ingresa sin número de lote, se ignora `lot_stock` y solo se registra en `page_data`.
2. **Desconexión Total en Producción:**
   - La finalización de Órdenes de Trabajo (`finalizar_ot`) descuenta insumos e incrementa producto terminado exclusivamente en el JSON `page_data`. Jamás ha interactuado con `lot_stock`.
3. **Condición de Carrera en `page_data`:**
   - Cada actualización de stock requiere: `SELECT json` -> deserializar en Python -> modificar diccionario -> serializar -> `UPDATE page_data SET json`.
   - Dos ventas o recepciones concurrentes provocan que la última sobreescriba y destruya los cambios de la primera.
4. **Desconexión en Creación de Productos:**
   - El catálogo maestro tiene 111 productos activos en `products`, pero `page_data.inventory_items` solo tiene 11 productos registrados. Los restantes 100 productos no existen en la vista principal de bodega.
