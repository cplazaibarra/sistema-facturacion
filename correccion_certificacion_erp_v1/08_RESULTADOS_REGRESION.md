# Resultados finales de regresión y cobertura

Se consolidan las últimas ejecuciones completas por suite sobre el mismo código productivo. Los intentos anteriores permanecen archivados; las repeticiones no aumentan el total.

Plan original:922; resultados {'PASS': 922}. Total ampliado:1018; ejecutadas:1018; resultados:{'PASS': 1017, 'FAIL': 1}. No se descuentan casos fallidos ni bloqueados del plan anterior.

Regresión:599. Incluye los ocho casos previamente bloqueados una nueva protección de downgrade y seis pruebas de arranque/inicializador READ ONLY. Funcionales/E2E:228. Navegador:190. Control acumulado de protección:1 (FAIL). Ciclos E2E:{'PASS': 5}. Las repeticiones de preparación/diagnóstico no se cuentan como casos nuevos.

| MÓDULO | PRUEBAS | PASS | FAIL | BLOCKED | ESTADO |
|---|---|---|---|---|---|
| Productos | 20 | 20 | 0 | 0 | YELLOW |
| Proveedores | 10 | 10 | 0 | 0 | YELLOW |
| Clientes | 10 | 10 | 0 | 0 | YELLOW |
| Órdenes de compra | 10 | 10 | 0 | 0 | YELLOW |
| Recepción | 10 | 10 | 0 | 0 | YELLOW |
| Inventario y Kardex | 30 | 30 | 0 | 0 | YELLOW |
| Costos PPP/FIFO y precios | 20 | 20 | 0 | 0 | YELLOW |
| Cotizaciones | 15 | 15 | 0 | 0 | GREEN |
| Ventas | 10 | 10 | 0 | 0 | YELLOW |
| Preparación y despacho | 20 | 20 | 0 | 0 | YELLOW |
| Producción | 57 | 57 | 0 | 0 | GREEN |
| Cuentas por Cobrar | 10 | 10 | 0 | 0 | YELLOW |
| Cuentas por Pagar | 34 | 34 | 0 | 0 | GREEN |
| Gastos Operacionales | 23 | 23 | 0 | 0 | GREEN |
| Deudas | 20 | 20 | 0 | 0 | YELLOW |
| Cuentas bancarias | 10 | 10 | 0 | 0 | YELLOW |
| Conciliación | 39 | 39 | 0 | 0 | GREEN |
| Flujo de Caja | 25 | 25 | 0 | 0 | GREEN |
| Reportes | 10 | 10 | 0 | 0 | YELLOW |
| Usuarios, permisos y administración | 31 | 30 | 1 | 0 | RED |

La tabla agrupa pruebas funcionales y de navegador. La regresión complementaria y los cinco ciclos se contabilizan aparte. Matriz individual en evidencia/matriz_casos_final.json y CSV.

## Cambios de preparación sin debilitar aserciones

La regresión de idempotencia de producción ahora recibe y consume un insumo antes de fabricar; conserva primera finalización exitosa, segundo rechazo y una sola salida. La de conciliación positiva dispone de aprobación contable explícita, conservando el caso negativo no aprobado. La de transferencia CxP dispone de cuenta activa y conserva rechazo del segundo intento sin clave. Se ajustó sólo el teardown para eliminar sus pagos sintéticos antes de su factura; el ledger de producción no tiene borrado por negocio.

La copia del caso operario-3 conserva stock esperado0 y comprueba ausencia de salida; elimina la contradicción inalcanzada de asignar costo1300 a una fabricación inexistente. La versión original se conserva intacta.

## Límites de cobertura

Los 13 módulos YELLOW conservan la limitación de la certificación anterior: cinco lecturas/contrastes UI no equivalen a cinco altas o flujos CRUD interactivos completos por cada función. Los cinco módulos críticos tienen25 recorridos interactivos adicionales aprobados. No se declara GREEN global por una suite verde. No se prueban integración SII, cartolas reales, reparaciones históricas ni una reversa de fabricación/pago inexistente.
