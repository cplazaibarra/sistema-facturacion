"""
core/database.py
Core database infrastructure and connection management for the ERP system.
Preserves PostgreSQL connection semantics with psycopg2 and RealDictCursor.
"""

import os
from typing import Generator
import psycopg2
import psycopg2.extras


def get_connection():
    """
    Returns a connection to the PostgreSQL database using environment variables.
    Configured with psycopg2.extras.RealDictCursor by default.
    """
    testing = os.environ.get("APP_ENV", "").lower() == "testing" or os.environ.get("ERP_TEST_MODE") == "1"
    if testing:
        from core.test_database_guard import validate_test_database_config, verify_test_connection
        target = validate_test_database_config(os.environ)
        conn = psycopg2.connect(
            host=target["host"], port=target["port"], dbname=target["database"],
            user=target["user"], password=target["password"],
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        return verify_test_connection(conn)
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "postgres"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
