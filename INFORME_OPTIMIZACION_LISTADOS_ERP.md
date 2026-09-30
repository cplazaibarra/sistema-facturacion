# Informe de optimización de listados ERP

Fecha: 2026-09-27.

**ESTADO FINAL DEL OBJETIVO TRANSVERSAL: RED — INCOMPLETO.**

Este documento registra un avance verificable, no la finalización solicitada de todo el ERP. Quedan pantallas P0 con cargas masivas; Productos recibió una normalización puntual a 30, pero el resto de P1/P2 todavía requiere auditoría e implementación. No se declara GREEN por tener una suite verde.

## Baseline y alcance

- BASELINE REAL: **434 PASSED / 0 FAILED**, 137,18 s.
- PANTALLAS/UNIDADES AUDITADAS: **44 unidades funcionales** en la matriz; algunas agrupan formularios, detalles o endpoints equivalentes. No son 44 URLs distintas.
- PANTALLAS CON MEJORAS IMPLEMENTADAS: **9 unidades verificadas** (dashboard y listados de conciliación, cotizaciones, matriz de compras, cuentas bancarias, CxP operativa, deudas y productos).
- UNIDADES NO MODIFICADAS EN ESTA INTERVENCIÓN: **35**, incluyendo excepciones NO APLICA y trabajo pendiente.
- SUITE COMPLETA POSTERIOR: **455 PASSED / 0 FAILED**, 155,36 s.
- Inventario previo: [AUDITORIA_PAGINACION_ERP.md](AUDITORIA_PAGINACION_ERP.md).

## Cambios implementados

1. `core/pagination.py`: PAGE_SIZE=30, parseo y normalización, metadatos y URLs conservando parámetros repetidos. El navegador no controla el tamaño.
2. Componente `_pagination.html`: rango de registros, Anterior/Siguiente y página actual, sin larga lista numerada.
3. Conciliación bancaria: detalle SQL fijo de 30, páginas inválidas normalizadas, mismo WHERE para KPIs y detalle. Exportación explícita completa, sin el antiguo techo artificial de 100.000.
4. Cotizaciones: filtros de estado, cliente, producto y búsqueda en SQL; COUNT y tarjetas con todo el universo filtrado; detalle limitado; clientes e historiales asociados cargados por lotes. Filtros del navegador navegan a page=1.
5. Productos comprados: CTE mensual y agrupación por producto, COUNT y totales en SQL; LIMIT 30 aplicado a productos agrupados. CSV conserva todas las coincidencias y ahora transmite también la búsqueda.
6. Cuentas bancarias: COUNT y SELECT LIMIT 30 OFFSET, conservando formularios y permisos existentes.
7. Dashboard: la consulta de ventas recientes usa LIMIT 5 antes de deserializar; se elimina el recorte posterior a cargar todas las ventas.
8. CxP operativa: el detalle usa filtros/búsqueda en PostgreSQL antes de LIMIT 30; KPIs se calculan con agregaciones completas. Selectores grandes de proveedor/cuenta usan búsqueda remota acotada.
9. Deudas: lista con COUNT y LIMIT 30 SQL, filtros y orden determinístico; las cuentas del formulario se resuelven remotamente.
10. Productos: se conserva la búsqueda SQL existente y se fija el límite a PAGE_SIZE=30; las páginas inválidas se normalizan y la navegación compacta preserva filtros.

No se cambiaron escrituras de inventario, FIFO, PPP, reservas, pagos, facturación ni producción. No se agregaron índices ni migraciones.

## Matriz de resultados

“Pendiente” significa no optimizado por esta intervención, aunque exista una paginación anterior. Cantidades: fuentes del inventario inicial, medidas durante la suite y susceptibles de incluir fixtures. La evidencia de detalle posterior está separada más abajo.

| Pantalla | Registros (fuentes) | Antes | Después | Paginación | Filtros | Excel / CSV | Performance | Tests | Estado |
|---|---|---|---|---|---|---|---|---|---|
| Productos | products: 11301 | SQL paginado; 25/50/100 | SQL LIMIT 30 fijo | Sí | SKU/nombre/categoría/tipo en SQL | Exportación existente sin cambios | No medido | 2 pruebas específicas + suite 455 green | Implementado; Excel aún no validado para aceptación |
| Ventas | sales: 1683 | No detalle; clientes completos; 25/50/100 | Sin cambios | Sí | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Cotizaciones | sales: 1683 | Sí; Visual | LIMIT 30 | SQL OFFSET | SQL / preservados | Sin exportación en esta pantalla | 10 queries; 120.63 ms; 222511 bytes | Suite + navegador; fixtures 0/1/30/31/60/61 | Detalle verificado; ver limitaciones |
| Clientes | clients: 10 | Sí; No | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Proveedores | suppliers: 2222 | No; 25/50/100 | Sin cambios | Sí | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Órdenes de compra | purchase_orders: 1413 | No detalle; 25/50/100 | Sin cambios | Sí | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Productos comprados | purchase_order_items: 1523 | Sí; Python slice | LIMIT 30 | SQL OFFSET | SQL / preservados | CSV completo probado | 6 queries; 85.59 ms; 206064 bytes | Suite + navegador; fixtures 0/1/30/31/60/61 | Detalle verificado; ver limitaciones |
| Recepciones recientes | inventory_entries: 1830 | No detalle; sí OC y proveedores; LIMIT 20 | Sin cambios | Acotado sin navegación | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Facturas proveedores / CxP operativa | purchase_invoices: 434 | Facturas completas + selectores masivos | LIMIT 30 y selectores remotos ≤30 | Sí | Estado/búsqueda SQL | Exportación visible no aplica | Medición previa a selectores; navegador probado anteriormente | 36 pruebas incluyendo CxP | Implementado; Excel universal no aplica |
| Inventario / Stock | products: 11301; inventory_movements: 6360; lot_stock: 1508 | Sí; Visual | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Kardex catálogo | products: 11301; inventory_movements: 6360 | Sí; Python slice | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Kardex producto | inventory_movements: 6360 | Sí histórico completo; Python slice | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Lotes y vencimientos | lot_stock: 1508 | No; 25/50/100 | Sin cambios | Sí | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Ajustes de inventario | inventory_adjustment_requests: 4 | Sí; No | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Órdenes de producción | production_orders: 1618 | No detalle; sí productos selector; 25/50/100 | Sin cambios | Sí | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Recetas | product_recipes: 1389 | No; 25/50/100 | Sin cambios | Sí | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Calendario producción | production_orders: 1618 | Ventana semanal + pendientes; No | Sin cambios | Ventana | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Listas de precios | products: 11301 | No; 25/50/100 | Sin cambios | Sí | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Gastos operacionales | operational_expenses: 16 | Sí; No | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Facturas de compra y gastos | purchase_invoices: 434; operational_expense_occurrences: 15 | Sí; Python slice | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| CxP financiera | purchase_invoices: 434; operational_expense_occurrences: 15 | Sí; Python slice | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| CxC financiera | sales: 1683; sale_payment_items: 76 | Sí; Python slice | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Conciliación bancaria | bank_transactions: 277 | No salvo per_page sin límite; SQL tamaño arbitrario | LIMIT 30 | SQL OFFSET | SQL / preservados | XLSX completo probado | 5 queries; 187.12 ms; 419160 bytes | Suite + navegador; fixtures 0/1/30/31/60/61 | Detalle verificado; ver limitaciones |
| Deudas | debts: 111 | Detalle completo, cuentas completas al modal | LIMIT 30; cuentas por API remota | Sí | filtros WHERE SQL | Exportación XLSX existente sin cambios | No medido | 36 pruebas incluyendo reglas y rutas | Implementado; exportación sin prueba >30 |
| Cuotas y pagos de deuda | debt_installments: 339; debt_payments: 87 | Por deuda; No | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Flujo de caja | sales: 1683; purchase_invoices: 434; bank_transactions: 277; debt_installments: 339 | Sí; Python slice 30 | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Ingresos históricos y futuros | sales: 1683 | Sí; No | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Reporte ventas por producto | sales: 1683 | Sí; JavaScript | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Reporte compras por proveedor | purchase_orders: 1413; purchase_invoices: 434 | Sí grupos; JavaScript | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Reporte gastos por categoría | inventory_entries: 1830 | Agregados; No | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Dashboard ventas recientes | sales: 1683 | Sí y slice 5; Python slice | LIMIT 5 | Resumen fijo | SQL / preservados | Sin exportación en esta pantalla | 1 queries; 76.65 ms; 44314 bytes | Suite + navegador | Detalle verificado; ver limitaciones |
| Proyección ventas | sales: 1683 (snapshot durante baseline) | Sí; No | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Usuarios | users: 6 | Sí; No | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Roles | roles: 7; users: 6 | Sí; No | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Cuentas bancarias | bank_accounts: 689 | Sí; No | LIMIT 30 | SQL OFFSET | SQL / preservados | Sin exportación en esta pantalla | Ver medición JSON | Suite + navegador | Detalle verificado; ver limitaciones |
| CxP operativa | purchase_invoices: 434; inventario_entries: 1830 | Facturas completas + paginación JS | LIMIT 30 | Estado/búsqueda SQL | No hay exportación visible | Ver medición JSON | Suite financiera + prueba nueva; navegador pendiente | Detalle verificado; selectores completos pendientes |
| Operario recepción | purchase_orders: 1413 | Sí pendientes; No | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Operario OT / finalizar | production_orders: 1618 | Sí activas; No | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Operario historial | inventory_entries: 1830; production_lot_consumptions: 201; production_orders: 1618 | 30 por cada una de 3 fuentes; Top 30 Python | Sin cambios | Parcial | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Operario inicio | inventory_entries: 1830; production_orders: 1618 | 5 por fuente; Resumen 5 | Sin cambios | Parcial | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | NO APLICA |
| Trazabilidad / genealogía | lots: 1508; production_lot_consumptions: 201; sale_lot_movements: 132 | Grafo por lote; Búsqueda limitada | Sin cambios | Parcial | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | NO APLICA |
| Auditorías contextuales | bank_reconciliation_audit: 207; collection_actions: 0 | Por entidad; No | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Documentos / detalle OC, OT, recepción, ajustes, receta | purchase_order_items: 1523; production_order_items: 3042; inventory_entry_items: 802 | Por documento; No | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | NO APLICA |
| Formularios y selectores | products: 11301; clients: 10; suppliers: 2222 | Sí catálogos; No | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | Pendiente |
| Exportaciones e impresión | Dataset filtrado: no medido | Sí por contrato; No | Sin cambios | No | Sin cambios | Sin cambios | No medido | Regresión general; no aceptación individual | NO APLICA |

## Mediciones reales posteriores

Medición única local, sin calentamiento controlado. No equivale a benchmark ni se extrapola a 10.000/100.000 filas. No se midieron tiempos, queries ni bytes antes de la modificación; no se afirma una reducción porcentual.

| Ruta | HTTP | Filas detalle recuperadas | Filas recuperadas en todas las consultas | Queries | Backend ms | HTML bytes |
|---|---:|---:|---:|---:|---:|---:|
| /dashboard | 200 | 5 | 5 | 1 | 76.65 | 44314 |
| /reporteria/conciliacion-bancaria | 200 | 30 | 775 | 5 | 187.12 | 419160 |
| /ventas/cotizaciones | 200 | 23 | 68 | 10 | 120.63 | 222511 |
| /compras/productos-comprados | 200 | 30 | 46 | 6 | 85.59 | 206064 |
| /administracion/cuentas-bancarias | 200 | 30 | 31 | 2 | 47.03 | 117085 |

La conciliación todavía obtiene todas las cuentas bancarias para selectores (733 en esta medición). Por eso recuperar 30 movimientos NO equivale a recuperar sólo 30 filas totales de PostgreSQL. Se documenta como optimización auxiliar pendiente. Cotizaciones conserva listas DISTINCT de etiquetas para los selectores; no envía todas las cabeceras ni historiales.

Archivos de evidencia:

- [Consultas y mediciones](docs/pagination_evidence/measurements.json): SQL real y número de filas recuperadas por cada detalle.
- [Planes EXPLAIN ANALYZE](docs/pagination_evidence/explain.json): consultas representativas, no benchmark completo de todas las rutas con sus JOIN.
- [Navegador autenticado](docs/pagination_evidence/browser.json): HTTP, filas, navegación y errores.

## OFFSET, keyset e índices

Se mantiene OFFSET para los listados intervenidos: UX con número de página y cardinalidades medidas moderadas. En consultas representativas:

- bank_transactions: 299 filas; OFFSET 0: 0,400 ms; OFFSET 270: 0,274 ms.
- bank_accounts: 733 filas; OFFSET 0: 0,045 ms; OFFSET 720: 0,180 ms.

No hay evidencia medida que justifique introducir keyset o nuevos índices en esos dos casos. Estos planes NO justifican el rendimiento futuro con decenas de miles de filas ni sustituyen medir los demás P0/P1. Los órdenes de detalles modificados incluyen ID único como desempate. La matriz mensual usa cantidad DESC, nombre ASC, product_id ASC.

## Pruebas

- 20 casos nuevos: conciliación/cotizaciones/matriz con 0, 1, 30, 31, 60 y 61 registros, continuidad y ausencia de duplicados; pruebas de KPI completo, XLSX/CSV completos, tamaño solicitado abusivo y páginas inválidas según pantalla; RBAC de cuentas y conciliación.
- Los fixtures nuevos limpian exclusivamente sus registros en `finally`/teardown.
- Se actualizó el test antiguo de matriz que exigía 25 para reflejar la nueva regla 30; no se borraron casos de regresión.
- Pruebas específicas iniciales: 35 passed (conciliación, matriz, rutas y primeros casos nuevos); 28 passed (reglas de cotización, snapshots y rutas); 19 passed (nuevo archivo completo).
- Browser: 14 rutas principales respondieron HTTP 200, sin pageerror JavaScript ni respuestas HTTP >=400 capturadas por Playwright. El log del servidor sí mostró un 404 de `/favicon.ico` durante la primera carga; no se certifica ausencia absoluta de 404. Anterior/Siguiente probado en conciliación, matriz y cuentas; búsqueda sin coincidencias y reset de página probado en cotizaciones y conciliación.
- El conteo genérico del navegador es del primer tbody, que puede ser un formulario vacío o una tabla resumen. NO se usa para certificar todas las tablas de recepciones o Flujo de Caja. Los tests de los detalles migrados comprueban las filas específicas.
- RBAC existente preservado: varias rutas previas sólo tienen autenticación global (p.ej. cotizaciones/compras), no un decorador de permiso por módulo. No se declara auditada ni corregida toda la seguridad del ERP.

## Trabajo pendiente obligatorio

- P0: inventario, catálogo y movimientos Kardex, facturas/CxP operativa, CxC, CxP financiera, facturas y gastos, ingresos, reporte de ventas, proyección de ventas y Flujo de Caja.
- Flujo de Caja conserva exactamente el motor previo: en este checkout `paginate_movements` hace slice Python después de la consolidación. La premisa de SQL server-side inicial no coincide con el código revisado.
- Kardex reconstruye PPP con recurrencia cronológica; aplicar LIMIT antes de esa reconstrucción alteraría saldos. Necesita diseño y pruebas de equivalencia antes de migrar, no un recorte prematuro.
- P1: normalización 30 en productos/ventas/OC/OT/recetas/lotes/precios/proveedores; clientes, deudas, gastos, ajustes, recepción, operario, calendario e historiales.
- P2: evaluar maestros y cuotas sin degradar documentos de 12/24/36 cuotas; NO paginar catálogos pequeños por defecto.
- Autocompletes/selectores: evitar descargas completas donde ya hay endpoints remotos compatibles.
- Falta medición/aceptación individual de cada pantalla pendiente, validación completa de filtros y navegación en navegador y cierre de bloques.

## Semáforos de alcance transversal

| Área | Estado | Motivo |
|---|---|---|
| P0 | RED | Avance parcial; quedan cargas masivas, incluido inventario, Kardex, CxC, reportes financieros y Flujo de Caja |
| P1 | RED | No iniciado; P0 no está cerrado |
| P2 | RED | Evaluado en inventario; implementación aún no corresponde |
| N+1 | RED | Cargas batch preservadas en lo migrado; sin certificación transversal |
| KPIs | RED | Verificados en conciliación/matriz/cotizaciones; resto pendiente |
| EXCEL | RED | XLSX bancario y CSV matriz verificados; aceptación transversal pendiente |
| RBAC | RED | Permisos existentes preservados y tests específicos verdes; revisión transversal incompleta |
| REGRESIÓN | GREEN | Suite completa posterior: 455 passed / 0 failed; aún no certifica cada requisito funcional transversal |

**ESTADO FINAL: RED. El objetivo del usuario aún no está cumplido.**

## Actualización de continuación — 2026-09-27

La validación específica tras añadir CxP, Deudas y Productos ejecutó 36 pruebas y luego 2 pruebas de Productos/inventario; la última suite completa ejecutada es **455 PASSED / 0 FAILED (155,36 s)**. Durante esa regresión, el test de recepción que esperaba una factura nueva en la primera página falló porque el orden existente prioriza vencimientos; se actualizó para buscar esa factura sobre el conjunto server-side. No se cambió la regla ni el orden de negocio.

La suite GREEN sólo demuestra no regresión del código cubierto. No implica aceptación transversal: no se han migrado los restantes informes P0 ni medido cada listado, así que P0, P1, KPIs/Excel/RBAC globales y estado final permanecen RED/PENDIENTE según la matriz.
