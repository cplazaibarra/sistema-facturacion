"""Pytest startup guard: verify the target database itself is an authorized run DB."""
import psycopg2
import pytest

from core.test_database_guard import (
    UnsafeTestDatabase,
    validate_connection_parameters,
    validate_test_database_config,
    verify_test_connection,
)


def pytest_configure(config):
    import os
    try:
        target = validate_test_database_config(os.environ)
        original_connect = psycopg2.connect
        conn = original_connect(
            host=target["host"], port=target["port"], dbname=target["database"],
            user=target["user"], password=target["password"], connect_timeout=5,
        )
        try:
            verify_test_connection(conn)
        finally:
            conn.close()

        # Cover direct psycopg2 calls in repositories, migration helpers,
        # concurrency tests, and child code imported after pytest startup.
        def guarded_connect(dsn=None, *args, **kwargs):
            params = dict(kwargs)
            if dsn is not None:
                params["dsn"] = dsn
            validate_connection_parameters(os.environ, params)
            opened = original_connect(dsn, *args, **kwargs) if dsn is not None else original_connect(*args, **kwargs)
            try:
                verify_test_connection(opened)
            except Exception:
                opened.close()
                raise
            return opened

        psycopg2.connect = guarded_connect
    except (UnsafeTestDatabase, psycopg2.Error) as exc:
        raise pytest.UsageError(f"{exc}") from exc
