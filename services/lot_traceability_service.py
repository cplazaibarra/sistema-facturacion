"""
services/lot_traceability_service.py
Service layer for complete 360° lot traceability and genealogy.
"""

from typing import Dict, Any, List, Optional
import repositories.lot_genealogy_repo as lot_repo
import repositories.sales_repo as sales_repo
import repositories.inventory_repo as inv_repo


class LotTraceabilityService:
    @staticmethod
    def get_lot_traceability(lot_id: int) -> Optional[Dict[str, Any]]:
        """
        Retorna la vista 360° del ciclo de vida del lote:
        - Identidad del lote y producto
        - Origen (Recepción, OC, Proveedor, OT)
        - Movimientos de inventario asociados
        - Consumo en Producción
        - Genealogía descendiente (Forward)
        - Genealogía ascendiente (Backward)
        - Salidas en ventas y clientes
        """
        lot = lot_repo.get_lot(lot_id)
        if not lot:
            return None

        forward = lot_repo.trace_lot_forward(lot_id)
        backward = lot_repo.trace_lot_backward(lot_id)
        recall = lot_repo.get_lot_recall_impact(lot_id)

        return {
            "identity": {
                "lot_id": lot["id"],
                "lot_number": lot["lot_number"],
                "product_id": lot["product_id"],
                "product_name": lot["product_name"],
                "sku": lot["sku"],
                "lot_type": lot["lot_type"],
                "status": lot["status"],
                "created_at": lot["created_at"],
                "expiry_date": lot["expiry_date"],
                "initial_quantity": lot["initial_quantity"],
                "warehouse": lot["warehouse"],
                "notes": lot["notes"]
            },
            "origin": {
                "origin_type": lot["origin_type"],
                "supplier_name": lot.get("supplier_name"),
                "oc_number": lot.get("oc_number"),
                "entry_order_number": lot.get("entry_order_number"),
                "production_ot_number": lot.get("production_ot_number")
            },
            "forward_tree": forward["tree_lots"],
            "backward_tree": backward["ancestors"],
            "productions_consumed": forward["productions"],
            "sales_dispatched": forward["sales"],
            "recall_summary": {
                "affected_lots_count": recall["affected_lots_count"],
                "affected_sales_count": recall["affected_sales_count"],
                "affected_clients_count": recall["affected_clients_count"],
                "total_units_sold": recall["total_units_sold"],
            }
        }

    @staticmethod
    def trace_lot_forward(lot_id: int) -> Dict[str, Any]:
        """Recorre la cadena hacia adelante."""
        return lot_repo.trace_lot_forward(lot_id)

    @staticmethod
    def trace_lot_backward(lot_id: int) -> Dict[str, Any]:
        """Recorre la cadena hacia atrás."""
        return lot_repo.trace_lot_backward(lot_id)

    @staticmethod
    def get_lot_recall_impact(lot_id: int) -> Dict[str, Any]:
        """Calcula el impacto de un recall."""
        return lot_repo.get_lot_recall_impact(lot_id)

    @staticmethod
    def search_lots(query_str: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        """Busca lotes registrados."""
        return lot_repo.search_lots(query_str, limit=limit)

    @staticmethod
    def trace_sale_to_origin(sale_id: int) -> Dict[str, Any]:
        """
        Dada una venta (ej. VTA-0093):
        Reconstruye los productos vendidos, los lotes de salida, las OTs que los fabricaron,
        los lotes de insumos utilizados y los proveedores originales.
        """
        sale = sales_repo.get_sale(sale_id)
        if not sale:
            return {"error": "Venta no encontrada", "sale": None, "trace": []}

        lot_moves = inv_repo.get_sale_lot_movements(sale_id)
        traces = []

        for move in lot_moves:
            lot_id = move.get("lot_id")
            if not lot_id and move.get("lot_number"):
                # Buscar por product_id y lot_number si lot_id es null
                found = lot_repo.get_lot_by_product_and_number(move["product_id"], move["lot_number"])
                if found:
                    lot_id = found["id"]

            if lot_id:
                backward = lot_repo.trace_lot_backward(lot_id)
                traces.append({
                    "product_id": move["product_id"],
                    "product_name": move["product_name"],
                    "lot_number": move["lot_number"],
                    "quantity_sold": move["quantity"],
                    "lot_id": lot_id,
                    "backward_trace": backward
                })
            else:
                traces.append({
                    "product_id": move["product_id"],
                    "product_name": move["product_name"],
                    "lot_number": move["lot_number"],
                    "quantity_sold": move["quantity"],
                    "lot_id": None,
                    "backward_trace": None,
                    "status": "UNKNOWN_OR_WITHOUT_LOT"
                })

        return {
            "sale": dict(sale),
            "lot_movements_count": len(lot_moves),
            "traces": traces
        }
