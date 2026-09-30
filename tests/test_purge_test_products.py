import os
from tools.purge_test_products import KEEP_SQL, guard_environment


def test_keep_set_is_deterministic_oldest_then_id():
    assert 'ORDER BY created_at ASC, id ASC LIMIT %s' in KEEP_SQL


def test_purge_guard_rejects_production(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    try:
        guard_environment()
    except RuntimeError as exc:
        assert 'producción' in str(exc)
    else:
        raise AssertionError('production guard did not reject')
