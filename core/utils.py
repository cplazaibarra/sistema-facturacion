"""
core/utils.py
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
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def is_valid_email(email: str) -> bool:
    """Valida que el correo tenga la estructura correcta (ej: usuario@dominio.com, .cl, etc.)."""
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    if not EMAIL_REGEX.match(email):
        return False
    parts = email.split('@')
    if len(parts) != 2:
        return False
    domain = parts[1]
    domain_parts = domain.split('.')
    if len(domain_parts) < 2:
        return False
    for part in domain_parts:
        if not part or not re.match(r'^[a-zA-Z0-9-]+$', part):
            return False
    tld = domain_parts[-1]
    if len(tld) < 2 or not tld.isalpha():
        return False
    return True


def normalize_rut_str(rut_str: str, dv_str: str = None) -> tuple[str, str]:
    """Normaliza y separa el cuerpo y el dígito verificador del RUT chileno."""
    if not rut_str:
        return "", ""
    clean = str(rut_str).strip().replace(".", "").upper()
    if "-" in clean:
        parts = clean.split("-", 1)
        r_body = parts[0].strip()
        r_dv = parts[1].strip()
    else:
        r_body = clean
        r_dv = str(dv_str or "").strip().upper()
    return r_body, r_dv

