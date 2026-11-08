"""Test-process boundary: no connection outside the marked ephemeral databases."""
import os
import re
if os.environ.get('CERTIFICATION_BOUNDARY') == '1':
    import psycopg2
    from psycopg2.extensions import parse_dsn
    original_connect = psycopg2.connect
    def guarded_connect(dsn=None, *args, **kwargs):
        params = parse_dsn(dsn) if dsn else {}
        params.update(kwargs)
        dbname = params.get('dbname', params.get('database'))
        allowed = {v for v in (os.environ.get('DB_NAME'), os.environ.get('MIGRATION_TEST_DB')) if v}
        if dbname not in allowed or not re.fullmatch(r'facturacion_test_run_[0-9a-f]{12}', dbname or ''):
            raise psycopg2.OperationalError('CERTIFICATION: connection outside the ephemeral database refused')
        if params.get('user', os.environ['DB_USER']) != os.environ['DB_USER']:
            raise psycopg2.OperationalError('CERTIFICATION: privileged database identity refused')
        if params.get('password', os.environ.get('DB_PASSWORD')) != os.environ.get('DB_PASSWORD'):
            raise psycopg2.OperationalError('CERTIFICATION: alternate database credential refused')
        if params.get('service') or params.get('servicefile') or params.get('hostaddr'):
            raise psycopg2.OperationalError('CERTIFICATION: libpq service/address overrides refused')
        if re.search(r'(?:^|\s)(?:-c\s+)?(?:role|session_authorization|session_replication_role)\s*=', str(params.get('options', '')), re.I):
            raise psycopg2.OperationalError('CERTIFICATION: libpq role-changing options refused')
        conn = original_connect(dsn, *args, **kwargs) if dsn else original_connect(*args, **kwargs)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user, shobj_description(oid, 'pg_database') FROM pg_database WHERE datname=current_database()")
                row = cur.fetchone()
                if isinstance(row, dict):
                    actual_db, actual_user, marker = row.get('current_database'), row.get('current_user'), row.get('shobj_description')
                else:
                    actual_db, actual_user, marker = row
            conn.rollback()
            expected_id = dbname.rsplit('_', 1)[1]
            if actual_db != dbname or actual_user != os.environ['DB_USER'] or marker != 'ERP_TEST_DATABASE_RUN:v1:' + expected_id:
                raise psycopg2.OperationalError(
                    'CERTIFICATION: database identity/marker mismatch '
                    f'(database_match={actual_db == dbname}, role_match={actual_user == os.environ["DB_USER"]}, '
                    f'marker_match={marker == "ERP_TEST_DATABASE_RUN:v1:" + expected_id}, '
                    f'actual_database={actual_db!r}, actual_role={actual_user!r}, actual_marker={marker!r}, '
                    f'expected_database={dbname!r}, expected_role={os.environ["DB_USER"]!r})'
                )
        except Exception:
            conn.close()
            raise
        return conn
    psycopg2.connect = guarded_connect
