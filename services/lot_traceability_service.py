"""
services/lot_traceability_service.py
Service layer for complete 360° lot traceability and genealogy.
"""

from typing import Dict, Any, List, Optional
from collections import Counter
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
        tree_lots = forward["tree_lots"]
        movements = lot_repo.get_inventory_movements_for_lots(
            [item["lot_id"] for item in tree_lots]
        )
        # A canceled sale is still preserved in the ledger, but must not appear as
        # an effective physical dispatch in the live traceability diagram.
        visible_movements = [
            movement for movement in movements
            if not (
                movement.get("reference_type") in ("sale", "sale_cancellation")
                and movement.get("sale_status") in ("Cancelada", "Anulada")
            )
        ]
        # Some supported dispatch flows record the physical lot issue in
        # sale_lot_movements without a matching Kardex row. Use that existing
        # dispatch ledger as a fallback and de-duplicate rows already in Kardex.
        def sale_key(row):
            return (
                row.get("sale_id") or row.get("reference_id"),
                row.get("lot_id"),
                row.get("lot_number"),
                round(abs(float(row.get("quantity") or 0)), 6),
            )
        kardex_sale_counts = Counter(
            sale_key(m) for m in visible_movements
            if m.get("reference_type") == "sale" and float(m.get("quantity") or 0) < 0
        )
        dispatch_fallbacks = []
        for sale in forward["sales"]:
            key = sale_key(sale)
            if kardex_sale_counts[key]:
                kardex_sale_counts[key] -= 1
                continue
            dispatch_fallbacks.append({
                "movement_id": sale.get("movement_id"),
                "movement_source": "sale_lot_movements",
                "lot_id": sale.get("lot_id"),
                "product_id": sale.get("product_id"),
                "lot_number": sale.get("lot_number"),
                "product_name": sale.get("product_name"),
                "sku": sale.get("sku"),
                "movement_type": "SALE",
                "quantity": -abs(float(sale.get("quantity") or 0)),
                "warehouse": None,
                "reference_type": "sale",
                "reference_id": sale.get("sale_id"),
                "notes": "Despacho registrado en el historial de lotes de la venta",
                "created_at": sale.get("moved_at"),
                "sale_number": sale.get("sale_number"),
                "customer_name": sale.get("customer_name"),
                "customer_email": sale.get("customer_email"),
                "sale_status": sale.get("sale_status"),
            })
        visible_movements.extend(dispatch_fallbacks)
        visible_movements.sort(key=lambda m: (str(m.get("created_at") or ""), int(m.get("movement_id") or 0)))
        direct_movements = [m for m in visible_movements if m.get("lot_id") == lot_id]
        direct_outflows = [m for m in direct_movements if float(m.get("quantity") or 0) < 0]
        genealogy_outflows = [m for m in visible_movements if float(m.get("quantity") or 0) < 0]
        net_available = sum(float(m.get("quantity") or 0) for m in direct_movements)
        current_available = float(lot.get("available_qty") or 0)
        lot_status = lot.get("status")
        if lot_status == "RECALLED":
            status_label = "Retirado (Recall)"
        elif lot_status == "QUARANTINE":
            status_label = "En cuarentena"
        elif lot_status == "EXPIRED":
            status_label = "Vencido"
        elif lot_status == "DEPLETED" and current_available > 1e-9:
            status_label = "Inconsistencia de saldo"
        elif current_available <= 1e-9 or lot_status == "DEPLETED":
            status_label = "Agotado"
        else:
            status_label = "Disponible"

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
                "available_qty": lot["available_qty"],
                "status_label": status_label,
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
            "forward_tree": tree_lots,
            "backward_tree": backward["ancestors"],
            "productions_consumed": forward["productions"],
            "sales_dispatched": forward["sales"],
            "movements": visible_movements,
            "outflows": genealogy_outflows,
            "direct_outflows": direct_outflows,
            "summary": {
                "initial_quantity": float(lot.get("initial_quantity") or 0),
                "total_outflow": sum(abs(float(m.get("quantity") or 0)) for m in direct_outflows),
                "outflow_count": len(direct_outflows),
                "available_qty": current_available,
                "ledger_net_qty": net_available,
            },
            "recall_summary": {
                "affected_lots_count": recall["affected_lots_count"],
                "affected_sales_count": recall["affected_sales_count"],
                "affected_clients_count": recall["affected_clients_count"],
                "total_units_sold": recall["total_units_sold"],
            },
            "recall": recall,
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
