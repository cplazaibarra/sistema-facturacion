# Diseño del Modelo Objetivo de Inventario (Fuente de Verdad Relacional)
**Sistema de Facturación / Bodega Miel (ERP Single-Tenant)**  
**Fase 2 — Consistencia y Fuente de Verdad de Inventario**

---

## 1. Definición de la Fuente de Verdad

### 1.1 Veredicto sobre `lot_stock`
Tras la auditoría y reconciliación de datos reales en `docs/INVENTORY_RECONCILIATION_REPORT.md`, se concluye técnicamente que:
- `lot_stock` **NO puede ser la única fuente de verdad** del ERP.
- **Razones Técnicas:**
  1. No todos los productos requieren lote (`products.requires_lot = FALSE`, como envases, etiquetas, tapas, servicios y ciertos productos procesados).
  2. Los saldos iniciales y los consumos de producción no fueron modelados históricamente como lotes.
  3. No modela salidas directas de productos no loteados ni ajustes de mermas/inventario físico.

### 1.2 La Solución de Arquitectura: Libro Diario de Movimientos (`inventory_movements`)
La fuente de verdad definitiva del ERP será un **Kardex / Ledger Relacional Centralizado**: la tabla `inventory_movements` en PostgreSQL.
- **Principio Fundamental:** El stock físico NO es un valor arbitrario editable.
- **Fórmula:**
  $$\text{Stock Disponible Actual}(p) = \sum \text{quantity}(\text{movimientos de } p)$$
- `lot_stock` se mantendrá como una **proyección de lotes activos** para trazabilidad FIFO y control sanitario (miel, polen, propóleo), sincronizada de forma transaccional con `inventory_movements`.

---

## 2. Estructura de la Tabla Objetivo `inventory_movements`

```sql
CREATE TABLE IF NOT EXISTS inventory_movements (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    movement_type TEXT NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    unit_cost DOUBLE PRECISION DEFAULT 0.0,
    lot_number TEXT,
    warehouse TEXT DEFAULT 'Almacén Principal',
    reference_type TEXT,
    reference_id INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL,
    created_by TEXT DEFAULT 'Sistema'
);

CREATE INDEX IF NOT EXISTS idx_inv_mov_product_id ON inventory_movements(product_id);
CREATE INDEX IF NOT EXISTS idx_inv_mov_lot_number ON inventory_movements(lot_number);
CREATE INDEX IF NOT EXISTS idx_inv_mov_reference ON inventory_movements(reference_type, reference_id);
CREATE INDEX IF NOT EXISTS idx_inv_mov_created_at ON inventory_movements(created_at);
```

### 2.1 Tipos de Movimiento Estandarizados (`movement_type`)
- `PURCHASE_RECEIPT` (+): Ingreso por recepción de orden de compra o factura.
- `SALE` (-): Despacho o consumo por venta confirmada.
- `PRODUCTION_INPUT` (-): Consumo de materia prima o insumo en Orden de Trabajo.
- `PRODUCTION_OUTPUT` (+): Alta de producto terminado por Orden de Trabajo finalizada.
- `ADJUSTMENT_IN` (+) / `ADJUSTMENT_OUT` (-): Ajuste auditado de inventario físico.
- `RETURN` (+): Devolución autorizada de cliente.
- `INITIAL_BALANCE` (+): Carga inicial de migración o inventario base.

---

## 3. Modelo Operativo de Productos con y sin Lote

### 3.1 Productos Con Lote (`requires_lot = TRUE`)
1. **Ingreso (Compra o PT):**
   - Se inserta movimiento `PURCHASE_RECEIPT` o `PRODUCTION_OUTPUT` en `inventory_movements` con `lot_number`.
   - Se crea o actualiza el registro en `lot_stock` (`available_qty += qty`).
2. **Egreso (Venta o Insumo OT):**
   - El sistema aplica FIFO seleccionando el lote disponible más antiguo (`ORDER BY entry_date ASC, id ASC`).
   - Se inserta movimiento `SALE` o `PRODUCTION_INPUT` en `inventory_movements` vinculando el `lot_number`.
   - Se decrementa `lot_stock.available_qty`.
   - Se registra en `sale_lot_movements` para auditoría comercial.

### 3.2 Productos Sin Lote (`requires_lot = FALSE`)
1. **Ingreso:**
   - Se inserta movimiento en `inventory_movements` con `lot_number = NULL`.
   - NO se altera `lot_stock`.
2. **Egreso:**
   - Se valida que `SUM(quantity) >= qty_solicitada`.
   - Se inserta movimiento negativo en `inventory_movements`.
   - Trazabilidad directa a través de `reference_type` y `reference_id`.

---

## 4. Flujo de Producción con la Fuente Relacional

Al finalizar una Orden de Trabajo (`finalizar_ot`):
```text
BEGIN TRANSACTION;
  1. Para cada insumo planificado y adicional:
     - Validar disponibilidad relacional.
     - Si el insumo tiene lote -> consumir de lot_stock (FIFO).
     - INSERT INTO inventory_movements (type='PRODUCTION_INPUT', qty=-qty, ref='production_order', ref_id=ot_id).
  2. Para el producto final:
     - Si el producto final requiere lote -> generar/asignar número de lote y registrar en lot_stock.
     - INSERT INTO inventory_movements (type='PRODUCTION_OUTPUT', qty=+ot_qty, unit_cost=costo_real, ref='production_order', ref_id=ot_id).
  3. UPDATE production_orders SET status='Finalizada', completed_at=NOW();
  4. (Compatibilidad Fase 2) Actualizar página JSON page_data("inventory_items").
COMMIT;
```

---

## 5. Regla de Costeo y VPP (Valor Promedio Ponderado)

La función `get_product_calculated_cost(product_id)` queda preservada intacta:
1. **Ventana de 30 días:** Promedio ponderado de compras recientes en `inventory_entry_items`.
2. **Fallback:** Precio unitario de la última compra registrada en `inventory_entry_items`.
3. **Fallback Catálogo:** `products.cost` si no existen compras.
El modelo relacional no altera esta fórmula, garantizando continuidad financiera idéntica.

---

## 6. Los 10 Invariantes de Inventario (INV-001 a INV-010)

1. **INV-001 (No Negatividad):** El stock disponible relacional de un producto nunca puede ser inferior a 0.
2. **INV-002 (Salidas con Origen):** Toda salida (`quantity < 0`) debe tener un documento origen identificable (`reference_type`, `reference_id`).
3. **INV-003 (Entradas con Origen):** Toda entrada (`quantity > 0`) debe tener documento o justificación de origen trazable.
4. **INV-004 (Consistencia de Lotes):** Para productos con `requires_lot = TRUE`, $\sum \text{available\_qty en lot\_stock} == \text{stock relacional disponible}$.
5. **INV-005 (Venta No Duplicada):** Una venta no puede descontar existencias más de una vez para el mismo ítem.
6. **INV-006 (Recepción No Duplicada):** Una recepción de compra no puede ingresar existencias dos veces.
7. **INV-007 (OT Idempotente):** La finalización de una Orden de Trabajo no puede ejecutarse dos veces sobre la misma OT.
8. **INV-008 (Magnitud Distinta de Cero):** La cantidad de un movimiento de inventario no puede ser exactamente 0.0.
9. **INV-009 (Inmutabilidad Histórica):** Los movimientos históricos de inventario son inmutables; las correcciones se realizan exclusivamente mediante contra-asientos o movimientos de ajuste.
10. **INV-010 (Ajustes Justificados):** Todo ajuste manual debe contar obligatoriamente con motivo documentado y usuario responsable.
