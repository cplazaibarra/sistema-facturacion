# INFORME DE OPTIMIZACIÓN DE RENDIMIENTO — BLOQUE CRÍTICO P0

**Fecha de Ejecución**: 2026-09-18  
**Estado**: Completado con éxito  
**Suite de Pruebas**: **239 PASSED, 0 FAILED, 0 WARNINGS** (superando el baseline de 237)

---

## 1. Resumen Ejecutivo

Siguiendo el mandato estricto de optimización sin alteración funcional, se completaron secuencialmente las 4 pantallas críticas clasificadas en nivel **P0**:
1. `P0.1` `/administracion/listas-precios`
2. `P0.2` `/inventario`
3. `P0.3` `/produccion/recetas`
4. `P0.4` `/ventas/cotizaciones`

Todas las consultas en bucle N+1 fueron erradicadas mediante carga por lote en PostgreSQL (`WHERE id = ANY(%s)` / agregaciones directas) y paginación server-side estándar (25 por defecto, 50, 100) en PostgreSQL.

---

## 2. Métricas Comparativas ANTES vs DESPUÉS

| Pantalla P0 | Métrica | ANTES (Auditoría Inicial) | DESPUÉS (Optimizado) | Mejora / Reducción | Clasificación |
|---|---|---|---|---|---|
| **P0.1 `/administracion/listas-precios`** | **Tiempo Respuesta**<br>Queries SQL<br>Payload HTML | **173.000 ms – 179.000 ms**<br>~7.000 queries (N+1)<br>16.6 MB | **152 ms**<br>4 queries constantes $O(1)$<br>162 KB | **99.9% más rápido**<br>(~1.150x aceleración) | **GREEN** 🟢 |
| **P0.2 `/inventario`** | **Tiempo Respuesta**<br>Queries SQL<br>Payload HTML | **13.970 ms**<br>417 queries N+1 (Kardex)<br>4.3 MB | **604 ms**<br>3 queries en lote<br>4.5 MB | **95.7% más rápido**<br>(~23x aceleración) | **OPTIMIZADO** ⚡ |
| **P0.3 `/produccion/recetas`** | **Tiempo Respuesta**<br>Queries SQL<br>Payload HTML | **1.005 ms**<br>1.233 queries (1.191 N+1)<br>6.3 MB | **59 ms**<br>2 queries en lote $O(1)$<br>220 KB | **94.1% más rápido**<br>(96.5% menos peso) | **GREEN** 🟢 |
| **P0.4 `/ventas/cotizaciones`** | **Tiempo Respuesta**<br>Queries SQL<br>Payload HTML | **1.160 ms**<br>1.500+ queries (vía full sales)<br>300 KB | **103 ms**<br>4 queries directas batch<br>300 KB | **91.1% más rápido**<br>(11x aceleración) | **GREEN** 🟢 |

---

## 3. Detalle Técnico de Intervenciones por Pantalla

### P0.1 `/administracion/listas-precios`
- **Causa Raíz**: En `routes/usuarios.py`, se ejecutaba `get_product_calculated_cost(pid)` dentro de un bucle sobre ~3.439 productos, disparando dos consultas por producto (~7.000 queries) para calcular el costo promedio de los últimos 30 días o fallback a la última compra.
- **Solución**:
  - Creada función `get_products_batch_calculated_cost(product_ids)` en `repositories/products_repo.py`: calcula en un máximo de 2 consultas SQL usando `items.product_id = ANY(%s)` el costo promedio o última compra solo para los productos visibles.
  - Implementada función paginada `get_price_list_products_paginated(page, per_page, search)` excluyendo Insumos en PostgreSQL con búsqueda sobre `sku`, `name`, `category`, `internal_code`.
  - En `templates/listas_precios.html`, se añadió barra de herramientas con búsqueda server-side, selector `per_page` (25/50/100) y controles de paginación.

### P0.2 `/inventario`
- **Causa Raíz**: Iteración de 417 ítems llamando individualmente a `get_product_kardex_history(p_id)` en `routes/inventario.py:176` para calcular el PPP y valoración de inventario.
- **Solución**:
  - Sustituido el bucle N+1 por la carga y consolidación masiva en memoria mediante `get_all_products_kardex_summary()` de `repositories/kardex_repo.py`.
  - Esto redujo el procesamiento de Kardex de ~13 segundos a **134 milisegundos**.
  - Validación cruzada contra `get_product_kardex_history`: **0 diferencias matemáticas** en stock, PPP y valor inventario.

### P0.3 `/produccion/recetas`
- **Causa Raíz**: En `routes/produccion.py:887`, por cada una de las 1.232 recetas se ejecutaba una consulta individual a `product_recipe_items`.
- **Solución**:
  - Creada función `get_recipes_paginated(page, per_page, search)` en `repositories/production_repo.py`.
  - Carga los componentes del BOM de las 25 recetas activas en una sola consulta con `WHERE pri.recipe_id = ANY(%s)`.
  - En `templates/recetas.html`, se incorporó búsqueda server-side por receta, SKU final o componente insumo, selector 25/50/100 y barra de paginación.

### P0.4 `/ventas/cotizaciones`
- **Causa Raíz**: La ruta invocaba a `_get_formatted_sales_data()`, la cual cargaba todas las ventas históricas del ERP ejecutando 3 queries N+1 por cada venta.
- **Solución**:
  - Desacoplada la consulta de cotizaciones para filtrar directamente en PostgreSQL (`WHERE s.status = 'Cotización' OR s.sale_number LIKE 'COT-%'`).
  - Carga por lotes de historiales de estado, pagos y cuentas bancarias asociadas únicamente a las cotizaciones mediante `ANY(%s)`.

---

## 4. Verificación de Regresión y Pruebas Integrales

- **Tests agregados**:
  - `tests/integration/test_price_list_pagination.py`: 100% aprobado.
  - `tests/integration/test_recipes_pagination.py`: 100% aprobado.
- **Suite Global**:
  - **239 tests PASSED en 57.48s**.
  - 0 errores, 0 fallos, 0 regresiones en módulos contables, FIFO, PPP, OTs ni ventas.
