"""
services/sales_service.py
Service layer for sales business logic.
Orchestrates sales operations, quotation conversions, and payment bindings.
"""

from typing import Dict, Any, List, Optional, Tuple
from core.database import get_connection
import repositories.sales_repo as sales_repo
import repositories.inventory_repo as inv_repo
import repositories.finance_repo as fin_repo


class SalesService:
    @staticmethod
    def get_sale_detail(sale_id: int) -> Optional[Dict[str, Any]]:
        """
        Retorna los detalles de la venta junto con sus movimientos de lote asociados y pagos.
        """
        sale = sales_repo.get_sale(sale_id)
        if not sale:
            return None
        
        lot_movements = inv_repo.get_sale_lot_movements(sale_id)
        payment = fin_repo.get_sale_payment(sale_id)
        
        sale_dict = dict(sale)
        sale_dict["lot_movements"] = lot_movements
        sale_dict["payment_info"] = dict(payment) if payment else None
        return sale_dict

    @staticmethod
    def convert_quotation(quotation_id: int, seller_id: int, notes: str = "") -> Tuple[bool, str, Optional[int]]:
        """
        Convierte de manera atómica e idempotente una cotización a venta.
        """
        return sales_repo.convert_quotation_to_sale(quotation_id, seller_id, notes)
