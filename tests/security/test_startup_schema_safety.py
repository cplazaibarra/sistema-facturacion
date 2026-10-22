"""Startup must not apply DDL/seeds to an operational configuration.
All subprocesses still target only the restricted ephemeral PostgreSQL clone.
"""
import os,subprocess,sys,secrets
from pathlib import Path
import pytest

@pytest.mark.parametrize('environment',['development','production'])
def test_non_testing_import_does_not_migrate_readonly_database(environment):
    env=dict(os.environ,SECRET_KEY=secrets.token_hex(32),APP_ENV=environment,ERP_TEST_MODE='0',PGOPTIONS='-c default_transaction_read_only=on')
    # Inherit only the existing clone target; sitecustomize rejects any other DB.
    result=subprocess.run([sys.executable,'-c','import app; print("SAFE_STARTUP")'],cwd=Path(__file__).resolve().parents[2],env=env,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
    assert 'SAFE_STARTUP' in result.stdout
    assert 'Applying migration' not in result.stdout


def test_testing_import_requires_explicit_ephemeral_authorization():
    env=dict(os.environ,SECRET_KEY=secrets.token_hex(32),APP_ENV='testing',ERP_TEST_MODE='0',PGOPTIONS='-c default_transaction_read_only=on')
    result=subprocess.run([sys.executable,'-c','import app'],env=env,capture_output=True,text=True,timeout=20)
    assert result.returncode!=0
    assert 'ERP_TEST_MODE is not explicitly enabled' in result.stderr


def test_testing_initialization_is_really_blocked_by_postgres_readonly():
    env=dict(os.environ,SECRET_KEY=secrets.token_hex(32),APP_ENV='testing',ERP_TEST_MODE='1',PGOPTIONS='-c default_transaction_read_only=on')
    result=subprocess.run([sys.executable,'-c','import app'],env=env,capture_output=True,text=True,timeout=20)
    assert result.returncode!=0
    assert 'read-only transaction' in result.stderr


@pytest.mark.parametrize('environment',['development','production'])
def test_direct_initializer_refuses_non_testing_configuration(environment):
    env=dict(os.environ,SECRET_KEY=secrets.token_hex(32),APP_ENV=environment,ERP_TEST_MODE='0',PGOPTIONS='-c default_transaction_read_only=on')
    result=subprocess.run([sys.executable,'-c','from db import init_db; init_db()'],env=env,capture_output=True,text=True,timeout=20)
    assert result.returncode!=0
    assert 'ERP_TEST_MODE is not explicitly enabled' in result.stderr
    assert 'Applying migration' not in result.stdout
