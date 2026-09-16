# Modelo Relacional de Genealogía de Lotes (Fase 5B)

**Fecha:** 15 de Septiembre de 2026  
**Sistema:** ERP Facturación & Gestión de Negocio  

---

## 1. Diagrama Entidad-Relación

```mermaid
erDiagram
    PRODUCTS ||--o{ LOTS : "identifica"
    SUPPLIERS ||--o{ LOTS : "provee"
    PURCHASE_ORDERS ||--o{ LOTS : "adquiere"
    INVENTORY_ENTRIES ||--o{ LOTS : "recibe"
    PRODUCTION_ORDERS ||--o{ PRODUCTION_LOT_CONSUMPTIONS : "consume"
    LOTS ||--o{ PRODUCTION_LOT_CONSUMPTIONS : "es consumido"
    PRODUCTION_ORDERS ||--o{ PRODUCTION_LOT_OUTPUTS : "produce"
    LOTS ||--o{ PRODUCTION_LOT_OUTPUTS : "es producido"
    LOTS ||--o{ LOT_STOCK : "saldo disponible"
    LOTS ||--o{ SALE_LOT_MOVEMENTS : "despachado en"
    SALES ||--o{ SALE_LOT_MOVEMENTS : "vende"

    LOTS {
        int id PK
        int product_id FK
        text lot_number
        text lot_type
        text origin_type
        int origin_id
        int supplier_id FK
        int purchase_order_id FK
        int inventory_entry_id FK
        int production_order_id FK
        double initial_quantity
        text created_at
        text expiry_date
        text status
        text warehouse
        text notes
    }

    PRODUCTION_LOT_CONSUMPTIONS {
        int id PK
        int production_order_id FK
        int input_product_id FK
        int input_lot_id FK
        double quantity_consumed
        text created_at
    }

    PRODUCTION_LOT_OUTPUTS {
        int id PK
        int production_order_id FK
        int output_product_id FK
        int output_lot_id FK
        double quantity_produced
        text created_at
    }

    SALE_LOT_MOVEMENTS {
        int id PK
        int sale_id FK
        int product_id FK
        int lot_id FK
        text lot_number
        int quantity
        text moved_at
    }
```

---

## 2. Definición de Atributos Clave

1. **`lots`:**
   - `id`: Clave primaria sintética inmutable. Nunca cambia aunque el número comercial de lote se repita entre proveedores o temporadas.
   - `product_id`: Referencia obligatoria a `products(id) ON DELETE RESTRICT`.
   - `lot_type`: `'RAW_MATERIAL'`, `'SEMI_FINISHED'`, `'FINISHED_PRODUCT'`, `'SUPPLY'`, `'OTHER'`.
   - `origin_type`: `'PURCHASE'`, `'PRODUCTION'`, `'INITIAL_MIGRATION'`, `'ADJUSTMENT'`.
   - `status`: `'ACTIVE'`, `'DEPLETED'`, `'QUARANTINE'`, `'RECALLED'`, `'EXPIRED'`.
   - `initial_quantity`: Cantidad original ingresada al lote.
2. **`production_lot_consumptions`:**
   - Vincula cada orden de trabajo con el lote exacto de insumo consumido.
   - Inmutable: Registrado dentro de la misma transacción en que se descuenta el stock.
3. **`production_lot_outputs`:**
   - Vincula cada orden de trabajo con el lote de producto intermedio o terminado generado.
   - Permite la trazabilidad multinivel (`Materia Prima -> Subproducto -> Producto Final`).

---

## 3. Principio de Inmutabilidad

- Todas las llaves foráneas (`FK`) hacia `lots`, `products`, `suppliers`, `purchase_orders`, `production_orders` y `sales` están configuradas con `ON DELETE RESTRICT`.
- Está prohibido el borrado físico (`DELETE CASCADE`) de registros históricos de lotes o movimientos.
- Un lote agotado (`available_qty = 0`) pasa a estado inactivo pero conserva el 100% de su historia genealógica.
