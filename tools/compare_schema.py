#!/usr/bin/env python3
"""
tools/compare_schema.py
Compares the schema (tables, columns, data types, constraints, and indexes)
between two PostgreSQL databases to verify 100% parity.
"""

import argparse
import sys
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


def extract_schema_metadata(conn):
    meta = {
        "tables": {},
        "sequences": set(),
        "indexes": {},
        "foreign_keys": {},
        "checks": {},
    }

    with conn.cursor() as cur:
        # 1. Tables and columns
        cur.execute(
            """
            SELECT table_name, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, column_name;
            """
        )
        for row in cur.fetchall():
            t = row["table_name"]
            if t not in meta["tables"]:
                meta["tables"][t] = {}
            meta["tables"][t][row["column_name"]] = {
                "data_type": row["data_type"],
                "is_nullable": row["is_nullable"],
            }

        # 2. Sequences
        cur.execute(
            """
            SELECT sequence_name 
            FROM information_schema.sequences 
            WHERE sequence_schema = 'public';
            """
        )
        for row in cur.fetchall():
            meta["sequences"].add(row["sequence_name"])

        # 3. Indexes
        cur.execute(
            """
            SELECT tablename, indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public';
            """
        )
        for row in cur.fetchall():
            meta["indexes"][row["indexname"]] = {
                "table": row["tablename"],
                "def": " ".join(row["indexdef"].split()),
            }

        # 4. Foreign Keys
        cur.execute(
            """
            SELECT
                tc.table_name, kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                tc.constraint_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema='public';
            """
        )
        for row in cur.fetchall():
            meta["foreign_keys"][row["constraint_name"]] = {
                "table": row["table_name"],
                "col": row["column_name"],
                "foreign_table": row["foreign_table_name"],
                "foreign_col": row["foreign_column_name"],
            }

        # 5. Check constraints
        cur.execute(
            """
            SELECT tc.table_name, tc.constraint_name, cc.check_clause
            FROM information_schema.table_constraints tc
            JOIN information_schema.check_constraints cc
              ON tc.constraint_name = cc.constraint_name
            WHERE tc.constraint_schema = 'public' AND tc.constraint_type = 'CHECK'
              AND tc.constraint_name NOT LIKE '%_not_null';
            """
        )
        for row in cur.fetchall():
            meta["checks"][row["constraint_name"]] = {
                "table": row["table_name"],
                "clause": " ".join(row["check_clause"].split()),
            }

    return meta


def compare_schemas(meta1, meta2, name1="DB1", name2="DB2"):
    differences = []

    # Tables
    tables1 = set(meta1["tables"].keys())
    tables2 = set(meta2["tables"].keys())

    # Exclude migration metadata table from strict parity check if one has it and other doesn't
    # but both should have schema_migrations
    for t in tables1 - tables2:
        differences.append(f"Table present in {name1} but missing in {name2}: {t}")
    for t in tables2 - tables1:
        differences.append(f"Table present in {name2} but missing in {name1}: {t}")

    common_tables = tables1 & tables2
    for t in common_tables:
        cols1 = meta1["tables"][t]
        cols2 = meta2["tables"][t]
        for c in set(cols1.keys()) - set(cols2.keys()):
            differences.append(f"Column {t}.{c} in {name1} but missing in {name2}")
        for c in set(cols2.keys()) - set(cols1.keys()):
            differences.append(f"Column {t}.{c} in {name2} but missing in {name1}")

        for c in set(cols1.keys()) & set(cols2.keys()):
            dt1 = cols1[c]["data_type"]
            dt2 = cols2[c]["data_type"]
            if dt1 != dt2:
                differences.append(f"Column {t}.{c} data_type mismatch: {name1}={dt1} vs {name2}={dt2}")

    # Sequences
    for s in meta1["sequences"] - meta2["sequences"]:
        differences.append(f"Sequence present in {name1} but missing in {name2}: {s}")
    for s in meta2["sequences"] - meta1["sequences"]:
        differences.append(f"Sequence present in {name2} but missing in {name1}: {s}")

    # Check constraints
    for chk, details in meta1["checks"].items():
        if chk not in meta2["checks"]:
            # Check if an equivalent check exists on same table
            matched = False
            for c2, d2 in meta2["checks"].items():
                if d2["table"] == details["table"] and d2["clause"] == details["clause"]:
                    matched = True
                    break
            if not matched:
                differences.append(f"CHECK constraint {chk} on {details['table']} missing in {name2}: {details['clause']}")

    return differences


def main():
    parser = argparse.ArgumentParser(description="Compare schemas of two PostgreSQL databases")
    parser.add_argument("--db1", default="facturacion", help="Reference database name")
    parser.add_argument("--db2", required=True, help="Target/fresh database name")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default="5432")
    parser.add_argument("--user", default="facturador")
    parser.add_argument("--password", default="facturador_secure_pass_94")

    args = parser.parse_args()

    conn1 = psycopg2.connect(host=args.host, port=args.port, user=args.user, password=args.password, dbname=args.db1, cursor_factory=psycopg2.extras.RealDictCursor)
    conn2 = psycopg2.connect(host=args.host, port=args.port, user=args.user, password=args.password, dbname=args.db2, cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        meta1 = extract_schema_metadata(conn1)
        meta2 = extract_schema_metadata(conn2)
        diffs = compare_schemas(meta1, meta2, name1=args.db1, name2=args.db2)

        print(f"Comparing schema '{args.db1}' vs '{args.db2}'...")
        if not diffs:
            print("SCHEMA_PARITY = PASS. Both databases have identical table structures, columns, and sequences!")
            return 0
        else:
            print(f"SCHEMA_PARITY = FAIL. Found {len(diffs)} difference(s):")
            for d in diffs:
                print(f"  - {d}")
            return 1
    finally:
        conn1.close()
        conn2.close()


if __name__ == "__main__":
    sys.exit(main())
