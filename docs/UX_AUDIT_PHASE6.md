# AUDITORÍA DE EXPERIENCIA DE USUARIO (UX) — FASE 6
Fecha: Septiembre 2026
ERP Facturación & Gestión Bodega Miel

## 1. Resumen Ejecutivo
Se realizó una auditoría funcional y de interfaz sobre las 14 áreas de trabajo del ERP para elevar el sistema a un estándar operacional robusto, claro, rápido y consistente, preservando el stack ligero (Flask + Jinja2 + Vanilla JS + CSS).

---

## 2. Matriz de Clasificación de Hallazgos por Módulo

| Módulo | Ruta Principal | Claridad / Información | Paginación / Búsqueda | Feedback / Acciones | Severidad |
|---|---|---|---|---|---|
| **Login** | `/login` | Claro, minimalista, CSRF activo. | N/A | Falta spinner en envío de credenciales. | **LOW** |
| **Dashboard** | `/` | Indicadores ejecutivos, gráficos Chart.js. | Filtro temporal básico (6m, 12m, año). Falta filtro temporal unificado (hoy, 7d, 30d, mes). Lectura parcial de `page_data` en métricas de stock. | Requiere conectar métricas a PostgreSQL real al 100%. | **HIGH** |
| **Productos** | `/productos` | Tabla completa con fotos, SKU, precios, tipo. | Carga todos los productos en una sola tabla HTML sin paginación server-side. Búsqueda solo cliente. | Falta link contextual directo a "Ver lotes de este producto". | **MEDIUM** |
| **Proveedores** | `/proveedores` | Lista de proveedores con RUT, contacto y compras. | Carga completa en memoria. | Funcional y ordenado. | **LOW** |
| **Clientes** | `/ventas/clientes` | Catálogo de clientes, tipo y condición de venta. | Carga completa. Búsqueda solo cliente. | Modal de edición funcional. | **LOW** |
| **Compras OC** | `/compras/oc` | Listado de órdenes de compra y estados. | Carga completa. | Recepción debe incluir enlace contextual directo a trazabilidad del lote recibido. | **MEDIUM** |
| **Ingreso Mercadería** | `/ingreso-mercaderia` | Formulario de recepción con lote obligatorio si `requires_lot=True`. | Requiere confirmación clara y botón anti doble-click. | Añadir botón "Ver Trazabilidad" tras ingreso exitoso. | **MEDIUM** |
| **Inventario** | `/inventario` | Pestañas Stock General y Stock por Lote. | N+1 potencial en mapeos. Dependencia residual de `page_data.inventory_items`. | En pestaña Lotes, incorporar link directo `[🔍 Ver Trazabilidad]` por cada fila. | **HIGH** |
| **Producción (OT)** | `/produccion` | Visualización de OTs, estados y costos. | Múltiples consultas SQL directas en ruta (`routes/produccion.py`). | OTs finalizadas deben mostrar link contextual a `Genealogía del Lote Producido`. | **HIGH** |
| **Cotizaciones** | `/ventas/cotizaciones` | Listado y conversiones a venta. | Tabla grande, requiere paginación. | Idempotencia protegida, falta protección visual de doble-click en conversión. | **MEDIUM** |
| **Ventas** | `/ventas` | Tabla estilo Salesforce con badges y estados de pago. | Filtros por tarjetas de métrica. Falta paginación server-side. | En el modal de detalle de venta, los lotes despachados deben tener link directo a la Ficha 360° del Lote. | **HIGH** |
| **Cuentas por Pagar (CxP)** | `/compras/cuentas-por-pagar` | Gestión de facturas, vencimientos y pagos a proveedores. | Muy completa con estados visuales (Pendiente, Pagada, Vencida). | Buen rendimiento. | **LOW** |
| **Cuentas por Cobrar (CxC)** | `/ventas` (Filtro Retrasadas) | Vinculada al módulo de ventas y pagos. | Filtrable por estado de pago. | Consistente. | **LOW** |
| **Bancos** | `/usuarios/cuentas-bancarias` | Cuentas corrientes y saldos. | Conciliación manual simple. | Adecuado. | **LOW** |
| **Trazabilidad** | `/trazabilidad` | 360° funcional implementada en Fase 5B. | Búsqueda por query `q`. Debe enriquecerse para buscar por OT, OC, Venta, Proveedor y Cliente. | Agregar exportación Recall CSV / PDF y timeline visual refinada. | **CRITICAL** |
| **Reportes** | `/reporteria/*` | Reportes de Flujo de Caja, Ingresos y Lotes son reales. Reportes de Ventas, Compras y Gastos poseen tablas estáticas/mock. | Falta unificar reportes con datos relacionales reales y retirar mocks. | **CRITICAL** |

---

## 3. Plan de Acción Priorizado

1. **Trazabilidad 360° y Recall (Prioridad CRITICAL):**
   - Ampliar buscador `/trazabilidad` para soportar búsqueda por OT, OC, factura, venta, cliente, proveedor, SKU y lote.
   - Enriquecer timeline de vida del lote y mapa genealógico.
   - Implementar exportación de Recall a formato CSV y PDF simple descargable.
2. **Saneamiento de Reportes y Eliminación de Mocks (Prioridad CRITICAL):**
   - Conectar `/reporteria/ventas`, `/reporteria/compras` y `/reporteria/gastos` a consultas PostgreSQL reales agregadas por período.
   - Si no existen datos para un período, mostrar estado vacío "SIN DATOS REGISTRADOS" en lugar de valores hardcodeados.
3. **Links Contextuales de Trazabilidad (Prioridad HIGH):**
   - Desde Compras (Recepción) -> Ver Lote en Trazabilidad.
   - Desde Inventario (Pestaña Lotes) -> Ver Trazabilidad.
   - Desde OT (Producción Finalizada) -> Ver Genealogía de Lote.
   - Desde Ventas (Modal de detalle de venta) -> Enlace a cada lote entregado.
4. **Dashboard Ejecutivo Real (Prioridad HIGH):**
   - Conectar métricas de stock y ventas a PostgreSQL puro (`inventory_movements` y `sales`).
   - Selector temporal dinámico: Hoy, 7 días, 30 días, Mes actual, Año actual.
5. **Reducción de SQL Directo en Rutas (Prioridad HIGH):**
   - Migrar consultas SQL de `routes/produccion.py` hacia `repositories/production_repo.py`.
   - Migrar consultas de `routes/ventas.py` hacia `repositories/sales_repo.py` manteniendo propagación exacta de conexiones y transacciones.
6. **Protección Anti Doble-Click y UX Operacional (Prioridad MEDIUM):**
   - Script global para deshabilitar botones de formularios críticos (Guardar, Confirmar, Finalizar OT, Convertir) y mostrar spinner "Procesando...".
