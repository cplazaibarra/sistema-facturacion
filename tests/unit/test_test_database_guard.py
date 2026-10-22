import pytest

from core.test_database_guard import UnsafeTestDatabase, validate_test_database_config


RUN = "facturacion_test_run_012345abcdef"
URL = f"postgresql://tester:secret@127.0.0.1:5432/{RUN}"
MARKER = "ERP_TEST_DATABASE_RUN:v1:012345abcdef"


def env(**overrides):
    base = {
        "APP_ENV": "testing",
        "ERP_TEST_MODE": "1",
        "DATABASE_URL": URL,
        "TEST_DATABASE_URL": URL,
        "DB_NAME": RUN,
        "DB_HOST": "127.0.0.1",
        "DB_PORT": "5432",
        "DB_USER": "tester",
        "DB_PASSWORD": "secret",
        "ERP_TEST_RUN_ID": "012345abcdef",
    }
    base.update(overrides)
    return base


def test_authorized_ephemeral_test_database_is_allowed():
    result = validate_test_database_config(env(), database_marker=MARKER)
    assert result["database"] == RUN
    assert result["run_id"] == "012345abcdef"


@pytest.mark.parametrize("overrides", [
    {"DB_NAME": "facturacion"},
    {"DATABASE_URL": "postgresql://u:p@127.0.0.1:5432/facturacion"},
    {"APP_ENV": "production"},
    {"APP_ENV": "development"},
])
def test_development_or_production_database_is_blocked(overrides):
    with pytest.raises(UnsafeTestDatabase):
        validate_test_database_config(env(**overrides), database_marker=MARKER)


@pytest.mark.parametrize("overrides", [
    {"DATABASE_URL": ""},
    {"TEST_DATABASE_URL": ""},
    {"ERP_TEST_MODE": "0"},
    {"DB_HOST": "db-prod.internal"},
    {"DB_NAME": "facturacion_test_run_other"},
    {"DATABASE_URL": "postgresql://u:p@127.0.0.1:5432/facturacion_test_run_012345abcdef",
     "TEST_DATABASE_URL": "postgresql://u:p@127.0.0.1:5432/facturacion_test_run_fedcba987654"},
])
def test_absent_or_ambiguous_configuration_is_blocked(overrides):
    with pytest.raises(UnsafeTestDatabase):
        validate_test_database_config(env(**overrides), database_marker=MARKER)


def test_missing_or_incorrect_database_marker_is_blocked():
    with pytest.raises(UnsafeTestDatabase):
        validate_test_database_config(env(), database_marker=None)
    with pytest.raises(UnsafeTestDatabase):
        validate_test_database_config(env(), database_marker="ERP_TEST_DATABASE_TEMPLATE:v1")


@pytest.mark.parametrize("overrides", [
    {"APP_ENV": "production"},
    {"APP_ENV": "development"},
    {"ERP_TEST_MODE": "0"},
    {"DATABASE_URL": ""},
    {"TEST_DATABASE_URL": ""},
    {"DB_NAME": "facturacion"},
    {"DATABASE_URL": "postgresql://tester:secret@127.0.0.1:5432/facturacion"},
    {"DATABASE_URL": "postgresql://tester:secret@127.0.0.1:5432/facturacion_test_run_012345abcdef?options=-c%20search_path%3Dpublic"},
    {"DATABASE_URL": "postgresql://other:secret@127.0.0.1:5432/facturacion_test_run_012345abcdef"},
    {"DB_USER": "operational_admin"},
    {"ERP_TEST_RUN_ID": "fedcba987654"},
    {"DB_HOST": "db-prod.internal"},
    {"DATABASE_URL": "postgresql://tester:secret@127.0.0.1:5433/facturacion_test_run_012345abcdef"},
    {"DATABASE_URL": "postgresql://tester:secret@127.0.0.1:5432/facturacion_test_run_012345abcdef", "TEST_DATABASE_URL": "postgresql://tester:secret@127.0.0.1:5432/facturacion_test_run_fedcba987654"},
])
def test_required_negative_harness_configurations_are_blocked(overrides):
    with pytest.raises(UnsafeTestDatabase):
        validate_test_database_config(env(**overrides))


@pytest.mark.parametrize("params", [
    {"dbname": "facturacion"},
    {"dbname": "facturacion_cleanup_verify"},
    {"dbname": RUN, "user": "operational_admin"},
    {"dbname": RUN, "host": "db-prod.internal"},
    {"dbname": RUN, "port": 5433},
    {"dbname": RUN, "password": "another-password"},
    {"dbname": RUN, "hostaddr": "203.0.113.10"},
    {"dbname": RUN, "service": "production"},
    {"dbname": RUN, "options": "-c role=admin"},
])
def test_secondary_connection_to_non_authorized_target_is_blocked(params):
    from core.test_database_guard import validate_connection_parameters
    with pytest.raises(UnsafeTestDatabase):
        validate_connection_parameters(env(), params)


def test_safe_readonly_connection_options_are_allowed():
    from core.test_database_guard import validate_connection_parameters
    result = validate_connection_parameters(env(), {
        "dbname": RUN, "options": "-c default_transaction_read_only=on -c statement_timeout=45000"
    })
    assert result["database"] == RUN


@pytest.mark.parametrize("protected", ["facturacion", "facturacion_cleanup_verify"])
def test_migration_helper_refuses_protected_database_without_explicit_admin_switch(monkeypatch, protected):
    import tools.migrate as migrate
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ERP_TEST_MODE", "0")
    monkeypatch.delenv("ERP_ALLOW_PROTECTED_MIGRATIONS", raising=False)
    with pytest.raises(RuntimeError, match="protected database"):
        migrate.get_connection(protected)


def test_migration_helper_cannot_redirect_test_run_to_protected_database(monkeypatch):
    import tools.migrate as migrate
    for key, value in env().items():
        monkeypatch.setenv(key, value)
    with pytest.raises(UnsafeTestDatabase):
        migrate.get_connection("facturacion")
