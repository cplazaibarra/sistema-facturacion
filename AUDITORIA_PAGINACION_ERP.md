# Auditoría de paginación del ERP

Fecha: 2026-09-27. Estado: inventario previo a modificaciones de código.

Baseline ejecutada: **434 PASSED / 0 FAILED**, 137,18 s. Checkout con numerosos cambios previos: no se han descartado ni atribuido a esta tarea.

Se revisaron rutas, templates, repositories, services y fachada db.py. Los conteos siguientes son conteos de tablas fuente, NO conteos filtrados de cada pantalla. Se tomaron mientras la suite estaba ejecutándose, por lo que pueden incluir fixtures transitorios. No se inventan tiempos, payload ni mediciones de queries.

Hallazgo crítico: Flujo de Caja en este checkout NO pagina en PostgreSQL: `cash_flow_repo.paginate_movements` recorta una lista completa. Los tests existentes verdes no demuestran LIMIT SQL. Lo mismo ocurre en Kardex, productos comprados y reportes financieros.

## Matriz

| Pantalla | Ruta | Template | Repository | Tabla/Fuente | Cantidad actual (fuentes) | ¿Carga todo? | ¿Tiene paginación? | ¿Server-side SQL? | Riesgo | Acción recomendada |
|---|---|---|---|---|---|---|---|---|---|---|
| Productos | /productos | productos | products_repo | products | products: 11301 | No detalle; sí selectores | 30 | Sí | P1 | Hecho: límite fijo, filtros SQL y Excel sin cambios; revisar otros selectores |
| Ventas | /ventas | ventas | sales_repo | sales | sales: 1683 | No detalle; clientes completos | 25/50/100 | Sí | P1 | Fijar 30; mantener batch de pagos e historial y KPIs |
| Cotizaciones | /ventas/cotizaciones | cotizaciones | routes/ventas.py | sales | sales: 1683 | Sí | Visual | No | P0 | WHERE de todos los filtros; COUNT/agregados; LIMIT; batch sólo IDs visibles |
| Clientes | /ventas/clientes | clientes | clients_repo | clients | clients: 10 | Sí | No | No | P1 | Búsqueda y paginación SQL; existe API de búsqueda remota |
| Proveedores | /proveedores | proveedores | suppliers_repo | suppliers | suppliers: 2222 | No | 25/50/100 | Sí | P1 | Fijar 30 y validar continuidad |
| Órdenes de compra | /compras/oc | compras_oc | purchases_repo | purchase_orders | purchase_orders: 1413 | No detalle | 25/50/100 | Sí | P1 | Fijar 30; conservar agregados |
| Productos comprados | /compras/productos-comprados | compras_productos_comprados | reporting_repo | purchase_order_items | purchase_order_items: 1523 | Sí | Python slice | No | P0 | Agrupar por producto en SQL, paginar grupos; totales completos y CSV completo |
| Recepciones recientes | /ingreso-mercaderia | ingreso_mercaderia | inventory_repo | inventory_entries | inventory_entries: 1830 | No detalle; sí OC y proveedores | LIMIT 20 | Acotado sin navegación | P1 | Paginar historial; documentar selectores completos |
| Facturas proveedores / CxP operativa | /compras/cuentas-por-pagar | compras_cuentas_pagar | purchases_repo | purchase_invoices | purchase_invoices: 434 | No para detalle; selectores antes completos | 30 | Sí | P0 | Facturas paginadas; KPIs separados en SQL; proveedores/cuentas remotos; validar Excel |
| Inventario / Stock | /inventario | inventario | legacy_repo + kardex_repo + inventory_repo | products,inventory_movements,lot_stock | products: 11301; inventory_movements: 6360; lot_stock: 1508 | Sí | Visual | No | P0 | Paginar proyección legacy SQL; preservar reservas y PPP; lotes independientes |
| Kardex catálogo | /kardex | kardex | kardex_repo | products,inventory_movements | products: 11301; inventory_movements: 6360 | Sí | Python slice | No | P0 | Separar cálculo histórico y detalle; SQL para filtros/COUNT/LIMIT |
| Kardex producto | /kardex?product_id=ID | kardex | kardex_repo | inventory_movements | inventory_movements: 6360 | Sí histórico completo | Python slice | No | P0 | Preservar recurrencia PPP exacta; paginar detalle SQL |
| Lotes y vencimientos | /reporteria/inventario-lotes | reporte_inventario_lotes | inventory_repo | lot_stock | lot_stock: 1508 | No | 25/50/100 | Sí | P1 | Fijar 30; añadir desempate ls.id al orden |
| Ajustes de inventario | /inventario/ajustes | ajustes_inventario | inventory_adjustments_repo | inventory_adjustment_requests | inventory_adjustment_requests: 4 | Sí | No | No | P1 | Mover búsqueda Python a WHERE y paginar sin tocar aprobaciones |
| Órdenes de producción | /produccion | produccion | production_repo | production_orders | production_orders: 1618 | No detalle; sí productos selector | 25/50/100 | Sí | P1 | Fijar 30; revisar batch y catálogos auxiliares |
| Recetas | /produccion/recetas | recetas | production_repo | product_recipes | product_recipes: 1389 | No | 25/50/100 | Sí | P1 | Fijar 30; conservar batch de componentes |
| Calendario producción | /produccion/calendario | calendario_produccion | production_repo | production_orders | production_orders: 1618 | Ventana semanal + pendientes | No | Ventana | P1 | Conservar semana completa; paginar cola sin programar |
| Listas de precios | /administracion/listas-precios | listas_precios | products_repo | products | products: 11301 | No | 25/50/100 | Sí | P1 | Fijar 30; costos por lote |
| Gastos operacionales | /administracion/gastos-operacionales | gastos_operacionales | operational_expenses_repo | operational_expenses | operational_expenses: 16 | Sí | No | No | P1 | Paginar maestro conservando filtros SQL |
| Facturas de compra y gastos | /reporteria/facturas-compras-gastos | reporte_facturas_compras_gastos | reporting_repo | purchase_invoices,operational_expense_occurrences | purchase_invoices: 434; operational_expense_occurrences: 15 | Sí | Python slice | No | P0 | UNION con reglas actuales; filtros SQL; agregados separados; Excel completo |
| CxP financiera | /reporteria/cuentas-por-pagar | reporte_cuentas_por_pagar | reporting_repo | purchase_invoices,operational_expense_occurrences | purchase_invoices: 434; operational_expense_occurrences: 15 | Sí | Python slice | No | P0 | Saldo y vencimientos equivalentes en SQL antes de LIMIT; KPIs/Excel completos |
| CxC financiera | /reporteria/cuentas-por-cobrar | reporte_cuentas_por_cobrar | reporting_repo | sales,sale_payment_items | sales: 1683; sale_payment_items: 76 | Sí | Python slice | No | P0 | Conservar fallback de pagos y cobranza; filtrar SQL antes de LIMIT |
| Conciliación bancaria | /reporteria/conciliacion-bancaria | conciliacion_bancaria | bank_reconciliation_repo | bank_transactions | bank_transactions: 277 | No salvo per_page sin límite | SQL tamaño arbitrario | Sí | P0 | Fijar 30, normalizar página, KPIs con todos los filtros; Excel sin truncar |
| Deudas | /reporteria/deudas | finanzas_deudas | debts_repo | debts | debts: 111 (conteo previo) | No para detalle | 30 | Sí | P1 | Hecho: filtros + COUNT/LIMIT SQL, desempate ID; KPI mantiene universo global |
| Cuotas y pagos de deuda | /reporteria/deudas/ID | finanzas_deuda_detalle | debts_repo | debt_installments,debt_payments | debt_installments: 339; debt_payments: 87 | Por deuda | No | No | P2 | Conservar planes cortos completos; evaluar deudas largas |
| Flujo de caja | /reporteria/flujo-caja | reporte_flujo_caja | cash_flow_repo | sales,purchase_invoices,bank_transactions,debt_installments | sales: 1683; purchase_invoices: 434; bank_transactions: 277; debt_installments: 339 | Sí | Python slice 30 | No | P0 | Contradice antecedente: consolidación completa y slice; separar detalle SQL preservando motor |
| Ingresos históricos y futuros | /reporteria/ingresos | reporte_ingresos | reporting_repo | sales | sales: 1683 | Sí | No | No | P0 | Paginar ambos detalles SQL; meses/gráfico completos |
| Reporte ventas por producto | /reporteria/ventas | reporte_ventas | reporting_repo | sales | sales: 1683 | Sí | JavaScript | No | P0 | Agregar productos SQL y paginar; KPIs completos |
| Reporte compras por proveedor | /reporteria/compras | reporte_compras | reporting_repo | purchase_orders,purchase_invoices | purchase_orders: 1413; purchase_invoices: 434 | Sí grupos | JavaScript | No | P1 | Paginar agregados de proveedores; KPIs completos |
| Reporte gastos por categoría | /reporteria/gastos | reporte_gastos | reporting_repo | inventory_entries | inventory_entries: 1830 | Agregados | No | No | P2 | Evaluar categorías; no paginar meses ni KPIs |
| Dashboard ventas recientes | /dashboard | dashboard | sales_repo | sales | sales: 1683 | Sí y slice 5 | Python slice | No | P0 | LIMIT 5 en consulta existente, sin navegación por ser resumen |
| Proyección ventas | /proyeccion-ventas | proyeccion_ventas | proyeccion_engine.py | sales / products_json | sales: 1683 (snapshot durante baseline) | Sí | No | No | P0 | Motor fuera de repositories: carga todas las ventas y genera todos los productos; agregar y paginar sin cambiar proyección |
| Usuarios | /usuarios | usuarios | auth_repo | users | users: 6 | Sí | No | No | P2 | 6 usuarios observados; no aporta paginar actualmente |
| Roles | /roles | roles | auth_repo | roles,users | roles: 7; users: 6 | Sí | No | No | P2 | Catálogo pequeño de permisos; conservar |
| Cuentas bancarias | /administracion/cuentas-bancarias | cuentas_bancarias | finance_repo | bank_accounts | bank_accounts: 689 | Sí | No | No | P0 | Volumen observado alto incluso maestro; paginar y revisar selectores |
| Operario recepción | /operario/recepcion | operario/recepcion_list | purchases_repo | purchase_orders | purchase_orders: 1413 | Sí pendientes | No | No | P1 | Paginar SQL con búsqueda q |
| Operario OT / finalizar | /operario/ot; /operario/finalizar | operario/ot_list | production_repo | production_orders | production_orders: 1618 | Sí activas | No | No | P1 | Paginar cabeceras y cargar componentes sólo de página |
| Operario historial | /operario/historial | operario/historial | services/operario_service.py | inventory_entries,production_lot_consumptions,production_orders | inventory_entries: 1830; production_lot_consumptions: 201; production_orders: 1618 | 30 por cada una de 3 fuentes | Top 30 Python | Parcial | P1 | UNION y LIMIT global; navegación histórica |
| Operario inicio | /operario/ | operario/home | services/operario_service.py | inventory_entries,production_orders | inventory_entries: 1830; production_orders: 1618 | 5 por fuente | Resumen 5 | Parcial | NO APLICA | Resumen acotado 15 candidatos; mantener UX |
| Trazabilidad / genealogía | /trazabilidad; /api/lots/ID/traceability | trazabilidad | lot_genealogy_repo | lots,production_lot_consumptions,sale_lot_movements | lots: 1508; production_lot_consumptions: 201; sale_lot_movements: 132 | Grafo por lote | Búsqueda limitada | Parcial | NO APLICA | Grafo completo necesario para relaciones; no cortar genealogía |
| Auditorías contextuales | /reporteria/conciliacion-bancaria/movimientos/ID/historial; /reporteria/cuentas-por-cobrar/ID/historial-cobranza | JSON / modal | bank_reconciliation_repo + reporting_repo | bank_reconciliation_audit,collection_actions | bank_reconciliation_audit: 207; collection_actions: 0 | Por entidad | No | No | P1 | Medir crecimiento por entidad; paginar historiales largos |
| Documentos / detalle OC, OT, recepción, ajustes, receta | Rutas /ID y APIs de detalle | editar_oc; editar_ot; detalle_ajuste_inventario; operario/ot_detail | purchases_repo + production_repo + inventory_repo | purchase_order_items,production_order_items,inventory_entry_items | purchase_order_items: 1523; production_order_items: 3042; inventory_entry_items: 802 | Por documento | No | No | NO APLICA | Líneas del documento deben preservarse completas; revisar consultas por componente |
| Formularios y selectores | /ventas/cotizacion/nueva; /produccion/nueva; /produccion/recetas/nueva; /compras/oc/nueva; /inventario/ajustes/nuevo | nueva_cotizacion; nueva_ot; nueva_receta; nueva_oc; nuevo_ajuste_inventario | products_repo + clients_repo + suppliers_repo | products,clients,suppliers | products: 11301; clients: 10; suppliers: 2222 | Sí catálogos | No | No | P1 | Documentar descarga masiva; reutilizar búsqueda remota existente donde sea compatible |
| Exportaciones e impresión | Rutas exportar-excel/exportar-csv/exportar/pdf | XLSX / CSV / PDF | services/*excel* + report_export_service | Dataset filtrado | Dataset filtrado: no medido | Sí por contrato | No | No | NO APLICA | Conservar universo completo; no heredar LIMIT de pantalla |

## Decisiones y riesgos

- P0 antes de P1; P2 sólo cuando aporta. GREEN exige evidencia por pantalla, no sólo suite general.
- LIMIT/OFFSET es la primera opción por navegación numerada y volúmenes actuales. Medir primera/última página con EXPLAIN ANALYZE antes de decidir cursor. No se afirma aún que OFFSET profundo tenga buen rendimiento.
- No se agregan índices sin plan medido. En lot_stock falta desempate único tras nombre/fecha.
- KPIs y Excel requieren consultas del universo completo; no deben reutilizar la lista visible. Conciliación tiene actualmente KPIs sólo por cuenta/fechas aunque el detalle admite más filtros.
- N+1: ventas/cotizaciones/recetas tienen cargas batch; inventario consolidó PPP en batch pero aún carga todo. Dashboard carga todas las ventas para mostrar 5. Componentes de receta/disponibilidad y selectores requieren revisión contextual.
- Los JOIN LATERAL de último pago/cuota no son por sí mismos N+1 del cliente. Los JOIN uno-a-muchos deben verificar cardinalidad antes de COUNT y LIMIT. No se ha demostrado un JOIN cartesiano accidental; jsonb_array_elements expande líneas deliberadamente.
- PPP/Kardex reconstruyen saldos por recurrencia histórica. Aplicar LIMIT a movimientos antes del cálculo alteraría resultados: se necesita equivalencia matemática y separación de detalle; no tocar FIFO, reservas ni escritura del ledger.
- page_data contiene proyecciones JSON legacy. Cortar después de get_page_data no cumple aceptación; usar expansión SQL cuando se migre el listado.
- Cuotas de una deuda y componentes de un documento no se paginan ciegamente. Estados, permisos y categorías pequeñas se conservan completos.

## Evidencia estática reproducible

Los siguientes son puntos detectados por análisis sintáctico; un fetchall no implica problema si sigue a LIMIT o devuelve agregados. La matriz es la clasificación funcional.

- `routes/auth.py`: L59 slice, L61 slice.
- `routes/dashboard.py`: L21 slice, L33 slice.
- `routes/inventario.py`: L195 fetchall, L957 fetchall, L469 fetchall.
- `routes/produccion.py`: L518 fetchall, L531 fetchall, L1131 fetchall, L106 fetchall, L154 fetchall, L310 fetchall, L973 fetchall, L1070 fetchall, L1111 fetchall.
- `routes/usuarios.py`: L290 fetchall.
- `routes/ventas.py`: L84 fetchall, L379 fetchall, L401 fetchall, L1831 fetchall, L1846 fetchall, L414 fetchall, L424 fetchall, L434 fetchall, L1636 slice, L1676 slice, L55 slice, L258 fetchall, L268 fetchall, L106 fetchall, L112 fetchall, L1578 fetchall.
- `repositories/auth_repo.py`: L25 fetchall, L91 fetchall.
- `repositories/bank_reconciliation_repo.py`: L584 fetchall, L626 fetchall, L59 fetchall, L203 fetchall, L411 fetchall, L672 fetchall, L714 fetchall, L758 fetchall, L1027 fetchall.
- `repositories/cash_flow_repo.py`: L45 slice, L72 slice, L94 fetchall, L104 fetchall, L167 fetchall, L225 fetchall, L280 fetchall, L334 fetchall, L394 fetchall, L444 fetchall, L501 fetchall, L554 fetchall, L612 fetchall.
- `repositories/clients_repo.py`: L28 fetchall, L183 fetchall.
- `repositories/debts_repo.py`: L56 fetchall, L299 fetchall, L384 fetchall, L599 fetchall.
- `repositories/expense_categories_repo.py`: L14 fetchall.
- `repositories/finance_repo.py`: L113 fetchall, L297 fetchall, L388 fetchall, L491 fetchall, L143 fetchall, L29 fetchall, L286 fetchall.
- `repositories/inventory_adjustments_repo.py`: L124 fetchall.
- `repositories/inventory_repo.py`: L695 fetchall, L960 fetchall, L513 fetchall, L1140 fetchall, L1186 fetchall, L294 fetchall, L313 fetchall, L356 fetchall, L410 fetchall, L497 fetchall, L527 fetchall, L540 fetchall, L882 fetchall, L885 fetchall, L238 fetchall.
- `repositories/kardex_repo.py`: L724 slice, L53 fetchall, L169 fetchall, L607 fetchall, L617 fetchall, L316 slice, L330 fetchall, L336 fetchall, L343 fetchall, L404 fetchall, L464 fetchall, L474 fetchall, L362 slice.
- `repositories/legacy_repo.py`: L52 fetchall.
- `repositories/lot_genealogy_repo.py`: L231 fetchall, L254 fetchall, L270 fetchall, L332 fetchall, L355 fetchall, L474 fetchall, L420 fetchall.
- `repositories/operational_expenses_repo.py`: L31 fetchall, L128 fetchall.
- `repositories/production_repo.py`: L56 fetchall, L75 fetchall, L97 fetchall, L212 fetchall, L238 fetchall, L260 fetchall, L392 fetchall, L452 fetchall, L730 fetchall, L860 fetchall, L971 fetchall, L990 fetchall, L1010 fetchall, L1062 fetchall, L1080 fetchall, L1193 fetchall, L1218 fetchall, L467 fetchall, L576 fetchall, L669 fetchall, L916 slice, L339 fetchall, L356 fetchall, L908 fetchall, L916 slice.
- `repositories/products_repo.py`: L132 fetchall, L521 fetchall, L718 fetchall, L538 fetchall, L623 fetchall, L686 fetchall, L35 fetchall, L345 fetchall, L361 fetchall.
- `repositories/purchases_repo.py`: L318 fetchall, L348 fetchall, L376 fetchall, L783 fetchall, L802 fetchall, L176 fetchall, L518 fetchall, L534 fetchall, L562 fetchall, L608 fetchall, L711 fetchall, L724 fetchall, L736 fetchall.
- `repositories/reporting_repo.py`: L417 slice, L477 slice, L478 slice, L479 slice, L1616 slice, L1811 slice, L2285 slice, L288 slice, L352 fetchall, L454 fetchall, L616 fetchall, L627 fetchall, L648 fetchall, L704 slice, L705 slice, L807 fetchall, L823 fetchall, L837 fetchall, L850 fetchall, L864 fetchall, L879 fetchall, L893 fetchall, L911 fetchall, L926 slice, L927 slice, L1036 fetchall, L1093 fetchall, L1190 fetchall, L1952 fetchall, L1957 fetchall, L181 fetchall, L196 fetchall, L229 fetchall, L483 slice, L507 slice, L507 slice, L1329 fetchall, L1416 fetchall, L1487 fetchall, L240 fetchall, L249 fetchall, L306 fetchall, L364 fetchall, L483 slice, L483 slice, L583 fetchall, L593 fetchall, L603 fetchall, L638 fetchall, L663 fetchall, L1182 fetchall, L1226 fetchall, L488 slice, L488 slice, L518 slice, L518 slice, L695 slice, L809 slice, L825 slice, L839 slice, L852 slice, L866 slice, L881 slice, L895 slice, L913 slice.
- `repositories/sales_repo.py`: L309 fetchall, L344 fetchall, L361 fetchall, L392 fetchall, L63 fetchall, L124 fetchall, L163 fetchall, L517 fetchall, L380 fetchall, L387 fetchall, L713 fetchall, L812 fetchall, L995 fetchall, L1059 fetchall, L1074 fetchall, L750 fetchall, L1480 fetchall, L755 fetchall, L1153 fetchall.
- `repositories/suppliers_repo.py`: L36 fetchall, L80 fetchall, L293 fetchall.
- `services/bank_reconciliation_excel_service.py`: L470 slice, L333 slice, L335 slice, L337 slice, L361 slice.
- `services/debt_excel_service.py`: L150 slice, L153 slice.
- `services/operario_service.py`: L119 slice, L47 fetchall, L73 fetchall, L100 fetchall, L79 slice, L106 slice.
- `services/products_excel_service.py`: L547 slice.
- `services/stock_context.py`: L62 fetchall, L77 fetchall.

## Cobertura de templates

- `templates/administracion.html`: 0 tablas; 1 bucles Jinja.
- `templates/ajustes_inventario.html`: 1 tablas; 2 bucles Jinja.
- `templates/base.html`: 0 tablas; 1 bucles Jinja.
- `templates/calendario_produccion.html`: 1 tablas; 3 bucles Jinja.
- `templates/clientes.html`: 1 tablas; 3 bucles Jinja.
- `templates/compras_cuentas_pagar.html`: 5 tablas; 5 bucles Jinja.
- `templates/compras_oc.html`: 5 tablas; 6 bucles Jinja.
- `templates/compras_productos_comprados.html`: 1 tablas; 7 bucles Jinja.
- `templates/conciliacion_bancaria.html`: 3 tablas; 5 bucles Jinja.
- `templates/cotizaciones.html`: 2 tablas; 7 bucles Jinja.
- `templates/cuentas_bancarias.html`: 1 tablas; 1 bucles Jinja.
- `templates/dashboard.html`: 1 tablas; 1 bucles Jinja.
- `templates/editar_oc.html`: 0 tablas; 2 bucles Jinja.
- `templates/editar_ot.html`: 0 tablas; 1 bucles Jinja.
- `templates/editar_producto.html`: 1 tablas; 4 bucles Jinja.
- `templates/editar_proveedor.html`: 1 tablas; 1 bucles Jinja.
- `templates/editar_receta.html`: 1 tablas; 0 bucles Jinja.
- `templates/editar_rol.html`: 0 tablas; 1 bucles Jinja.
- `templates/editar_usuario.html`: 0 tablas; 1 bucles Jinja.
- `templates/finanzas_deuda_detalle.html`: 2 tablas; 3 bucles Jinja.
- `templates/finanzas_deudas.html`: 1 tablas; 5 bucles Jinja.
- `templates/gastos_operacionales.html`: 2 tablas; 5 bucles Jinja.
- `templates/ingreso_mercaderia.html`: 3 tablas; 4 bucles Jinja.
- `templates/ingreso_ventas.html`: 1 tablas; 4 bucles Jinja.
- `templates/inventario.html`: 5 tablas; 6 bucles Jinja.
- `templates/kardex.html`: 2 tablas; 6 bucles Jinja.
- `templates/kardex_producto.html`: 1 tablas; 2 bucles Jinja.
- `templates/listas_precios.html`: 1 tablas; 5 bucles Jinja.
- `templates/login.html`: 0 tablas; 1 bucles Jinja.
- `templates/nueva_cotizacion.html`: 1 tablas; 1 bucles Jinja.
- `templates/nueva_oc.html`: 0 tablas; 1 bucles Jinja.
- `templates/nueva_ot.html`: 0 tablas; 1 bucles Jinja.
- `templates/nueva_receta.html`: 0 tablas; 2 bucles Jinja.
- `templates/nuevo_ajuste_inventario.html`: 0 tablas; 3 bucles Jinja.
- `templates/operario/historial.html`: 0 tablas; 1 bucles Jinja.
- `templates/operario/home.html`: 0 tablas; 2 bucles Jinja.
- `templates/operario/ot_detail.html`: 0 tablas; 3 bucles Jinja.
- `templates/operario/ot_list.html`: 0 tablas; 1 bucles Jinja.
- `templates/operario/recepcion_form.html`: 0 tablas; 2 bucles Jinja.
- `templates/operario/recepcion_list.html`: 0 tablas; 1 bucles Jinja.
- `templates/produccion.html`: 2 tablas; 6 bucles Jinja.
- `templates/productos.html`: 1 tablas; 3 bucles Jinja.
- `templates/productos_import_preview.html`: 1 tablas; 3 bucles Jinja.
- `templates/proveedores.html`: 1 tablas; 2 bucles Jinja.
- `templates/proyeccion_ventas.html`: 1 tablas; 3 bucles Jinja.
- `templates/recetas.html`: 1 tablas; 3 bucles Jinja.
- `templates/reporte_compras.html`: 1 tablas; 1 bucles Jinja.
- `templates/reporte_cuentas_por_cobrar.html`: 1 tablas; 3 bucles Jinja.
- `templates/reporte_cuentas_por_pagar.html`: 1 tablas; 3 bucles Jinja.
- `templates/reporte_facturas_compras_gastos.html`: 1 tablas; 3 bucles Jinja.
- `templates/reporte_flujo_caja.html`: 2 tablas; 3 bucles Jinja.
- `templates/reporte_gastos.html`: 1 tablas; 1 bucles Jinja.
- `templates/reporte_ingresos.html`: 3 tablas; 3 bucles Jinja.
- `templates/reporte_inventario_lotes.html`: 1 tablas; 3 bucles Jinja.
- `templates/reporte_ventas.html`: 1 tablas; 1 bucles Jinja.
- `templates/roles.html`: 0 tablas; 6 bucles Jinja.
- `templates/trazabilidad.html`: 3 tablas; 4 bucles Jinja.
- `templates/usuarios.html`: 1 tablas; 4 bucles Jinja.
- `templates/ventas.html`: 4 tablas; 10 bucles Jinja.
- `templates/ver_proveedor.html`: 1 tablas; 1 bucles Jinja.

Nota de ampliación de cobertura: se verificó también `proyeccion_engine.py`, invocado por `/proyeccion-ventas`: contiene `SELECT ... FROM sales` sin LIMIT (L78) y una tabla por producto potencialmente grande. Se corrigió la clasificación inicial de esta fila a P0; no es una proyección estática de page_data.

## Avance posterior a la auditoría

Se modificaron sólo cinco unidades del bloque P0: dashboard, conciliación, cotizaciones, matriz de productos comprados y cuentas bancarias. Ver `INFORME_OPTIMIZACION_LISTADOS_ERP.md` y `docs/pagination_evidence/` para resultados. La matriz anterior conserva el estado previo y no equivale a una certificación de cierre.

Los historiales asociados en cotizaciones se cargan por lote para IDs visibles, evitando N+1; aún pueden crecer por documento. No se certifica un límite global de 30 para todas las relaciones hijas ni para opciones de selector. La autenticación global y los decoradores RBAC previos se conservaron; varias rutas históricas carecen de permiso explícito por módulo.

Avance P0 adicional: `/compras/cuentas-por-pagar` usa COUNT + LIMIT 30 en facturas, búsqueda de proveedor/factura/OC/recepción en SQL y resumen global de facturas mediante agregación. El conteo de guías sin factura es escalar SQL. El autocomplete de proveedor/cuenta fue convertido luego a búsqueda remota con límite 30.

## Addendum de continuación — 2026-09-27

- Baseline real de esta solicitud: **434 PASSED / 0 FAILED**.
- CxP operativa `/compras/cuentas-por-pagar`: filtros y búsqueda SQL antes de `LIMIT 30`; COUNT y KPIs globales separados; proveedores/cuentas se buscan mediante API remota limitada a 30. Se mantiene la exportación de universo completo existente. Navegación y proveedor remoto se probaron con sesión autenticada en navegador en la validación previa.
- Deudas `/reporteria/deudas`: filtros WHERE, COUNT, ORDER BY determinístico y `LIMIT/OFFSET` SQL; KPIs globales intactos. El formulario de nueva deuda ya no serializa todas las cuentas bancarias.
- Productos `/productos`: listado SQL paginado preexistente, ahora con PAGE_SIZE fijo 30, `page` inválido normalizado, sin selector 50/100 y paginador compacto que preserva filtros.
- Se ajustó la prueba de recepción/CxP para encontrar una factura nueva usando búsqueda global server-side en lugar de suponer que está en la primera página ordenada por vencimiento.
- Pruebas específicas posteriores: **36 passed / 0 failed** en recibos, deudas y listados; **2 passed / 0 failed** en Productos y salud de rutas.
- Suite completa posterior: **455 passed / 0 failed en 155,36 s**.
- La suite green no cierra el objetivo: siguen pendientes P0 (inventario y Kardex, reportes financieros CxC/CxP, facturas/gastos, ingresos, ventas, proyección y Flujo de Caja), además de pruebas completas de Excel/KPIs/RBAC por pantalla y validación autenticada en navegador de todas las pantallas afectadas.
