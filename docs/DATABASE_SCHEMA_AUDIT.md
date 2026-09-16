# AUDITORÍA TÉCNICA DE BASE DE DATOS Y ESQUEMA (FASE 4)

**Fecha:** 2026-09-15  
**Motor:** PostgreSQL 16 (x86_64-alpine)  
**Base de Datos:** `facturacion`  
**Usuario:** `facturador`  
**Estado previo:** Suite de pruebas en 60 PASSED, 0 FAILED (Commit `d537ca5`)

---

## 1. Resumen Ejecutivo del Esquema Actual

La base de datos operativa contiene actualmente **30 tablas**, **30 secuencias** y **46 índices**.  
A través de la inspección directa de `information_schema` y `pg_catalog`, se identificaron tanto las tablas centrales consolidadas como las discrepancias estructurales generadas por la evolución histórica mediante llamadas imperativas `ALTER TABLE` en `init_db()`.

### Tablas Relevadas (30 en total):
1. `bank_accounts` (Cuentas bancarias de la empresa)
2. `client_categories` (Clasificación comercial por email de cliente)
3. `clients` (Directorio maestro de clientes y RUTs)
4. `inventory_entries` (Cabecera de recepciones/ingresos a bodega)
5. `inventory_entry_items` (Detalle de recepciones con lotes)
6. `inventory_movements` (Kardex transaccional oficial - Fuente de Verdad)
7. `lot_stock` (Proyección de saldo disponible por lote/FIFO)
8. `page_data` (Almacén clave-valor JSON legacy)
9. `product_margins` (Configuración de márgenes comerciales y por categoría)
10. `product_recipe_items` (Detalle de insumos y consumos de recetas)
11. `product_recipes` (Cabecera de recetas BOM asociadas a producto final)
12. `product_suppliers` (Matriz relación Producto-Proveedor)
13. `production_order_additional_items` (Insumos no planificados en OTs)
14. `production_order_items` (Insumos planificados por receta en OTs)
15. `production_orders` (Órdenes de Trabajo / Producción)
16. `products` (Catálogo maestro de productos y materias primas)
17. `purchase_invoices` (Facturas de compra recibidas de proveedores)
18. `purchase_order_items` (Detalle de líneas de órdenes de compra)
19. `purchase_orders` (Órdenes de Compra)
20. `roles` (Roles del sistema y matriz de permisos JSON)
21. `sale_lot_movements` (Trazabilidad de lotes despachados por venta)
22. `sale_payment_items` (Abonos/pagos recibidos por venta)
23. `sale_payments` (Estado consolidado de pago y facturación por venta)
24. `sales` (Ventas y Cotizaciones)
25. `sales_entries` (Registros de venta históricos desnormalizados)
26. `sales_payment_history` (Auditoría de eventos de pago)
27. `sales_status_history` (Auditoría de estados comerciales de ventas)
28. `supplier_contacts` (Directorio de personas de contacto en proveedores)
29. `suppliers` (Empresas proveedoras)
30. `users` (Usuarios y credenciales con hash PBKDF2-SHA256)

---

## 2. Hallazgos Críticos y Discrepancias Estructurales

### A. Tablas Faltantes en el DDL de `init_db()`
En el código de `init_db()` en `db.py`:
- **`purchase_invoices`**: No posee sentencia `CREATE TABLE` dentro de `init_db()`. Una instalación en blanco no creaba esta tabla, provocando errores en Cuentas por Pagar.
- **`client_categories`**: Tampoco posee sentencia `CREATE TABLE` en `init_db()`. Provocaba fallos al registrar ventas o categorizar clientes.

### B. Llaves Foráneas (Foreign Keys) Faltantes
1. `purchase_invoices.supplier_id`: La columna existe pero carecía de constraint formal `FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT`. *(Auditoría confirma 0 registros huérfanos actualmente)*.
2. `sale_payment_items.bank_account_id`: Posee FK pero carecía de índice de cobertura para joins de recaudación.
3. `clients.category_id`: Es de tipo `VARCHAR(50)` referenciando identificadores como `'cat_1'`, gestionados a nivel aplicación en `page_data` o catálogo dinámico.

### C. Restricciones CHECK Faltantes
Se verificaron los invariantes de integridad en los datos existentes:
- `lot_stock.available_qty >= 0`: 0 violaciones. (Esencial para evitar saldos negativos).
- `lot_stock.initial_qty >= 0`: 0 violaciones.
- `inventory_movements.quantity <> 0`: 0 violaciones. (Un movimiento no puede registrar 0 unidades).
- `purchase_order_items.quantity_ordered > 0`: 0 violaciones.
- `inventory_entry_items.quantity > 0`: 0 violaciones.
- `sale_lot_movements.quantity > 0`: 0 violaciones.
- `product_recipe_items.quantity_required >= 0`: Se encontraron 8 registros con valor `0.0` (separadores con consumo pendiente de parametrizar). Por tanto, la restricción debe ser `quantity_required >= 0`.

### D. Índices de Cobertura Faltantes en Claves Foráneas
PostgreSQL no crea índices automáticos en columnas de claves foráneas. Las siguientes columnas críticas carecían de índice, impactando el rendimiento de joins y bloqueos de eliminación en cascada:
- `purchase_order_items(purchase_order_id)`
- `purchase_order_items(product_id)`
- `inventory_entries(purchase_order_id)`
- `inventory_entries(supplier_id)`
- `inventory_entry_items(inventory_entry_id)`
- `inventory_entry_items(product_id)`
- `purchase_invoices(purchase_order_id)`
- `purchase_invoices(supplier_id)`
- `purchase_invoices(inventory_entry_id)`
- `purchase_invoices(bank_account_id)`
- `sale_payment_items(sale_id)`
- `sale_payment_items(bank_account_id)`
- `sale_lot_movements(sale_id)`
- `sale_lot_movements(product_id)`
- `sales_status_history(sale_id)`
- `sales_payment_history(sale_id)`
- `production_order_items(production_order_id)`
- `production_order_items(input_product_id)`
- `production_order_additional_items(production_order_id)`
- `production_order_additional_items(input_product_id)`
- `product_recipe_items(recipe_id)`
- `product_recipe_items(input_product_id)`
- `supplier_contacts(supplier_id)`
- `users(role_id)`
- `sales(sale_date)`
- `sales(customer_name)`

---

## 3. Secuencias y Generación de Correlativos

Las secuencias de correlativos introducidas en la Fase 3 se encuentran operativas:
- `purchase_order_number_seq`
- `sales_number_seq`
- `production_order_number_seq`

Se preservarán en el sistema de migraciones garantizando que su valor actual se sincronice o mantenga con `GREATEST(COALESCE(MAX(id), 0), 1)`.

---

## 4. Conclusión y Hoja de Ruta para Migraciones

Para garantizar que un PostgreSQL vacío pueda ser levantado desde cero mediante `tools/migrate.py up`, el esquema debe dividirse en migraciones ordenadas, idempotentes y estrictamente reversibles (`.up.sql` y `.down.sql`).
