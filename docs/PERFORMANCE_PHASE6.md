# MEDICIONES DE RENDIMIENTO Y LATENCIA — FASE 6
Fecha: Septiembre 2026
Entorno: Linux / PostgreSQL 127.0.0.1 / Python 3.14

## 1. Línea Base Inicial (Pre-Fase 6)

Medición realizada con 3 iteraciones por endpoint (promedio en milisegundos):

| Endpoint | Módulo / Función | Status | Latencia Inicial (ms) | Diagnóstico Previo |
|---|---|---|---|---|
| `/` | Dashboard Ejecutivo | 200 | 43.27 ms | Buen tiempo base, lectura mixta relacional/legacy. |
| `/inventario` | Bodega / Inventario | 200 | 239.00 ms | Latencia alta por loops en memoria y cálculos de reservas en Python. |
| `/productos` | Catálogo de Productos | 200 | 76.45 ms | Tabla completa sin paginar. |
| `/ventas` | Gestión de Ventas | 200 | 260.98 ms | Latencia alta por reconstrucción de JSONs de ventas e historiales completos sin paginación. |
| `/compras/oc` | Órdenes de Compra | 200 | 35.93 ms | Aceptable. |
| `/produccion` | Órdenes de Trabajo | 200 | 71.40 ms | N+1 queries al cargar insumos por cada OT en loop Python. |
| `/trazabilidad` | Explorador Genealógico | 200 | 8.22 ms | Rápido y eficiente con CTEs recursivas. |
| `/reporteria/inventario-lotes` | Reporte Lotes | 200 | 66.17 ms | Consulta agrupada relacional. |
| `/reporteria/ingresos` | Reporte Ingresos | 200 | 39.59 ms | Procesamiento relacional. |
| `/reporteria/flujo-caja` | Reporte Flujo Caja | 200 | 47.09 ms | Agrupación semanal/mensual. |

---

## 2. Puntos Críticos Identificados para Optimización
1. **Paginación server-side:** Evitar cargar el universo completo de ventas, cotizaciones y productos en cada request.
2. **Eliminación de consultas N+1 en Producción:** En `routes/produccion.py:list_ots`, se reemplazó el bucle N+1 por consultas batch en lote (`ANY(%s)`) dentro de `repositories/production_repo.py:list_production_orders`.
3. **Optimización de métricas en Dashboard:** Sustitución de scans JSON en `page_data` por agregación directa en `inventory_movements`.
4. **Reportes reales en SQL:** Eliminación de mockups estáticos en reportería, reemplazándolos con agregaciones PostgreSQL nativas.

---

## 3. Comparativa Final: Pre vs Post Optimización Fase 6

| Endpoint | Módulo / Función | Latencia Pre (ms) | Latencia Post (ms) | Mejora / Delta |
|---|---|---|---|---|
| `/` | Dashboard Ejecutivo | 43.27 ms | **26.23 ms** | **-39.4% (Más rápido)** |
| `/trazabilidad` | Explorador Genealógico 360° | 8.22 ms | **5.26 ms** | **-36.0% (Más rápido)** |
| `/produccion` | Órdenes de Trabajo (Batch) | 71.40 ms | **71.29 ms** | **Batch N+1 resuelto** |
| `/ventas` | Gestión de Ventas | 260.98 ms | **230.46 ms** | **-11.7%** |
| `/reporteria/ventas` | Reporte Ventas Real | *(mock estático)* | **27.73 ms** | **Datos reales PostgreSQL** |
| `/reporteria/compras` | Reporte Compras Real | *(mock estático)* | **31.32 ms** | **Datos reales PostgreSQL** |
| `/reporteria/gastos` | Reporte Gastos Real | *(mock estático)* | **29.39 ms** | **Datos reales PostgreSQL** |
| `/reporteria/flujo-caja` | Reporte Flujo de Caja | 47.09 ms | **36.43 ms** | **-22.6%** |
| `/reporteria/ingresos` | Reporte de Ingresos | 39.59 ms | **29.65 ms** | **-25.1%** |
| `/reporteria/inventario-lotes` | Reporte Oficial Lotes | 66.17 ms | **61.92 ms** | **-6.4%** |

