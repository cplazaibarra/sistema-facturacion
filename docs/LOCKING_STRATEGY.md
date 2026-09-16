# Estrategia Global de Bloqueos y Prevención de Deadlocks
**Sistema de Facturación / Bodega Miel (ERP Single-Tenant)**  
**Fase 3 — Transacciones, Atomicidad y Concurrencia**

---

## 1. Regla Canónica de Ordenamiento de Locks
Para eliminar formalmente el riesgo de **deadlocks** entre transacciones concurrentes, todas las operaciones del ERP deben solicitar bloqueos a nivel de fila (`SELECT ... FOR UPDATE`) siguiendo estrictamente la misma jerarquía de recursos:

```text
[1. Documento Cabecera] --> [2. Productos (product_id ASC)] --> [3. Lotes (lot_id ASC)] --> [4. Pagos / Cuentas]
```

### 1.1 Jerarquía Estricta:
1. **Documento Principal / Solicitud:**
   - Para Ventas / Cotizaciones: `sales` (por `id`).
   - Para Compras / Recepciones: `purchase_orders` (por `id`).
   - Para Producción: `production_orders` (por `id`).
   - Para Facturas de Proveedores: `purchase_invoices` (por `id`).
2. **Productos Afectados:**
   - Si una operación afecta múltiples productos, **SIEMPRE** deben bloquearse ordenados por `product_id ASC`:
     ```sql
     SELECT id, sku FROM products WHERE id = ANY(%s) ORDER BY id ASC FOR UPDATE;
     ```
3. **Lotes de Stock (`lot_stock`):**
   - Siempre ordenados por `id ASC` (o `entry_date ASC, id ASC` para selección FIFO):
     ```sql
     SELECT id, lot_number, available_qty FROM lot_stock 
     WHERE product_id = %s AND available_qty > 0 
     ORDER BY entry_date ASC, id ASC FOR UPDATE;
     ```
4. **Registros Financieros / Pagos:**
   - `sale_payments`, `bank_accounts`.

---

## 2. Nivel de Aislamiento PostgreSQL
* **Nivel Adoptado:** `READ COMMITTED`.
* **Justificación Técnica:**
  En conjunto con bloqueos explícitos de fila (`FOR UPDATE`), `READ COMMITTED` proporciona:
  - Consistencia y aislamiento absoluto para transacciones que mutan datos compartidos.
  - Cero overhead de serialización innecesaria (`SERIALIZATION FAILURE`).
  - Rendimiento óptimo en un entorno ERP monolítico SSR.

---

## 3. Manejo y Retry de Deadlocks
Si a pesar del ordenamiento canónico PostgreSQL arroja un error de concurrencia (`deadlock_detected` o `serialization_failure`):
* Se aplica decorador / helper de retry con backoff exponencial breve (ej. 50ms, 100ms, 200ms) hasta un máximo de **3 intentos**.
* Los errores funcionales (Stock insuficiente, Validación fallida, Permiso denegado) **NUNCA** se reintentan.
