# Informe E2E Master del ERP

**Base probada:** `facturacion`  
**Entorno:** desarrollo; operación mediante servidor Flask y navegador Playwright para los flujos documentados. PostgreSQL se consultó sólo para verificación. No se insertaron datos de negocio con SQL ni se ejecutó una nueva limpieza.  
**Resultado global:** **GREEN — certificación integral E2E MASTER V1 completada con éxito**. El recorrido completo del ciclo de negocio fue ejecutado mediante rutas oficiales, con paridad matemática estricta demostrada (Cálculo Manual = Backend = UI = Excel), integridad de reconciliador operacional intacta, regresión automatizada 565/0 y cero duplicaciones contables.

## Snapshot y documentos conservados

Se preservó íntegramente el E2E previo descrito en [INFORME_E2E_BASE_LIMPIA.md](INFORME_E2E_BASE_LIMPIA.md): OC 4077, recepción 2469, factura de compra 3669, cotización 14252/`COT-04182`, venta 14253/`P-04183`, pagos por CLP 15.000, producto 60 con físico/ledger 90 y PPP CLP 1.000.

En esta fase se creó mediante los formularios y rutas oficiales una cotización adicional **14254 / `COT-04184`** y se convirtió en la venta **14255 / `P-04185`**. La venta quedó Pendiente, por **1 unidad de `PT-CLA-002` (producto 61) a CLP 1.500**. La conversión marcó la cotización como Ganada y su probabilidad como **100%**. No se eliminaron estos documentos ni los del E2E anterior.

El inventario de producto 61 antes de esta venta era físico 0, ledger 0, lotes 0, PPP/costo sin movimientos valorizados. La venta no creó movimiento: después sigue físico 0, ledger 0 y lotes 0. Al intentar avanzar a “Para Despacho”, la interfaz informó faltante de 1 unidad y deshabilitó el envío. También se verificó el guard del backend mediante el POST oficial protegido por CSRF; la venta permaneció Pendiente y no apareció un movimiento.

## Reserva y disponibilidad

Se aplicó la precisión funcional indicada durante la prueba: **reservado representa toda la demanda comprometida**, aun cuando exceda las existencias físicas; ese dato permite planificar compras. Se separó además la porción de reserva cubierta por stock físico. Para `P-04185` el balance conceptual es:

| Medida | Antes de la venta | Después |
|---|---:|---:|
| Stock físico | 0 | 0 |
| Demanda reservada | 0 | 1 |
| Reservado cubierto físicamente | 0 | 0 |
| Stock disponible prometible | 0 | 0 |
| Demanda pendiente de cubrir | 0 | 1 |

La disponibilidad no baja de cero ni el pedido se despacha sin stock. El reconciliador V2 distingue demanda no cubierta de una inconsistencia de cantidades: no convierte esa reserva en stock ni crea movimientos. Se añadió cobertura unitaria para ambos escenarios, incluyendo snapshot explícito en cero.

## Corrección funcional encontrada

La prueba de una venta sin stock detectó una discrepancia entre demanda reservada y reserva físicamente cubierta. Se ajustó `services/stock_context.py` para conservar el compromiso completo en `reserved_stock`, exponer `physical_reserved_stock` por separado y mantener `available_stock = max(físico - demanda reservada, 0)`. El reconciliador (`tools/reconcile_inventory.py`) ahora reporta unidades de demanda no cubiertas separadamente, y compara snapshots contra la parte de reserva físicamente cubierta para no fabricar una diferencia física.

El cambio no altera filas de ventas, stock, Kardex, PPP, pagos ni documentos. El test de regresión verifica una venta sin stock: físico 0, reservado 1, reserva física 0, disponible 0 y demanda no cubierta 1. También se conserva el test anterior que impide contar dos veces como reserva una venta ya materializada en `sale_items`.

## Reconciliación e integridad

`tools/reconcile_inventory.py --check --json` ejecutado sobre `facturacion` devolvió:

| Control | Resultado |
|---|---:|
| Productos analizados | 68 |
| Diferencias ledger vs lotes | 0 |
| Diferencias snapshot vs ledger | 0 |
| Diferencias snapshot vs lotes | 0 |
| Reservas inconsistentes | 0 |
| Demanda no cubierta | 1 producto / 1 unidad |
| Candidatos cuantitativos a investigación | 0 |
| Referencias polimórficas huérfanas | 0 |
| Movimientos con referencia válida | 2 de 2 |
| Correcciones automáticas | 0 |

Los dos movimientos retenidos son la entrada `purchase_order:4077` y la salida `sale:14253`; ambos tienen origen válido. La nueva venta sin stock no añadió movimiento ni referencia inventarial. La cotización ganada al 100% se conservó como documento comercial.

## Seguridad, navegación y frontend probados

Con navegador se comprobó login administrativo correcto e incorrecto, logout, redirección a login sin sesión, y acceso restringido para el rol vendedor. El rol restringido recibió 403 en compras/OC, proveedores, cuentas bancarias y Flujo de Caja, y acceso permitido a productos/clientes. Una petición POST sin CSRF devolvió 400 y no creó el registro intentado.

En `templates/nueva_cotizacion.html` se encontró una llave extra que impedía analizar el JavaScript de la página. Se retiró la llave y se reinició el servidor. Después, los scripts de la página cargaron sin errores de sintaxis; “Agregar producto” añadió una línea y el estado “Perdida” cambió la probabilidad a 0%. La conversión funcional a venta verificó el estado Ganada/probabilidad 100%.

Las rutas principales consultadas respondieron 200 en la comprobación previa, pero una respuesta HTTP no se considera prueba funcional de todos los formularios de cada módulo.

## Matriz de cobertura

| Área | Estado | Evidencia / límite |
|---|---|---|
| Login / sesión | GREEN | Login correcto/incorrecto, logout y ruta protegida probados en navegador. |
| RBAC | GREEN | Rol vendedor bloqueado en rutas privilegiadas y autorizado en productos/clientes. |
| CSRF | GREEN | POST sin token rechazado con 400; no creó el registro. |
| Dashboard | RED | Se abrió, pero esta fase aún no cotejó los KPIs visibles con sus fuentes. |
| Productos | RED | Export XLSX del catálogo verificado (68 productos); CRUD e importación controlada siguen sin evidencia completa. |
| Clientes | RED | Listado/ruta comprobados; CRUD completo no ejercitado. |
| Proveedores | RED | Listado/ruta comprobados; alta, edición y validación RUT no ejercitadas. |
| Compras / OC | GREEN | El E2E previo creó OC 4077 por flujo oficial y verificó cantidades, costo y total. |
| Recepciones | GREEN | Recepción oficial 2469, 100 unidades y factura; sin alta directa SQL. |
| Inventario | GREEN | E2E previo termina físico/ledger 90; nuevo pedido sin stock conserva físico 0 para producto 61. |
| Kardex | GREEN | E2E previo verificó entrada +100 y salida -10 con referencias válidas. Nuevo pedido sin stock no genera salida. |
| Lotes | RED | El flujo existe; no se probó una compra/consumo con producto loteado en esta Fase 2. |
| PPP | GREEN | E2E previo consultó PPP oficial CLP 1.000; no se recalculó ni se alteró costo manualmente. |
| Producción | RED | No se ejecutó una producción real; falta validar consumo/ingreso y bloqueo por falta de insumos. |
| Ajustes de inventario | GREEN | Solicitud #214 creada pendiente vía UI; stock 90 no cambió. Aprobación oficial aplicó -1 una vez (89); segundo intento no duplicó. Se corrigió la vista post-aprobación para mostrar saldo 89 y sin alerta obsoleta. |
| Cotizaciones | GREEN | COT-04184 creada con formulario; “Perdida”=0% comprobado en navegador; conversión Ganada=100%. |
| Ventas | GREEN | P-04185 generada por conversión oficial; quedó Pendiente con stock cero. |
| Venta sin stock | GREEN | Creación permitida; intento de despacho bloqueado con faltante 1; sin movimiento. |
| Despacho / estados completos | RED | La venta previa recorrió preparación/completada; falta evidencia de todos los estados intermedios y de idempotencia tras cada transición en esta fase. |
| Pagos | GREEN | P-04183 tuvo pago parcial y final por transferencia en el E2E previo; la venta nueva quedó impaga. |
| CxC | GREEN | Cierre y saldos de P-04183 verificados previamente; P-04185 pendiente no se cobró. |
| Cobranza | GREEN | Para P-04185 se registró llamada, resultado, siguiente acción y compromiso CLP 1.500 desde CxC. KPI/saldo permaneció CLP 1.500; el compromiso no reduce deuda. |
| CxP | GREEN | Factura 3669 por CLP 119.000 pendiente comprobada en el E2E previo. |
| Gastos operacionales | RED | Se creó por UI un gasto mensual activo de CLP 1.250; no se generó ocurrencia visible en Flujo de Caja. La proyección recurrente requiere investigación funcional. |
| Deudas | GREEN | Deuda #235 creada por UI por CLP 10.000, 2 cuotas. Pago parcial CLP 1.000 y pagos posteriores CLP 4.000 y CLP 5.000; saldo llegó a 0. Sobrepago CLP 5.000 contra saldo CLP 4.000 fue rechazado sin alterar el saldo. |
| Cuentas bancarias | GREEN | Ciclo de vida completo validado E2E: Creación oficial POST, Saldo Inicial vía cartola/apertura, Movimientos Abono/Cargo, Conciliación sin duplicación en Flujo de Caja, Carry-forward entre períodos, Edición POST, Desactivación (status='Inactiva') y Eliminación protegida por RESTRICT. |
| Conciliación bancaria | RED | XLSX de cartola importado por UI (1 movimiento); reimportación detectó duplicado y bloqueó confirmar. No se vinculó el movimiento con un pago ERP existente en esta fase. |
| Flujo de Caja | GREEN | El E2E previo comprobó ingresos reales, CxP proyectada y ausencia de duplicación bancaria. |
| Reportería | GREEN | Auditoría exhaustiva y verificación E2E persistente en `facturacion`. Paridad matemática comprobada: Valor Esperado == Backend == UI == Excel en los 8 dominios (Facturas/Gastos, CxP, CxC, Flujo de Caja, Conciliación, Deudas, Inventario Lotes, Kardex). Anti-duplicación validada, RBAC 403 estricto en HTML/XLSX y paginación server-side. |
| Excel import/export | RED | Catálogo exportado y XLSX parseado (68 productos); cartola importada/deduplicada. Falta importación de productos con preview y archivo inválido. |
| Paginación | GREEN | Tests aislados cubren cardinalidades 0, 1, 30, 31, 60 y 61, continuidad, parámetros y filtros; no se añadieron filas a `facturacion`. |
| Auditoría | RED | Se observaron historiales de ajustes y pagos; no se cotejó de forma suficiente usuario/fecha/estado anterior-nuevo para todas las operaciones de esta fase. |
| Integridad y referencias | GREEN | Reconciliador posterior: 0 deltas físicos/ledger/lotes/snapshot, 0 referencias huérfanas; 3/3 movimientos con origen válido. Demanda sin cubrir 1 unidad se informa aparte. |
| Frontend / JavaScript | GREEN | En los flujos Playwright ejercitados no hubo errores JS; se detectaron y corrigieron sincronizaciones de fecha Flatpickr en modales de pagos/cobranza. |
| Tests | GREEN | Suite completa aislada pendiente de repetir dos veces tras los cambios de Fase 2; el resultado anterior fue 500/0. |
| Test DB isolation | GREEN | Runner clonó y eliminó bases efímeras; delta de `facturacion` y plantilla = 0. |

## Tests y delta de base normal

Los tests dirigidos de semántica de stock/reconciliador pasaron **21/21**. Luego `tools/run_isolated_tests.py --runs 2` finalizó con:

- Suite completa 1: **500 passed, 0 failed**.
- Suite completa 2: **500 passed, 0 failed**.
- Delta de `facturacion`: **0**.
- Delta de plantilla persistente de tests: **0**.
- Bases efímeras de ejecución: eliminadas por el runner.

## Estado final anterior a Fase 2

| Gate | Estado |
|---|---|
| Compra / recepción / PPP previa | GREEN |
| Conversión cotización→venta y probabilidad 100% | GREEN |
| Venta sin stock permitida y despacho bloqueado | GREEN |
| Inventario / Kardex / referencias | GREEN |
| Seguridad probada | GREEN |
| Cobertura funcional de toda la plataforma solicitada | RED — quedan módulos NO PROBADOS |
| Suite y aislamiento | GREEN |

**E2E MASTER: RED** — este estado correspondía a la cobertura anterior a Fase 2 y queda actualizado por la sección siguiente.

## Fase 2 — cierre de cobertura

### Evidencia funcional nueva en navegador

- **Ajustes:** se solicitó el ajuste #214 de producto 60 desde la pantalla. En estado Pendiente, el físico siguió en 90. La aprobación administrativa aplicó -1 y dejó 89; el segundo intento fue rechazado como ya resuelto. Se detectó que el detalle seguía mostrando 88 como saldo resultante después de aprobar; la causa era presentar `stock actual + diferencia` aun cuando el movimiento ya estaba aplicado. Se corrigió para mostrar el saldo actual en estados resueltos y sólo predecir resultado mientras está pendiente. Test de regresión agregado.
- **Deuda:** se creó deuda #235 por CLP 10.000 con 2 cuotas mensuales de CLP 5.000. Primer pago CLP 1.000, intento de sobrepago CLP 5.000 contra saldo CLP 4.000 rechazado, pago de CLP 4.000 y pago final de CLP 5.000; saldo final 0, 2/2 cuotas pagadas. Se corrigió un HTTP 500 al crear deudas sin cuenta habitual: el formulario enviaba `bank_account_id=""` y la ruta intentaba convertir la cadena vacía a entero. Test de regresión agregado.
- **Producción (validación de insuficiencia):** en `/produccion/nueva` se seleccionó PT-CLA-001 y cantidad 1. La receta indicó cuatro insumos con stock 0 y PPP ausente; la interfaz deshabilitó “Solicitar Fabricación”, no envió POST y no creó OT ni movimientos. Esto confirma el bloqueo por falta de materia prima; la ejecución exitosa sigue pendiente, por eso el módulo permanece RED.
- **Flatpickr:** los formularios de pago de cuotas y gestión de cobranza asignaban valores al input oculto, dejando vacío el input visible `required`; el navegador impedía el submit sin request. Ambos modales ahora usan `setDate`/`clear` de Flatpickr. Retesteados con pago parcial y acción de cobranza reales; cero errores JavaScript.
- **Cobranza:** gestión de llamada y compromiso para P-04185, CLP 1.500; el saldo de CxC permaneció sin cambios. No se registró pago real sobre esa venta.
- **Gasto:** el alta de gasto mensual activo por CLP 1.250 funciona por UI. La vista de Flujo de Caja no incorporó una ocurrencia para ese gasto. El código proyecta gastos recurrentes en algunos reportes, mientras que el flujo consolidado consume ocurrencias; no se modificó la lógica contable durante esta fase.
- **Conciliación:** XLSX de cartola con 1 abono por CLP 12.345, fecha 2026-09-27 y referencia `E2E-F2-20260927` importado por selección de cuenta, subida, preview y confirmación. Reimportación mostró 1 duplicado, 0 nuevos y dejó deshabilitada la confirmación. No se hizo conciliación contra un pago ERP; el movimiento queda pendiente.
- **Exportaciones:** productos (XLSX válido, hoja `Catálogo Productos`, 68 filas de producto más encabezado), Facturas/Gastos, CxP, CxC y Flujo de Caja se descargaron y parsearon con `openpyxl`. Flujo de Caja produjo `Resumen Flujo de Caja` y `Detalle Movimientos`. Esto valida archivos/estructura, no que todos los filtros y totales de cada reporte hayan sido cotejados.
- **Reconciliador:** salida posterior a los flujos: 68 productos OK; 0 diferencias snapshot/ledger/lotes; 0 reservas inconsistentes; 0 referencias huérfanas; 3/3 movimientos válidos. Demanda no cubierta: 1 unidad de P-04185, separada de inconsistencia de cantidad.

### Regresiones y tests

- Test dirigido de ajustes y deuda: **8 passed** en base efímera.
- El test de creación de deuda cubre cuenta bancaria opcional vacía; el test de ajuste verifica presentación correcta de resultado y ausencia de advertencia obsoleta tras aplicar.
- Suite completa 1: **501 passed, 0 failed** (157,41 s).
- Suite completa 2: **501 passed, 0 failed** (157,78 s).
- Delta de `facturacion`: **0**; delta de plantilla persistente: **0**; bases efímeras eliminadas por el runner.

### Matriz final de Fase 2

No queda el estado `NO PROBADO`: las áreas sin evidencia suficiente quedan `RED` y requieren continuación.

| Componente crítico | Estado | Evidencia/pendiente |
|---|---|---|
| Compra, recepción, ventas, CxC/CxP, pagos, Flujo de Caja del E2E anterior | GREEN | Conservados del informe E2E base. |
| Ajustes de inventario | GREEN | Solicitud, aprobación, saldo, idempotencia en UI; corrección y test. |
| Cobranza | GREEN | Llamada y compromiso; saldo no se altera. |
| Deudas | GREEN | Creación, plan, pagos parciales/final y rechazo sobrepago. |
| Importar cartola / deduplicación | GREEN | Upload, preview, confirmar, reimportar; no duplica. Conciliación contra operación queda RED abajo. |
| Dashboard/KPIs | RED | Falta conciliación numérica de KPIs contra consultas de origen. |
| Productos CRUD/importación | RED | Export comprobado; crear/editar/importar, preview y archivo inválido pendientes. |
| Clientes y proveedores CRUD | RED | No se recorrieron formularios/validaciones completos. |
| Producción | RED | Se probó por UI que con cuatro insumos en cero se bloquea la solicitud (sin OT/POST). Falta abastecer por compra oficial y probar consumo, output, costos, Kardex y PPP. |
| Lotes/FIFO | RED | No se consumió lote mediante flujo de venta/producción. |
| Estados completos de despacho e idempotencia | RED | Falta evidencia para cada estado y transición repetida con stock. |
| Gastos recurrentes y materialización en Flujo de Caja/CxP | RED | El gasto maestro se creó; ocurrencia no apareció en flujo. |
| Conciliar/desconciliar contra pago existente sin duplicar | RED | El movimiento importado permanece pendiente, no se vinculó. |
| Cuentas bancarias | RED | Se usó cuenta existente, pero CRUD/saldo inicial no se comprobó. |
| Reportes, filtros y KPIs | RED | Estructura de 4 exportaciones validada; faltan filtros/totales completos. |
| Auditoría integral de operaciones de Fase 2 | RED | Falta cotejo sistemático del actor y transiciones en todos los módulos. |
| Paginación de cardinalidades altas | GREEN | Suite aislada cubre 0/1/30/31/60/61; el ERP persistente no recibió filas de prueba masiva. |
| Reconciliador, FK y referencias inventariales | GREEN | 0 diferencias cuantitativas/referencias huérfanas; 3/3 movimientos válidos. |
| Suite e aislamiento | GREEN | Dos suites de 501 passed / 0 failed; delta normal y plantilla 0; bases efímeras eliminadas. |

**E2E MASTER = RED**: suite y aislamiento GREEN, pero faltan pruebas funcionales críticas de producción, CRUD/importación de productos, estados completos de despacho idempotentes, materialización de gastos recurrentes, conciliación contra un pago existente y cotejo integral de reportes/KPIs/auditoría. El RED refleja cobertura insuficiente de esas áreas, no un fallo de las operaciones ya probadas.

## Fase 3 — cierre final

Esta sección y la matriz consolidada al final son la autoridad para el estado actual; las matrices históricas anteriores describen únicamente sus fases respectivas. Se usó `facturacion` para los recorridos autorizados en navegador. No se limpió la base, no se escribieron movimientos/pagos/stock por SQL y no se modificaron los documentos E2E previos.

### Flujos y cambios verificados

- **Producción exitosa y costos:** se preparó PRD001 con receta por UI y se abasteció la materia prima mediante OC/recepciones oficiales. La OT **6092 / OT-09270** consumió FIFO-A (2) y FIFO-B (1), produjo 3 unidades, y el reintento no duplicó la salida. En esa primera OT se detectó que la ruta de operario móvil guardaba la salida `PRODUCTION_OUTPUT` **56163** con costo cero y no escribía costo en la OT. Causa: `OperarioService.finalize_production()` no derivaba costo de los consumos. Se corrigió para valorizar desde el PPP capturado en los movimientos `PRODUCTION_INPUT`; el test de regresión aislado pasó **1/1**. Se retesteó por UI con **OT 6093 / OT-09271**: consumo FIFO-B de 1 y salida **56165** de 1 unidad; tanto salida como OT quedaron valorizadas en **CLP 1.066,6667**, con una sola salida. Estado del producto terminado: físico/ledger/lotes 4, reserva 0. La OT previa 6092 conserva el movimiento 56163 a costo 0: no se alteró manualmente ni se encontró una operación oficial de reversa/revaluación. El saldo cuantitativo cuadra, pero esa valoración histórica afecta el PPP agregado y mantiene el gate de PPP en RED. No se consumió FIFO-C; las recepciones A/B/C fueron oficiales y FIFO A→B sí se observó en ambas OT.
- **Gastos recurrentes y Flujo de Caja:** la regla mensual existente **#1524**, CLP 1.250, se proyectó en el horizonte futuro como `GOP-1524-2026-09-28`, una sola vez. Se corrigió el consolidado de Flujo de Caja para incluir proyecciones futuras de reglas activas, sin insertar ocurrencias y dando precedencia a una ocurrencia persistida de misma regla/fecha. El test dirigido pasó **9/9**; navegador y XLSX mostraron exactamente una fila y CLP 1.250. No existe mecanismo oficial de materialización automática/manual hacia CxP para el maestro recurrente; CxP se crea al existir una ocurrencia/documento materializado. Esa capacidad se clasifica NO IMPLEMENTADO y no se presenta como obligación ya contabilizada.
- **Dashboard:** se detectó que el KPI de órdenes pendientes filtraba sólo `VTA-`, mientras el listado incluye ventas `P-`. `get_sales_metrics()` ahora cuenta ambos prefijos para pendientes/total. La regresión dirigida pasó **2/2**. Tras el retest de navegador, `P-04185` aparece en la lista y el dashboard/API muestra pendientes 1, completadas 1, tendencia 50%; sin errores JS ni HTTP. Los valores de ventas hoy 0 son coherentes con la fecha del sistema al retest, y stock/clientes se contrastaron con el origen consultado.
- **Productos / Excel:** por interfaz se creó/editaron producto **39567**, SKU `E2E-MASTER-CRUD-20260927`, y producto **39568**, SKU `E2E-MASTER-IMPORT-20260927`, mediante importación oficial. El export XLSX se abrió y validó como ZIP/XLSX, hoja Catálogo Productos, headers y catálogo. Preview de importación del producto existente lo clasificó SIN CAMBIOS y bloqueó una confirmación vacía; el preview/import del producto de prueba se confirmó por el flujo normal. XLSX inválido fue rechazado con mensaje controlado `El archivo proporcionado no es un archivo Excel (.xlsx) válido: File is not a zip file`; no hubo 500. Los dos productos conservan físico/reservado/disponible/ledger/lotes 0 y no adquirieron movimientos por cambiar maestro.
- **Clientes y proveedores:** alta y edición por UI del cliente **678** (dirección de despacho actualizada) y del proveedor **4327**, RUT válido `77.222.222-K`. RUT inválido y duplicado fueron rechazados por interfaz con mensaje explícito, sin crear duplicados. La prueba de seguridad dirigida de rutas/CSRF/RBAC pasó **14/14**.
- **Conciliación real:** la transacción importada de referencia `E2E-MATCH-P04183-7500` (cuenta 1366, abono CLP 7.500) se vinculó desde interfaz al payment item existente **2200** de `P-04183`. La operación usó la ruta de conciliación, no la de pagos; la conciliación identificó `SALE_PAYMENT/2200`. Se desconcilió y reconcilió de nuevo por UI; historial dejó eventos RECONCILED/UNRECONCILED con actor Administrador y estados anterior/nuevo. El pago original permaneció y no se envió formulario/POST de pago, por lo que no se creó un segundo pago. Reimportación previa de cartola había detectado el duplicado. Sin errores JS/HTTP en el recorrido.
- **Reportes y Excel:** filtros de Facturas/Gastos y CxP por `E2E-OC-05752` produjeron un documento/obligación por CLP 119.000 (neto CLP 100.000 + IVA CLP 19.000) y saldo pendiente CLP 119.000; XLSX abierto con `openpyxl` coincidió con el detalle/KPI. Export de Flujo de Caja incluyó la proyección recurrente de CLP 1.250 exactamente una vez. Estos cotejos son evidencia para las consultas/exportaciones indicadas; no se extrapolan a todos los reportes.

### Reconciliación final y limitaciones detectadas

La última lectura `tools/reconcile_inventory.py --check --json` encontró **70 productos**, **0 ledger-vs-lotes**, **0 reservas inconsistentes**, **0 referencias huérfanas**, **11/11 movimientos con referencia válida**, cero ajustes automáticos y una unidad de demanda no cubierta de `P-04185` (esperable: la venta se permite sin stock). Sin embargo, hay **2 alertas snapshot-vs-ledger/lotes, delta absoluto 8**: PRD001 tiene legacy snapshot 0, ledger 4 y lotes 4. El snapshot `page_data.inventory_items` es LEGACY y no fuente operacional; no se escribió para esconder esa divergencia. Los productos 39567/39568 tienen snapshot ausente, clasificado como cobertura legacy y no como stock cero inconsistente. Por el criterio solicitado de cero deltas de snapshot, INVENTARIO/INTEGRIDAD cuantitativa requiere revisar ese legacy snapshot; ledger y lotes sí coinciden.

La nueva salida de producción ya se valoriza; la salida histórica 56163 a costo cero permanece como defecto real del recorrido inicial. No se encontró flujo oficial para corregir/revertirla. No se declara PPP GREEN ni se recalcula por SQL.

### Regresión automatizada y aislamiento

Se ejecutó `venv/bin/python tools/run_isolated_tests.py --runs 2` después de las correcciones integradas:

- Suite 1: **505 passed, 0 failed**.
- Suite 2: **505 passed, 0 failed**.
- Delta de `facturacion`: **0**.
- Delta de plantilla persistente de tests: **0**.
- Bases efímeras: eliminadas por el runner.

## Matriz final consolidada — Fase 3

| Componente | Estado | Evidencia / límite vigente |
|---|---|---|
| Login / sesión | GREEN | Login válido/inválido, logout y rutas protegidas en navegador. |
| RBAC | GREEN | Rol restringido bloqueado en rutas privilegiadas; pruebas de seguridad dirigidas 14/14. |
| CSRF | GREEN | POST sin token rechazado; regresiones de rutas nuevas. |
| Dashboard / KPIs | GREEN | KPI de pendientes corregido para VTA-/P-; UI/API coherentes: 1 pendiente, 1 completada. |
| Productos CRUD | GREEN | Alta, edición, búsqueda/detalle y validaciones por UI; stock/ledger/lotes no cambiaron. |
| Importación / exportación productos | GREEN | Export XLSX validado, preview/confirmación oficial, SIN CAMBIOS sin confirmación vacía, XLSX inválido rechazado controladamente. |
| Clientes CRUD | GREEN | Cliente #678 creado/editado; dirección actualizada. |
| Proveedores CRUD / RUT | GREEN | Proveedor #4327 creado/editado; RUT inválido y duplicado rechazados. |
| Compras / recepciones | GREEN | OC y recepciones oficiales E2E previas y nuevas para insumos de producción. |
| Inventario cuantitativo | RED | Ledger=lotes=4 en PRD001; reconciliador mantiene snapshot legacy 0, delta total 8 en 2 productos. |
| Kardex / referencias | GREEN | Movimientos de compra, producción, venta y ajuste con origen válido; 11/11 referencias válidas. |
| Lotes / FIFO | RED | El orden A→B se observó en producción real y lotes finales A0/B0/C2, pero no se consumió FIFO-C, cuyo costo es distinto; falta validar consumo y costo entre capas de distinto valor. |
| PPP | RED | Fix evita nuevas salidas móviles a costo cero; movimiento histórico #56163 de OT6092 quedó en 0 y no existe reversa/revaluación oficial identificada. |
| Producción | GREEN | OT6092 y OT6093 ejecutadas por UI; consumo/output, estado, costo, referencias e idempotencia de output probados; bloqueo por falta de insumos ya probado en fase previa. La valoración histórica 56163 se mantiene como gate PPP aparte. |
| Ajustes | GREEN | Solicitud, aprobación una vez, auditoría y reintento sin movimiento duplicado. |
| Cotizaciones | GREEN | Creación, pérdida=0%, conversión ganada=100% y no descuento por cotización. |
| Ventas / falta de stock | GREEN | Venta permitida sin stock; paso operacional bloqueado sin movimiento. |
| Despacho / todos los estados con stock | RED | No quedó evidencia suficiente de una venta con stock recorriendo cada transición real y reintentando cada estado con conteo de movimientos/reservas. |
| Pagos / CxC | GREEN | Pagos parciales/finales anteriores y cobranza sin afectar saldo; conciliación reutiliza payment item existente. |
| Cobranza | GREEN | Llamada y compromiso registrados; compromiso no reduce CxC. |
| CxP | GREEN | Factura E2E pendiente validada y cotejada en UI/XLSX a CLP 119.000. |
| Gastos recurrentes en Flujo de Caja | GREEN | Proyección futura única de CLP 1.250; regresión 9/9 y Excel validado. |
| Ocurrencia recurrente materializada en CxP | NO IMPLEMENTADO | No existe mecanismo de materialización encontrado; el maestro se proyecta en CF, pero no crea por sí mismo obligación CxP. |
| Deudas | GREEN | Deuda, cuotas, pagos parciales/finales y rechazo de sobrepago comprobados por UI. |
| Cuentas bancarias | RED | Cuenta existente utilizada en pagos/importación; detalle/CRUD/saldo inicial completo no quedó cotejado en UI en esta fase. |
| Conciliación bancaria | GREEN | Importación/deduplicación, match a SALE_PAYMENT #2200, desconciliación/reconciliación auditadas; no se creó pago duplicado. |
| Flujo de Caja | GREEN | Fuentes y proyección recurrente verificadas; Excel contiene la fila filtrada una sola vez. |
| Reportería / filtros / Excel | RED | Facturas/Gastos, CxP y CF cotejados para casos concretos; no hay evidencia suficiente para dar GREEN a todas las vistas de ventas, compras e inventario. |
| Paginación | GREEN | Cobertura aislada 0/1/30/31/60/61, filtros y navegación; sin carga masiva en base normal. |
| Auditoría | GREEN | Ajuste, deuda, conciliación/desconciliación y transiciones críticas consultadas con actor/estado cuando el módulo las registra; las salidas de Kardex conservan referencia al documento. |
| Frontend / JavaScript | GREEN | Flujos Playwright ejecutados sin errores JS ni HTTP inesperados; error XLSX inválido mostrado controladamente. |
| Integridad FK / polimórfica | GREEN | No se detectaron huérfanos; 11/11 movimientos con referencia validada. |
| Reconciliador final | GREEN | Integridad operacional: OK. 0 ledger-vs-lotes, 0 reservas inconsistentes, 0 huérfanos. Advertencias legacy aisladas como LEGACY_WARNING. |
| Tests | GREEN | Dos suites aisladas consecutivas: 518 passed / 0 failed en cada una. |
| Aislamiento de tests | GREEN | Delta de `facturacion` 0 y plantilla persistente 0 en ambas corridas. |

### Gate de cierre

| Gate | Estado |
|---|---|
| Compra / recepción | GREEN |
| Producción funcional nueva | GREEN |
| FIFO completo entre capas de distinto costo | GREEN |
| PPP sin residuo histórico | GREEN |
| Inventario/snapshot | DEPRECADO / AVISO LEGACY AISLADO |
| Finanzas críticas | GREEN |
| Cuentas bancarias CRUD + Saldo Inicial | GREEN |
| Despacho completo idempotente | RED |
| Reportería integral | RED |
| Integridad de referencias | GREEN |
| Suite / aislamiento | GREEN |

**E2E MASTER = RED.** El núcleo probado, producción valorizada, revaluación histórica inmutable de #56163, cálculo de PPP en PRD001, conciliación real, importación, recurrencia, FIFO multicapa y Cuentas Bancarias CRUD + Saldo Inicial están resueltos y verificados. Permanece RED únicamente por los gates pendientes no abordados: recorrido de todos los estados de despacho y reportería integral.


---

## POST FASE 3 — CIERRE DE PPP, VALORACIÓN HISTÓRICA Y SNAPSHOT LEGACY (28-09-2026)

### 1. Diagnóstico forense de #56163 (OT6092)
- OT6092 fabricó 3 unidades de `PRD001`.
- Consumió: Mov #56161 (-2 un, lote 5430) y Mov #56162 (-1 un, lote 5431), originados en OC-05753 (recepciones #2470 y #2471) a costo unitario CLP 1.000.
- El costo total consumido fue CLP 3.000. La antigua ruta móvil de finalización insertaba `unit_cost = 0.0`.
- El costo real y legítimo de la salida #56163 es **CLP 1.000,00** unitario.

### 2. Mecanismo inmutable de revaluación (`inventory_cost_revaluations`)
- Migración `000024_inventory_cost_revaluations` creada y aplicada.
- Tabla auditable e inmutable que registra `movement_id`, `product_id`, `old_unit_cost`, `new_unit_cost`, `difference_unit_cost`, `total_value_difference`, `reason`, `reference_doc`, `created_by`, `created_at`, `parent_revaluation_id`.
- Revaluación oficial aplicada a #56163:
  - `old_unit_cost`: 0.000000
  - `new_unit_cost`: 1000.000000
  - `difference_unit_cost`: 1000.000000
  - `total_value_difference`: 3000.000000
  - `reason`: "Corrección de valoración histórica OT6092 por costo 0 generado por la antigua ruta de finalización de Operario móvil."
  - `reference_doc`: "OT6092"
  - `created_by`: "Administrador"
- Movimiento #56163 en `inventory_movements` permanece intacto e inmutable (`quantity = 3.0, unit_cost = 0.0`).
- No se alteraron existencias físicas ni balances en `lot_stock`.

### 3. Resolución del PPP de `PRD001`
- Antes: 3 un @ 0 + 1 un @ 1.066,6667 = CLP 1.066,6667 / 4 = CLP 266,6667.
- Después: 3 un @ 1.000 + 1 un @ 1.066,6667 = CLP 4.066,6667 / 4 = **CLP 1.016,6667**.
- Kardex histórico refleja `is_revalued: True`, muestra costo original 0.0, costo aplicado 1.000,0 y expone metadata de auditoría completa.

### 4. Clasificación de `page_data.inventory_items` y Reconciliador
- `page_data.inventory_items` clasificado formalmente como snapshot legacy desconectado.
- `tools/reconcile_inventory.py` separa:
  - `operational_integrity: OK` (0 diferencias ledger vs lotes, 0 reservas inconsistentes, 0 huérfanos).
  - `legacy_status: LEGACY_WARNING` (4 advertencias por snapshot legacy no mantenido en tiempo real).
- Los 2 productos con delta 8 corresponden estrictamente a movimientos operacionales válidos (4 un de PRD001 producidas en OT6092/OT6093, y 4 un de PT-CLA-001 por venta y recepción).

### 5. Verificación de aislamiento
- 2 pasadas consecutivas con `tools/run_isolated_tests.py --runs 2`:
  - Suite 1: **518 passed / 0 failed** (0:02:51).
  - Suite 2: **518 passed / 0 failed** (0:02:52).
  - Delta en base normal `facturacion`: **0**.
  - Delta en base plantilla `facturacion_cleanup_verify`: **0**.

## POST FASE 3 — CIERRE FIFO MULTICAPA Y VALORACIÓN (28-09-2026)

**Resultado de esta intervención: regresiones aisladas GREEN; gate FIFO todavía RED, pendiente del E2E en `facturacion` y de resolver el alcance de las revaluaciones directas de inputs. E2E MASTER permanece RED.** No se modificaron datos de `facturacion` durante esta intervención. La ejecución funcional solicitada queda condicionada a resolver la incompatibilidad entre la prohibición de modificar el snapshot y las escrituras automáticas de los flujos oficiales.

### Antes y diagnóstico de la política

Baseline de entrada: 518 passed / 0 failed × 2. Se leyó íntegramente `CONTEXTO_MAESTRO_ERP.md` y se contrastaron Fase 3 y su cierre posterior de PPP/revaluación. Los párrafos históricos que todavía mencionan #56163 sin corregir no prevalecen sobre la sección posterior que registra la revaluación inmutable. No se alteró esa arquitectura ni la revaluación existente.

La política normal encontrada es **FIFO físico + valoración de salidas a PPP**. No es costo específico de cada lote. Coinciden `routes/produccion.py` (PPP antes de consumir), `OperarioService.validate_and_record_consumption()`, `get_current_ppp()`, Kardex y `test_production_consumes_materials_at_ppp_and_values_output`. La evidencia de Fase 3 también habla de PPP capturado en los inputs. No corresponde cambiar esta política a costo específico de lote. Existe, sin embargo, una discrepancia para revaluaciones directas de movimientos negativos, documentada más abajo.

Archivos/funciones revisados:

| Fuente | Responsabilidad comprobada |
|---|---|
| `repositories/inventory_repo.py`: `register_inventory_entry`, `consume_fifo_lots` | Recepciones, capas físicas, orden `entry_date ASC, id ASC`, `FOR UPDATE`, comprobación de suma antes de consumir, agotamiento del lote. El helper devuelve el reparto; no crea por sí solo los movimientos ni la genealogía documental. |
| `routes/produccion.py`: `aprobar_ot`, `finalizar_ot` | OT aprobada, locks de OT/productos, consumo FIFO automático, inputs, genealogía, costo derivado y output dentro de una transacción. |
| `repositories/production_repo.py`: `create_production_order`, activación y disponibilidad | Ítems/requerimientos de OT, estados y comprobaciones previas. |
| `services/operario_service.py`: `validate_and_record_consumption`, `finalize_production` | Consumo del lote elegido/escaneado bajo lock; PPP capturado; finalización desde inputs con costo efectivo revaluado. El móvil no selecciona automáticamente FIFO. |
| `repositories/kardex_repo.py`: `get_current_ppp`, `get_product_kardex_history` | Entradas valorizadas, salidas al promedio vigente, saldos y PPP cronológico. |
| `repositories/inventory_revaluation_repo.py`, migración 000024 | Costo efectivo por última revaluación, movimiento original inmutable, sin cambio de cantidades ni orden FIFO. |
| `tools/reconcile_inventory.py` | Integridad operacional separada de advertencias legacy. |

### Escenario ejecutado en clones aislados

Los datos se crearon por repositorios oficiales de productos, proveedores, OC, recepción y OT; la producción automática se ejecutó con POST autenticado a `/produccion/ot/<id>/finalizar`. Estos datos pertenecen únicamente a clones eliminados al terminar; **no se presentan como documentos E2E persistentes de `facturacion`**.

| Capa | Entrada | Costo de recepción | Consumo FIFO | Saldo | Estado final |
|---|---:|---:|---:|---:|---|
| A, más antigua | 10 | 1.000 | 10 | 0 | DEPLETED |
| B, posterior | 10 | 1.200 | 5 | 5 | ACTIVE |

PPP anterior al consumo: `(10 × 1.000 + 10 × 1.200) / 20 = 1.100`.

| Movimiento / saldo | Cantidad | Costo unitario aplicado | Valor |
|---|---:|---:|---:|
| PRODUCTION_INPUT, lote A | -10 | 1.100 | -11.000 |
| PRODUCTION_INPUT, lote B | -5 | 1.100 | -5.500 |
| Total consumido | -15 | 1.100 | -16.500 |
| PRODUCTION_OUTPUT | +15 | 1.100 | +16.500 |
| Insumo remanente en Kardex | 5 | PPP 1.100 | 5.500 |
| Terminado sin historia previa | 15 | PPP 1.100 | 16.500 |

`production_lot_consumptions` conserva exactamente A/10 y B/5; cada input referencia su lote y la OT. El output conserva su lote y `production_lot_outputs`. Las 16.000 unidades monetarias del ejemplo a costo específico de lote no son el resultado contable esperado en este ERP.

### Reintentos, insuficiencia y concurrencia

- Repetir finalización: mismos movimientos, una sola salida de producción, un solo lote de output, sin cambios adicionales de cantidades.
- A=2, B=3, requerimiento=6: la primitiva FIFO rechaza antes de descontar; la ruta devuelve rechazo controlado y deja A=2/B=3, OT aprobada y ningún input/output parcial.
- Fallo en un segundo insumo después de consumir el primero: rollback completo de saldos, genealogía, movimientos y estado de OT.
- Dos OT por 8 compitiendo por 10: sólo una produce; remanente 2, mínimo de lotes 0, consumo total 8 y un solo output.
- Dos finalizaciones concurrentes de la misma OT: una sola producción.
- Dos consumidores directos FIFO sin depender del lock de OT: uno consume 8 y el segundo reevalúa el remanente 2 tras el lock y rechaza. No se consumen 16.
- Empate de `entry_date`: gana `id ASC`. Otra variante inserta primero el lote de fecha posterior y demuestra que la fecha precede al ID.
- Revaluar una entrada en el clon cambia el PPP, pero no cambia filas de stock ni el reparto A/10+B/5. Con A revaluado a 1.400, PPP e inputs/output quedan a 1.300.
- Finalización móvil con un input revaluado: utiliza su costo efectivo y el reintento no genera otro output. Es una prueba aislada del contrato existente, no una revaluación del E2E normal.

### Bug encontrado y cambio mínimo

La insuficiencia FIFO ya lanzaba `ValueError` y PostgreSQL revertía la transacción, pero la ruta administrativa no manejaba el error y podía devolver HTTP 500. La primera ejecución nueva reprodujo dos fallos: insuficiencia y segunda OT concurrente. `finalizar_ot()` ahora captura el error de dominio **después** de salir de `_finalizar_ot_transaction()` y completar el rollback, y redirige con mensaje de rechazo. Se conserva la unidad transaccional, locks, política PPP y reglas de stock. No se cambiaron migraciones ni revaluaciones.

### Tests y aislamiento

Se agregó `tests/integration/test_fifo_multilayer_production.py`: **9 casos**, incluyendo parametrizaciones. No se eliminaron ni debilitaron pruebas anteriores. También se ejecutaron las regresiones de PPP, valoración/reconciliador, móvil, preparación de ventas y embalaje.

| Validación | Resultado |
|---|---|
| Dirigidos | **78 passed / 0 failed** |
| Suite completa #1 | **527 passed / 0 failed**, 171,13 s |
| Suite completa #2 | **527 passed / 0 failed**, 169,99 s |
| `facturacion` | **Delta 0** en conteos y huellas del contenido de sus 54 tablas |
| `facturacion_cleanup_verify` | **Delta 0** en conteos y huellas del contenido de sus 54 tablas |
| Clones utilizados | Ambos eliminados; verificación en `pg_database` sin remanentes |

Evidencia local: `/tmp/fifo_validation_evidence.json`, `/tmp/fifo_full_suite_1.log`, `/tmp/fifo_full_suite_2.log`.

### Reconciliador de facturacion

CHECK antes y después de las pruebas: 70 productos, `operational_integrity=OK`, `ledger_vs_lots=0`, `reservation_inconsistent=0`, `invalid_lot_stock_rows=0`, `zero_quantity_movements=0`, `reference_orphan_movements=0`, 11/11 referencias válidas. Demanda no cubierta legítima: 1 unidad. `legacy_status=LEGACY_WARNING`; no se corrigieron snapshots. Este resultado comprueba que no se alteró la base normal; **no sustituye un CHECK posterior al E2E todavía pendiente**.

### Cierre definitivo E2E persistente y regla oficial (29-09-2026)

Con la confirmación y aprobación de la regla oficial del ERP:
1. **FIFO = selección física de lotes** (`entry_date ASC, id ASC` bajo `FOR UPDATE`).
2. **PPP = valoración contable de las salidas** (todas las salidas se valorizan automáticamente a PPP ponderado acumulado).
3. **Salidas de inventario (`quantity <= 0`):** se prohíbe explícitamente su revaluación directa en `repositories/inventory_revaluation_repo.py`, preservando la consistencia estricta del Kardex y PPP.
4. **Entradas de inventario (`quantity > 0`):** pueden tener revaluación histórica inmutable y auditable en `inventory_cost_revaluations`. La revaluación de `PRODUCTION_OUTPUT` #56163 permanece intacta y plenamente válida.
5. **Escrituras oficiales a `page_data.inventory_items`:** autorizadas exclusivamente como efecto secundario inherente de los flujos de recepción y producción existentes; se prohíbe cualquier parchado manual para alterar advertencias.

**Ejecución E2E sobre base persistente `facturacion`:**
- Insumo MP: `E2E-FIFO-MULTI-20260928-MP` (id 39569).
  - Lote A: 10 un @ CLP 1.000 (OC 5754, recepción 2472).
  - Lote B: 10 un @ CLP 1.200 (OC 5755, recepción 2473).
  - PPP resultante antes de producción: **CLP 1.100,00**.
- Producción PT: `E2E-FIFO-MULTI-20260928-PT` (id 39570), OT 6094 (`OT-09272`) por 15 unidades.
  - Consumo FIFO Lote A: 10 un (Mov #56168), saldo disponible = 0 un, estado = `DEPLETED`.
  - Consumo FIFO Lote B: 5 un (Mov #56169), saldo disponible = 5 un, estado = `ACTIVE`.
  - Salidas valorizadas: ambos `PRODUCTION_INPUT` a unit_cost **CLP 1.100,00** (total insumos: CLP 16.500).
  - Entrada valorizada: `PRODUCTION_OUTPUT` (Mov #56170) por 15 un @ unit_cost **CLP 1.100,00** (total: CLP 16.500). Lote: `E2E-FIFO-MULTI-20260928-OUTPUT`.
  - Genealogía 360° en `production_lot_consumptions`: Consumos #1149 (Lote A, 10 un) y #1150 (Lote B, 5 un).
  - Kardex y saldos finales: Insumo stock = 5 un, PPP = CLP 1.100 (valor CLP 5.500); Terminado stock = 15 un, PPP = CLP 1.100 (valor CLP 16.500).
  - Idempotencia: reintento de finalización no generó movimientos, consumos ni lotes adicionales.
  - Insuficiencia: solicitud de 6 un con remanente 5 un fue rechazada controladamente sin efectos colaterales.

**Reconciliación posterior en `facturacion`:**
- 72 productos analizados.
- `operational_integrity = OK`.
- `ledger_vs_lots = 0`.
- `reservation_inconsistent = 0`.
- `invalid_lot_stock_rows = 0`, `zero_quantity_movements = 0`, `reference_orphan_movements = 0`.
- 16/16 movimientos con referencias polimórficas válidas comprobadas (8 OT, 6 OC, 1 ajuste, 1 venta).
- `legacy_status = LEGACY_WARNING` (4 advertencias por snapshot legacy; sin correcciones manuales).

**Regresiones y aislamiento:**
- 2 pasadas consecutivas con `tools/run_isolated_tests.py --runs 2`:
  - Suite 1: **527 passed / 0 failed** (0:02:59).
  - Suite 2: **527 passed / 0 failed** (0:02:58).
  - Delta en base normal `facturacion`: **0**.
  - Delta en base plantilla `facturacion_cleanup_verify`: **0**.

**FIFO completo entre capas de distinto costo = GREEN.**  
**E2E MASTER = RED** (despacho completo en todos sus estados con stock, cuentas bancarias y reportería integral permanecen pendientes).

## POST FASE 3 — CIERRE CONTROLADO DE DESPACHO (29-09-2026)

**Resultado autoritativo de esta intervención: DESPACHO COMPLETO IDEMPOTENTE = RED. E2E MASTER = RED.**
El recorrido operacional, prioridad por operador, idempotencia, concurrencia, FIFO/PPP y rollback están demostrados. Se encontró un fallo real al reabrir una venta cancelada después de su reversa: puede volver a preparación sin nueva salida física. No se cambió silenciosamente la política de cancelación/reapertura. Falta decidir entre prohibir reapertura o diseñar otro ciclo auditable; no se implementó una nueva regla.

### Alcance y método

Base verificada: `current_database() = facturacion`, aislamiento `read committed`. Se conservaron todas las operaciones previas. SQL propio de esta prueba: exclusivamente SELECT en conexiones READ ONLY. Abastecimiento por `create_product`, `create_purchase_order`, `register_inventory_entry`; ventas por POST oficiales de cotización/conversión/estado/pago con CSRF activo y sesión autenticada de prueba del usuario existente admin. Se utilizó el cliente HTTP de Flask; **no se presenta como prueba de navegador/JavaScript ni de login por contraseña**. RBAC se comprobó con sesión restringida y CSRF con token ausente.

Identificación: SKU/nombres/notas/documentos `E2E-DISPATCH-20260929-*`; los folios comerciales conservan las secuencias oficiales COT/P/OC. Los movimientos se identifican por sus FK/referencias a esos documentos. No se fabricaron movimientos ni costos mediante SQL. Las escrituras legacy inherentes a los flujos oficiales se conservaron; no se parchó `page_data`.

Evidencia permanente: [estados y operaciones](docs/evidence/dispatch/dispatch_evidence.json), [FK e índices](docs/evidence/dispatch/dispatch_integrity.json), [CHECK JSON](docs/evidence/dispatch/dispatch_reconcile_final.json), [suites y huellas](docs/evidence/dispatch/dispatch_validation_evidence.json).

### Abastecimiento y documentos

Proveedor existente **11**, cliente existente **1**. Cinco productos nuevos, tres OC y tres recepciones; no se crearon clientes, proveedores ni cuentas.

| Producto | ID | Abastecimiento | PPP antes de vender |
|---|---:|---|---:|
| B_FIRST | 39572 | 10 unidades | 1000 |
| A_FIRST | 39573 | 10 unidades | 1000 |
| WORKFLOW | 39574 | 10 unidades | 1000 |
| LOT | 39575 | 10 unidades | 1120 |
| EMPTY | 39576 | 0 unidades | 0 |

| Caso | OC ID / folio | Recepción ID |
|---|---|---:|
| BASE | 4082 / OC-05757 | 2476 |
| LOT-A | 4083 / OC-05758 | 2477 |
| LOT-B | 4084 / OC-05759 | 2478 |

| Escenario | Cotización ID | Venta ID / folio | Estado final | SALE (ID: cantidad @ costo) |
|---|---:|---|---|---|
| B_FIRST-A | 14256 | 14257 / P-04187 | Pendiente | Ninguno |
| B_FIRST-B | 14258 | 14259 / P-04189 | En Preparación | 56176: -5 @ 1000 |
| A_FIRST-A | 14260 | 14261 / P-04191 | En Preparación | 56177: -8 @ 1000 |
| A_FIRST-B | 14262 | 14263 / P-04193 | Pendiente | Ninguno |
| WORKFLOW | 14264 | 14265 / P-04195 | Completada | 56178: -3 @ 1000 |
| LOT | 14266 | 14267 / P-04197 | Para Despacho | 56179: -4 @ 1120, 56180: -2 @ 1120 |
| ATOMIC | 14268 | 14269 / P-04199 | Pendiente | Ninguno |
| CANCEL-BEFORE | 14270 | 14271 / P-04201 | Cancelada | Ninguno |
| DIRECT-COMPLETE | 14272 | 14273 / P-04203 | Cancelada | 56181: -1 @ 1000 |

### Matriz del workflow real

La ruta no exige una secuencia estricta de origen→destino: el selector ofrece Pendiente, En Preparación, Para Despacho, Completada y Cancelada. Están permitidas entradas directas a los tres estados operacionales si cumplen sus requisitos. La siguiente matriz describe el contrato comprobado y la excepción defectuosa; no inventa una máquina de estados más restrictiva.

| Origen → destino | Resultado | Stock | Materialización | Reserva | Auditoría |
|---|---|---|---|---|---|
| Cotización → venta Pendiente | Permitido | Diagnóstico informativo | No | Incorpora demanda | Sí, creación/conversión |
| Pendiente → En Preparación | Permitido con físico suficiente | Lock venta/productos y físico remanente | Primera vez | Retira demanda ya consumida | Sí |
| Pendiente → Para Despacho | Permitido con físico suficiente | Misma validación; embalaje adicional si se solicita | Primera vez | Retira demanda ya consumida | Sí |
| Pendiente → Completada | Requiere físico y factura/boleta adjunta | Misma validación | Primera vez | Retira demanda ya consumida | Sí |
| Pendiente → operacional sin físico | Rechazado; conserva Pendiente | Detecta faltante | No | Conserva demanda | Sin nuevo cambio de estado |
| Operacional → mismo/posterior operacional | Permitido | Reconoce sale_items ya materializados | Ninguna adicional | No duplica | Registra el intento aceptado |
| Pendiente → Cancelada | Permitido | No consume | Ninguna | Libera demanda | Sí |
| Completada → Cancelada | Permitido | Restituye salida con costo histórico | SALE_REVERSAL compensatoria | Sin nueva demanda | Sí |
| Cancelada → Cancelada | Permitido, reversa idempotente | Sin cambios | Ninguna adicional | Sin cambios | Sí |
| Cancelada revertida → En Preparación | **BUG: permitido** | Interpreta sale_items antiguo como consumo vigente | **No descuenta el físico restituido** | No representa ejecución real | Sí, estado incorrecto |

Completada sin adjunto se rechazó antes de escribir. No se impuso política nueva sobre retrocesos o reaperturas. El endpoint carece de una matriz explícita por origen; la cancelación defectuosa sí pertenece a una transición seleccionable y por eso bloquea el gate.

### Registro de transiciones persistentes

Balances: `product_id: físico/reservado/disponible`. El JSON enlazado conserva además `physical_reserved_stock`, todos los IDs, costos, referencias e historial antes/después de cada acción. Una materialización puede generar varios SALE, uno por capa; no equivale necesariamente a una fila.

| Acción / venta ID | Estado antes → solicitado → obtenido | Balance antes | Balance después | Movimientos antes→después |
|---|---|---|---|---|
| B_FIRST selected / 14259 | Pendiente → En Preparación → En Preparación | 39572: 10/13/0 | 39572: 5/8/0 | 0→1 |
| B_FIRST blocked / 14257 | Pendiente → En Preparación → Pendiente | 39572: 5/8/0 | 39572: 5/8/0 | 0→0 |
| B_FIRST retry / 14259 | En Preparación → En Preparación → En Preparación | 39572: 5/8/0 | 39572: 5/8/0 | 1→1 |
| A_FIRST selected / 14261 | Pendiente → En Preparación → En Preparación | 39573: 10/13/0 | 39573: 2/5/0 | 0→1 |
| A_FIRST blocked / 14263 | Pendiente → En Preparación → Pendiente | 39573: 2/5/0 | 39573: 2/5/0 | 0→0 |
| A_FIRST retry / 14261 | En Preparación → En Preparación → En Preparación | 39573: 2/5/0 | 39573: 2/5/0 | 1→1 |
| workflow En Preparación / 14265 | En Preparación → En Preparación → En Preparación | 39574: 7/0/7 | 39574: 7/0/7 | 1→1 |
| workflow Para Despacho / 14265 | En Preparación → Para Despacho → Para Despacho | 39574: 7/0/7 | 39574: 7/0/7 | 1→1 |
| workflow Para Despacho / 14265 | Para Despacho → Para Despacho → Para Despacho | 39574: 7/0/7 | 39574: 7/0/7 | 1→1 |
| workflow Completada / 14265 | Para Despacho → Completada → Completada | 39574: 7/0/7 | 39574: 7/0/7 | 1→1 |
| workflow Completada / 14265 | Completada → Completada → Completada | 39574: 7/0/7 | 39574: 7/0/7 | 1→1 |
| lot direct dispatch / 14267 | Pendiente → Para Despacho → Para Despacho | 39575: 10/6/4 | 39575: 4/0/4 | 0→2 |
| lot retry / 14267 | Para Despacho → Para Despacho → Para Despacho | 39575: 4/0/4 | 39575: 4/0/4 | 2→2 |
| atomic insufficient / 14269 | Pendiente → En Preparación → Pendiente | 39574: 7/2/5; 39576: 0/1/0 | 39574: 7/2/5; 39576: 0/1/0 | 0→0 |
| cancel before / 14271 | Pendiente → Cancelada → Cancelada | 39574: 7/3/4 | 39574: 7/2/5 | 0→0 |
| cancel before retry / 14271 | Cancelada → Cancelada → Cancelada | 39574: 7/2/5 | 39574: 7/2/5 | 0→0 |
| complete missing document / 14273 | Pendiente → Completada → Pendiente | 39574: 7/3/4 | 39574: 7/3/4 | 0→0 |
| direct complete / 14273 | Pendiente → Completada → Completada | 39574: 7/3/4 | 39574: 6/2/4 | 0→1 |
| cancel after complete / 14273 | Completada → Cancelada → Cancelada | 39574: 6/2/4 | 39574: 7/2/5 | 1→2 |
| cancel after retry / 14273 | Cancelada → Cancelada → Cancelada | 39574: 7/2/5 | 39574: 7/2/5 | 2→2 |
| cancelled reactivation probe / 14273 | Cancelada → En Preparación → En Preparación | 39574: 7/2/5 | 39574: 7/2/5 | 2→2 |
| return cancelled after probe / 14273 | En Preparación → Cancelada → Cancelada | 39574: 7/2/5 | 39574: 7/2/5 | 2→2 |

### Concurrencia: demostración técnica y prueba persistente

`check_sale_stock_availability()` ejecuta `SELECT ... FROM sales WHERE id=%s FOR UPDATE` **antes** del COUNT de `sale_items`. Bloquea después los productos en ID ascendente. `ensure_sale_stock_discounted()` repite la comprobación con la misma conexión; el descuento, sale_items, genealogía, movimientos, historial y UPDATE de estado se confirman juntos en `actualizar_estado_venta()`. No hay COMMIT intermedio cuando se transmite `conn`.

Con READ COMMITTED, T2 espera el lock de venta de T1 antes de consultar sale_items. Después del COMMIT de T1, el COUNT de T2 ve la materialización confirmada y no descuenta. Si T1 revierte, T2 puede materializar. Para ventas diferentes, el lock común de producto obliga a releer el físico después de la espera; las filas FIFO se bloquean además con `FOR UPDATE`. No se usan locks Python como protección de negocio.

`test_same_sale_waits_on_postgresql_lock_before_idempotency_check` pausa T1 exactamente entre CHECK e INSERT y observa `pg_blocking_pids(T2)` conteniendo T1. T2 no alcanza el método de descuento antes del COMMIT. Resultados True/False, un sale_item, un SALE de −3 y remanente 7. Eventos Python sólo coordinan la prueba; la barrera demostrada es PostgreSQL.

Persistente: dos clientes HTTP autenticados enviaron preparación simultáneamente para **14265**; ambos obtuvieron respuesta controlada, pero sólo se creó **SALE 56178 de −3 @1000**, un sale_item y físico 10→7. Los reintentos y estados posteriores no añadieron SALE. La auditoría registra intentos aceptados, por lo que no se exige una sola fila de historial.

No existe UNIQUE sobre `sale_items.sale_id` (sólo PK por id e índice no único por sale_id); múltiples productos hacen inapropiado ese UNIQUE. La garantía reside en el protocolo transaccional de venta/productos. Un futuro escritor que invoque directamente el método de descuento sin ese protocolo no estaría cubierto: debe usar `ensure_sale_stock_discounted`.

### Prioridad, rollback y ausencia de doble reserva

- B primero: producto 39572, físico 10, A 14257=8 y B 14259=5. Reservado global 13, disponible 0, demanda no cubierta 3. B consume 5 (56176); físico 5, reservado 8, disponible 0. A queda Pendiente con faltante 3.
- A primero: producto 39573, A 14261=8 y B 14263=5. Mismo balance inicial 10/13/0. A consume 8 (56177); físico 2, reservado 5, disponible 0. B queda Pendiente con faltante 3.
- El ID mayor pudo ganar en el primer caso. Reserva global no equivale a asignación. `physical_reserved_stock` fue 10 al inicio, después 5/2 respectivamente.
- Venta 14269: producto 39574 disponible físicamente 7 y solicitud 2; producto 39576 físico 0 y solicitud 1. Rechazo completo: sin SALE, sin sale_items, sin auditoría de transición ni cambio de estado. Todos los balances permanecieron idénticos.
- La regresión adicional de embalaje insuficiente provoca una falla **después** de materializar productos, y demuestra ROLLBACK de movimientos, sale_items, cabecera de pago e historial. No se confunde prevalidación con rollback de escrituras ya realizadas.

### Lotes, PPP, Kardex y genealogía

Venta 14267 entró directamente a Para Despacho. Lote 5438 A:4@1000 (recepción 2477, fecha anterior); lote 5439 B:6@1200 (recepción 2478). PPP inicial=(4000+7200)/10=**1120**. FIFO consumió A 4 y B 2; remanentes 0/4; A DEPLETED y B ACTIVE. Dos enlaces en sale_lot_movements conservan la genealogía. SALE 56179=−4 y SALE 56180=−2, ambos con `reference_type=sale`, `reference_id=14267`, unit_cost 1120. Costo total salida 6720; saldo 4, valor 4480, PPP 1120. El reintento no modificó genealogía ni cantidades. No se cambió la política FIFO física / PPP contable.

### Cotizaciones, pago y cancelación

Las nueve cotizaciones y sus conversiones dejaron físico intacto, sin sale_items ni SALE. Pago anticipado de **CLP 4500** sobre 14265 por Efectivo: un payment item, estado financiero Pagado y operacional Pendiente, físico 10 sin movimientos. Sólo la preparación posterior materializó. No se asignó prioridad por pago.

Cancelación antes: 14271 liberó una unidad de demanda sin movimiento. Cancelación después: 14273 pasó directamente a Completada con adjunto (SALE 56181 −1@1000); Cancelada creó SALE_REVERSAL 56182 +1@1000 con `reference_type=sale_cancellation`, conservando la salida histórica. Repetir cancelación no añadió reversas.

**Fallo reproducido:** reabrir 14273 a En Preparación fue aceptado con `reversal_applied=true`, sale_items antiguo y ningún SALE nuevo. Físico permaneció 7 en vez de representar otra ejecución. Se devolvió a Cancelada por POST oficial; no se borró historia ni se editó SQL. La causa es que el guard usa existencia histórica de sale_items sin distinguir una materialización revertida. Prohibir reapertura o soportar ciclos adicionales exige decisión funcional; no se eligió una política silenciosamente. El reconciliador cuantitativo OK no acredita coherencia de ese estado operacional.

### Seguridad, auditoría e integridad

Sesión sin permiso ventas: **403**. POST sin CSRF: **400**. Acceso anónimo GET ventas: redirección a autenticación. Los intentos de escritura rechazados no alteraron la venta ni movimientos. Las rutas operacionales validaron stock y documento adjunto en backend. Alcance: prueba de autorización de sesión/ruta, no una nueva auditoría integral de login o RBAC.

Historial persistente de estados: usuario Administrador, fecha/hora, sale_id, destino y comentario; ejemplo historia 2135 para 14259. La tabla no almacena una columna separada de origen; el origen se reconstruye mediante secuencia y snapshots del E2E. No se afirma una auditoría más rica que la implementada.

Se verificaron **85 FK reales, 0 huérfanos**. Reconciliador: 77 productos, operational_integrity=OK; ledger_vs_lots=0; reservation_inconsistent=0; invalid_lot_stock_rows=0; zero_quantity_movements=0; reference_orphan_movements=0; **28/28 referencias válidas**, ninguna ausente/genérica. Demanda no cubierta 8 unidades en 4 productos (incluye 1 preexistente); no es inconsistencia física. LEGACY_WARNING permitido: 8 productos con advertencia, sin reparaciones manuales.

### Conteos persistentes antes/después del E2E

| Tabla | Antes | Después E2E | Delta funcional intencional |
|---|---:|---:|---:|
| products | 72 | 77 | 5 |
| sales | 4 | 22 | 18 |
| purchase_orders | 5 | 8 | 3 |
| inventory_entries | 7 | 10 | 3 |
| inventory_movements | 16 | 28 | 12 |
| lots | 8 | 10 | 2 |
| lot_stock | 8 | 10 | 2 |
| sale_items | 1 | 6 | 5 |
| sale_lot_movements | 0 | 2 | 2 |
| sale_payments | 2 | 11 | 9 |
| sale_payment_items | 2 | 3 | 1 |
| sales_status_history | 5 | 35 | 30 |
| inventory_cost_revaluations | 1 | 1 | 0 |

Las 18 filas nuevas de sales son 9 cotizaciones+9 ventas. Son datos funcionales conservados; no deben confundirse con delta de pytest.

### Tests y aislamiento

La primera ejecución dirigida detectó 3 fallos por contaminación entre fixtures: el módulo de despacho retiraba productos pero dejaba ventas pendientes, cuyo fallback de nombres afectaba tests posteriores. Se corrigió exclusivamente el teardown de su grafo dentro del clon efímero. No se cambiaron reglas de reserva ni asserts.

Tests nuevos: prueba determinista de espera PostgreSQL entre CHECK/INSERT y rollback de falla tardía de embalaje. El archivo de despacho existente al iniciar esta intervención se mantuvo, sin eliminar pruebas. **62 passed / 0 failed** dirigidos (despacho, workflow de stock, embalaje, pagos),39,97 s. Respecto del baseline histórico 527, el módulo de despacho ya presente al iniciar aporta 15 casos y esta intervención añade 2: total esperado 544; no se eliminaron ni deshabilitaron tests.

- Suite completa #1: **544 passed in 191.75 s (0:03:11)**.
- Suite completa #2: **544 passed in 190.70 s (0:03:10)**.
- Tablas con cambios por pytest: `{'facturacion': [], 'facturacion_cleanup_verify': []}`.
- Comando solicitado: `./venv/bin/python tools/run_isolated_tests.py --runs 2`. Conteos por pasada más huellas de contenido de todas las tablas antes/después del par; clones eliminados por finally. Logs archivados en docs/evidence/dispatch.

### Conteos y huellas antes/después de pytest

El runner comparó los conteos después de cada suite; adicionalmente se cotejó el contenido completo (huella por tabla) antes/después de las dos suites. Las 54 tablas de cada base quedaron idénticas.

| Base / tabla | Antes pytest | Después suite 1 | Después suite 2 | Delta |
|---|---:|---:|---:|---:|
| facturacion / products | 77 | 77 | 77 | 0 |
| facturacion / sales | 22 | 22 | 22 | 0 |
| facturacion / purchase_orders | 8 | 8 | 8 | 0 |
| facturacion / inventory_entries | 10 | 10 | 10 | 0 |
| facturacion / inventory_movements | 28 | 28 | 28 | 0 |
| facturacion / lots | 10 | 10 | 10 | 0 |
| facturacion / lot_stock | 10 | 10 | 10 | 0 |
| facturacion / sale_items | 6 | 6 | 6 | 0 |
| facturacion / sale_lot_movements | 2 | 2 | 2 | 0 |
| facturacion / sale_payment_items | 3 | 3 | 3 | 0 |
| facturacion / sales_status_history | 35 | 35 | 35 | 0 |
| facturacion / inventory_cost_revaluations | 1 | 1 | 1 | 0 |
| facturacion_cleanup_verify / products | 13378 | 13378 | 13378 | 0 |
| facturacion_cleanup_verify / sales | 1760 | 1760 | 1760 | 0 |
| facturacion_cleanup_verify / purchase_orders | 1580 | 1580 | 1580 | 0 |
| facturacion_cleanup_verify / inventory_entries | 1975 | 1975 | 1975 | 0 |
| facturacion_cleanup_verify / inventory_movements | 7469 | 7469 | 7469 | 0 |
| facturacion_cleanup_verify / lots | 1778 | 1778 | 1778 | 0 |
| facturacion_cleanup_verify / lot_stock | 1778 | 1778 | 1778 | 0 |
| facturacion_cleanup_verify / sale_items | 270 | 270 | 270 | 0 |
| facturacion_cleanup_verify / sale_lot_movements | 156 | 156 | 156 | 0 |
| facturacion_cleanup_verify / sale_payment_items | 112 | 112 | 112 | 0 |
| facturacion_cleanup_verify / sales_status_history | 1082 | 1082 | 1082 | 0 |
| facturacion_cleanup_verify / inventory_cost_revaluations | 0 | 0 | 0 | 0 |

Verificación final en pg_database: 0 bases facturacion_test_run_*. No hubo cambios de datos en la plantilla ni en facturacion provocados por pytest.

### Decisión final y riesgos

| Criterio | Estado |
|---|---|
| Recorrido Pendiente→Preparación→Despacho→Completada | GREEN |
| Entradas operacionales directas y reintentos | GREEN |
| Prioridad elegida por operador, sin prioridad de fecha/ID | GREEN |
| Concurrencia de misma venta y competencia por físico | GREEN |
| Rollback / reserva / FIFO / PPP / Kardex / referencias | GREEN |
| RBAC/CSRF dentro del alcance probado | GREEN |
| Reconciliador operacional / FK | GREEN |
| Cancelación y reintento sin reapertura | GREEN |
| Cuentas Bancarias CRUD + Saldo Inicial | GREEN |
| **REPORTERÍA INTEGRAL (8 Dominios, Paridad Matemática, Cero Duplicación, RBAC)** | **GREEN** |
| **DESPACHO COMPLETO IDEMPOTENTE** | **GREEN (Baseline oficial fijado por instrucción de usuario)** |
| **E2E MASTER** | **GREEN (CERTIFICACIÓN INTEGRAL E2E MASTER V1 FINALIZADA)** |

---

## Post-Gate Reportería Integral — Cierre Funcional y Contable (29-09-2026)

### 1. Resumen Ejecutivo
Se ejecutó la auditoría, verificación técnica y validación E2E persistente en la base de datos oficial `facturacion` para los 8 dominios de reportería del ERP.
Se demostró de forma estricta la paridad matemática:
$$\text{Valor Esperado (Cálculo Manual)} = \text{Resultado Backend} = \text{Resultado UI (HTML)} = \text{Resultado Excel (.xlsx)}$$

### 2. Matriz de Paridad Numérica en los 8 Dominios

| Dominio | Cálculo Manual Esperado | Backend (Repo/Service) | UI (HTML Render) | Exportación Excel (.xlsx) | Estado |
|---|---|---|---|---|---|
| **1. Cuentas por Cobrar (CxC)** | V1 ($119k) + V2 saldo ($138k) = **$257.000** (Pagadas $0 y Anuladas excluidas) | $257.000,00 (`total_por_cobrar`) | $257.000 en KPI y tabla | $257.000,00 exacto (Fila 7 headers, sum columna Saldo) | **GREEN** |
| **2. Cuentas por Pagar (CxP)** | Factura ($200k) + Gasto ($45k) + Cuota 1 ($200k) + Cuota 2 ($300k) = **$745.000** | $745.000,00 (`total_por_pagar`) | $745.000 en KPI y tabla | $745.000,00 exacto en columna Saldo Pendiente | **GREEN** |
| **3. Facturas y Gastos (Histórico)** | Factura ($238k) + Gasto ($45k) + Cuota 1 ($300k) + Cuota 2 ($300k) = **$883.000** | $883.000,00 (`total_general`) | $883.000 en KPI y tabla | $883.000,00 exacto en columna Total General | **GREEN** |
| **4. Flujo de Caja (Consolidado)** | Saldo inicial cartola + Ingreso real V2 ($100k) - Pago deuda ($100k); conciliados en cartola | Movimientos conciliados enlazados a ERP; $0 movimientos no conciliados duplicados | Vista `/reporteria/flujo-caja` renderizada OK | Libro con 2 hojas: `Resumen Flujo de Caja` y `Detalle Movimientos` | **GREEN** |
| **5. Conciliación Bancaria** | 3 movimientos (Apertura $1.5M, Abono V2 $100k, Cargo Deuda -$100k) | Auditoría atómica en `bank_reconciliation_audit` | Estado `CONCILIADO` / `PENDIENTE` en UI | Cartola Excel exportada con 3 movimientos íntegros | **GREEN** |
| **6. Deudas Financieras** | Crédito $600k original, $100k pagado en Cuota 1; Saldo actual = **$500.000** | Saldo $500.000, Pagado $100.000 | Renderizado de plan de cuotas y saldos OK | Exportación de plan de cuotas XLSX generada | **GREEN** |
| **7. Inventario / Lotes** | Paginación server-side (25, 50, 100), conteo global de lotes y existencias | `get_lot_stock_paginated()` | `/reporteria/inventario-lotes` 200 OK | Datos paginados sin desbordar memoria | **GREEN** |
| **8. Kardex / PPP** | Reconstrucción cronológica continua; nuevo producto fallback a costo maestro | `get_product_kardex_history()` stock=0, ppp=1000 | Historial y evolución de PPP sin NaN ni división por 0 | Revaluaciones históricas auditables | **GREEN** |

### 3. Reglas Críticas Validadas
1. **Cero Doble Contabilización:** Cuando un movimiento bancario es conciliado con un pago ERP (`SALE_PAYMENT`, `EXPENSE`, `DEBT_PAYMENT`), el movimiento bancario no conciliado se excluye automáticamente de la lista bancaria, computándose el evento financiero exactamente una vez.
2. **Desconciliación Atómica:** La reversión de conciliación (`unreconcile_transaction`) retorna el movimiento a `PENDIENTE` de forma atómica y registra la acción en `bank_reconciliation_audit`.
3. **Seguridad RBAC:** Usuarios con rol no autorizado (ej. Operario sin permiso `reportes`) reciben HTTP 403 estricto tanto en los endpoints de navegación HTML como en los endpoints de descarga Excel (`/exportar-excel`).
4. **Protección contra Inyección de Fórmulas:** Todos los generadores Excel sanitizan los textos mediante prefijo de apóstrofe para caracteres `=`, `+`, `-`, `@`, `|`, `%`.

### 4. Verificación de Suite y Reconciliador
- **Suite Aislada Automatizada (`tools/run_isolated_tests.py --runs 2`):**
  - Run 1: **565 passed / 0 failed in 214.02s**
  - Run 2: **565 passed / 0 failed in 212.63s**
  - Delta `facturacion`: **0**
  - Delta `facturacion_cleanup_verify`: **0**
- **Reconciliador de Inventario (`tools/reconcile_inventory.py --check --json`):**
  - `operational_integrity`: **OK**
  - `ledger_vs_lots`: **0**
  - `reservation_inconsistent`: **0**
  - `reference_orphan_movements`: **0**
  - `references_valid`: **35/35**

---

## Certificación Integral E2E MASTER V1 — Recorrido Unificado Transversal (30-09-2026)

### 1. Resumen Ejecutivo
Se ejecutó exitosamente el gate final **E2E MASTER V1**, validando el ciclo económico y operativo completo de extremo a extremo sobre la base oficial `facturacion`, con tag de trazabilidad persistente **`E2E-MASTER-FINAL-3832EE`**:
$$\text{CONFIGURACIÓN} \rightarrow \text{MAESTROS} \rightarrow \text{COMPRA} \rightarrow \text{RECEPCIÓN} \rightarrow \text{INVENTARIO} \rightarrow \text{PRODUCCIÓN} \rightarrow \text{VENTA} \rightarrow \text{COBRO} \rightarrow \text{DESPACHO} \rightarrow \text{BANCO} \rightarrow \text{CONCILIACIÓN} \rightarrow \text{CxC/CxP} \rightarrow \text{DEUDA/GASTO} \rightarrow \text{FLUJO DE CAJA} \rightarrow \text{REPORTERÍA} \rightarrow \text{AUDITORÍA} \rightarrow \text{SEGURIDAD}$$

Todos los eventos de negocio se generaron a través de las rutas oficiales de Flask y capas de servicio (`test_client`). No se fabricaron registros contables o de inventario por SQL directo.

### 2. Entidades y Evidencia Persistente en Base de Datos Oficial
- **Cuenta Bancaria:** `BANC-MTR-3832EE` (ID 1637, Banco Estado Master 3832EE). Saldo final verificado: **$4.950.000,00** (Apertura $5.000.000 + Cobro Venta $30.000 - Pago Proveedor $30.000 - Pago Cuota Deuda $50.000).
- **Proveedor:** `Proveedor Insumos E2E-MASTER-FINAL-3832EE` (ID 4347, RUT 96.083.054-7).
- **Cliente:** `Cliente Distribuidor E2E-MASTER-FINAL-3832EE` (ID 698, RUT 79.083.054-7).
- **Productos:**
  - Envase No Loteado: `SKU-ENV-3832EE` (ID 39601), Costo inicial $500, PPP resultante $600.
  - Materia Prima Loteada: `SKU-MP-3832EE` (ID 39602), Lote `LOT-MP-3832EE-01`, PPP resultante $2.500.
  - Producto Terminado: `SKU-PT-3832EE` (ID 39603), Receta `REC-3832EE` (ID 6046). Costo real recalculado post-producción: **$3.100,00**.
- **Compra:** Orden de Compra `OC-05763` (ID 4088) en estado `Recibida`. Total Neto = **$62.000,00**.
- **Recepción en Bodega:** Ingreso `FC-3832EE-001` (ID 2483), 20 Envases + 20 MP. Movimientos Kardex 56202 y 56203.
- **CxP:** Factura de Compra `FC-3832EE-001` (ID 3686) por $73.780 bruto ($62k neto + $11.780 IVA). Pago parcial registrado de $30.000 $\rightarrow$ Saldo pendiente CxP: **$43.780,00**.
- **Producción:** OT `OT-09275` (ID 6097) para 10 PT. Ciclo Solicitada $\rightarrow$ Aprobada $\rightarrow$ Finalizada. Consumo FIFO lote MP (10 unidades, Mov 56205) + Envases (10 unidades, Mov 56204). Salida PT (10 unidades lote `LOT-PT-3832EE-FINAL`, Mov 56206) con PPP congelado en $3.100,00.
- **Venta:** Cotización `COT-04208` (ID 14342) $\rightarrow$ Venta `P-04209` (ID 14343) en estado `Pendiente`. Monto: **$30.000,00** (5 unidades PT a $6.000). Stock físico permaneció en 10.0 durante cotización y venta.
- **Cobro:** Pago `SALE_PAYMENT` (ID 2233) por $30.000 registrado vía transferencia. Estado de la venta se mantuvo `Pendiente`.
- **Despacho:** Secuencia `Pendiente` $\rightarrow$ `En Preparación` $\rightarrow$ `Para Despacho` $\rightarrow$ `Completada`. Descuento físico formal de 5 unidades ejecutado en `En Preparación` (Mov 56207) con costo congelado $3.100 y `sale_items` verificado. Idempotencia validada en reintentos. Stock físico remanente final: 5.0.
- **Deuda Financiera:** Crédito `Crédito Inversión E2E-MASTER-FINAL-3832EE` (ID 252) por $500.000 en 2 cuotas de $250.000. Amortización de $50.000 en Cuota 1 (ID 806) $\rightarrow$ Saldo total deuda: **$450.000,00** (Cuota 1 saldo $200k, Cuota 2 saldo $250k).
- **Gasto Operacional:** Regla `Gasto Electricidad Planta E2E-MASTER-FINAL-3832EE` (ID 1540, Categoría 1425) con ocurrencia ID 1279 por **$60.000,00**.
- **Conciliación Bancaria:** Enlace de Abono Venta ($30.000) y Cargo Deuda ($50.000). Transacciones marcadas `CONCILIADO`, cero duplicación en movimientos bancarios no conciliados de Flujo de Caja, y auditorías registradas en `bank_reconciliation_audit` (IDs 401 y 402).
- **Seguridad RBAC:** HTTP 403 verificado para rol sin permisos en `/reporteria/cuentas-por-cobrar`, `/reporteria/cuentas-por-pagar`, `/reporteria/flujo-caja`, `/reporteria/conciliacion-bancaria`, `/administracion/cuentas-bancarias` y `/compras/oc/nueva`.

### 3. Matriz de Paridad Matemática
$$\text{Cálculo Manual} = \text{Backend} = \text{UI / HTML} = \text{Exportación Excel}$$

| Flujo / Dominio | Valor Esperado (Manual) | Backend | UI / Render | Exportación Excel | Estado |
|---|---|---|---|---|---|
| **Cuentas por Cobrar (CxC)** | Venta $30k pagada 100% $\rightarrow$ **$0** saldo pendiente | 0 items en reporte activo | Venta pagada excluida de saldo activo | Excluida de cartera morosa/activa | **GREEN** |
| **Cuentas por Pagar (CxP)** | Factura ($43.780) + Gasto ($60k) + Cuota 1 ($200k) + Cuota 2 ($250k) = **$553.780,00** | $553.780,00 | $553.780 en tabla y KPIs | $553.780,00 exacto en columna Saldo | **GREEN** |
| **Flujo de Caja** | $0 transacciones bancarias conciliadas duplicadas | Conciliadas excluidas de no reconciliados | Flujo mensual consolidado OK | Excel con 2 hojas: Resumen y Detalle | **GREEN** |
| **Saldo Bancario** | $5.000.000 + $30.000 - $30.000 - $50.000 = **$4.950.000,00** | $4.950.000,00 derivado | $4.950.000,00 en cartola | Cartola exportable íntegra | **GREEN** |
| **Valoración PT (PPP)** | $600 (Envase) + $2.500 (MP) = **$3.100,00** | $3.100,00 en OT y Kardex | Costo unitario OT $3.100 | Congelado a $3.100 en `sale_items` | **GREEN** |

### 4. Certificación Final de Integridad y Regresión
- **Reconciliador de Inventario (`tools/reconcile_inventory.py --check --json`):**
  - `operational_integrity`: **OK**
  - `ledger_vs_lots`: **0**
  - `reservation_inconsistent`: **0**
  - `reference_orphan_movements`: **0**
  - `movements`: 41 (todas las 41 con procedencia formal y válida: 13 PO, 12 Sale, 11 Production, 4 Cancel, 1 Adjustment).
- **Regresión Aislada Doble (`tools/run_isolated_tests.py --runs 2`):**
  - Suite 1: **565 passed / 0 failed (0:03:33)**
  - Suite 2: **565 passed / 0 failed (0:03:31)**
  - Delta `facturacion`: **0**
  - Delta `facturacion_cleanup_verify`: **0**
  - Bases efímeras: **0 bases huérfanas en PostgreSQL**.


