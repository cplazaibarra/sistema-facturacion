"""Fail-closed guard for pytest database connections."""
import os
from urllib.parse import parse_qs, unquote, urlparse


RUN_PREFIX = "facturacion_test_run_"
RUN_MARKER_PREFIX = "ERP_TEST_DATABASE_RUN:v1:"
_MARKER_NOT_CHECKED = object()


class UnsafeTestDatabase(RuntimeError):
    pass


def validate_test_database_config(env, database_marker=_MARKER_NOT_CHECKED):
    """Validate explicit test mode, matching URLs, and the DB-level run marker."""
    if env.get("ERP_TEST_MODE") != "1":
        raise UnsafeTestDatabase("Tests refused: ERP_TEST_MODE is not explicitly enabled.")
    if env.get("APP_ENV") != "testing":
        raise UnsafeTestDatabase("Tests refused: APP_ENV is not testing.")
    test_url = env.get("TEST_DATABASE_URL")
    app_url = env.get("DATABASE_URL")
    if not test_url or not app_url:
        raise UnsafeTestDatabase("Tests refused: TEST_DATABASE_URL and DATABASE_URL are required.")
    if test_url != app_url:
        raise UnsafeTestDatabase("Tests refused: DATABASE_URL does not match TEST_DATABASE_URL.")
    parsed = urlparse(test_url)
    if parsed.scheme not in ("postgres", "postgresql") or not parsed.hostname or not parsed.path:
        raise UnsafeTestDatabase("Tests refused: database URL is invalid or ambiguous.")
    dbname = unquote(parsed.path.lstrip("/"))
    if not dbname.startswith(RUN_PREFIX):
        raise UnsafeTestDatabase("Tests refused: database is not an ephemeral authorized test run.")
    run_id = dbname[len(RUN_PREFIX):]
    if len(run_id) != 12 or any(ch not in "0123456789abcdef" for ch in run_id.lower()):
        raise UnsafeTestDatabase("Tests refused: test database name has an invalid run ID.")
    if env.get("DB_NAME") != dbname:
        raise UnsafeTestDatabase("Tests refused: DB_NAME and test URL target different databases.")
    if env.get("DB_HOST") != parsed.hostname:
        raise UnsafeTestDatabase("Tests refused: DB_HOST and test URL host do not match.")
    if str(env.get("DB_PORT", "5432")) != str(parsed.port or 5432):
        raise UnsafeTestDatabase("Tests refused: DB_PORT and test URL port do not match.")
    if database_marker is not _MARKER_NOT_CHECKED:
        expected = f"{RUN_MARKER_PREFIX}{run_id}"
        if database_marker != expected:
            raise UnsafeTestDatabase("Tests refused: PostgreSQL database marker is absent or invalid.")
    return {"database": dbname, "run_id": run_id, "host": parsed.hostname,
            "port": parsed.port or 5432, "user": unquote(parsed.username or ""),
            "password": unquote(parsed.password or "")}


def assert_current_test_database_authorized(check_database=True):
    """Fail closed before app import or destructive test DB setup."""
    target = validate_test_database_config(os.environ)
    if check_database:
        import psycopg2
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
