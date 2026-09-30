# Informe E2E sobre la base limpia

**Base verificada:** `facturacion`  
**Método:** flujos HTTP autenticados de la aplicación Flask; SQL se usó sólo para lectura y comprobación. No se insertaron datos de negocio directamente en PostgreSQL.  
**Alcance:** una compra recibida, una cotización convertida en venta, y dos pagos parciales que completan el cobro.

## Snapshot inicial

| Entidad | Inicial |
|---|---:|
| Productos | 68 |
| Clientes | 10 |
| Proveedores | 10 |
| Cuentas bancarias | 10 |
| Ventas | 0 |
| Cotizaciones | 0 |
| Órdenes de compra | 0 |
| Recepciones | 0 |
| Movimientos de inventario | 0 |
| Lotes | 0 |
| Órdenes de producción | 0 |
| Deudas | 0 |

Producto seleccionado: ID 60, SKU `PT-CLA-001`, “Miel de Ulmo 1 Kg PET”, categoría y unidad válidas, sin control de lote. Proveedor: ID 11, Proveedor Miel Sur. Cliente: ID 1, “Clinete 10”. Cuenta receptora: ID 1366, Banco Estado.

## Compra, recepción, inventario y PPP

Se creó por el formulario/ruta oficial la OC **4077 (`OC-05752`)**, con una línea de 100 unidades a CLP 1.000 netos por unidad, total neto CLP 100.000. La creación de la OC no cambió el inventario: físico 0, reservado 0, disponible 0.

La recepción oficial creó la recepción **2469**, factura **3669** por CLP 119.000 (IVA incluido), y el movimiento de inventario **56155**, tipo `PURCHASE_RECEIPT`, cantidad +100, costo unitario CLP 1.000 y referencia `purchase_order:4077`. La factura quedó pendiente, con vencimiento 27-10-2026.

| Estado del producto 60 | Físico | Reservado | Disponible | Ledger | Lotes | PPP oficial |
|---|---:|---:|---:|---:|---:|---:|
| Antes | 0 | 0 | 0 | 0 | 0 | 0 |
| Tras recepción | 100 | 0 | 100 | 100 | 0 | CLP 1.000 |
| Final E2E | 90 | 0 | 90 | 90 | 0 | CLP 1.000 |

El Kardex registra la entrada vinculada a la OC/recepción. El PPP consultado por el servicio oficial y el costo unitario capturado en la venta son CLP 1.000. El campo legacy `products.cost` permaneció en 0; no se actualizó manualmente. Es una divergencia del caché/campo legacy que debe evaluarse aparte, ya que el costo dinámico usado por PPP y la venta es correcto.

## Cotización, venta y reserva

Se creó y emitió la cotización **14252 (`COT-04182`)** para el cliente 1: 10 unidades a CLP 1.500, total CLP 15.000. Permaneció sin efecto sobre stock (100/0/100). Se convirtió mediante el endpoint oficial, pasando a Ganada y generando la venta **14253 (`P-04183`)**.

La conversión descontó físicamente las 10 unidades: generó un único movimiento `SALE` de -10, costo unitario capturado CLP 1.000, referencia `sale:14253`; la venta comenzó Pendiente. La transición oficial a **En Preparación** fue permitida con el stock existente y no generó un segundo descuento. Repetirla tampoco duplicó el movimiento. La venta terminó Completada al pagarse.

Durante esta prueba apareció una doble contabilización real: una venta ya descontada físicamente, pero aún Pendiente, también se contaba como reserva. Se corrigió `services/stock_context.py` para excluir de las reservas las ventas con líneas de venta ya materializadas en `sale_items`. Se agregó la regresión `test_already_discounted_pending_sale_is_not_reserved_twice`. Antes de la corrección, ese estado mostraba físico 90, reservado 10, disponible 80; después, físico 90, reservado 0, disponible 90. El stock final corresponde a +100 de recepción y -10 de venta.

El snapshot de costo de la línea de venta fue CLP 1.000; ingreso neto CLP 15.000, costo de venta CLP 10.000 y diferencia bruta CLP 5.000 según los importes de línea. No se modificaron reglas de precio ni valoración.

## Pagos, CxC/CxP y flujo de caja

Se registraron dos pagos oficiales por transferencia, ambos en cuenta 1366 y con la evidencia requerida por el flujo:

| Pago | Monto | Saldo tras pago |
|---|---:|---:|
| Parcial | CLP 7.500 | CLP 7.500 |
| Final | CLP 7.500 | CLP 0 |

La venta mostró estado financiero Pendiente tras el abono parcial y Pagado tras el segundo; se conservaron dos payment items, sin movimiento de inventario adicional. CxC respondió HTTP 200 en la validación intermedia; tras completar el cobro no quedaron saldos pendientes y el reporte CxC mostró cero obligaciones abiertas. CxP muestra una obligación pendiente por CLP 119.000.

El flujo de caja mostró CLP 15.000 de ingresos reales (dos abonos), CLP 119.000 de egreso proyectado por la factura pendiente y ninguna duplicación por movimientos bancarios. Con saldo inicial de cuenta igual a cero, el escenario proyecta saldo -CLP 104.000 y alerta de déficit. La transferencia de venta queda registrada para su tratamiento de conciliación; esta prueba no ejecutó conciliación bancaria.

## Integridad y validación funcional

Al cierre se validaron 17 rutas mediante un cliente Flask autenticado, todas HTTP 200: dashboard, productos, inventario, Kardex, ventas, cotizaciones, compras/OC, recepción, producción, CxC, CxP, deudas, conciliación, flujo de caja, reportes y cuentas bancarias. Esto valida respuestas HTTP de aplicación; no se realizó una sesión de navegador real ni una inspección de errores JavaScript.

`tools/reconcile_inventory.py --check --json` reportó 68 productos, snapshots 68/68, cero diferencias ledger/lotes, snapshot/ledger y snapshot/lotes, cero reservas inconsistentes o ambiguas, cero candidatos cuantitativos y cero referencias inválidas. Encontró dos movimientos y ambos tienen referencias válidas (`purchase_order:4077` y `sale:14253`); no hubo correcciones automáticas. Los movimientos de inventario finales son dos, los lotes cero, la recepción una y la factura de compra una.

La comprobación de cierre volvió a ejecutarse en modo CHECK y devolvió esos mismos resultados. La DB reportó `current_database() = facturacion`; hay 82 FK públicas y 0 sin validar. Los conteos concretos al cierre son: 68 productos, 10 clientes, 10 proveedores, 10 cuentas, 2 filas en `sales` (1 cotización + 1 venta), 1 OC, 1 recepción, 2 movimientos, 0 lotes, 1 factura de compra y 2 payment items para la venta. Las 17 rutas autenticadas volvieron a responder HTTP 200.

## Suite aislada y cambio realizado

La prueba de regresión específica pasó: 6 tests. Luego se ejecutaron dos suites completas en clones efímeros de la base de tests, ambas con **485 passed, 0 failed**. El runner valida conteos de `facturacion` y de la plantilla persistente antes/después de cada suite, y elimina cada clon al terminar; ambas suites finalizaron sin reportar variación persistente. El baseline anterior era 484 tests; el único agregado fue la regresión de doble reserva.

La repetición inicial detectó además una colisión intermitente de RUT en `test_e2e_supplier_and_po_payment_terms_flow`: el test derivaba tres identificadores de un timestamp sin comprobar que estuvieran libres. El test ahora busca un RUT válido disponible en la DB efímera antes de crear cada proveedor. Conserva el flujo y sus asserts de negocio. La prueba dirigida pasó (11/11) y, tras el ajuste, las dos suites completas pasaron 485/485.

Los documentos creados por este E2E permanecen en `facturacion` deliberadamente. El delta esperado frente al snapshot limpio corresponde únicamente a esos documentos y sus dependencias; el runner aislado no lo incrementó.

## Semáforo

| Área | Estado | Evidencia |
|---|---|---|
| Compra | GREEN | OC 4077, 100 × CLP 1.000 |
| Recepción | GREEN | Recepción 2469, entrada +100 |
| Inventario | GREEN | Físico/ledger 90; reservado 0; disponible 90 |
| Kardex | GREEN | Entrada +100 y salida -10 con referencias válidas |
| PPP | GREEN | Servicio oficial CLP 1.000; el campo legacy `products.cost` sigue 0 y queda documentado |
| Cotización | GREEN | COT-04182 emitida y ganada |
| Venta | GREEN | P-04183 completada; una sola salida física |
| Reserva | GREEN | Doble conteo corregido y cubierto por test |
| Pago | GREEN | Dos transferencias de CLP 7.500 |
| CxC | GREEN | Saldo cerrado; prueba parcial intermedia HTTP 200 |
| CxP | GREEN | Factura pendiente de CLP 119.000 |
| Flujo de caja | GREEN | Ingresos/egreso proyectado sin duplicación; alerta de déficit explícita |
| Integridad | GREEN | Reconciliador: cero diferencias/referencias rotas |
| Tests | GREEN | 2 × 485 passed, 0 failed |
| Aislamiento de tests | GREEN | Clones efímeros, delta persistente cero según runner |

**E2E FINAL: GREEN**
