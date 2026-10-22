"""
tests/integration/test_migrations_phase4.py
Automated test suite for Phase 4: Schema, Migrations, Parity, and Database Integrity.
"""

import os
import psycopg2
import psycopg2.extras
import pytest
from dotenv import load_dotenv
import tools.migrate as mig
import tools.seed_required as seed_req
import tools.compare_schema as cmp_schema
from core.test_database_guard import assert_current_test_database_authorized

load_dotenv()

@pytest.fixture(scope="module")
def fresh_test_db():
    """Empty DB provisioned by parent harness; never use a privileged connection."""
    assert_current_test_database_authorized()
    from core.test_database_guard import validate_test_database_config
    dbname = os.environ.get('MIGRATION_TEST_DB', '')
    # Separate run-name/marker, same restricted role. No fixed auxiliary DB.
    from urllib.parse import urlparse, urlunparse
    env = dict(os.environ)
    parsed = urlparse(env['TEST_DATABASE_URL'])
    url = urlunparse(parsed._replace(path='/'+dbname))
    env.update(DB_NAME=dbname,TEST_DATABASE_URL=url,DATABASE_URL=url,ERP_TEST_RUN_ID=dbname.rsplit('_',1)[1])
    validate_test_database_config(env)
    info = dict(host=env['DB_HOST'],port=env['DB_PORT'],user=env['DB_USER'],password=env['DB_PASSWORD'],dbname=dbname)
    with get_test_conn(info) as conn, conn.cursor() as cur:
        cur.execute("SELECT shobj_description(oid,'pg_database') AS marker FROM pg_database WHERE datname=current_database()")
        validate_test_database_config(env,cur.fetchone()['marker'])
        cur.execute("SELECT COUNT(*) AS n FROM pg_tables WHERE schemaname='public'")
        assert cur.fetchone()['n'] == 0, 'Migration fixture must start empty'
    yield info
    # Parent finally drops database even if collection/setup/test fails.


def get_test_conn(db_info):
    return psycopg2.connect(
        host=db_info["host"],
        port=db_info["port"],
        user=db_info["user"],
        password=db_info["password"],
        dbname=db_info["dbname"],
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def test_migrations_forward_apply_cleanly(fresh_test_db):
    """Verify that all migrations apply cleanly in an empty database."""
    with get_test_conn(fresh_test_db) as conn:
        total_files = len(mig.get_migration_files())
        applied = mig.apply_all_migrations(conn)
        assert applied == total_files, f"Expected {total_files} migrations applied, got {applied}"

        # Verify tracking in schema_migrations
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM schema_migrations;")
            assert cur.fetchone()["count"] == total_files


def test_migrations_idempotency(fresh_test_db):
    """Running up again on fully migrated database should apply 0 migrations."""
    with get_test_conn(fresh_test_db) as conn:
        applied = mig.apply_all_migrations(conn)
        assert applied == 0


def test_schema_parity_against_reference_db(fresh_test_db):
    """Compare schema between reference db and fresh test database."""
    ref_conn = mig.get_connection()
    test_conn = get_test_conn(fresh_test_db)

    try:
        ref_meta = cmp_schema.extract_schema_metadata(ref_conn)
        test_meta = cmp_schema.extract_schema_metadata(test_conn)
        diffs = cmp_schema.compare_schemas(ref_meta, test_meta, name1="reference", name2="test_fresh")
        assert len(diffs) == 0, f"Schema differences found: {diffs}"
    finally:
        ref_conn.close()
        test_conn.close()


def test_required_catalogs_seeding(fresh_test_db):
    """Verify that seed_required_catalogs populates essential roles, admin user, and config."""
    with get_test_conn(fresh_test_db) as conn:
        seed_req.seed_required_catalogs(conn)

        with conn.cursor() as cur:
            # Check roles
            cur.execute("SELECT COUNT(*) as count FROM roles;")
            assert cur.fetchone()["count"] >= 6

            # Check admin user
            cur.execute("SELECT username, email, is_active FROM users WHERE username = 'admin';")
            admin = cur.fetchone()
            assert admin is not None
            assert admin["username"] == "admin"
            assert admin["is_active"] is True

            # Check default bank account
            cur.execute("SELECT COUNT(*) as count FROM bank_accounts;")
            assert cur.fetchone()["count"] >= 1


def test_check_constraints_enforced(fresh_test_db):
    """Verify that CHECK constraints prevent invalid negative quantities."""
    with get_test_conn(fresh_test_db) as conn:
        # Create dummy product
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO products (sku, name, created_at) VALUES ('TEST-CHK-01', 'Test Product', NOW()::text) RETURNING id;"
            )
            prod_id = cur.fetchone()["id"]

            # Test lot_stock negative available_qty
            with pytest.raises(psycopg2.IntegrityError) as excinfo:
                cur.execute(
                    "INSERT INTO lot_stock (product_id, lot_number, initial_qty, available_qty) VALUES (%s, 'LOT-NEG', 10, -5);",
                    (prod_id,)
                )
            assert "chk_lot_stock_available_qty" in str(excinfo.value)
        conn.rollback()

        # Test inventory_movements quantity <> 0
        with conn.cursor() as cur:
            with pytest.raises(psycopg2.IntegrityError) as excinfo:
                cur.execute(
                    "INSERT INTO inventory_movements (product_id, movement_type, quantity, created_at) VALUES (%s, 'IN', 0, NOW()::text);",
                    (prod_id,)
                )
            assert "chk_inv_mov_quantity" in str(excinfo.value)
        conn.rollback()


def test_atomic_sequences_exist_and_increment(fresh_test_db):
    """Verify that business sequences exist and nextval works."""
    with get_test_conn(fresh_test_db) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT nextval('purchase_order_number_seq') AS po_num;")
            po_val = cur.fetchone()["po_num"]
            assert po_val >= 1

            cur.execute("SELECT nextval('sales_number_seq') AS sale_num;")
            sale_val = cur.fetchone()["sale_num"]
            assert sale_val >= 1

            cur.execute("SELECT nextval('production_order_number_seq') AS ot_num;")
            ot_val = cur.fetchone()["ot_num"]
            assert ot_val >= 1
        conn.commit()


def test_migration_rollback_step(fresh_test_db):
    """Verify that migration rollback (down) works step by step."""
    with get_test_conn(fresh_test_db) as conn:
        latest_version = mig.get_migration_files()[-1]["version"]
        reverted = mig.down_cmd(conn, steps=1)
        assert reverted == 1

        # Check status shows latest migration reverted
        applied = mig.get_applied_migrations(conn)
        assert latest_version not in applied

        # Re-apply latest migration to restore state
        reapplied = mig.up_cmd(conn)
        assert reapplied == 1
        applied = mig.get_applied_migrations(conn)
        assert latest_version in applied


def test_health_check_endpoint():
    """Verify /health endpoint works and reports healthy status."""
    from app import app
    client = app.test_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_rollback_preserves_posted_opening_snapshots(fresh_test_db):
    """A downgrade must not discard any financial snapshot, even in an isolated DB."""
    with get_test_conn(fresh_test_db) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO purchase_invoices(invoice_number,invoice_amount,payment_status) VALUES ('CERT-DOWN-PROTECTION',11900,'Pendiente') RETURNING id")
            invoice_id=cur.fetchone()['id']
            cur.execute("INSERT INTO purchase_payment_openings(invoice_id,payment_amount,payment_date) VALUES (%s,2000,'2026-10-20')",(invoice_id,))
        conn.commit()
        with pytest.raises(psycopg2.errors.RaiseException,match='historical snapshots must be preserved'):
            mig.down_cmd(conn,steps=1)
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute('SELECT payment_amount FROM purchase_payment_openings WHERE invoice_id=%s',(invoice_id,))
            assert cur.fetchone()['payment_amount']==2000
        assert mig.get_migration_files()[-1]['version'] in mig.get_applied_migrations(conn)
