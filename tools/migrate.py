#!/usr/bin/env python3
"""
tools/migrate.py
Lightweight SQL migration runner for the ERP system.
Supports transactional forward and reverse migrations tracking applied versions in schema_migrations table.
"""

import argparse
import os
import sys
import glob
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = BASE_DIR / "migrations"


def get_connection(dbname=None):
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=dbname or os.environ.get("DB_NAME", "facturacion"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def init_migrations_table(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(32) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
    conn.commit()


def get_applied_migrations(conn):
    init_migrations_table(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT version, name, applied_at FROM schema_migrations ORDER BY version ASC;")
        return {row["version"]: row for row in cur.fetchall()}


def get_migration_files():
    up_files = sorted(glob.glob(str(MIGRATIONS_DIR / "*_*.up.sql")))
    migrations = []
    for up_file in up_files:
        p = Path(up_file)
        version, name = p.name.split("_", 1)
        name = name[:-7]  # strip '.up.sql'
        down_file = p.parent / f"{version}_{name}.down.sql"
        migrations.append({
            "version": version,
            "name": name,
            "up_file": str(p),
            "down_file": str(down_file) if down_file.exists() else None,
        })
    return migrations


def apply_migration(conn, migration):
    version = migration["version"]
    name = migration["name"]
    up_file = migration["up_file"]
    print(f"Applying migration {version}_{name}...")
    with open(up_file, "r", encoding="utf-8") as f:
        sql = f.read()

    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (%s, %s);",
                (version, name),
            )
        conn.commit()
        print(f"  -> Successfully applied {version}_{name}")
    except Exception as e:
        conn.rollback()
        print(f"  [ERROR] Failed to apply {version}_{name}: {e}", file=sys.stderr)
        raise


def rollback_migration(conn, migration):
    version = migration["version"]
    name = migration["name"]
    down_file = migration["down_file"]
    if not down_file or not os.path.exists(down_file):
        raise FileNotFoundError(f"Down migration file missing for version {version}: {down_file}")

    print(f"Reverting migration {version}_{name}...")
    with open(down_file, "r", encoding="utf-8") as f:
        sql = f.read()

    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute("DELETE FROM schema_migrations WHERE version = %s;", (version,))
        conn.commit()
        print(f"  -> Successfully reverted {version}_{name}")
    except Exception as e:
        conn.rollback()
        print(f"  [ERROR] Failed to revert {version}_{name}: {e}", file=sys.stderr)
        raise


def status_cmd(conn):
    applied = get_applied_migrations(conn)
    all_mig = get_migration_files()
    print("=" * 60)
    print("MIGRATION STATUS")
    print("=" * 60)
    if not all_mig:
        print("No migration files found in", MIGRATIONS_DIR)
        return

    for m in all_mig:
        v = m["version"]
        if v in applied:
            app_info = applied[v]
            print(f"[APPLIED]   {v}_{m['name']} (applied at: {app_info['applied_at']})")
        else:
            print(f"[PENDING]   {v}_{m['name']}")
    print("=" * 60)


def up_cmd(conn, target_version=None):
    applied = get_applied_migrations(conn)
    all_mig = get_migration_files()
    pending = [m for m in all_mig if m["version"] not in applied]

    if not pending:
        print("No pending migrations to apply.")
        return 0

    applied_count = 0
    for m in pending:
        if target_version and m["version"] > target_version:
            break
        apply_migration(conn, m)
        applied_count += 1
    print(f"Done. Applied {applied_count} migration(s).")
    return applied_count


def down_cmd(conn, steps=1, all_down=False):
    applied = get_applied_migrations(conn)
    all_mig = {m["version"]: m for m in get_migration_files()}
    sorted_applied = sorted(applied.keys(), reverse=True)

    if not sorted_applied:
        print("No applied migrations to revert.")
        return 0

    to_revert = sorted_applied if all_down else sorted_applied[:steps]
    reverted_count = 0
    for v in to_revert:
        if v not in all_mig:
            raise RuntimeError(f"Cannot revert version {v}: corresponding migration files not found!")
        rollback_migration(conn, all_mig[v])
        reverted_count += 1
    print(f"Done. Reverted {reverted_count} migration(s).")
    return reverted_count


def mark_applied(conn, version, name):
    """Mark a migration as applied without running SQL (used for initial adoption if tables already exist)."""
    init_migrations_table(conn)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO schema_migrations (version, name) 
            VALUES (%s, %s)
            ON CONFLICT (version) DO NOTHING;
            """,
            (version, name)
        )
    conn.commit()


def apply_all_migrations(conn):
    """Programmatic entry point for application bootstrap."""
    return up_cmd(conn)


def main():
    parser = argparse.ArgumentParser(description="ERP PostgreSQL Migration Runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Initialize schema_migrations table")
    subparsers.add_parser("status", help="Show current migration status")

    up_parser = subparsers.add_parser("up", help="Apply pending migrations")
    up_parser.add_argument("--to", dest="target_version", help="Target migration version")

    down_parser = subparsers.add_parser("down", help="Rollback migrations")
    down_parser.add_argument("--steps", type=int, default=1, help="Number of migrations to revert")
    down_parser.add_argument("--all", action="store_true", help="Revert all applied migrations")

    args = parser.parse_args()

    with get_connection() as conn:
        if args.command == "init":
            init_migrations_table(conn)
            print("schema_migrations table initialized.")
        elif args.command == "status":
            status_cmd(conn)
        elif args.command == "up":
            up_cmd(conn, target_version=args.target_version)
        elif args.command == "down":
            down_cmd(conn, steps=args.steps, all_down=args.all)


if __name__ == "__main__":
    main()
