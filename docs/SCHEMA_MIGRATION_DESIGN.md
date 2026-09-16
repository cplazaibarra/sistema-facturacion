# DISEÑO DEL SISTEMA DE MIGRACIONES (FASE 4)

**Objetivo:** Establecer un mecanismo de versionado de base de datos reproducible, transaccional, idempotente y mantenible, sin introducir frameworks complejos u ORMs incompatibles con la arquitectura monolítica liviana de Flask.

---

## 1. Arquitectura del Runner de Migraciones (`tools/migrate.py`)

El sistema utiliza un ejecutor SQL puro escrito en Python utilizando `psycopg2`.

### Principios de Diseño:
1. **Transaccionalidad Atómica:** Toda migración (sea `UP` o `DOWN`) se ejecuta dentro de una transacción (`BEGIN ... COMMIT`). Si ocurre cualquier excepción SQL, se ejecuta `ROLLBACK` y el estado de la base de datos permanece intacto.
2. **Registro de Versiones (`schema_migrations`):**
   ```sql
   CREATE TABLE IF NOT EXISTS schema_migrations (
       version VARCHAR(32) PRIMARY KEY,
       name VARCHAR(255) NOT NULL,
       applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
   );
   ```
3. **Archivos de Migración Pareados:**
   Ubicados en `migrations/`, nombrados con prefijo numérico de 6 dígitos:
   - `000001_initial_core.up.sql` / `000001_initial_core.down.sql`
   - `000002_commercial_and_purchases.up.sql` / `000002_commercial_and_purchases.down.sql`
   - `000003_production_and_recipes.up.sql` / `000003_production_and_recipes.down.sql`
   - `000004_inventory_and_traceability.up.sql` / `000004_inventory_and_traceability.down.sql`
   - `000005_constraints_and_indexes.up.sql` / `000005_constraints_and_indexes.down.sql`
4. **Comandos Soportados:**
   - `python tools/migrate.py status`: Muestra la lista de migraciones disponibles y cuáles han sido aplicadas.
   - `python tools/migrate.py up`: Aplica todas las migraciones pendientes en orden correlativo.
   - `python tools/migrate.py down`: Revierte la última migración aplicada ejecutando su script `.down.sql`.
   - `python tools/migrate.py init`: Crea la tabla `schema_migrations`.

---

## 2. Estructura y Modularidad de las Migraciones

### Migración 000001 — `initial_core`
- `roles` (Roles del sistema y permisos)
- `users` (Usuarios, contraseñas hasheadas y relación con roles)
- `page_data` (Almacén clave-valor legacy para compatibilidad)
- `bank_accounts` (Cuentas bancarias de la empresa)
- `client_categories` (Categorías comerciales de clientes)
- `clients` (Maestro de clientes)
- `product_margins` (Márgenes comerciales por SKU y categoría)

### Migración 000002 — `commercial_and_purchases`
- `suppliers` (Maestro de proveedores)
- `supplier_contacts` (Contactos de proveedores)
- `products` (Catálogo maestro de productos y materias primas)
- `product_suppliers` (Asociación proveedor-producto)
- `sales` (Ventas y cotizaciones)
- `sales_entries` (Registros desnormalizados de venta históricos)
- `sale_payments` (Control de pago y facturación de venta)
- `sale_payment_items` (Abonos parciales de venta con cuenta bancaria)
- `sales_status_history` (Historial de estados comerciales)
- `sales_payment_history` (Historial de auditoría de pagos)
- `purchase_orders` (Órdenes de compra)
- `purchase_order_items` (Detalle de órdenes de compra)
- `purchase_invoices` (Facturas de compra con FKs a proveedores y cuentas)

### Migración 000003 — `production_and_recipes`
- `product_recipes` (Recetas de producción asociadas a producto final)
- `product_recipe_items` (Insumos de recetas)
- `production_orders` (Órdenes de trabajo / producción)
- `production_order_items` (Insumos requeridos en órdenes de trabajo)
- `production_order_additional_items` (Insumos adicionales en producción)

### Migración 000004 — `inventory_and_traceability`
- `inventory_entries` (Recepciones de bodega por compra o producción)
- `inventory_entry_items` (Detalle de recepción con asignación de lotes)
- `lot_stock` (Proyección de saldo disponible por lote)
- `sale_lot_movements` (Trazabilidad de lotes consumidos por venta)
- `inventory_movements` (Kardex transaccional oficial - Fuente de Verdad)
- Secuencias atómicas: `purchase_order_number_seq`, `sales_number_seq`, `production_order_number_seq`.

### Migración 000005 — `constraints_and_indexes`
- Constraints `CHECK`:
  - `lot_stock(available_qty >= 0)`
  - `lot_stock(initial_qty >= 0)`
  - `inventory_movements(quantity <> 0)`
  - `purchase_order_items(quantity_ordered > 0)`
  - `inventory_entry_items(quantity > 0)`
  - `sale_lot_movements(quantity > 0)`
  - `product_recipe_items(quantity_required >= 0)`
- Clave foránea faltante:
  - `purchase_invoices(supplier_id) REFERENCES suppliers(id)`
- Índices de rendimiento y cobertura para todas las claves foráneas en tablas de alto tráfico (`sales`, `purchase_orders`, `inventory_entries`, etc.).

---

## 3. Integración con `init_db()`
La función `init_db()` en `db.py` delega completamente la creación y actualización del esquema al runner de migraciones:
1. Conecta a la base de datos configurada.
2. Ejecuta `tools.migrate.apply_all_migrations(conn)`.
3. Ejecuta la siembra mínima obligatoria de catálogos (`tools.seed_required.seed_required_catalogs(conn)`).
4. El código legacy lleno de `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` queda reemplazado por la ejecución limpia de migraciones versionadas.
