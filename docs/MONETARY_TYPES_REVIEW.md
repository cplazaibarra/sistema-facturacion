# REVISIÓN DE TIPOS MONETARIOS Y DECIMALES (FASE 4)

**Fecha:** 2026-09-15  
**Contexto:** Auditoría técnica de precisión numérica para precios, cantidades, montos y costos en PostgreSQL.

---

## 1. Estado Actual del Esquema

En el código heredado proveniente de SQLite (`REAL`), las columnas numéricas con decimales fueron migradas inicialmente como `DOUBLE PRECISION`.

Las columnas afectadas incluyen:
- **Precios y Totales de Venta:** `sales.total_amount`, `sales_entries.unit_price`, `sales_entries.total_price`, `sale_payments.invoice_amount`, `sale_payments.payment_amount`, `sale_payment_items.payment_amount`.
- **Precios y Totales de Compra:** `purchase_orders.total_amount`, `purchase_order_items.unit_price`, `purchase_order_items.total_price`, `purchase_invoices.invoice_amount`, `purchase_invoices.payment_amount`.
- **Costos y Kardex:** `products.cost`, `inventory_movements.unit_cost`, `inventory_movements.quantity`, `production_orders.unit_cost`, `production_order_items.unit_cost`, `production_order_additional_items.unit_cost`.
- **Pesos y Dimensiones:** `products.weight_kg`, `products.width_cm`, `products.height_cm`, `products.depth_cm`, `products.associated_kg`.
- **Cantidades con Decimales:** `production_order_items.quantity_required`, `production_order_additional_items.quantity`, `product_recipe_items.quantity_required`.

---

## 2. Análisis de Riesgos y Evaluación Técnica

1. **Aritmética de Punto Flotante (`DOUBLE PRECISION`):**
   - *Ventajas:* Compatibilidad directa con tipos nativos `float` en Python y serialización JSON sin conversor especial.
   - *Riesgos:* Errores de redondeo binario en operaciones de acumulación contable centavo a centavo (p. ej. `0.1 + 0.2 != 0.3`).
2. **Tipo Decimal Exacto (`NUMERIC(12, 2)` o `NUMERIC(14, 4)`):**
   - *Ventajas:* Precisión absoluta requerida por estándares contables e impositivos.
   - *Impacto en Código:* `psycopg2` devuelve objetos `decimal.Decimal` de Python para columnas `NUMERIC`. Si el código del ERP realiza llamadas como `json.dumps()` sin un serializador personalizado o mezcla `Decimal` con `float` en cálculos aritméticos directos, Python lanza excepciones de tipo (`TypeError: unsupported operand type(s) for +: 'decimal.Decimal' and 'float'`).

---

## 3. Dictamen y Recomendación para el Roadmap

- **Fase 4:** Mantener `DOUBLE PRECISION` en las definiciones del esquema base para no romper las operaciones actuales ni causar regresiones de tipos en las 60 pruebas funcionales e integradas de la aplicación.
- **Fase 5/6 (Modularización y Refactorización):** Programar una migración tipada a `NUMERIC(12, 2)` para montos en moneda local (CLP no usa decimales legalmente, pero se calculan unitarios netos con decimales) y `NUMERIC(14, 4)` para costos unitarios, asegurando previamente que todos los modelos y serializadores de API admitan `Decimal`.
