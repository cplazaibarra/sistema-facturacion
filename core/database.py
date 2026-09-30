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
    if os.environ.get("ERP_TEST_MODE") == "1":
        from core.test_database_guard import assert_current_test_database_authorized
        assert_current_test_database_authorized(check_database=False)
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "postgres"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
