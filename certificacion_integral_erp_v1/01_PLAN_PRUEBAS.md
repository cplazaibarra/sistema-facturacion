# Plan de certificación ERP V1

Alcance: versión de trabajo Python/Flask, Jinja/JavaScript y PostgreSQL monotenant, con modificaciones previas sin commit. HEAD y tag exactos se conservan en `evidencia/estado_inicial.json`. No se equipara el tag v1.0.0 a este árbol modificado.

Se identificaron 32 familias funcionales agrupadas en 20 módulos. Se planificaron cinco escenarios nuevos por familia, cinco ciclos empresariales completos, cinco comprobaciones de navegador por familia y cinco formularios adicionales de cotización, y la regresión existente como soporte, no como sustituto de un oráculo financiero independiente. Ocho pruebas heredadas de migración se planifican BLOCKED por incompatibilidad con el namespace de aislamiento.

Método: operación normal, valores diferentes, límite/validación, integración y repetición/reversa/complejidad. Los detalles ejecutables son `tests/test_certification.py` y `tests/test_cycles.py`; `scripts/reference.py` calcula importes independientemente de servicios monetarios productivos. No se aceptan tolerancias de pesos: Decimal ROUND_HALF_UP, subtotal a 0,01, neto/IVA a 1 peso; PPP a 0,0001 conforme al valor expuesto por el repositorio.

La preparación usa una copia de archivos fuera del workspace productivo y una base efímera marcada, vaciada dentro del clon. El usuario de pruebas carece de permisos de escritura en las dos bases protegidas y no puede crear bases ni roles. `sitecustomize.py` rechaza conexiones externas al clon. Las migraciones pendientes y uploads sólo ocurren dentro de ese entorno. `run.py` limpia base, rol, procesos y filesystem en finally, también al fallar pruebas.

Datos iniciales: 10 clientes, 10 proveedores, 20 productos, lotes, materias primas, terminados y stock cero; dos bancos ficticios. Los datos de volumen adicionales para paginación son explícitamente sintéticos. Inventario inicial y obligaciones de apertura están cuantificados en `datos_sinteticos.json`. Catálogos, usuarios y secuencias son fixtures; sus ajustes durante la preparación no modifican el ERP.

Los fallos originales de preparación y de adaptadores se conservan en carpetas de intentos. Los resultados finales se contabilizan una vez por identificador; los intentos previos no se suman como nuevas funcionalidades aprobadas.

Comando reproducible: `venv/bin/python certificacion_integral_erp_v1/scripts/run.py`. Herramientas instaladas existentes; no se instalaron dependencias. Ninguna corrección productiva, commit, push, modificación de tag o de OT reales forma parte de la certificación.
