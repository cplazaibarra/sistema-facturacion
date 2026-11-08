"""Test-process boundary: no database connections outside the authorized clone."""
import os
if os.environ.get('CERTIFICATION_BOUNDARY') == '1':
    import psycopg2
    from psycopg2.extensions import parse_dsn
    original_connect = psycopg2.connect
    def guarded_connect(dsn=None, *args, **kwargs):
        params = parse_dsn(dsn) if dsn else {}
        params.update(kwargs)
        if params.get('dbname', params.get('database')) != os.environ['DB_NAME']:
            raise psycopg2.OperationalError('CERTIFICATION: connection outside the ephemeral database refused')
        if params.get('user', os.environ['DB_USER']) != os.environ['DB_USER']:
            raise psycopg2.OperationalError('CERTIFICATION: privileged database identity refused')
        return original_connect(dsn, *args, **kwargs) if dsn else original_connect(*args, **kwargs)
    psycopg2.connect = guarded_connect
