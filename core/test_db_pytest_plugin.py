"""Pytest startup guard: verify the target database itself is an authorized run DB."""
import psycopg2
import pytest

from core.test_database_guard import (
    RUN_MARKER_PREFIX,
    UnsafeTestDatabase,
    validate_test_database_config,
)


def pytest_configure(config):
    import os
    try:
        target = validate_test_database_config(os.environ)
        conn = psycopg2.connect(
            host=target["host"], port=target["port"], dbname=target["database"],
            user=target["user"], password=target["password"], connect_timeout=5,
        )
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname=current_database()")
                row = cur.fetchone()
                marker = row[0] if row else None
            validate_test_database_config(os.environ, database_marker=marker)
        finally:
            conn.close()
    except (UnsafeTestDatabase, psycopg2.Error) as exc:
        raise pytest.UsageError(f"{exc}") from exc
