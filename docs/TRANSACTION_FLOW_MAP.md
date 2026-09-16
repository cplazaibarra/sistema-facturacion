# Mapa de Fronteras Transaccionales y Concurrencia (ACID)
**Sistema de Facturación / Bodega Miel (ERP Single-Tenant)**  
**Fase 3 — Transacciones, Atomicidad y Concurrencia**

---

## 1. Introducción y Principio Rector
El objetivo fundamental de la Fase 3 es transformar cada operación crítica del negocio en una **unidad de trabajo atómica (ACID)** en PostgreSQL:

$$\text{Operación de Negocio} \equiv \text{Una Única Transacción PostgreSQL}$$

Una operación debe **completarse en su totalidad** o **revertirse completamente (`ROLLBACK`)**. Bajo ninguna circunstancia se admitirán persistencias intermedias, commits independientes dentro de funciones auxiliares ni lecturas no protegidas frente a concurrencia.

---

## 2. Matriz de Fronteras Transaccionales de los Flujos Críticos

A continuación se analizan en detalle los 6 flujos neurálgicos del ERP:

| Flujo | Función Principal / Archivo | Funciones Llamadas | Conexiones / Commits Anteriores | Tablas Afectadas | Riesgos de Concurrencia | Estrategia de Bloqueo (Locks) | Idempotencia Requerida |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **A. Recepción de Compra** | `register_inventory_entry()` (`db.py`) | `get_product_calculated_cost()`, `record_inventory_movement()`, `set_page_data()` | **2 conexiones separadas** (SQL principal con commit propio + bloque `try` posterior modificando JSON `page_data` sin transacción) | `purchase_orders`, `purchase_order_items`, `inventory_entries`, `inventory_entry_items`, `lot_stock`, `inventory_movements`, `page_data` | Recepción duplicada por doble click; sobre-recepción por recepciones concurrentes de la misma OC; fallo en `page_data` dejando Kardex persistido | `SELECT FOR UPDATE` en `purchase_orders` y `purchase_order_items` (ordenados por `product_id ASC`) | Comprobar que `quantity_received + qty <= quantity_ordered`; clave única en recepción |
| **B. Venta Directa (POS)** | `insert_sale_direct()` (`db.py` / `routes/ventas.py`) | `validate_stock_for_sale()`, `discount_stock_for_sale()`, `record_inventory_movement()`, `upsert_sale_payment()` | **Múltiples conexiones y commits:** `insert_sale` commit -> `discount_stock` commit -> `sale_payments` commit -> `set_page_data` | `sales`, `sale_payments`, `sales_status_history`, `lot_stock`, `sale_lot_movements`, `inventory_movements`, `page_data` | Stock negativo por ventas concurrentes; venta creada sin rebajar inventario si falla descuento; duplicación de folios | `SELECT FOR UPDATE` en `products` y `lot_stock` ordenados por `product_id ASC`, `id ASC` | Folio atómico vía `SEQUENCE`; reversión total si stock insuficiente |
| **C. Conversión Cotización → Venta** | `_convert_quotation_to_sale()` (`routes/ventas.py`) | `get_sale()`, `validate_stock_for_sale()`, `insert_sale()`, `discount_stock_for_sale()`, `record_inventory_movement()` | **4 conexiones con commits desacoplados:** `SELECT MAX(id)` -> `insert_sale()` -> `UPDATE sales` -> `discount_stock_for_sale()` | `sales`, `sale_payments`, `sales_status_history`, `lot_stock`, `sale_lot_movements`, `inventory_movements`, `page_data` | **Crítico:** Doble conversión por clics simultáneos crea 2 ventas distintas, doble cobro en CxC y doble descuento en Kardex | `SELECT FOR UPDATE` sobre la cotización en `sales WHERE id = %s`; validar estado == 'Cotización' | Si ya fue convertida, retornar folio existente sin duplicar ni descontar |
| **D. Finalización de OT** | `finalizar_ot()` (`routes/produccion.py`) | `set_page_data()`, `record_inventory_movement()` | **Mixta:** SQL principal commit, pero `page_data` serializado antes en memoria sin lock | `production_orders`, `production_order_items`, `production_order_additional_items`, `inventory_entries`, `inventory_entry_items`, `inventory_movements`, `page_data` | Doble finalización de la misma OT generando doble producto terminado y doble consumo de insumos | `SELECT FOR UPDATE` sobre `production_orders WHERE id = %s`; validar status == 'Aprobada' | Rechazar inmediatamente si status != 'Aprobada' (`ALREADY_FINALIZED`) |
| **E. Pagos Proveedores (CxP)** | `register_purchase_payment()` (`db.py`) | `get_purchase_invoice()` | Conexión única con commit simple pero sin bloqueo sobre el saldo de la factura | `purchase_invoices`, `bank_accounts` | Doble pago simultáneo; pagar monto superior al saldo pendiente; pago a cuenta inexistente | `SELECT FOR UPDATE` sobre `purchase_invoices WHERE id = %s` | Comprobar status != 'Pagada'; pago no puede exceder saldo adeudado |
| **F. Pagos Clientes (CxC)** | `upsert_sale_payment()` (`db.py` / `routes/ventas.py`) | `insert_sale_payment_item()` | Actualización aislada sin lock previo sobre la venta ni verificación de sobrepago | `sales`, `sale_payments`, `sale_payment_items` | Pagos duplicados por reenvío HTTP; incongruencia de saldo total pagado | `SELECT FOR UPDATE` sobre `sale_payments WHERE sale_id = %s` | Idempotencia por id de ítem de pago / validación de saldo |

---

## 3. Principio de No Invocación de Commits Internos
Todos los helpers del sistema (`record_inventory_movement`, `consume_fifo_lots`, `discount_stock_for_sale`, etc.) deben admitir el parámetro opcional `conn=None`.  
Si `conn` es provisto, **NO ejecutarán `conn.commit()` ni `conn.rollback()`**. El control transaccional recae exclusivamente en la función orquestadora principal.
