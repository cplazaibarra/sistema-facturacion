# Auditoría de SQL Directo en Rutas (Phase 5)

**Fecha de Auditoría:** 15 de Septiembre de 2026  
**Sistema:** ERP Facturación & Gestión de Negocio  
**Total de Puntos SQL Directos Identificados:** 98 sentencias `cur.execute` en 6 archivos de ruta.

---

## 1. Resumen Ejecutivo por Módulo

| Módulo de Rutas | Archivo | Concurrencias SQL | Tablas Afectadas | Estado / Diagnóstico |
|---|---|---|---|---|
| **Inventario** | `routes/inventario.py` | 6 | `products`, `lot_stock`, `inventory_entries` | Consultas auxiliares de kardex y filtros puntuales. |
| **Producción** | `routes/produccion.py` | 32 | `production_orders`, `production_order_items`, `product_recipes`, `product_recipe_items`, `page_data` | Lógica central de órdenes de producción y recetas (BOM) ejecutada directamente en controladores. |
| **Compras** | `routes/compras.py` | 5 | `purchase_orders`, `purchase_items`, `purchase_invoices` | Consultas de búsqueda y reportes auxiliares de compras. |
| **Usuarios** | `routes/usuarios.py` | 2 | `product_margins`, `roles` | Lectura de márgenes y verificación de roles. |
| **Autenticación** | `routes/auth.py` | 1 | `users` | Consulta de verificación de credenciales activa. |
| **Ventas** | `routes/ventas.py` | 32 | `sales`, `sale_payments`, `client_categories`, `product_margins`, `clients` | Flujos transaccionales de pago, aprobación, actualización de estado y cotizaciones. |

---

## 2. Detalle de Puntos Críticos y Clasificación

### A. `routes/produccion.py` (32 sentencias)
- **Líneas 16, 29, 44, 83:** Listado, conteo y filtrado de órdenes de trabajo (`production_orders`).
- **Líneas 118, 140, 156:** Creación de OT (`INSERT INTO production_orders`, `INSERT INTO production_order_items`). Utiliza `get_next_ot_number()` para numeración atómica.
- **Líneas 252, 272, 288, 301:** Flujo de inicio de producción y consumo de insumos.
- **Líneas 326, 341, 354, 380, 407, 422:** Finalización de orden de producción:
  - Hace `SELECT FOR UPDATE` sobre `page_data` para consistencia legacy.
  - Registra movimientos de inventario de entrada y salida (`record_inventory_movement`).
  - Actualiza estado de la OT a `'Finalizada'`.
- **Líneas 524, 536, 573, 585, 599, 615, 680-708, 733-737:** Gestión de recetas y BOM (`product_recipes`, `product_recipe_items`).
- **Recomendación:** Mantener las rutas delegando a `repositories/production_repo.py` en futuras iteraciones de limpieza de controladores sin alterar el contrato HTTP actual.

### B. `routes/ventas.py` (32 sentencias)
- **Líneas 30:** Lectura de usuario autenticado para auditoría de vendedor.
- **Líneas 74, 93, 99, 106:** Sincronización de clientes legacy y categorías.
- **Líneas 417, 420, 428, 436, 448:** Búsqueda y creación de cliente al emitir venta/cotización.
- **Líneas 502, 514, 523, 540, 555, 571, 586:** Registro y aprobación de pagos de venta (`sale_payments`):
  - Línea 502: Aplica `SELECT FOR UPDATE` sobre `sales` para evitar condiciones de carrera en pagos simultáneos (preservado de Fase 3).
- **Líneas 726, 737, 740, 755, 770:** Transición atómica de estado a `'Pagado'` / `'Completada'`.
- **Líneas 823, 835, 850, 857, 873, 880, 896:** Gestión documental de facturas de venta y comprobantes de transferencia.
- **Líneas 1244, 1265, 1319, 1336, 1373, 1409, 1466-1492:** Flujo de conversión de cotización a venta.
  - Preserva verificación de idempotencia y validación atómica de stock de Fase 3.

### C. `routes/inventario.py` (6 sentencias)
- **Líneas 107, 122, 137:** Consultas de agregación de kardex y movimientos por producto.
- **Líneas 364, 668, 676:** Consultas de validación de SKU y detalles de ingreso.

### D. `routes/compras.py` (5 sentencias)
- **Líneas 670, 693:** Consultas analíticas de compras por proveedor y período.
- **Líneas 765, 829, 851:** Búsqueda rápida de órdenes pendientes de factura.

### E. `routes/usuarios.py` (2 sentencias)
- **Líneas 80, 111:** Consultas de catálogo de roles y márgenes de producto.

### F. `routes/auth.py` (1 sentencia)
- **Línea 16:** Búsqueda de usuario activo para autenticación con soporte de hashing de contraseña (Fase 1).

---

## 3. Conclusiones y Plan de Acción
1. **Preservación de Transaccionalidad:** Todas las rutas críticas con sentencias directas utilizan `with get_connection() as conn:` y context managers de cursor, garantizando `COMMIT` / `ROLLBACK` seguro.
2. **Bloqueos Concurrentes Intactos:** Los bloqueos `SELECT FOR UPDATE` implementados en Fase 3 en `ventas.py` (L502) y `produccion.py` (L326) operan de manera correcta y consistente.
3. **Estrategia Fase 5:** La extracción de `db.py` en repositorios proporciona la base limpia para que en la subsiguiente optimización de controladores las rutas llamen directamente a los métodos de dominio sin necesidad de recrear la conexión en cada handler.
