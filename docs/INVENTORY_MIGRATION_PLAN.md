# Plan de Migración de Inventario a Fuente de Verdad Relacional
**Sistema de Facturación / Bodega Miel (ERP Single-Tenant)**  
**Fase 2 — Consistencia y Fuente de Verdad de Inventario**

---

## 1. Estrategia de Migración por Etapas

Para garantizar cero interrupciones y eliminar cualquier riesgo de pérdida de datos o inconsistencias contables, la migración se estructura en 7 etapas progresivas:

```text
[Etapa A: Reconocimiento] --> [Etapa B: Modelo Destino] --> [Etapa C: Migración Base]
                                                                     |
[Etapa G: Retiro Legacy] <-- [Etapa F: Escrituras] <-- [Etapa E: Lecturas] <-- [Etapa D: Dual-Read]
  (Fases posteriores)
```

---

### ETAPA A — Reconocimiento y Auditoría (Completada en Fase 2)
- Mapeo completo de operaciones de stock (`docs/INVENTORY_FLOW_MAP.md`).
- Herramienta read-only de reconciliación creada (`tools/reconcile_inventory.py`).
- Reporte detallado de discrepancias (`docs/INVENTORY_RECONCILIATION_REPORT.md`).
- Clasificación de causas: saldos iniciales SQLite, recepciones sin lote y consumos de OT en JSON.

### ETAPA B — Creación del Modelo Relacional Destino (Fase 2)
- Creación de la tabla `inventory_movements` con índices en PostgreSQL.
- Implementación de funciones core en backend:
  - `record_inventory_movement()`: Inserción atómica y validada de movimientos.
  - `get_relational_stock(product_id)`: Cálculo en tiempo real de stock relacional sumando movimientos.
  - `get_relational_stock_by_sku(sku)`: Consulta directa por código SKU.

### ETAPA C — Población de Datos Base y Transacciones Históricas (Fase 2)
- Migración controlada de saldos:
  1. Insertar movimientos `PURCHASE_RECEIPT` a partir de `inventory_entry_items` existentes.
  2. Insertar movimientos `PRODUCTION_OUTPUT` a partir de `production_orders` finalizadas.
  3. Insertar movimientos `PRODUCTION_INPUT` a partir de los insumos de OTs finalizadas.
  4. Para los saldos remanentes de la semilla legacy (`PRD001`, `PRD002`, `PRD003`, `PRD004`, `INS001`, `INS002`, `INS003`), registrar movimientos `INITIAL_BALANCE` con nota explícita de auditoría.
- Validación de que ningún stock resulte negativo.

### ETAPA D — Validación con Dual-Read (Fase 2)
- Implementación del helper `get_stock_with_dual_read(product_id_or_sku)`:
  - Lee el stock de `page_data` (`legacy_stock`).
  - Lee el stock relacional de `inventory_movements` (`relational_stock`).
  - Si difieren, emite advertencia en el log de auditoría (`erp.security` / `erp.inventory`) registrando:
    `SKU | legacy_stock | relational_stock | delta`.
  - Retorna el valor seguro para garantizar continuidad operativa sin romper vistas existentes.

### ETAPA E — Cambio Gradual de Lecturas (Fase 3/4)
- Redirección progresiva de pantallas de consulta hacia la fuente relacional:
  - `/inventario`
  - `/productos`
  - Dashboard (tarjetas y alertas de stock bajo)
  - Validación de stock en cotizaciones y ventas

### ETAPA F — Cambio Gradual de Escrituras (Fase 3/4)
- Consolidación de escrituras relacionales con transacciones ACID y `SELECT ... FOR UPDATE` (Fase 3).
- Eliminación de la escritura en `page_data` en compras, ventas y producción.

### ETAPA G — Retiro Definitivo de `page_data.inventory_items` (Fase 5/6)
> [!IMPORTANT]
> **LA ETAPA G NO SE EJECUTA EN LA FASE 2.**  
> El JSON `page_data.inventory_items` se preserva al 100% como mecanismo de compatibilidad durante la transición.

---

## 2. Estrategia de Rollback y Mitigación de Riesgos

1. **Aislamiento por Tabla Nueva:**
   - La tabla `inventory_movements` es aditiva y no reemplaza ninguna tabla previa ni altera columnas existentes.
   - En caso de anomalía, la aplicación continúa leyendo de `page_data` y `lot_stock` sin degradación.
2. **Preservación de JSON Legacy:**
   - Durante toda la Fase 2, todas las escrituras en `page_data.inventory_items` continúan ejecutándose con normalidad (dual-write donde aplique).
3. **Idempotencia de Scripts de Migración:**
   - Los scripts de población utilizan claves de referencia (`reference_type`, `reference_id`, `movement_type`) para evitar duplicación de movimientos si se ejecutan múltiples veces.
