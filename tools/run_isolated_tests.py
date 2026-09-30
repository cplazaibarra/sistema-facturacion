#!/usr/bin/env python3
"""Run pytest twice on disposable clones of an explicitly marked test template."""
import argparse
import os
import re
import subprocess
import sys
import secrets
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
            cur.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (dbname,))
            cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(dbname)))
    finally:
        conn.close()


def create_run_db(cfg):
    run_id = secrets.token_hex(6)
    dbname = RUN_PREFIX + run_id
    conn = admin_connection(cfg)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("CREATE DATABASE {} WITH TEMPLATE {} OWNER {}").format(
                sql.Identifier(dbname), sql.Identifier(TEMPLATE_DB), sql.Identifier(cfg["DB_USER"])))
            cur.execute(sql.SQL("COMMENT ON DATABASE {} IS %s").format(sql.Identifier(dbname)),
                        (f"ERP_TEST_DATABASE_RUN:v1:{run_id}",))
    finally:
        conn.close()
    return dbname, run_id


def test_url(cfg, dbname):
    user = quote(cfg["DB_USER"], safe="")
    password = quote(cfg["DB_PASSWORD"], safe="")
    return f"postgresql://{user}:{password}@{cfg['DB_HOST']}:{cfg['DB_PORT']}/{dbname}"


def run_suite(cfg, number, pytest_args=()):
    dbname, run_id = create_run_db(cfg)
    url = test_url(cfg, dbname)
    env = os.environ.copy()
    env.update({
        "APP_ENV": "testing", "ERP_TEST_MODE": "1", "ERP_TEST_RUN_ID": run_id,
        "TEST_DATABASE_URL": url, "DATABASE_URL": url,
        "DB_HOST": cfg["DB_HOST"], "DB_PORT": str(cfg["DB_PORT"]),
        "DB_USER": cfg["DB_USER"], "DB_PASSWORD": cfg["DB_PASSWORD"], "DB_NAME": dbname,
    })
    log = Path(f"/tmp/erp_isolated_pytest_{number}.log")
    try:
        with log.open("w") as output:
            result = subprocess.run([sys.executable, "-m", "pytest", "-q", *pytest_args], cwd=ROOT,
                                    env=env, stdout=output, stderr=subprocess.STDOUT)
        print(f"SUITE {number}: {'GREEN' if result.returncode == 0 else 'RED'}; log={log}")
        print("\n".join(log.read_text(errors="replace").splitlines()[-18:]))
        return result.returncode, dbname
    finally:
        drop_run_db(cfg, dbname)


def render_report(before_normal, before_template, after, results):
    lines = [
        "# Informe de aislamiento de base de tests", "",
        f"**Fecha:** {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"**Base normal:** `{NORMAL_DB}`", f"**Base de plantilla test (persistente, inmutable durante suites):** `{TEMPLATE_DB}`",
        "**Aislamiento por suite:** copia PostgreSQL efímera `facturacion_test_run_<12 hex>`; se elimina en `finally`.",
        "**Protección:** pytest requiere URLs iguales, `APP_ENV=testing`, `ERP_TEST_MODE=1`, host/DB_NAME coincidentes y COMMENT de PostgreSQL con ID del run; cada conexión de app revalida configuración.", "",
        "Los conteos normal/template se toman con transacción `READ ONLY`. Cada suite clona la plantilla, ejecuta tests que pueden hacer commit/concurrencia y elimina la copia completa al finalizar. No hay rollback forzado sobre tests transaccionales.", "",
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
    results = []
    if args.pytest_args:
        code, _ = run_suite(cfg, 1, args.pytest_args)
        if table_counts(cfg, NORMAL_DB) != before_normal or table_counts(cfg, TEMPLATE_DB) != before_template:
            raise RuntimeError("Persistent counts changed during isolated diagnostic test run.")
        return code
    for number in (1, 2):
        status_code, _ = run_suite(cfg, number, args.pytest_args)
        after_normal_run = table_counts(cfg, NORMAL_DB)
        after_template_run = table_counts(cfg, TEMPLATE_DB)
        expected_status = "GREEN" if status_code == 0 else "RED"
        results.append((expected_status, after_normal_run))
        if after_normal_run != before_normal or after_template_run != before_template:
            raise RuntimeError("Persistent normal/test-template counts changed during isolated test run.")
        if status_code != 0:
            render_report(before_normal, before_template, after_template_run, results)
            return status_code
    render_report(before_normal, before_template, table_counts(cfg, TEMPLATE_DB), results)
    print("NORMAL DATABASE DELTA: 0; TEST TEMPLATE DELTA: 0; ephemeral run databases dropped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
