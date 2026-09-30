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
