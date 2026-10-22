"""Fail-closed guard for pytest database connections."""
import os
import re
from urllib.parse import unquote, urlparse


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
    if (parsed.scheme not in ("postgres", "postgresql") or not parsed.hostname or not parsed.path
            or parsed.query or parsed.fragment or parsed.params):
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
    if not env.get("ERP_TEST_RUN_ID") or env["ERP_TEST_RUN_ID"] != run_id:
        raise UnsafeTestDatabase("Tests refused: ERP_TEST_RUN_ID does not match the ephemeral database.")
    user = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    if not user or user != env.get("DB_USER") or password != env.get("DB_PASSWORD"):
        raise UnsafeTestDatabase("Tests refused: database URL credentials do not match the restricted test role.")
    if database_marker is not _MARKER_NOT_CHECKED:
        expected = f"{RUN_MARKER_PREFIX}{run_id}"
        if database_marker != expected:
            raise UnsafeTestDatabase("Tests refused: PostgreSQL database marker is absent or invalid.")
    return {"database": dbname, "run_id": run_id, "host": parsed.hostname,
            "port": parsed.port or 5432, "user": user, "password": password}


def validate_connection_parameters(env, params):
    """Reject secondary/ambiguous connections before libpq can open a socket."""
    target = validate_test_database_config(env)
    dsn = params.pop("dsn", None)
    if dsn:
        parsed_dsn = urlparse(dsn)
        if parsed_dsn.scheme:
            if parsed_dsn.query or parsed_dsn.fragment:
                raise UnsafeTestDatabase("Tests refused: connection URL options are not allowed.")
            resolved = {
                "dbname": unquote(parsed_dsn.path.lstrip("/")),
                "host": parsed_dsn.hostname,
                "port": str(parsed_dsn.port or 5432),
                "user": unquote(parsed_dsn.username or ""),
                "password": unquote(parsed_dsn.password or ""),
            }
        else:
            from psycopg2.extensions import parse_dsn
            resolved = parse_dsn(dsn)
        resolved.update(params)
        params = resolved
    dbname = params.get("dbname", params.get("database", target["database"]))
    host = params.get("host", target["host"])
    port = str(params.get("port", target["port"]))
    user = params.get("user", target["user"])
    password = params.get("password", target["password"])
    target = _authorized_connection_target(env, dbname)
    if (host != target["host"] or port != str(target["port"]) or user != target["user"]
            or password != target["password"]):
        raise UnsafeTestDatabase("Tests refused: secondary connection is outside the authorized ephemeral database/role.")
    if params.get("service") or params.get("servicefile") or params.get("hostaddr"):
        raise UnsafeTestDatabase("Tests refused: libpq service/address overrides may redirect a test connection.")
    options = str(params.get("options", ""))
    if re.search(r"(?:^|\s)(?:-c\s+)?(?:role|session_authorization|session_replication_role)\s*=", options, re.I):
        raise UnsafeTestDatabase("Tests refused: libpq options may not change the PostgreSQL role or authorization context.")
    return target


def _authorized_connection_target(env, dbname):
    target = validate_test_database_config(env)
    if dbname == target["database"]:
        return target
    auxiliary = env.get("MIGRATION_TEST_DB")
    if auxiliary and dbname == auxiliary and dbname.startswith(RUN_PREFIX):
        run_id = dbname[len(RUN_PREFIX):]
        if len(run_id) == 12 and all(ch in "0123456789abcdef" for ch in run_id.lower()):
            return {**target, "database": dbname, "run_id": run_id}
    raise UnsafeTestDatabase("Tests refused: connection is outside the authorized ephemeral database set.")


def verify_test_connection(conn, env=None):
    """Verify server-side database, role, and run marker on an opened connection."""
    env = os.environ if env is None else env
    target = validate_test_database_config(env)
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT current_database(), current_user,
                shobj_description(oid, 'pg_database')
                FROM pg_database WHERE datname=current_database()""")
            row = cur.fetchone()
        # The verification query opens a transaction. Leave the connection in
        # its original idle state so callers can set isolation/read-only mode.
        conn.rollback()
        if isinstance(row, dict):
            actual_db, actual_user, marker = row.get("current_database"), row.get("current_user"), row.get("shobj_description")
        else:
            actual_db, actual_user, marker = row if row else (None, None, None)
        actual_target = _authorized_connection_target(env, actual_db)
        if not row or actual_db != actual_target["database"] or actual_user != actual_target["user"]:
            raise UnsafeTestDatabase("Tests refused: PostgreSQL resolved a different database or role.")
        expected = f"{RUN_MARKER_PREFIX}{actual_target['run_id']}"
        if marker != expected:
            raise UnsafeTestDatabase("Tests refused: PostgreSQL database marker is absent or invalid.")
    except Exception:
        conn.close()
        raise
    return conn


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
            verify_test_connection(conn)
        finally:
            conn.close()
