"""
repositories/production_repo.py
Domain repository extracted from db.py.
Preserves exact implementation, parameters, locks, and return types.
"""

import os
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import psycopg2
import psycopg2.extras
from werkzeug.security import generate_password_hash

from core.database import get_connection


def get_next_ot_number(conn=None) -> str:
    """Genera el siguiente número correlativo único para una Orden de Trabajo (ej: OT-00001)"""
    def _execute(cursor):
        cursor.execute("SELECT nextval('production_order_number_seq') as val")
        val = cursor.fetchone()["val"]
        return f"OT-{val:05d}"

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                val_str = _execute(cur)
            c.commit()
            return val_str

