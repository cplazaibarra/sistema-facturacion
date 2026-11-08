#!/usr/bin/env python3
"""Rebuild a clean ERP V1 checkout in a marked disposable PostgreSQL database."""
import argparse
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--env-file", required=True, type=Path)
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    if not (checkout / ".git").exists() or not (checkout / "app.py").is_file():
        raise SystemExit("Checkout must be a Git checkout containing app.py")
    load_dotenv(args.env_file.resolve())
    host = os.getenv("DB_HOST") or "127.0.0.1"
    port = str(os.getenv("DB_PORT") or "5432")
    admin_user = os.environ["DB_USER"]
    admin_password = os.environ["DB_PASSWORD"]
    run_id = secrets.token_hex(6)
    dbname = f"facturacion_test_run_{run_id}"
    role = f"erp_test_{run_id}"
    role_password = secrets.token_urlsafe(32)
    if not re.fullmatch(r"facturacion_test_run_[0-9a-f]{12}", dbname):
        raise RuntimeError("Generated database name failed the ephemeral namespace guard")

    admin = psycopg2.connect(
        host=host, port=port, user=admin_user, password=admin_password,
        dbname="postgres", connect_timeout=8,
    )
    admin.autocommit = True
    role_created = False
    database_created = False
    try:
        with admin.cursor() as cur:
            cur.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT")
                .format(sql.Identifier(role)), (role_password,),
            )
            role_created = True
            cur.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(dbname), sql.Identifier(role),
            ))
            database_created = True
            cur.execute(sql.SQL("COMMENT ON DATABASE {} IS %s").format(
                sql.Identifier(dbname),
            ), (f"ERP_TEST_DATABASE_RUN:v1:{run_id}",))

        env = os.environ.copy()
        for key in list(env):
            if key.startswith("PG"):
                env.pop(key, None)
        url = (f"postgresql://{quote(role, safe='')}:{quote(role_password, safe='')}"
               f"@{host}:{port}/{dbname}")
        env.update(
            APP_ENV="testing", ERP_TEST_MODE="1", ERP_TEST_RUN_ID=run_id,
            DB_NAME=dbname, DB_HOST=host, DB_PORT=port, DB_USER=role,
            DB_PASSWORD=role_password, DATABASE_URL=url, TEST_DATABASE_URL=url,
            PYTHONPATH=str(checkout), PYTHONUNBUFFERED="1",
        )
        print("CHECKOUT_HEAD", subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=checkout, text=True,
        ).strip())
        migrated = subprocess.run(
            [sys.executable, str(checkout / "tools/migrate.py"), "up"],
            cwd=checkout, env=env, check=False,
        )
        if migrated.returncode:
            raise RuntimeError("Clean checkout migration command failed")

        with psycopg2.connect(
            host=host, port=port, user=role, password=role_password,
            dbname=dbname, connect_timeout=8,
        ) as conn, conn.cursor() as cur:
            cur.execute("SELECT version, name FROM schema_migrations ORDER BY version")
            applied = cur.fetchall()
            expected = sorted(
                (path.name.split("_", 1)[0], path.name.split("_", 1)[1][:-7])
                for path in (checkout / "migrations").glob("*.up.sql")
            )
            if applied != expected or len(applied) != 30:
                raise RuntimeError(f"Expected 30 ordered migrations; found {len(applied)}")
            cur.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'")
            tables = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM pg_indexes WHERE schemaname='public'")
            indexes = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM information_schema.views WHERE table_schema='public'")
            views = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM pg_constraint WHERE connamespace='public'::regnamespace")
            constraints = cur.fetchone()[0]
        print("SCHEMA", {"migrations": len(applied), "first": applied[0][0],
                          "last": applied[-1][0], "tables": tables,
                          "indexes": indexes, "views": views,
                          "constraints": constraints})

        health_code = (
            "from app import app; client=app.test_client(); response=client.get('/health'); "
            "print('FLASK_HEALTH', response.status_code, response.get_json()); "
            "assert response.status_code == 200 and response.get_json().get('status') == 'healthy'; "
            "print('FLASK_ROUTES', len(app.url_map._rules))"
        )
        result = subprocess.run(
            [sys.executable, "-c", health_code], cwd=checkout, env=env, check=False,
        )
        if result.returncode:
            raise RuntimeError("Clean checkout Flask health check failed")
        print("CLEAN_BUILD_RESULT PASS")
    finally:
        with admin.cursor() as cur:
            if database_created:
                cur.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=%s AND pid<>pg_backend_pid()", (dbname,),
                )
                cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(dbname)))
            if role_created:
                cur.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
            cur.execute("SELECT count(*) FROM pg_database WHERE datname=%s", (dbname,))
            remaining_db = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM pg_roles WHERE rolname=%s", (role,))
            remaining_role = cur.fetchone()[0]
        admin.close()
        print("CLEANUP", {"remaining_database": remaining_db, "remaining_role": remaining_role})
        if remaining_db or remaining_role:
            raise RuntimeError("Ephemeral PostgreSQL cleanup did not complete")


if __name__ == "__main__":
    main()
