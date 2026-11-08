# Informe final de release — ERP V1

**Fecha:** 22 de octubre de 2026 (America/Santiago)  
**Dictamen:** **GREEN**  
**Rama:** `main`  
**Commit final:** `b4e5a92292448527059b7aa7980707d10827ccd4`  
**Tag `v1.0.0`:** sin cambios (`d4e1d82ed8ad3af52ae4c135cae45f039e5f1163`)

## 1. Resumen ejecutivo

Se eliminó el bloqueo de versionamiento: los **60 archivos SQL** de las 30 migraciones (`.up.sql` y `.down.sql`) están ahora en Git. El release se reconstruyó desde un clon local limpio, aplicó las 30 migraciones en una base PostgreSQL efímera, arrancó Flask y respondió correctamente en `/health`.

La recertificación ejecutada desde el código del checkout limpio aprobó **1.047 pruebas únicas**: 629 de regresión, 228 funcionales/E2E y 190 de navegador. No hubo FAIL, errores, SKIP ni BLOCKED. Las 192 verificaciones monetarias y las 98 comparaciones de inventario incluidas en esos escenarios aprobaron sin diferencias. Las huellas completas de datos y esquema de las dos bases protegidas coincidieron antes y después.

Se crearon dos commits locales. No se hizo push ni se modificó el tag. El workspace conserva cambios e informes preexistentes ajenos al commit; no se descartaron ni se incorporaron en él.

## 2. Estado inicial y decisión de Git

Al inicio: rama `main`, HEAD `1e9b98002325a313b9de056de07ab456ac81be18`, índice sin cambios, 41 archivos rastreados modificados y 2.171 entradas sin seguimiento (principalmente evidencia, informes y datos de certificación previos). El registro está preservado en `/tmp/erp_release_git_status_initial.txt`.

El patrón `*.sql` de `.gitignore` ocultaba 42 migraciones presentes en el directorio. Se mantuvo la excepción `!migrations/*.sql` y se incorporaron explícitamente al índice las migraciones faltantes, junto con el código y las pruebas que forman el estado funcional certificado. No se agregó indiscriminadamente el contenido sin seguimiento.

Commits locales:

| Commit | Contenido |
|---|---|
| `5ef9636403699bb8125f479bdd4b1fd9a1718a70` | `release(erp-v1): complete migrations and certify clean build`; 89 archivos, incluidos los 42 SQL que faltaban, cambios ERP, controles de aislamiento y pruebas. |
| `b4e5a92292448527059b7aa7980707d10827ccd4` | `build(erp-v1): pin validated PostgreSQL driver`; actualiza `psycopg2-binary` de 2.9.9 a 2.9.12, que coincide con la versión usada en la certificación. |

La revisión de dependencias con `pip check` terminó sin conflictos. `pip install --no-index -r requirements.txt` confirmó que todos los paquetes declarados y sus versiones exactas están satisfechos en el entorno de certificación. No contiene credenciales el índice del release.

## 3. Inventario y validación de migraciones

Hay 30 versiones consecutivas, `000001`–`000030`, cada una con un único archivo `up` y su pareja `down`; 60 archivos en total. No se encontraron nombres duplicados ni parejas ausentes. Las migraciones `000028_purchase_payment_items`, `000029_expense_payment_items` y `000030_payment_opening_snapshots` están incluidas.

La prueba limpia aplicó todas las migraciones en orden, desde `000001` hasta `000030`, mediante `tools/migrate.py`. PostgreSQL aceptó las constraints, índices y vistas del esquema; el registro aplicado coincidió con los 30 archivos fuente. Resultado: **58 tablas, 180 índices, 234 constraints y 2 vistas**. No se aplicó DDL a `facturacion` ni a `facturacion_cleanup_verify`.

## 4. Reconstrucción desde checkout limpio

Se creó `/tmp/erp-v1-release-clean-final` desde el commit final. El checkout estaba limpio y contenía los 60 SQL versionados; no se copiaron archivos de aplicación desde el árbol de trabajo original. La base de validación y su rol se crearon con nombre y marcador efímeros, con una identidad restringida.

Resultados:

- Aplicadas las 30 migraciones desde el checkout limpio.
- Bootstrap de catálogos sintéticos completado al importar Flask en modo de prueba autorizado.
- `GET /health`: **200**, `status=healthy`, base conectada.
- Rutas Flask registradas: **189**.
- Base y rol efímeros eliminados: **sí**; restantes: **0**.
- Paquetes declarados: satisfechos; `pip check`: sin dependencias rotas.

Comandos principales:

```bash
git clone --no-hardlinks --no-local --branch main . /tmp/erp-v1-release-clean-final
venv/bin/pip install --no-index -r /tmp/erp-v1-release-clean-final/requirements.txt
venv/bin/python correccion_certificacion_erp_v1/scripts/verify_clean_release_build.py \
  --checkout /tmp/erp-v1-release-clean-final --env-file .env
```

El log de migraciones, verificación de esquema, health check y limpieza está en [clean_build_reconstruction.log](correccion_certificacion_erp_v1/evidencia/release_clean_checkout_20261022/clean_build_reconstruction.log). La herramienta de verificación está en [verify_clean_release_build.py](correccion_certificacion_erp_v1/scripts/verify_clean_release_build.py); es un artefacto de auditoría fuera del commit de producto.

## 5. Resultado de certificación

La suite completa se ejecutó tomando como fuente el checkout limpio del commit final. La evidencia inicial registra HEAD `b4e5a92292448527059b7aa7980707d10827ccd4` y estado Git vacío. Los fixtures y la evidencia del harness se guardaron fuera del checkout, en `correccion_certificacion_erp_v1/evidencia/release_clean_checkout_confirmed_20261022/`.

| Área | Pruebas | PASS | FAIL | BLOCKED | SKIP/ERROR | Estado |
|---|---:|---:|---:|---:|---:|---|
| Regresión | 629 | 629 | 0 | 0 | 0 | GREEN |
| Funcional y E2E | 228 | 228 | 0 | 0 | 0 | GREEN |
| Navegador base | 75 | 75 | 0 | 0 | 0 | GREEN |
| Navegador ampliado | 90 | 90 | 0 | 0 | 0 | GREEN |
| Navegador crítico | 25 | 25 | 0 | 0 | 0 | GREEN |
| **Total único** | **1.047** | **1.047** | **0** | **0** | **0** | **GREEN** |

El runner de aislamiento del checkout limpio repitió además la suite de regresión en dos clones efímeros: **629/629 PASS en cada corrida**. Son repeticiones de la misma cobertura y no se suman al total único. Los logs son [primera corrida](correccion_certificacion_erp_v1/evidencia/release_clean_checkout_20261022/evidencia/baseline_isolated_1.log) y [segunda corrida](correccion_certificacion_erp_v1/evidencia/release_clean_checkout_20261022/evidencia/baseline_isolated_2.log).

### Verificaciones financieras y de inventario

- Neto, IVA y total: **192/192 PASS**, diferencia monetaria **$0**.
- Inventario ledger/lotes: **98/98 coincidencias**, diferencia de unidades **0**.
- Sobrepagos CxP de compra y gasto: **0**.
- Diferencias entre encabezados y eventos de pagos: **0**.
- Diferencias de monto en conciliación: **0**.
- Diferencias en transferencias internas: **0**.

Estas comprobaciones están incluidas en los escenarios funcionales y no se agregan otra vez al total de 1.047.

Evidencia principal: [XML regresión](correccion_certificacion_erp_v1/evidencia/release_clean_checkout_confirmed_20261022/evidencia/baseline.xml), [XML funcional/E2E](correccion_certificacion_erp_v1/evidencia/release_clean_checkout_confirmed_20261022/evidencia/certification.xml), [montos e inventario](correccion_certificacion_erp_v1/evidencia/release_clean_checkout_confirmed_20261022/evidencia/control_monetario_final.json), [aislamiento](correccion_certificacion_erp_v1/evidencia/release_clean_checkout_confirmed_20261022/evidencia/aislamiento.json), [huella inicial](correccion_certificacion_erp_v1/evidencia/release_clean_checkout_confirmed_20261022/evidencia/estado_inicial.json) y [huella final](correccion_certificacion_erp_v1/evidencia/release_clean_checkout_confirmed_20261022/evidencia/estado_final.json). Los resultados de navegador están en `navegador.json`, `navegador_ampliado.json` y `navegador_critico.json` dentro de ese directorio.

## 6. Seguridad e integridad de bases

En el harness integral, el rol de prueba tuvo **cero** privilegios efectivos de escritura en tablas o secuencias, creación en el esquema público, creación de bases y membresía en roles en ambas bases protegidas. Las huellas completas de esquema y filas de `facturacion` y `facturacion_cleanup_verify` fueron idénticas antes y después.

Al finalizar no quedaron bases o roles de certificación ni la base auxiliar de migraciones. La reconstrucción desde cero también eliminó su base/rol. La evidencia final detectó **cero coincidencias** con los valores locales `DB_PASSWORD` y `SECRET_KEY`; no se imprimieron ni versionaron secretos.

## 7. Archivos del release y exclusiones

El commit incluye:

- Las **42 migraciones SQL** que faltaban (`000007`–`000024` y `000028`–`000030`, con sus pares `up/down`); junto a las 18 ya rastreadas suman las 30 migraciones completas.
- `.gitignore` con excepción para los SQL de `migrations/`.
- Correcciones de CxP, flujo de caja, conciliación, costos, precios, ventas, inventario y producción en `repositories/`, `routes/`, `services/`, `core/`, `app.py` y `db.py`.
- Pantallas y plantillas relacionadas, incluidas cotizaciones, logo de empresa, CxP, ventas y administración.
- Guardas de PostgreSQL, runners y pruebas unitarias, de integración, seguridad y recorrido financiero.
- `requirements.txt` alineado con la versión probada de `psycopg2-binary`.

Se excluyeron del commit los informes y capturas previos, logs/dumps, `.env`, artefactos sintéticos y `tools/repair_legacy_production_valuation.py` (utilidad de reparación histórica que no forma parte del arranque ni del release). Los cambios previos en `CONTEXTO_MAESTRO_ERP.md` e `INFORME_AISLAMIENTO_BASE_TESTS.md` también se conservaron fuera del commit.

## 8. Estado final de Git y acciones pendientes

- Rama `main`; HEAD `b4e5a92292448527059b7aa7980707d10827ccd4`.
- El checkout de release en `/tmp/erp-v1-release-clean-final` permaneció limpio.
- El workspace original mantiene dos documentos modificados previamente y los informes/evidencias sin seguimiento; no se descartaron.
- Índice final: sin cambios preparados.
- Tag `v1.0.0`: intacto.
- Push/publicación remota: no realizado.
- No quedan acciones técnicas bloqueantes identificadas para reconstruir el release.

## 9. Dictamen y recomendación

**GREEN para release controlado.** Los archivos de esquema y el código están versionados; el commit final reconstruye el esquema desde cero; Flask arranca; 1.047 pruebas funcionales, financieras y de navegador aprobaron; y las bases protegidas permanecieron intactas.

El commit está local en `main` y listo para revisión/despliegue controlado. No se publicó ni se movió `v1.0.0`.
