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
    elif dv_str:
        r_body = clean
        r_dv = str(dv_str).strip().upper()
    else:
        # Si no tiene guión ni se pasó DV separado, el último caracter es el DV si tiene longitud >= 7
        if len(clean) >= 7 and (clean[-1].isdigit() or clean[-1] == 'K'):
            r_body = clean[:-1]
            r_dv = clean[-1]
        else:
            r_body = clean
            r_dv = ""
    return r_body, r_dv


def calculate_chilean_dv(rut_body: str) -> str:
    """Calcula el dígito verificador de un RUT chileno usando el algoritmo Módulo 11."""
    clean_body = "".join(filter(str.isdigit, str(rut_body)))
    if not clean_body:
        return ""
    factors = [2, 3, 4, 5, 6, 7]
    s = sum(int(d) * factors[i % 6] for i, d in enumerate(reversed(clean_body)))
    remainder = 11 - (s % 11)
    if remainder == 11:
        return "0"
    elif remainder == 10:
        return "K"
    else:
        return str(remainder)


def validate_chilean_rut(rut_str: str, dv_str: str = None) -> tuple[bool, str, str]:
    """
    Valida un RUT chileno (con o sin puntos, con o sin guión/DV separado).
    Retorna (es_valido, rut_formateado, mensaje_error).
    Formato retornado: '12.345.678-9'
    """
    if not rut_str or not str(rut_str).strip():
        return False, "", "El RUT es obligatorio."

    r_body, r_dv = normalize_rut_str(rut_str, dv_str)
    if not r_body or not r_dv:
        return False, "", "Debe ingresar el RUT completo con su dígito verificador."

    clean_digits = "".join(filter(str.isdigit, r_body))
    if not clean_digits or clean_digits != r_body:
        return False, "", "El cuerpo del RUT solo debe contener dígitos numéricos."

    if len(clean_digits) < 6 or len(clean_digits) > 9:
        return False, "", "El RUT debe tener entre 6 y 9 dígitos en su cuerpo numérico."

    r_dv = r_dv.upper()
    if r_dv not in "0123456789K":
        return False, "", "El dígito verificador debe ser un número del 0 al 9 o la letra K."

    expected_dv = calculate_chilean_dv(clean_digits)
    if r_dv != expected_dv:
        return False, "", f"RUT inválido: el dígito verificador no coincide con el cuerpo del RUT."

    # Formatear estándar: XX.XXX.XXX-Y
    reversed_digits = clean_digits[::-1]
    groups = [reversed_digits[i:i+3] for i in range(0, len(reversed_digits), 3)]
    formatted_body = ".".join(groups)[::-1]
    formatted_rut = f"{formatted_body}-{r_dv}"

    return True, formatted_rut, ""


def format_chilean_rut(rut_str: str, dv_str: str = None) -> str:
    """Formatea un RUT a 'XX.XXX.XXX-Y' si es válido o normalizable."""
    r_body, r_dv = normalize_rut_str(rut_str, dv_str)
    clean_digits = "".join(filter(str.isdigit, r_body))
    if not clean_digits:
        return ""
    reversed_digits = clean_digits[::-1]
    groups = [reversed_digits[i:i+3] for i in range(0, len(reversed_digits), 3)]
    formatted_body = ".".join(groups)[::-1]
    if r_dv:
        return f"{formatted_body}-{r_dv.upper()}"
    return formatted_body


PAYMENT_TERMS_LABELS = {
    "CASH": "Al contado",
    "NET_30": "A 30 días",
    "NET_60": "A 60 días"
}
VALID_PAYMENT_TERMS = set(PAYMENT_TERMS_LABELS.keys())
DEFAULT_PAYMENT_TERMS = "NET_30"


def format_payment_terms(term: str | None) -> str:
    """Retorna la etiqueta legible para el usuario de una condición de pago."""
    if not term:
        return PAYMENT_TERMS_LABELS[DEFAULT_PAYMENT_TERMS]
    clean_term = str(term).strip().upper()
    return PAYMENT_TERMS_LABELS.get(clean_term, PAYMENT_TERMS_LABELS[DEFAULT_PAYMENT_TERMS])


