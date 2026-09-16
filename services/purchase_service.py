"""
services/purchase_service.py
Service layer for purchase orders and inventory reception.
"""

from typing import Dict, Any, List, Optional, Tuple
from core.database import get_connection
import repositories.purchases_repo as pur_repo
import repositories.inventory_repo as inv_repo


class PurchaseService:
    @staticmethod
    def get_order_summary(po_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene el resumen de una orden de compra junto con sus líneas e ingresos asociados.
        """
        po = pur_repo.get_purchase_order(po_id)
        if not po:
            return None
        
        items = pur_repo.get_purchase_order_items(po_id)
        entries = pur_repo.get_purchase_order_entries(po_id)
        
        po_dict = dict(po)
        po_dict["items"] = items
        po_dict["entries"] = entries
        return po_dict
