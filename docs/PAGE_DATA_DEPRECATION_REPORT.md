# INFORME DE DESACOPLE Y DEPRECACIÓN DE `page_data` (FASE 4)

**Fecha:** 2026-09-15  
**Objetivo:** Clasificar todas las claves y lecturas/escrituras en la tabla `page_data` para guiar su retiro definitivo y reemplazo en la Fase 5.

---

## 1. Inventario de Claves Activas en `page_data`

Actualmente residen 25 claves en `page_data`:

| Clave | Tamaño Aprox. | Propósito Actual | Estrategia de Migración Futura (Fase 5) |
|---|---|---|---|
| `admin_modules` | 1.1 KB | Estructura estática del menú de administración | Mover a constante en configuración de aplicación o código Python |
| `admin_settings` | 165 B | Razón social, RUT, dirección y contacto de la empresa | Mover a tabla relacional `company_settings` o variables de entorno |
| `bank_accounts` | Legacy | Cuentas bancarias | **Ya migrado** a tabla relacional `bank_accounts` |
| `client_categories` | Legacy | Categorías de clientes | **Ya migrado** a tabla relacional `client_categories` |
| `dashboard_stats` | 97 B | Métricas cacheadas para el panel principal | Reemplazar por consultas SQL directas en agregaciones |
| `dashboard_sales_chart` | 106 B | Datos de serie de tiempo para gráficos Chart.js | Reemplazar por endpoint de agregación SQL sobre `sales` |
| `dashboard_products_top` | 106 B | Ranking de productos más vendidos | Reemplazar por agregación SQL `GROUP BY product_id` sobre `sales` |
| `dashboard_recent_sales` | 364 B | Lista de últimas ventas en el home | Reemplazar por `SELECT ... FROM sales ORDER BY id DESC LIMIT 5` |
| `ingreso_default_date` | 12 B | Fecha por defecto de formularios | Manejar dinámicamente en frontend/servidor (`date.today()`) |
| `ingreso_products` | 174 B | Catálogo simplificado para formularios rápidos | Reemplazar por `SELECT id, name FROM products WHERE is_deleted = FALSE` |
| `ingreso_recent` | 290 B | Resumen de recepciones recientes | Reemplazar por consulta sobre `inventory_entries` |
| `ingreso_suppliers` | 60 B | Lista de proveedores rápida | Reemplazar por `SELECT name FROM suppliers` |
| `ingreso_warehouses` | 43 B | Nombres de bodegas disponibles | Mover a tabla relacional `warehouses` o enum |
| `inventory_categories` | 216 B | Lista de categorías de productos | Reemplazar por `SELECT DISTINCT category FROM products` |
| `inventory_items` | 2.2 KB | **Stock agregado desnormalizado legacy** | **Fuente de verdad oficial ya es `inventory_movements`**. Mantener lectura de compatibilidad hasta Fase 5 |
| `inventory_stats` | 54 B | Indicadores de stock bajo y valorización | Reemplazar por cálculo SQL sobre `lot_stock` / `inventory_movements` |
| `inventory_stock_filters` | 60 B | Opciones de filtro de UI | Constante en frontend o plantilla Jinja2 |
| `price_list_config` | 261 B | Parámetros de listas de precios | Mover a tabla `price_lists` |
| `proyeccion_*` (4 claves) | ~1.7 KB | Proyecciones y tendencias | Mover a servicio de analítica |
| `sales_*_options` (3 claves) | ~120 B | Enums de estado de entrega, pago y método | Constantes en Python / enums de base de datos |
| `ventas_metrics` | 529 B | KPIs de ventas | Agregación SQL sobre `sales` |
| `ventas_records` | 1.6 KB | Registros legacy de ventas | Reemplazado por tabla `sales` |

---

## 2. Puntos de Acceso en Código (`db.py` y Rutas)

- **Lecturas principales:** `get_page_data(key)` se utiliza extensivamente para poblar plantillas Jinja2 cuando los datos relacionales no están directamente enlazados al Blueprint.
- **Escrituras críticas:**
  - `inventory_items`: Modificado por `register_inventory_entry`, `discount_stock_for_sale`, y `finalizar_ot` para mantener sincronizada la vista legacy de bodega.

---

## 3. Estado en Fase 4 y Hoja de Ruta

- En esta Fase 4 **NO se elimina** la tabla `page_data` ni se alteran sus contratos para preservar la total compatibilidad con los módulos existentes.
- La tabla queda versionada formalmente en la migración `000001_initial_core.up.sql`.
- Su contenido base se inicializa de forma reproducible en los scripts de seeds requeridos.
