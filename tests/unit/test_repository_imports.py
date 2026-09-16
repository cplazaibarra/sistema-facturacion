"""
Unit tests for Phase 5 repository modularization:
- Direct imports of each repository without side-effects
- Detection of circular imports
- Completeness of domain functions
"""

import importlib
import inspect
import pytest


REPO_MODULES = [
    "core.database",
    "core.utils",
    "repositories.auth_repo",
    "repositories.products_repo",
    "repositories.suppliers_repo",
    "repositories.clients_repo",
    "repositories.legacy_repo",
    "repositories.reporting_repo",
    "repositories.purchases_repo",
    "repositories.finance_repo",
    "repositories.inventory_repo",
    "repositories.sales_repo",
    "repositories.production_repo",
    "services.inventory_service",
    "services.sales_service",
    "services.purchase_service",
]


@pytest.mark.parametrize("mod_name", REPO_MODULES)
def test_repository_module_imports_cleanly(mod_name):
    """Verifica que cada módulo del backend modular se importe sin errores ni dependencias circulares."""
    mod = importlib.import_module(mod_name)
    assert mod is not None


def test_no_circular_imports_across_repositories():
    """Valida la ausencia de ciclos de importación recargando módulos."""
    for mod_name in REPO_MODULES:
        mod = importlib.import_module(mod_name)
        reloaded = importlib.reload(mod)
        assert reloaded is not None


def test_core_utils_functions():
    """Prueba que core.utils exporta utilidades canónicas correctamente."""
    from core.utils import normalize_rut_str, is_valid_email
    
    # RUT normalization test
    rut_body, dv = normalize_rut_str("12.345.678-k")
    assert rut_body == "12345678"
    assert dv == "K"
    
    # Email test
    assert is_valid_email("test@example.com") is True
    assert is_valid_email("not-an-email") is False


def test_facade_exposes_all_repository_functions():
    """Verifica que db.py exponga como fachada todas las funciones de los repositorios de dominio."""
    import db
    
    for mod_name in REPO_MODULES:
        if mod_name.startswith("services."):
            continue
        mod = importlib.import_module(mod_name)
        for name, obj in inspect.getmembers(mod, inspect.isfunction):
            if obj.__module__ == mod_name and not name.startswith("_"):
                assert hasattr(db, name), f"db.py facade is missing exported function: {name} from {mod_name}"
