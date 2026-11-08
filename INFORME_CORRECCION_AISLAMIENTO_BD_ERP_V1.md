# Informe de corrección del aislamiento PostgreSQL — ERP V1

**Fecha:** 21 de octubre de 2026  
**Dictamen:** **YELLOW**  
**Repositorio:** rama `main`, HEAD `1e9b98002325a313b9de056de07ab456ac81be18` (`v1.0.0-9-g1e9b980`).  
**Informe consolidado en la raíz del proyecto**, según lo solicitado.

## 1. Resumen ejecutivo

Se endureció el aislamiento de pytest, los dos runners de pruebas, las conexiones secundarias, la inicialización Flask y el acceso del migrador a bases protegidas. La ejecución completa final utilizó clones PostgreSQL efímeros y terminó con:

- Regresión: **629 PASS, 0 FAIL, 0 errores, 0 omitidas**.
- Pruebas funcionales/E2E: **228 PASS**.
- Navegador: **190 PASS** (75 + 90 + 25).
- Total de la recertificación integral: **1.047 pruebas PASS**, sin fallos ni bloqueos.
- Ejecución focal del runner genérico: **42 PASS**; cubre configuración del guard, credenciales/destinos alternativos y fallos de limpieza simulados.
- Diferencias de huellas de contenido/esquema en `facturacion`: **0**.
- Diferencias de huellas de contenido/esquema en `facturacion_cleanup_verify`: **0**.
- Bases efímeras restantes: **0**. Roles temporales restantes: **0**.

El dictamen queda YELLOW porque la auditoría anterior confirmó DDL histórico en `facturacion`, pero no pudo atribuir el proceso/PID que lo aplicó. Esta fase demuestra que las ejecuciones finales no lo reprodujeron y que el proceso de pruebas careció de permisos efectivos para escribir en las bases protegidas; no borra ni revierte los objetos históricos.

## 2. Estado inicial

- Rama inicial: `main`.
- HEAD y tag V1 se conservaron durante el trabajo. No hubo commit, push, checkout, reset ni migración operacional.
- El árbol ya tenía cambios sin commit antes de esta tarea, incluidas correcciones financieras, archivos de auditoría y cambios de interfaz. Se preservaron; los cambios de esta fase se limitaron principalmente a aislamiento, migrador, runner y pruebas.
- El inventario exacto del estado sucio inicial se conserva en [git_estado_inicial.txt](correccion_certificacion_erp_v1/evidencia/aislamiento_definitivo/git_estado_inicial.txt).
- La última evidencia anterior señaló DDL en `facturacion`: migraciones `000028`, `000029` y `000030`, cuatro tablas vacías y dos vistas. Sus marcas de tiempo fueron 2026-10-21 03:45:48, 03:50:21 y 03:55:19 UTC. La plantilla no contenía esos cambios.
- La evidencia histórica no identificó un PID responsable. No se atribuye el incidente a un proceso específico sin prueba.

Fuentes históricas: [incidente de esquema de solo lectura](correccion_certificacion_erp_v1/evidencia/incidente_esquema_auditoria_solo_lectura.json), [certificación anterior](correccion_certificacion_erp_v1/10_INFORME_FINAL_RECERTIFICACION.md), [aislamiento anterior](INFORME_AISLAMIENTO_BASE_TESTS.md).

## 3. Diagnóstico y causa acotada

El cambio histórico fue DDL real, no un falso positivo de conteo: cambió `schema_migrations`, se añadieron tablas y vistas. Las huellas anteriores indicaban que las filas históricas previas no cambiaron y que las tablas nuevas estaban vacías. El origen del proceso que emitió el DDL continúa sin determinarse.

La auditoría de código acotó vías que podían permitir una repetición accidental:

1. Antes de la contención previa, importar Flask llamaba a `init_db()` automáticamente. Eso constituía una ruta de migración al importar o recargar la aplicación, aunque no demuestra que esa ruta originara el DDL observado.
2. El guard previo comparaba principalmente configuración al inicio; las conexiones secundarias no verificaban consistentemente el usuario real, el marcador de cada conexión y el destino resuelto por PostgreSQL.
3. `tools/run_isolated_tests.py` entregaba al proceso pytest las credenciales del usuario configurado para preparar la plantilla y sólo comparaba conteos. El usuario de la suite no era una identidad temporal independiente.
4. El runner genérico no garantizaba que todos los recursos se intentaran limpiar cuando fallaba pytest o una operación de limpieza.

La limitación histórica del actor está documentada; las vías de ejecución de pruebas y migración descritas arriba quedaron corregidas y probadas.

## 4. Protecciones implementadas

- `core/test_database_guard.py` exige `APP_ENV=testing`, `ERP_TEST_MODE=1`, URLs iguales y explícitas, nombre efímero con identificador hexadecimal, run ID coincidente, host/puerto/usuario/clave iguales y marcador PostgreSQL correcto. Rechaza URLs con parámetros ambiguos, roles alternativos, servicios libpq y destinos secundarios ajenos.
- Cada conexión de prueba comprueba en el servidor `current_database()`, `current_user` y el comentario marcador. La consulta de control se revierte antes de devolver la conexión para no interferir con el nivel de aislamiento de la aplicación.
- El plugin temprano de pytest valida antes de cargar `tests/conftest.py` y Flask; además intercepta conexiones directas de `psycopg2`, incluidas conexiones concurrentes y a la base auxiliar de migraciones.
- Ambos runners eliminan del entorno hijo las variables heredadas `PG*` que podrían redirigir libpq a otro servidor o base; sólo vuelven a incorporar las credenciales efímeras autorizadas. El runner genérico hereda además el límite `sitecustomize` para sus subprocesos.
- `core/database.py` valida el destino y la identidad de toda conexión en modo de pruebas. La inicialización previa de `app.py` y `db.init_db()` permanece condicionada a testing autorizado; no se debilitó ni se eliminó.
- `tools/migrate.py` rechaza conexiones a `facturacion` o a la plantilla salvo autorización administrativa explícita `ERP_ALLOW_PROTECTED_MIGRATIONS=1`. En modo de pruebas exige la identidad efímera y verifica el marcador.
- `tools/run_isolated_tests.py` crea un rol temporal `NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT`, crea clones efímeros y no entrega las credenciales de preparación al proceso pytest. Compara huellas completas de filas y esquema, no sólo conteos.
- El runner de certificación comprueba privilegios efectivos sobre tablas, esquema público, secuencias, creación de bases y membresías en roles para ambas bases protegidas. Su `sitecustomize` impide conexiones secundarias fuera del conjunto efímero marcado.
- La limpieza valida el marcador antes de borrar una base y sigue intentando limpiar los demás recursos aunque una eliminación falle. Un fallo de limpieza se reporta como error, no como éxito.

## 5. Pruebas negativas

Se ejecutaron **42 casos de guard/control del runner** en la ejecución focal del runner genérico. Incluyen configuración de producción/desarrollo, modo de prueba apagado, URL ausente o contradictoria, destinos protegidos, run ID incorrecto, identidad de usuario/host/puerto/clave inválida, `hostaddr`, conexiones secundarias, opciones que intentan cambiar autorización, y migraciones dirigidas a bases protegidas.

También se verificaron:

- **6 pruebas de arranque** con PostgreSQL efímero y modo de sólo lectura: importación en desarrollo/producción sin migración automática; rechazo del modo de prueba sin autorización; inicialización de prueba bloqueada por PostgreSQL READ ONLY; y rechazo de llamada directa a `init_db()` fuera del modo autorizado.
- **3 pruebas de fallo/limpieza** con dobles controlados: excepción durante pytest, fallo al borrar una de varias bases y rechazo de borrar una base con marcador incorrecto. No crean ni escriben datos en PostgreSQL.
- Pruebas de migración en una base auxiliar efímera marcada; no se usó una base fija ni la plantilla para aplicar DDL.

Resultado de la ejecución focal: `42 passed`. Registro reproducible: [runner genérico](correccion_certificacion_erp_v1/evidencia/aislamiento_definitivo/runner_generico.log).

## 6. Recertificación y resultados financieros

La ejecución final completa terminó con código cero en cada etapa:

| Etapa | Ejecutadas | PASS | FAIL/ERROR |
|---|---:|---:|---:|
| Regresión pytest | 629 | 629 | 0 |
| Funcional y E2E | 228 | 228 | 0 |
| Navegador base | 75 | 75 | 0 |
| Navegador ampliado | 90 | 90 | 0 |
| Navegador crítico | 25 | 25 | 0 |

La suite funcional incluye los cinco ciclos integrados y escenarios de CxP, flujo de caja, conciliación, producción y otros módulos. Las 192 comprobaciones monetarias independientes aprobaron; 98 pares de inventario ledger/lotes coincidieron. No se detectaron sobrepagos, desajustes cabecera/eventos, diferencias de conciliación, transferencias asimétricas ni diferencias monetarias.

## 7. Huellas de bases protegidas

La huella incluye filas serializadas de cada tabla y una huella de metadatos de relaciones, columnas, constraints, triggers, funciones, vistas y extensiones.

| Base | Objetos de datos antes/después | Huella de esquema antes | Huella de esquema después | Resultado |
|---|---:|---|---|---|
| `facturacion` | 58 / 58 tablas | `b2e80a1ea0b225e89d88c2f65b84f62042c11e7d80c982d1acd5eb9aeaac1a3b` | `b2e80a1ea0b225e89d88c2f65b84f62042c11e7d80c982d1acd5eb9aeaac1a3b` | Igual |
| `facturacion_cleanup_verify` | 54 / 54 tablas | `1be6eff8378a5045ca644c7397f57e15f07245cb1c3cecb3fd0249bdf45e406d` | `1be6eff8378a5045ca644c7397f57e15f07245cb1c3cecb3fd0249bdf45e406d` | Igual |

La comparación de las entradas completas también resultó idéntica, no sólo el resumen de cantidad. La plantilla permaneció intacta. Las migraciones históricas 000028–000030 permanecen en `facturacion`; no se revirtieron ni se borraron registros.

Evidencia final:

- [estado y limpieza del harness](correccion_certificacion_erp_v1/evidencia/recertificacion_aislamiento_final_confirmada/evidencia/aislamiento.json)
- [huella inicial](correccion_certificacion_erp_v1/evidencia/recertificacion_aislamiento_final_confirmada/evidencia/estado_inicial.json)
- [huella final](correccion_certificacion_erp_v1/evidencia/recertificacion_aislamiento_final_confirmada/evidencia/estado_final.json)
- [regresión XML](correccion_certificacion_erp_v1/evidencia/recertificacion_aislamiento_final_confirmada/evidencia/baseline.xml)
- [funcionales/E2E XML](correccion_certificacion_erp_v1/evidencia/recertificacion_aislamiento_final_confirmada/evidencia/certification.xml)
- [resultados navegador](correccion_certificacion_erp_v1/evidencia/recertificacion_aislamiento_final_confirmada/evidencia/navegador.json)
- [conciliación monetaria](correccion_certificacion_erp_v1/evidencia/recertificacion_aislamiento_final_confirmada/evidencia/control_monetario_final.json)

## 8. Archivos modificados en esta fase

- `core/database.py`
- `core/test_database_guard.py`
- `core/test_db_pytest_plugin.py`
- `tools/migrate.py`
- `tools/run_isolated_tests.py`
- `tests/unit/test_test_database_guard.py`
- `tests/unit/test_isolated_test_runner.py` (nuevo)
- `tests/integration/test_migrations_phase4.py`
- `correccion_certificacion_erp_v1/scripts/run.py`
- `correccion_certificacion_erp_v1/scripts/sitecustomize.py`
- `INFORME_CORRECCION_AISLAMIENTO_BD_ERP_V1.md` (este informe)

Las correcciones financieras existentes se conservaron; sus archivos no se modificaron en esta fase. `app.py` y `db.py` conservan la barrera de inicialización de la fase previa.

## 9. Estado de recursos, Git y credenciales

- Clon principal, base auxiliar de migraciones y rol de la última ejecución: eliminados; consultas finales reportaron **0 restantes**.
- Código y archivos temporales del servidor de navegador: eliminados al cerrar el runner.
- Huellas protegidas: idénticas antes/después.
- HEAD y tag `v1.0.0`: sin cambios.
- El árbol de Git sigue teniendo cambios preexistentes y cambios nuevos sin commit. No se hicieron commits ni pushes.
- `git diff --check` para los archivos de esta fase: sin errores.
- Barrido de 106 archivos de evidencia final contra los valores locales de `DB_PASSWORD` y `SECRET_KEY`: **0 coincidencias**. No se incluyeron credenciales en el informe.
- No se ejecutaron reparaciones históricas ni se alteró OT-09270.

## 10. Riesgos pendientes y dictamen

**Dictamen: YELLOW.** La barrera actual quedó probada en la suite completa, el navegador, conexiones secundarias y migraciones auxiliares; no se detectaron cambios en las bases protegidas durante esta recertificación. El runner de pruebas usa identidades limitadas y la comparación incluye estructura y contenido.

No se declara GREEN porque sigue sin conocerse qué proceso aplicó las migraciones históricas a `facturacion`. Los objetos de ese incidente permanecen allí y no se revirtieron, conforme a las restricciones. La evidencia permite concluir que la ejecución final actual no produjo cambios protegidos; no permite atribuir retrospectivamente el DDL histórico a un proceso con PID demostrado.

### Comandos reproducibles

```bash
venv/bin/python correccion_certificacion_erp_v1/scripts/run.py --output-name recertificacion_aislamiento_final_confirmada
venv/bin/python tools/run_isolated_tests.py --pytest-args tests/unit/test_isolated_test_runner.py tests/unit/test_test_database_guard.py
```

Los runners leen las credenciales sólo en el proceso de preparación, no las imprimen y pasan a pytest un rol temporal distinto.
