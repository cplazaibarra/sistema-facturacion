# AUDITORÍA DE REPORTES — FASE 6
Fecha: Septiembre 2026
ERP Facturación & Gestión Bodega Miel

## 1. Estado Actual de la Reportería

| Módulo / URL | Tipo de Datos | Detalle / Diagnóstico | Acción Requerida |
|---|---|---|---|
| `/reporteria/flujo-caja` | **REAL_DATA** | Consulta pagos cobrados reales (`sale_payments`), facturas de compras pagadas/pendientes (`purchase_invoices`), recepciones (`inventory_entries`) y ventas impagas. | Preservar. Optimizar agrupaciones y compatibilidad temporal. |
| `/reporteria/ingresos` | **REAL_DATA** | Consulta real de pagos recibidos vs compromisos futuros de cobro en `sales` y `sale_payments`. | Preservar. Añadir filtro por fechas. |
| `/reporteria/inventario-lotes` | **REAL_DATA** | Consulta relacional a `lot_stock` con joins a `products` y `inventory_entries`. | Preservar. Añadir links directos a trazabilidad. |
| `/proyeccion-ventas` | **REAL_DATA** | Motor estadístico `proyeccion_engine.py` calculando proyecciones a partir de ventas históricas. | Preservar. |
| `/reporteria/ventas` | **MOCK / STATIC** | Template `reporte_ventas.html` con números fijos hardcodeados ($1.245.000, 1.540 ventas, tabla con 3 productos fijos). La ruta en `routes/reportes.py` solo retorna `render_template('reporte_ventas.html')` sin pasar datos. | **REEMPLAZAR POR DATOS REALES**: Conectar a repositorio agregando ventas por producto, ingresos reales y estado sin datos si está vacío. |
| `/reporteria/compras` | **MOCK / STATIC** | Template `reporte_compras.html` con datos fijos ($450.000, 12 proveedores, 48 OC y 3 compras falsas). La ruta no calcula nada. | **REEMPLAZAR POR DATOS REALES**: Conectar con compras reales por proveedor agrupadas desde `purchase_orders` y `inventory_entries`. |
| `/reporteria/gastos` | **MOCK / STATIC** | Template `reporte_gastos.html` con categorías fijas ("Logística y Distribución", "Servicios Eléctricos"). Sin modelo de gastos operacionales detrás. | **REEMPLAZAR POR DATOS REALES**: Consolidar gastos reales de facturas de compras (`purchase_invoices`) por tipo/categoría, o mostrar "SIN REGISTROS DE GASTOS ADICIONALES". |

---

## 2. Principio Rector
Queda estrictamente prohibido mostrar datos inventados o simulados. Cualquier reporte en producción debe alimentarse exclusivamente de la base de datos PostgreSQL del ERP o informar explícitamente "Sin datos para el período seleccionado".
