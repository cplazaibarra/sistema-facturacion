# PLAN DE CONTINGENCIA Y RECUPERACIÓN DE BASE DE DATOS (FASE 4)

**Objetivo:** Procedimiento operativo seguro para respaldar, validar y restaurar la base de datos PostgreSQL del ERP en caso de fallo durante o después de aplicar las migraciones.

---

## 1. Copias de Seguridad (Backup)

### Respaldo Pre-Fase 4
Se generó un dump binario completo de la base de datos antes de cualquier modificación estructural:
- **Ubicación:** `backups/pre_phase4_backup.dump`
- **Comando de generación:**
  ```bash
  docker exec -t facturacion-db pg_dump -U facturador -d facturacion -F c -b -v > backups/pre_phase4_backup.dump
  ```
- **Tamaño:** ~115 KB (incluye esquema y datos completos).

### Procedimiento de Respaldo Periódico / Previo a Despliegues
```bash
BACKUP_FILE="backups/db_backup_$(date +%Y%m%d_%H%M%S).dump"
docker exec -t facturacion-db pg_dump -U facturador -d facturacion -F c -b -v > "$BACKUP_FILE"
```

---

## 2. Procedimiento de Restauración Completa (Disaster Recovery)

En caso de fallo catastrófico que requiera revertir el estado exacto de la base de datos:

1. **Detener la aplicación web:**
   ```bash
   pkill -f "python.*app.py" || true
   ```

2. **Cerrar conexiones activas y recrear base de datos:**
   ```bash
   docker exec -i facturacion-db psql -U facturador -d postgres -c "
     SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'facturacion' AND pid <> pg_backend_pid();
     DROP DATABASE IF EXISTS facturacion;
     CREATE DATABASE facturacion OWNER facturador;
   "
   ```

3. **Restaurar el dump:**
   ```bash
   cat backups/pre_phase4_backup.dump | docker exec -i facturacion-db pg_restore -U facturador -d facturacion --clean --if-exists
   ```

4. **Verificar integridad:**
   ```bash
   ./venv/bin/pytest -v
   ```

---

## 3. Reversión Granular por Migración (Down Migrations)

El sistema de migraciones implementado en `tools/migrate.py` soporta rollback controlado paso a paso mediante scripts `.down.sql`:

- Ver estado actual:
  ```bash
  ./venv/bin/python tools/migrate.py status
  ```

- Revertir la última migración aplicada:
  ```bash
  ./venv/bin/python tools/migrate.py down
  ```

- Revertir todas las migraciones:
  ```bash
  ./venv/bin/python tools/migrate.py down --all
  ```

Cada paso de migración se ejecuta dentro de un bloque transaccional atómico (`BEGIN ... COMMIT`). Si una sentencia falla durante la aplicación o reversión, PostgreSQL revierte automáticamente el bloque completo sin dejar esquemas corruptos o a medio migrar.
