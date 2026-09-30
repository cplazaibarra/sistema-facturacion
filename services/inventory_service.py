"""
services/inventory_service.py
Service layer for inventory business logic.
Orchestrates calls between inventory_repo, products_repo, and legacy_repo.
"""

from typing import Dict, Any, List, Optional, Tuple
from core.database import get_connection
import repositories.inventory_repo as inv_repo
import repositories.products_repo as prod_repo


class InventoryService:
    @staticmethod
    def get_stock_overview(product_id: int) -> Dict[str, Any]:
        """
        Devuelve el estado consolidado de stock para un producto:
        - stock disponible (relacional)
        - stock legacy y delta
        - desglose de lotes activos (FIFO)
        - costo promedio ponderado (VPP)
        """
        from services.stock_context import get_product_stock_balance
        balance = get_product_stock_balance(product_id) or {
            "physical_stock": 0.0, "reserved_stock": 0.0, "available_stock": 0.0
        }
        legacy, relational, delta = inv_repo.get_stock_with_dual_read(product_id)
        lots = inv_repo.get_lot_stock_by_product(product_id)
        vpp = prod_repo.get_product_calculated_cost(product_id)
        
        return {
            "product_id": product_id,
            **balance,
            "legacy_stock": legacy,
            "relational_stock": relational,
            "delta": delta,
            "vpp": vpp,
            "lots": lots,
            "lot_count": len(lots)
        }

    @staticmethod
    def validate_and_reserve_sale(product_id: int, quantity: float) -> Tuple[bool, str, dict]:
        """
        Valida si existe stock disponible para la venta considerando bloqueos de concurrencia.
        """
        return inv_repo.validate_stock_for_sale(product_id, quantity)

    @staticmethod
    def execute_stock_discount(sale_id: int, product_id: int, quantity: float, conn=None) -> bool:
        """
        Ejecuta el descuento de stock (FIFO + Kardex + Dual Write legacy).
        """
        return inv_repo.discount_stock_for_sale(sale_id, product_id, quantity, conn=conn)
