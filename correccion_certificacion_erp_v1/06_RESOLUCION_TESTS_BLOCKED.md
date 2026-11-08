# Resolución de los ocho casos bloqueados

Módulo: tests/integration/test_migrations_phase4.py. El bloqueo anterior era de seguridad: un fixture intentaba DROP/CREATE sobre `facturacion_test_phase4_auto` y conectarse como administrador a postgres. No era una dependencia faltante de negocio. No se ejecutó ese comportamiento.

El harness crea una segunda base vacía `facturacion_test_run_<id>` con marker propio y el mismo usuario restringido NOSUPERUSER/NOCREATEDB/NOCREATEROLE/NOINHERIT. El fixture valida nombre, URLs, marker y estado vacío; sólo usa esa base. El guard de conexiones permite exclusivamente ambas bases efímeras enumeradas, con la misma identidad restringida. Ninguna conexión auxiliar apunta a postgres desde los tests. El proceso padre elimina ambas bases y el rol en finally.

| Prueba original | Condición habilitada | Resultado de primera ejecución habilitada |
|---|---|---|
| test_migrations_forward_apply_cleanly | Base efímera vacía con permisos DDL propios | PASS |
| test_migrations_idempotency | Esquema migrado en la base anterior | PASS |
| test_schema_parity_against_reference_db | Comparación de dos clones, nunca contra normal | PASS |
| test_required_catalogs_seeding | Catálogos sintéticos en base auxiliar | PASS |
| test_check_constraints_enforced | Persistencia y rollback reales en auxiliar | PASS |
| test_atomic_sequences_exist_and_increment | Secuencias en auxiliar | PASS |
| test_migration_rollback_step | Down/up real, sólo auxiliar | PASS |
| test_health_check_endpoint | Flask conectado al clon principal | PASS |

Se agregó además test_rollback_preserves_posted_opening_snapshots: una migración down debe rechazar eliminar capturas financieras existentes y conservar el contenido. Los down de los ledgers también rechazan la eliminación de pagos ya registrados.

No se otorgaron permisos para escribir en facturacion o facturacion_cleanup_verify. Evidencia de cada base eliminada y huellas de contenido en aislamiento.json / estado_inicial.json / estado_final.json. El informe final registra nuevamente los ocho resultados de la última ronda.
