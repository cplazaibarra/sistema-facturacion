"""Negative cleanup tests use doubles; no PostgreSQL resources are touched."""
import pytest

import tools.run_isolated_tests as runner


def test_suite_always_requests_cleanup_when_pytest_process_raises(monkeypatch):
    names = ("facturacion_test_run_012345abcdef", "012345abcdef", "erp_test_012345abcdef", "secret", "facturacion_test_run_fedcba987654")
    cleaned = []
    monkeypatch.setattr(runner, "create_run_db", lambda cfg: names)
    monkeypatch.setattr(runner, "test_url", lambda *args: "postgresql://test:secret@localhost/db")
    monkeypatch.setattr(runner, "cleanup_run_resources", lambda cfg, dbs, role: cleaned.append((dbs, role)))
    monkeypatch.setattr(runner.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("simulated pytest failure")))

    with pytest.raises(RuntimeError, match="simulated pytest failure"):
        runner.run_suite({"DB_HOST": "localhost", "DB_PORT": "5432"}, 99)

    assert cleaned == [((names[4], names[0]), names[2])]


def test_cleanup_attempts_every_resource_even_when_one_drop_fails(monkeypatch):
    attempted = []

    def drop_database(cfg, dbname):
        attempted.append(dbname)
        if dbname.endswith("aaaaaaaaaaaa"):
            raise RuntimeError("simulated cleanup failure")

    monkeypatch.setattr(runner, "drop_run_db", drop_database)
    monkeypatch.setattr(runner, "drop_test_role", lambda cfg, role: attempted.append(role))
    with pytest.raises(RuntimeError, match="cleanup failed"):
        runner.cleanup_run_resources({}, ("facturacion_test_run_aaaaaaaaaaaa", "facturacion_test_run_bbbbbbbbbbbb"), "erp_test_cccccccccccc")

    assert attempted == ["facturacion_test_run_aaaaaaaaaaaa", "facturacion_test_run_bbbbbbbbbbbb", "erp_test_cccccccccccc"]


def test_runner_refuses_to_drop_database_with_wrong_marker(monkeypatch):
    statements = []

    class Cursor:
        def execute(self, statement, params=None):
            statements.append(str(statement))

        def fetchone(self):
            return ("ERP_TEST_DATABASE_TEMPLATE:v1",)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class Connection:
        autocommit = False

        def cursor(self):
            return Cursor()

        def close(self):
            pass

    monkeypatch.setattr(runner, "admin_connection", lambda *args, **kwargs: Connection())
    with pytest.raises(RuntimeError, match="without the matching ephemeral marker"):
        runner.drop_run_db({}, "facturacion_test_run_012345abcdef")
    assert not any("DROP DATABASE" in sql for sql in statements)
