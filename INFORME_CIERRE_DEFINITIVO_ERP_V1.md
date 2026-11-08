# Informe de cierre definitivo — ERP V1

**Fecha:** 21 de octubre de 2026 (America/Santiago)  
**Dictamen:** **YELLOW para entrega/despliegue; GREEN en la recertificación funcional, financiera y de aislamiento ejecutada en esta copia de trabajo.**  
**Rama/HEAD:** `main` / `1e9b98002325a313b9de056de07ab456ac81be18`  
**Tag V1:** `v1.0.0` sin cambios.

## 1. Resumen ejecutivo

Se revisaron las migraciones 000028–000030, el esquema actual de ambas bases protegidas, las rutas de inicialización/migración y la evidencia de certificación. Las tres migraciones son aditivas, corresponden a funciones financieras activas y sus objetos se usan en CxP, gastos, flujo de caja, reportes y conciliación bancaria. No hay evidencia de que sean objetos huérfanos o maliciosos.

La recertificación completa corrió contra clones efímeros y aprobó **1.047 pruebas**: 629 regresión, 228 funcionales/E2E y 190 de navegador. Pasaron también 192 comprobaciones monetarias independientes y 98 comparaciones de inventario ledger/lotes, sin diferencias. Ambas bases protegidas conservaron sus huellas completas de datos y esquema; el rol de pruebas no tuvo permisos efectivos de escritura sobre ellas y no quedaron recursos temporales.

Se corrigió un problema de trazabilidad de migraciones y el `.gitignore` ahora permite que Git muestre los SQL dentro de `migrations/`. El dictamen de entrega queda **YELLOW** porque los archivos de migración que el patrón global `*.sql` ocultaba siguen sin commit. No se hizo commit porque está expresamente prohibido. Un checkout limpio todavía no contiene esos archivos hasta que se incorporen al control de versiones; por eso no recomiendo desplegar desde un checkout limpio antes de resolver ese empaquetado.

La identidad histórica del proceso que aplicó las migraciones a `facturacion` continúa sin determinarse: no se hallaron logs PostgreSQL del período ni entradas de systemd que permitieran atribuirlo. Conforme al criterio de esta fase, esa falta de PID no se usa por sí sola para mantener YELLOW: el estado vigente fue validado, las migraciones son legítimas y las ejecuciones actuales permanecieron aisladas.

## 2. Dictamen

| Área | Dictamen | Motivo |
|---|---|---|
| Funcional y financiera, en esta copia | GREEN | Suites, escenarios E2E, navegador y oráculos monetarios/inventario sin fallos. |
| Protección de bases durante las corridas | GREEN | Huellas íntegras antes/después; el rol de pruebas no pudo escribir; recursos eliminados. |
| Estado actual de migraciones 000028–000030 | GREEN | Aplicadas en `facturacion`, definiciones coherentes con el código y vistas válidas. |
| Historial de actor DDL | No determinado | Logs históricos no disponibles; no se inventa atribución. |
| Artefacto de versión/despliegue | YELLOW | Los SQL ignorados por Git se muestran ahora como archivos sin seguimiento, pero no se hizo commit. |
| **Cierre global** | **YELLOW** | La funcionalidad actual está certificada en el entorno de trabajo; el paquete aún no es reproducible desde un checkout limpio. |

No se modificaron filas ni esquemas de `facturacion` o `facturacion_cleanup_verify`. Tampoco se revirtieron migraciones, repararon registros históricos o alteraron el tag V1.

## 3. Auditoría de migraciones 000028–000030

Los archivos SQL estaban presentes en el árbol de trabajo, pero el patrón global `*.sql` de `.gitignore` los ocultaba. Por ello, `git log` no ofrece fecha de creación/autores para estas migraciones y no se atribuye una fecha de autoría. Las fechas de aplicación sí constan en `schema_migrations` de la base operacional.

| Migración | Fecha aplicada en `facturacion` (UTC) | Objetos | Clasificación | Justificación |
|---|---|---|---|---|
| `000028_purchase_payment_items` | 2026-10-21 03:45:48 | Tabla `purchase_payment_items`, índice `idx_purchase_payment_invoice`, vista `purchase_payment_events` | LEGÍTIMA Y NECESARIA | El ledger de pagos parciales es consultado/escrito por `repositories/finance_repo.py`, `repositories/bank_reconciliation_repo.py`, `repositories/cash_flow_repo.py`, `repositories/reporting_repo.py` y `routes/compras.py`. Incluye monto positivo, FK con `RESTRICT` e idempotencia por factura. La vista conserva lectura de pagos del encabezado legado sin duplicarlos cuando existe ledger. |
| `000029_expense_payment_items` | 2026-10-21 03:50:21 | Tabla `expense_payment_items`, índice `idx_expense_payment_occurrence`, vista `expense_payment_events` | LEGÍTIMA Y NECESARIA | El ledger de pagos de gastos se usa en `repositories/operational_expenses_repo.py`, conciliación, flujo de caja y reportes. La tabla impone monto positivo, FK y clave idempotente por ocurrencia. La vista preserva compatibilidad con registros legados. |
| `000030_payment_opening_snapshots` | 2026-10-21 03:55:19 | Tablas `purchase_payment_openings`, `expense_payment_openings`; reemplaza las dos vistas anteriores | LEGÍTIMA Y NECESARIA | Al continuar el pago parcial de una obligación antigua, los repositorios guardan el pago legado inicial una sola vez. Las vistas consolidan apertura y nuevos pagos sin volver a sumar el encabezado legado. Los downgrades rechazan eliminar aperturas con pagos guardados. |

En conjunto crearon **cuatro tablas vacías** al momento de la auditoría inicial y **dos vistas**. No agregan funciones ni triggers; no hacen backfill ni reescriben pagos, facturas o datos históricos. Los `down.sql` protegen pagos/aperturas ya registrados y sólo permiten retirar los objetos cuando no se perderían hechos financieros. Las cuatro tablas de la base protegida seguían con cero filas en la evidencia de lectura de esta fase; las pruebas cargaron únicamente datos sintéticos en clones.

### Dependencias comprobadas

- CxP y pagos de compras: `repositories/finance_repo.py`, historial en `routes/compras.py`.
- Gastos y pagos: `repositories/operational_expenses_repo.py`.
- Conciliación: `repositories/bank_reconciliation_repo.py`.
- Flujo de caja: `repositories/cash_flow_repo.py`.
- Reportes: `repositories/reporting_repo.py`.
- `purchase_payment_events` y `expense_payment_events` se consultaron en ambas vistas con `LIMIT 0`; PostgreSQL resolvió columnas y dependencias sin error.

Por sus usos actuales, las migraciones no son obsoletas ni incompatibles. El SQL no contiene cambios destructivos en los `up`. La reversibilidad de 000028–000030 es condicional, deliberadamente: se rechaza un `down` que eliminaría pagos publicados.

## 4. Origen histórico del DDL

**Resultado: no determinado.** La lectura histórica documenta los tres registros de `schema_migrations` y las horas anteriores. La comparación previa no encontró cambios en filas antiguas; los objetos nuevos aparecían vacíos. Eso demuestra que hubo DDL real, pero no quién lo ejecutó.

Se revisaron los artefactos de certificación, los logs disponibles en el repositorio, `/var/log/postgresql` y la ventana de `journalctl` del 21-10-2026. No había archivos de log PostgreSQL ni entradas de servicio para atribuir el DDL. Se filtró también el log del contenedor PostgreSQL por las versiones/nombres/DDL y no se encontraron líneas pertinentes. No se inventan PID, usuario, comando ni proceso. La importación Flask que ejecutaba `init_db()` incondicionalmente fue una vía de riesgo en la implementación anterior; no hay evidencia suficiente para afirmar que originó este evento.

La mitigación vigente elimina esa vía: `app.py` sólo llama `init_db()` en modo `testing`, después de validar el destino efímero; `db.init_db()` aplica el mismo guard. El migrador rechaza bases protegidas salvo el override administrativo explícito. Las corridas actuales demostraron que las migraciones de bootstrap se aplicaron sólo en clones.

## 5. Estado del esquema y diferencias entre bases

La inspección se realizó en transacciones de sólo lectura. La evidencia completa está en [auditoría de esquema y migraciones](correccion_certificacion_erp_v1/evidencia/incidente_esquema_auditoria_solo_lectura.json).

| Base | Migraciones canónicas | Tablas | Vistas de pagos | Huella de esquema |
|---|---:|---:|---:|---|
| `facturacion` | 000001–000030 | 58 | 2, ambas válidas | `b2e80a1ea0b225e89d88c2f65b84f62042c11e7d80c982d1acd5eb9aeaac1a3b` |
| `facturacion_cleanup_verify` | Plantilla anterior a 000028–000030 | 54 | 0 | `1be6eff8378a5045ca644c7397f57e15f07245cb1c3cecb3fd0249bdf45e406d` |

La diferencia de cuatro tablas/dos vistas corresponde a 000028–000030 y es esperable: la plantilla es anterior y no se actualizó. En su `schema_migrations` hay dos registros heredados no canónicos (`25` / `26`, con nombres prefijados `000025_` / `000026_`) en lugar de las versiones canónicas `000025` / `000026`; esas dos entradas también aparecen como duplicados en `facturacion`, junto con las entradas canónicas. No se alteraron para limpiar el historial. La copia de la plantilla recibe las migraciones canónicas que faltan al iniciar las pruebas; las definiciones 000025/000026 son idempotentes (`IF NOT EXISTS` y reemplazo controlado de constraint), y la certificación completa pasó.

No se encontraron vistas de pago inválidas, dependencias rotas ni migraciones fuente sin registro canónico en `facturacion`. El estado irregular `25`/`26` se conserva como metadato histórico no canónico y queda documentado; no causa duplicación de operaciones porque el runner compara versiones canónicas y las migraciones faltantes son idempotentes. No se modificó la plantilla.

## 6. Correcciones implementadas

1. **Visibilidad de migraciones en Git:** se agregó `!migrations/*.sql` después de `*.sql` en `.gitignore`. Así Git deja de ocultar scripts de esquema necesarios para reconstruir el ERP.
2. **Trazabilidad del migrador:** `tools/migrate.py` emite un registro JSON `MIGRATION_AUDIT` sin secretos con fecha UTC, migración, base, usuario PostgreSQL, origen de aplicación, run ID, acción y resultado. Durante cada DDL establece `application_name` con la versión de migración. El bootstrap de pruebas informa el origen `flask_testing_bootstrap` desde `db.py`.
3. **Auditor de sólo lectura:** `correccion_certificacion_erp_v1/scripts/audit_schema_incident.py` ahora enumera todas las versiones aplicadas, compara contra archivos fuente, valida las vistas y registra sus columnas/definiciones y huellas.

La corrida focal confirmó que el log registra valores reales de base/usuario, y que no contiene credenciales. La captura está en [seed focal](correccion_certificacion_erp_v1/evidencia/cierre_definitivo_migrator_logging/evidencia/seed.log).

## 7. Resultados de recertificación

Comando integral:

```bash
venv/bin/python correccion_certificacion_erp_v1/scripts/run.py --output-name cierre_definitivo_20261021
```

El runner creó un clon marcado y un rol limitado, migró/sembró datos sintéticos, ejecutó pruebas, comparó huellas y limpió los recursos en `finally`.

| Área | Pruebas/controles | PASS | FAIL | BLOCKED | Estado |
|---|---:|---:|---:|---:|---|
| Regresión pytest | 629 | 629 | 0 | 0 | GREEN |
| Funcional y E2E | 228 | 228 | 0 | 0 | GREEN |
| Navegador, recorrido base | 75 | 75 | 0 | 0 | GREEN |
| Navegador, ampliado | 90 | 90 | 0 | 0 | GREEN |
| Navegador, crítico | 25 | 25 | 0 | 0 | GREEN |
| Finanzas, oráculo Decimal | 192 verificaciones (incluidas en los escenarios funcionales) | 192 | 0 | 0 | GREEN |
| Inventario ledger/lotes | 98 comparaciones (incluidas en los escenarios funcionales) | 98 | 0 | 0 | GREEN |
| Aislamiento | 10 comprobaciones de privilegios + 2 bases con huella antes/después | 12 | 0 | 0 | GREEN |
| Migraciones | 30 fuentes; aplicación completa/idempotencia en pruebas; 5 eventos de migración al clonar la plantilla | PASS | 0 | 0 | GREEN |
| Corrida focal posterior al ajuste de log | 35 pruebas seleccionadas; 193 se deselectaron | 35 | 0 | 0 | GREEN |

El total no duplicado de la recertificación integral es **1.047 PASS** (629 + 228 + 75 + 90 + 25), **0 FAIL**, **0 errores** y **0 omitidas**. Las 192 verificaciones monetarias y 98 de inventario son aserciones derivadas de los mismos escenarios y no se suman otra vez. Los 35 casos focales son una corrida posterior y tampoco se agregan al total integral.

La matriz funcional incluye cinco variantes por funcionalidad identificada y cinco ciclos completos de empresa; contempla compras/recepción, lotes, inventario, PPP/FIFO, cotizaciones, ventas/despacho, producción, CxC/CxP, gastos, deuda, bancos, conciliación, flujo, reportes y permisos. Las pruebas de navegador generaron evidencia para las pantallas y exportaciones cubiertas.

### Validaciones financieras y de inventario

- 192 de 192 documentos sintéticos coincidieron con el cálculo independiente neto + IVA y total; diferencia monetaria: **$0**.
- 98 de 98 comparaciones entre ledger de movimientos y lotes coincidieron; diferencia de unidades: **0**.
- Sobrepagos de compra/gasto: **0**.
- Diferencias encabezado/eventos de pagos: **0**.
- Diferencias de importe de conciliación: **0**.
- Diferencias de transferencias internas: **0**.
- Los cinco ciclos E2E aprobaron sin diferencias de inventario o montos.

Fuente de resultados: [XML de regresión](correccion_certificacion_erp_v1/evidencia/cierre_definitivo_20261021/evidencia/baseline.xml), [XML funcional/E2E](correccion_certificacion_erp_v1/evidencia/cierre_definitivo_20261021/evidencia/certification.xml), [control financiero](correccion_certificacion_erp_v1/evidencia/cierre_definitivo_20261021/evidencia/control_monetario_final.json), [resultados de navegador](correccion_certificacion_erp_v1/evidencia/cierre_definitivo_20261021/evidencia/navegador.json) y [corrida crítica de navegador](correccion_certificacion_erp_v1/evidencia/cierre_definitivo_20261021/evidencia/navegador_critico.json).

## 8. Aislamiento, huellas y limpieza

La ejecución integral protegió las bases con un rol restringido. En cada base se comprobaron privilegios efectivos de escritura en tablas, creación en esquema, escritura en secuencias, creación de bases y membresías de roles: **0 privilegios efectivos** para el rol de prueba en ambas bases.

| Base protegida | Huella completa antes | Huella completa después | Huella de esquema | Resultado |
|---|---|---|---|---|
| `facturacion` | `5c1ea42d957a834db2f6a58e1d981e28ff2c2d61a692ea986c3da6d9fb7b9f44` | igual | `b2e80a1ea0b225e89d88c2f65b84f62042c11e7d80c982d1acd5eb9aeaac1a3b` | Intacta |
| `facturacion_cleanup_verify` | `fcb8bd623e49b0e230a896516e77a62dc73bb9b513a902f9a886fcda6537a4fc` | igual | `1be6eff8378a5045ca644c7397f57e15f07245cb1c3cecb3fd0249bdf45e406d` | Intacta |

La huella completa combina el inventario ordenado de hashes de filas por tabla y la huella de esquema; coincide entre `estado_inicial.json` y `estado_final.json`. La corrida focal posterior también terminó con `persistent_databases_unchanged: true`.

Bases efímeras restantes: **0**. Base auxiliar de migraciones restante: **0**. Roles temporales restantes: **0**. El directorio de trabajo copiado para la suite se eliminó. No se detectaron escrituras DDL/DML atribuibles a estas ejecuciones en las bases protegidas.

Evidencias: [aislamiento integral](correccion_certificacion_erp_v1/evidencia/cierre_definitivo_20261021/evidencia/aislamiento.json), [huella inicial](correccion_certificacion_erp_v1/evidencia/cierre_definitivo_20261021/evidencia/estado_inicial.json), [huella final](correccion_certificacion_erp_v1/evidencia/cierre_definitivo_20261021/evidencia/estado_final.json) y [aislamiento focal posterior](correccion_certificacion_erp_v1/evidencia/cierre_definitivo_migrator_logging/evidencia/aislamiento.json).

## 9. Estado de Git y archivos

La rama y HEAD permanecieron en `main` y `1e9b98002325a313b9de056de07ab456ac81be18`; `v1.0.0` permaneció en `d4e1d82ed8ad3af52ae4c135cae45f039e5f1163`. No hubo commit, push, reset ni descarte de cambios.

Al comienzo del trabajo el árbol ya tenía cambios preexistentes, registrados en [estado Git inicial de esta auditoría](correccion_certificacion_erp_v1/evidencia/cierre_definitivo_20261021/git_estado_inicial.txt). Se conservaron. Cambios de esta fase:

- `.gitignore`
- `tools/migrate.py`
- `db.py`
- `correccion_certificacion_erp_v1/scripts/audit_schema_incident.py`
- `INFORME_CIERRE_DEFINITIVO_ERP_V1.md`
- Evidencia bajo `correccion_certificacion_erp_v1/evidencia/cierre_definitivo_20261021/` y `cierre_definitivo_migrator_logging/`.

La excepción de `.gitignore` hace visibles **42 archivos SQL de migración que antes quedaban ignorados** (versiones 000007–000024 y 000028–000030); siguen sin seguimiento de Git y no se añadieron al índice. Es la acción pendiente que causa el dictamen YELLOW para despliegue desde un checkout limpio. `git diff --check` no reportó errores en los archivos de esta fase; sí reportó espacios finales en líneas preexistentes de `templates/administracion.html`, que no se modificaron en esta fase.

## 10. Limitaciones, riesgos y acciones pendientes

1. **Versionar los SQL antes del próximo despliegue desde Git.** Revisar y añadir al cambio de release los 42 archivos visibles bajo `migrations/`; después verificar en un checkout limpio que existan los 30 pares `.up.sql`/`.down.sql` y ejecutar migraciones en una base descartable. No se hizo commit por instrucción.
2. **Mantener la plantilla inmutable durante esta certificación.** Tiene un historial no canónico de `25`/`26` y está antes de 000028–000030. El runner la actualiza sólo en el clon efímero. Si se decide normalizar su metadato, hacerlo como tarea administrativa separada sobre un clon, no manualmente durante pruebas.
3. **El actor del DDL de 2026-10-21 no puede recuperarse** con los logs disponibles. La aplicación ya no migra bases protegidas al importarse; el migrador registra las ejecuciones futuras. Para que PostgreSQL conserve también esos registros, la configuración de servidor debe retener logs que incluyan `application_name`.
4. **La auditoría financiera certifica reglas con datos sintéticos.** Las huellas históricas protegidas se comprobaron sólo para confirmar que no cambiaron; esta tarea no revalidó cada saldo/documento operacional individual ni ejecutó reparaciones históricas.

## 11. Recomendación de continuidad

La base operacional vigente puede seguir operando con el código y esquema actuales: las migraciones 000028–000030 están aplicadas, sus vistas son válidas, y la recertificación financiera/funcional pasó sin modificar datos reales. No volver a aplicar ni revertir esas migraciones manualmente en `facturacion`.

Antes de desplegar desde una copia limpia del repositorio, incorporar y revisar los SQL que ahora aparecen como no seguidos por Git. Mantener `facturacion_cleanup_verify` como plantilla anterior sólo si el runner continúa migrando cada clon y validando el resultado como lo hizo en esta prueba.

## 12. Evidencia y comandos

Auditoría de esquema estrictamente de sólo lectura:

```bash
venv/bin/python correccion_certificacion_erp_v1/scripts/audit_schema_incident.py
```

Recertificación completa aislada:

```bash
venv/bin/python correccion_certificacion_erp_v1/scripts/run.py --output-name cierre_definitivo_20261021
```

Corrida focal posterior a la corrección del log:

```bash
venv/bin/python correccion_certificacion_erp_v1/scripts/run.py --targeted --output-name cierre_definitivo_migrator_logging
```

Resultado focal: 35 aprobadas, 193 no seleccionadas; privilegios efectivos de escritura a las dos bases protegidas: cero; huellas intactas; limpieza correcta.

---

**Conclusión:** ERP V1 queda **GREEN en funcionalidad, finanzas y aislamiento dentro del estado de trabajo recertificado**. El **dictamen global de entrega es YELLOW** hasta incorporar al control de versiones los SQL de migración que `.gitignore` ocultaba. No hay defectos críticos financieros ni una alteración de las bases protegidas atribuible a esta certificación.
