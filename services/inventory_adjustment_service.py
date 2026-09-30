"""Casos de uso para el workflow de ajustes de inventario."""
from repositories.inventory_adjustments_repo import (
    create_adjustment, list_adjustments, get_adjustment,
    approve_adjustment, reject_adjustment,
)

ADJUSTMENT_REASONS = (
    "CONTEO FÍSICO", "MERMA", "DAÑO", "PÉRDIDA",
    "ERROR DE REGISTRO", "SOBRANTE", "OTRO",
)


class InventoryAdjustmentService:
    """Fachada estable para rutas/API; no contiene una segunda fuente de stock."""

    create = staticmethod(create_adjustment)
    list = staticmethod(list_adjustments)
    get = staticmethod(get_adjustment)
    approve = staticmethod(approve_adjustment)
    reject = staticmethod(reject_adjustment)
