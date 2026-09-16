# Informe de Clasificación y Deprecación de `page_data` (Fase 5)

**Fecha de Análisis:** 15 de Septiembre de 2026  
**Sistema:** ERP Facturación & Gestión de Negocio  
**Tabla:** `page_data` (PostgreSQL)

---

## 1. Contexto y Objetivos

La tabla `page_data` fue heredada del diseño monolítico inicial para almacenar documentos JSON no estructurados. Durante las Fases 2, 3 y 4 se migraron los modelos de datos principales a tablas relacionales tipadas y normalizadas.

En esta Fase 5, clasificamos la totalidad de las 25 claves activas en `page_data` para establecer una ruta clara y segura hacia su futura deprecación, garantizando que ninguna eliminación prematura rompa la compatibilidad actual ni la capa dual-write establecida en Fase 2.

---

## 2. Clasificación Exhaustiva de Claves

| Clave (`key`) | Categoría | Tamaño Aprox. | Estado en Fase 5 | Estrategia de Deprecación Futura |
|---|---|---|---|---|
| `admin_settings` | `BUSINESS_CRITICAL` | 165 B | ACTIVO | Migrar a tabla `system_settings` con clave-valor tipado en Fase 6+. |
| `inventory_items` | `LEGACY_INVENTORY` | 2.2 KB | ACTIVO (DUAL-WRITE) | **CRÍTICO:** Mantener sincronización dual-read/dual-write. Fuente de verdad oficial es `inventory_movements` (Fase 2). Deprecar sólo tras migración total de templates legacy. |
| `admin_modules` | `UI_CONFIGURATION` | 1.1 KB | ACTIVO | Configuración de navegación y menú lateral. Puede migrarse a catálogo relacional o archivo estático de configuración. |
| `ingreso_warehouses` | `UI_CONFIGURATION` | 43 B | ACTIVO | Opciones de bodegas para recepciones. Migrar a tabla `warehouses` en Fase 6. |
| `inventory_categories` | `UI_CONFIGURATION` | 216 B | ACTIVO | Catálogo de categorías en UI. Tabla relacional `categories` ya existe en Postgres; unificar lectura. |
| `inventory_stock_filters` | `UI_CONFIGURATION` | 60 B | ACTIVO | Etiquetas de filtros de stock en interfaz. |
| `price_list_config` | `UI_CONFIGURATION` | 261 B | ACTIVO | Definición de listas de precio y márgenes comerciales. |
| `sales_delivery_status_options` | `UI_CONFIGURATION` | 37 B | ACTIVO | Catálogo de estados de despacho en formularios de venta. |
| `sales_payment_method_options` | `UI_CONFIGURATION` | 51 B | ACTIVO | Opciones de medio de pago en formularios. |
| `sales_payment_status_options` | `UI_CONFIGURATION` | 34 B | ACTIVO | Opciones de estado de pago en formularios. |
| `ingreso_default_date` | `UI_CONFIGURATION` | 12 B | ACTIVO | Valor predeterminado en formulario de ingreso. |
| `ingreso_products` | `COMPATIBILITY` | 174 B | COMPATIBILIDAD | Lista preliminar de insumos para formulario de compras. La tabla `products` ya es la fuente real. |
| `ingreso_suppliers` | `COMPATIBILITY` | 60 B | COMPATIBILIDAD | Lista rápida de proveedores. La tabla `suppliers` ya es la fuente real. |
| `dashboard_stats` | `LEGACY_DEMO` | 97 B | `SAFE_TO_REMOVE_LATER` | Métricas demo. El backend ahora calcula estadísticas en tiempo real vía `get_sales_metrics()`. |
| `dashboard_products_top` | `LEGACY_DEMO` | 106 B | `SAFE_TO_REMOVE_LATER` | Reemplazado por agregación relacional `get_top_products()`. |
| `dashboard_recent_sales` | `LEGACY_DEMO` | 364 B | `SAFE_TO_REMOVE_LATER` | Reemplazado por consulta directa `list_sales(limit=...)`. |
| `dashboard_sales_chart` | `LEGACY_DEMO` | 106 B | `SAFE_TO_REMOVE_LATER` | Reemplazado por agregación `get_sales_chart_data()`. |
| `inventory_stats` | `LEGACY_DEMO` | 54 B | `SAFE_TO_REMOVE_LATER` | Estadísticas demo en desuso. |
| `ingreso_recent` | `LEGACY_DEMO` | 290 B | `SAFE_TO_REMOVE_LATER` | Historial demo de recepciones; reemplazado por `inventory_entries`. |
| `ventas_metrics` | `LEGACY_DEMO` | 529 B | `SAFE_TO_REMOVE_LATER` | Reemplazado por reporting relacional. |
| `ventas_records` | `LEGACY_DEMO` | 1.6 KB | `SAFE_TO_REMOVE_LATER` | Ventas demo; reemplazado por tabla `sales`. |
| `proyeccion_chart` | `LEGACY_DEMO` | 202 B | `SAFE_TO_REMOVE_LATER` | Datos demo de módulo de proyección. |
| `proyeccion_insights` | `LEGACY_DEMO` | 573 B | `SAFE_TO_REMOVE_LATER` | Datos demo de módulo de proyección. |
| `proyeccion_stats` | `LEGACY_DEMO` | 410 B | `SAFE_TO_REMOVE_LATER` | Datos demo de módulo de proyección. |
| `proyeccion_table` | `LEGACY_DEMO` | 567 B | `SAFE_TO_REMOVE_LATER` | Datos demo de módulo de proyección. |

---

## 3. Plan de Retiro Seguro (Roadmap Post-Fase 5)

1. **Fase 5 (Actual):**
   - Aislamiento completo de lecturas/escrituras en `repositories/legacy_repo.py` (`get_page_data`, `set_page_data`).
   - Mantenimiento estricto de invariantes de dual-write para `inventory_items` y configuraciones de UI.
   - Ninguna clave es borrada físicamente en esta fase para evitar regresiones visuales.
2. **Fase 6 (UX y Rendimiento):**
   - Sustituir llamadas de configuración de dropdowns (`sales_*_options`, `inventory_categories`) por catálogos relacionales o constantes cacheadas en memoria.
   - Eliminar lecturas fallback a claves `LEGACY_DEMO`.
3. **Fase Futura (Post-Fase 6):**
   - Retiro formal de `inventory_items` tras validar 100% de paridad y migración completa de vistas.
   - Eliminación de la tabla `page_data`.
