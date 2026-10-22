#!/usr/bin/env python3
"""Run pytest twice on disposable clones of an explicitly marked test template."""
import argparse
import os
import re
import subprocess
import sys
import secrets
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DB = "facturacion_cleanup_verify"
NORMAL_DB = "facturacion"
TEMPLATE_MARKER = "ERP_TEST_DATABASE_TEMPLATE:v1"
RUN_PREFIX = "facturacion_test_run_"
COUNTS = {
    "Productos": "products", "Ventas": "sales", "Órdenes de Compra": "purchase_orders",
    "Recepciones": "inventory_entries", "Movimientos": "inventory_movements", "Lotes": "lot_stock",
    "OT": "production_orders", "Clientes": "clients", "Proveedores": "suppliers",
    "Cuentas": "bank_accounts", "Deudas": "debts",
    "Revaluaciones": "inventory_cost_revaluations",
}


def config():
    load_dotenv(ROOT / ".env")
    result = {k: os.getenv(k) for k in ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD")}
    result["DB_HOST"] = result["DB_HOST"] or "127.0.0.1"
    result["DB_PORT"] = result["DB_PORT"] or "5432"
    if not result["DB_USER"] or result["DB_PASSWORD"] is None:
        raise RuntimeError("Test runner requires DB_USER and DB_PASSWORD from environment/.env.")
    return result


def admin_connection(cfg, dbname="postgres"):
    return psycopg2.connect(host=cfg["DB_HOST"], port=cfg["DB_PORT"], user=cfg["DB_USER"],
                            password=cfg["DB_PASSWORD"], dbname=dbname, connect_timeout=5)


def database_marker(cfg, dbname):
    with admin_connection(cfg) as conn, conn.cursor() as cur:
        cur.execute("SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname=%s", (dbname,))
        row = cur.fetchone()
        return row[0] if row else None


def table_counts(cfg, dbname):
    conn = psycopg2.connect(host=cfg["DB_HOST"], port=cfg["DB_PORT"], user=cfg["DB_USER"],
                            password=cfg["DB_PASSWORD"], dbname=dbname, connect_timeout=5,
                            options="-c default_transaction_read_only=on")
    conn.set_session(readonly=True, autocommit=False)
    result = {}
    try:
        with conn.cursor() as cur:
            for label, table in COUNTS.items():
                cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                if cur.fetchone()[0] is None:
                    result[label] = None
                else:
                    cur.execute(sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(table)))
                    result[label] = int(cur.fetchone()[0])
            cur.execute("SELECT count(*) FILTER(WHERE status='Cotización'), count(*) FILTER(WHERE status<>'Cotización' OR status IS NULL) FROM sales")
            result["Cotizaciones"], result["Ventas"] = map(int, cur.fetchone())
    finally:
        conn.rollback()
        conn.close()
    return result


def database_fingerprint(cfg, dbname):
    """Read-only fingerprint of public row contents and schema objects."""
    conn = admin_connection(cfg, dbname)
    conn.set_session(readonly=True, autocommit=False)
    tables = {}
    schema = {}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
            for (table,) in cur.fetchall():
                cur.execute(sql.SQL("SELECT count(*),md5(COALESCE(string_agg(h,'' ORDER BY h),'')) FROM (SELECT md5(to_jsonb(t)::text) AS h FROM public.{} t) rows").format(sql.Identifier(table)))
                count, digest = cur.fetchone()
                tables[table] = {"count": count, "sha256": digest}
            queries = {
                "relations": "SELECT c.relname,c.relkind,pg_get_userbyid(c.relowner),CASE WHEN c.relkind IN ('v','m') THEN pg_get_viewdef(c.oid,true) END FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S','i','I','f') ORDER BY c.relname",
                "columns": "SELECT table_name,column_name,ordinal_position,data_type,udt_name,is_nullable,column_default,character_maximum_length,numeric_precision,numeric_scale FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position",
                "constraints": "SELECT conrelid::regclass::text,conname,contype,pg_get_constraintdef(oid,true) FROM pg_constraint WHERE connamespace='public'::regnamespace ORDER BY 1,2",
                "triggers": "SELECT event_object_table,trigger_name,event_manipulation,action_timing,action_statement FROM information_schema.triggers WHERE trigger_schema='public' ORDER BY event_object_table,trigger_name,event_manipulation",
                "functions": "SELECT p.proname,pg_get_function_identity_arguments(p.oid),pg_get_function_result(p.oid),p.prokind,pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.prokind <> 'a' ORDER BY p.proname,2",
                "extensions": "SELECT extname,extversion FROM pg_extension ORDER BY extname",
            }
            for name, query in queries.items():
                cur.execute(query)
                schema[name] = cur.fetchall()
        return {
            "tables": tables,
            "schema_sha256": hashlib.sha256(json.dumps(schema, default=str, sort_keys=True).encode()).hexdigest(),
        }
    finally:
        conn.rollback()
        conn.close()


def ensure_marked_template(cfg):
    marker = database_marker(cfg, TEMPLATE_DB)
    if marker != TEMPLATE_MARKER:
        raise RuntimeError(
            f"Test runner refused: {TEMPLATE_DB} is not explicitly marked as a test template; marker={marker!r}. "
            "Mark it only after confirming this database is isolated."
        )


def mark_template(cfg):
    if TEMPLATE_DB != "facturacion_cleanup_verify" or TEMPLATE_DB == NORMAL_DB:
        raise RuntimeError("Refusing to mark an unexpected database as a test template.")
    conn = admin_connection(cfg)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname=%s", (TEMPLATE_DB,))
            if cur.fetchone() is None:
                raise RuntimeError(f"Test template database {TEMPLATE_DB} does not exist.")
            cur.execute(sql.SQL("COMMENT ON DATABASE {} IS %s").format(sql.Identifier(TEMPLATE_DB)), (TEMPLATE_MARKER,))
    finally:
        conn.close()
    print(f"Marked isolated test template {TEMPLATE_DB}; no table data changed.")


def drop_run_db(cfg, dbname):
    if not re.fullmatch(r"facturacion_test_run_[0-9a-f]{12}", dbname):
        raise RuntimeError("Refusing to drop database outside the ephemeral test-run namespace.")
    conn = admin_connection(cfg)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s", (dbname,))
            row = cur.fetchone()
            if row and row[0] != f"ERP_TEST_DATABASE_RUN:v1:{dbname.rsplit('_', 1)[1]}":
                raise RuntimeError("Refusing to drop a database without the matching ephemeral marker.")
            if row:
                cur.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (dbname,))
                cur.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(dbname)))
    finally:
        conn.close()


def drop_test_role(cfg, role):
    if not re.fullmatch(r"erp_test_[0-9a-f]{12}", role):
        raise RuntimeError("Refusing to drop a role outside the ephemeral test namespace.")
    conn = admin_connection(cfg)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
    finally:
        conn.close()


def cleanup_run_resources(cfg, databases, role):
    """Attempt every cleanup independently and report any resource left behind."""
    errors = []
    for dbname in databases:
        try:
            drop_run_db(cfg, dbname)
        except Exception as exc:
            errors.append(f"database {dbname}: {type(exc).__name__}")
    try:
        drop_test_role(cfg, role)
    except Exception as exc:
        errors.append(f"role {role}: {type(exc).__name__}")
    if errors:
        raise RuntimeError("Ephemeral resource cleanup failed: " + "; ".join(errors))


def create_run_db(cfg):
    run_id = secrets.token_hex(6)
    dbname = RUN_PREFIX + run_id
    role = f"erp_test_{run_id}"
    password = secrets.token_urlsafe(32)
    created = []
    role_created = False
    try:
        conn = admin_connection(cfg)
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT").format(sql.Identifier(role)), (password,))
                role_created = True
                cur.execute(sql.SQL("CREATE DATABASE {} WITH TEMPLATE {} OWNER {}").format(
                    sql.Identifier(dbname), sql.Identifier(TEMPLATE_DB), sql.Identifier(role)))
                created.append(dbname)
                cur.execute(sql.SQL("COMMENT ON DATABASE {} IS %s").format(sql.Identifier(dbname)),
                            (f"ERP_TEST_DATABASE_RUN:v1:{run_id}",))
                migration_db = RUN_PREFIX + secrets.token_hex(6)
                migration_id = migration_db.rsplit("_", 1)[1]
                cur.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(migration_db), sql.Identifier(role)))
                created.append(migration_db)
                cur.execute(sql.SQL("COMMENT ON DATABASE {} IS %s").format(sql.Identifier(migration_db)),
                            (f"ERP_TEST_DATABASE_RUN:v1:{migration_id}",))
        finally:
            conn.close()
        # Transfer only cloned objects to the restricted run role. The role
        # owns nothing in the two persistent databases.
        conn = admin_connection(cfg, dbname)
        try:
            with conn.cursor() as cur:
                cur.execute(sql.SQL("GRANT ALL ON SCHEMA public TO {}").format(sql.Identifier(role)))
                cur.execute(sql.SQL("GRANT ALL ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(role)))
                cur.execute(sql.SQL("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO {}").format(sql.Identifier(role)))
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                for (name,) in cur.fetchall():
                    cur.execute(sql.SQL("ALTER TABLE {} OWNER TO {}").format(sql.Identifier(name), sql.Identifier(role)))
                cur.execute("SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema='public'")
                for (name,) in cur.fetchall():
                    cur.execute(sql.SQL("ALTER SEQUENCE {} OWNER TO {}").format(sql.Identifier(name), sql.Identifier(role)))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        cleanup_errors = []
        for disposable_db in created:
            try:
                drop_run_db(cfg, disposable_db)
            except Exception as exc:
                cleanup_errors.append(f"database {disposable_db}: {type(exc).__name__}")
        if role_created:
            try:
                drop_test_role(cfg, role)
            except Exception as exc:
                cleanup_errors.append(f"role {role}: {type(exc).__name__}")
        if cleanup_errors:
            raise RuntimeError("Ephemeral provisioning failed and cleanup needs review: " + "; ".join(cleanup_errors))
        raise
    return dbname, run_id, role, password, migration_db


def test_url(cfg, dbname, user, password):
    user = quote(user, safe="")
    password = quote(password, safe="")
    return f"postgresql://{user}:{password}@{cfg['DB_HOST']}:{cfg['DB_PORT']}/{dbname}"


def run_suite(cfg, number, pytest_args=()):
    resources = None
    try:
        dbname, run_id, role, password, migration_db = create_run_db(cfg)
        resources = (dbname, migration_db, role)
        url = test_url(cfg, dbname, role, password)
        env = os.environ.copy()
        for key in list(env):
            if key.startswith("PG"):
                env.pop(key, None)
        env.update({
            "APP_ENV": "testing", "ERP_TEST_MODE": "1", "ERP_TEST_RUN_ID": run_id,
            "CERTIFICATION_BOUNDARY": "1",
            "TEST_DATABASE_URL": url, "DATABASE_URL": url,
            "DB_HOST": cfg["DB_HOST"], "DB_PORT": str(cfg["DB_PORT"]),
            "DB_USER": role, "DB_PASSWORD": password, "DB_NAME": dbname,
            "MIGRATION_TEST_DB": migration_db,
            "PYTHONPATH": str(ROOT / "correccion_certificacion_erp_v1" / "scripts") + os.pathsep + os.environ.get("PYTHONPATH", ""),
        })
        log = Path(f"/tmp/erp_isolated_pytest_{number}.log")
        with log.open("w") as output:
            result = subprocess.run([sys.executable, "-m", "pytest", "-q", *pytest_args], cwd=ROOT,
                                    env=env, stdout=output, stderr=subprocess.STDOUT)
        print(f"SUITE {number}: {'GREEN' if result.returncode == 0 else 'RED'}; log={log}")
        print("\n".join(log.read_text(errors="replace").splitlines()[-18:]))
        return result.returncode, dbname
    finally:
        if resources:
            cleanup_run_resources(cfg, (resources[1], resources[0]), resources[2])


def render_report(before_normal, before_template, after, results, hashes):
    lines = [
        "# Informe de aislamiento de base de tests", "",
        f"**Fecha:** {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"**Base normal:** `{NORMAL_DB}`", f"**Base de plantilla test (persistente, inmutable durante suites):** `{TEMPLATE_DB}`",
        "**Aislamiento por suite:** copia PostgreSQL efímera `facturacion_test_run_<12 hex>`; se elimina en `finally`.",
        "**Protección:** pytest requiere URLs iguales, `APP_ENV=testing`, `ERP_TEST_MODE=1`, host/DB_NAME coincidentes y COMMENT de PostgreSQL con ID del run; cada conexión de app revalida configuración.", "",
        "Los conteos normal/template se toman con transacción `READ ONLY`. Cada suite clona la plantilla, ejecuta tests que pueden hacer commit/concurrencia y elimina la copia completa al finalizar. No hay rollback forzado sobre tests transaccionales.", "",
        f"**Huella completa de datos/esquema normal estable:** `{hashes['facturacion']['before'] == hashes['facturacion']['after']}`; SHA-256 esquema antes/después `{hashes['facturacion']['before']['schema_sha256']}` / `{hashes['facturacion']['after']['schema_sha256']}`.",
        f"**Huella completa de datos/esquema plantilla estable:** `{hashes[TEMPLATE_DB]['before'] == hashes[TEMPLATE_DB]['after']}`; SHA-256 esquema antes/después `{hashes[TEMPLATE_DB]['before']['schema_sha256']}` / `{hashes[TEMPLATE_DB]['after']['schema_sha256']}`.", "",
        "## Base normal antes", "", "| Entidad | Cantidad |", "|---|---:|",
    ]
    for k,v in before_normal.items(): lines.append(f"| {k} | {v if v is not None else 'N/A'} |")
    lines += ["", "## Suites y comparación de conteos", ""]
    for i, (status, counts) in enumerate(results, 1):
        lines += [f"### Suite completa #{i}: {status}", "", "| Entidad | Antes | Después | Delta |", "|---|---:|---:|---:|"]
        for key, initial in before_normal.items():
            final = counts.get(key)
            delta = final - initial if initial is not None and final is not None else "N/A"
            lines.append(f"| {key} | {initial if initial is not None else 'N/A'} | {final if final is not None else 'N/A'} | {delta} |")
        lines.append("")
    lines += ["## Base persistente de test", "", "| Entidad | Antes suites | Después suite #2 | Delta |", "|---|---:|---:|---:|"]
    for key, initial in before_template.items():
        final = after.get(key)
        delta = final - initial if initial is not None and final is not None else "N/A"
        lines.append(f"| {key} | {initial if initial is not None else 'N/A'} | {final if final is not None else 'N/A'} | {delta} |")
    lines += ["", "## Auditoría del harness", "",
              "- `tests/conftest.py` anterior cargaba `.env` y luego importaba `app`; `app.py` inicializa esquema en import y podía conectarse a `facturacion`.",
              "- Muchas integraciones hacen `commit()` en varias conexiones y limpian sólo parte de sus documentos; rollback global no sería seguro.",
              "- Las pruebas de concurrencia, idempotencia, transacciones y migraciones conservan commits reales dentro de la DB efímera.",
              "- Unit/integration/security todas corren en la copia temporal. Browser/E2E externos no se encontraron como tests ejecutables en el árbol; scripts que usen pytest heredan el guard.",
              "- Fábricas siguen distribuidas; el aislamiento de DB por suite contiene fixtures heredados incluso cuando el teardown local es incompleto.",
              "- Tests nuevos del guard cubren permitido, development/production bloqueado, URL ausente, configuración ambigua y marker incorrecto.",
              "- La suite de migraciones crea `facturacion_test_phase4_auto` y tiene teardown explícito; queda dentro del proceso ya autorizado y se destruye al terminar el módulo.", "",
              "No se ejecutaron `TRUNCATE`, deletes ni limpieza de datos de la base normal. Los datos preexistentes permanecen intactos.", ""]
    (ROOT / "INFORME_AISLAMIENTO_BASE_TESTS.md").write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mark-template", action="store_true")
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--pytest-args", nargs=argparse.REMAINDER, default=[])
    args = parser.parse_args()
    cfg = config()
    if args.mark_template:
        mark_template(cfg)
        return 0
    if args.runs not in (1, 2):
        raise RuntimeError("The isolated workflow supports one diagnostic or two full suite runs.")
    ensure_marked_template(cfg)
    before_normal = table_counts(cfg, NORMAL_DB)
    before_template = table_counts(cfg, TEMPLATE_DB)
    hashes = {name: {"before": database_fingerprint(cfg, name)} for name in (NORMAL_DB, TEMPLATE_DB)}
    results = []
    if args.pytest_args:
        code, _ = run_suite(cfg, 1, args.pytest_args)
        after_hashes = {name: database_fingerprint(cfg, name) for name in (NORMAL_DB, TEMPLATE_DB)}
        if table_counts(cfg, NORMAL_DB) != before_normal or table_counts(cfg, TEMPLATE_DB) != before_template or any(after_hashes[n] != hashes[n]["before"] for n in hashes):
            raise RuntimeError("Protected database row/schema fingerprints changed during isolated diagnostic test run.")
        return code
    for number in (1, 2):
        status_code, _ = run_suite(cfg, number, args.pytest_args)
        after_normal_run = table_counts(cfg, NORMAL_DB)
        after_template_run = table_counts(cfg, TEMPLATE_DB)
        after_hashes = {name: database_fingerprint(cfg, name) for name in (NORMAL_DB, TEMPLATE_DB)}
        for name in hashes:
            hashes[name]["after"] = after_hashes[name]
        expected_status = "GREEN" if status_code == 0 else "RED"
        results.append((expected_status, after_normal_run))
        if after_normal_run != before_normal or after_template_run != before_template or any(after_hashes[n] != hashes[n]["before"] for n in hashes):
            raise RuntimeError("Protected database row/schema fingerprints changed during isolated test run.")
        if status_code != 0:
            render_report(before_normal, before_template, after_template_run, results, hashes)
            return status_code
    render_report(before_normal, before_template, table_counts(cfg, TEMPLATE_DB), results, hashes)
    print("NORMAL DATABASE ROW/SCHEMA HASHES: unchanged; TEST TEMPLATE ROW/SCHEMA HASHES: unchanged; ephemeral run databases dropped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
