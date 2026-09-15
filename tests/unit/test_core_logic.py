import pytest
from db import (
    normalize_rut_str,
    is_valid_email,
    get_next_oc_number
)

def test_normalize_rut_standard_hyphen():
    r_body, r_dv = normalize_rut_str("12.345.678-9")
    assert r_body == "12345678"
    assert r_dv == "9"

def test_normalize_rut_with_k():
    r_body, r_dv = normalize_rut_str("11.222.333-k")
    assert r_body == "11222333"
    assert r_dv == "K"

def test_normalize_rut_separate_dv():
    r_body, r_dv = normalize_rut_str("12345678", "5")
    assert r_body == "12345678"
    assert r_dv == "5"

def test_normalize_rut_empty():
    r_body, r_dv = normalize_rut_str("")
    assert r_body == ""
    assert r_dv == ""

def test_is_valid_email():
    assert is_valid_email("contacto@bodegamiel.com") is True
    assert is_valid_email("usuario.test+label@gmail.com") is True
    assert is_valid_email("invalido_sin_arroba") is False
    assert is_valid_email("sin_dominio@") is False
    assert is_valid_email("") is False

def test_get_next_oc_number_format():
    oc_num = get_next_oc_number()
    assert isinstance(oc_num, str)
    assert oc_num.startswith("OC-")
    # Formato esperado: OC-XXXXX (al menos 8 caracteres)
    assert len(oc_num) >= 8
