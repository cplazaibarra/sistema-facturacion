"""
services/operario_service.py
Service layer for Mobile Web Operator interface (/operario).
Orchestrates domain repositories for mobile workflows without duplicating business logic.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import json
import psycopg2

from core.database import get_connection
import repositories.purchases_repo as purchases_repo
import repositories.production_repo as production_repo
import repositories.inventory_repo as inventory_repo
import repositories.products_repo as products_repo
import repositories.lot_genealogy_repo as lot_repo
from services.lot_traceability_service import LotTraceabilityService


class OperarioService:
    @staticmethod
    def get_recent_actions(user_id: Optional[int] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Retorna las últimas acciones operacionales registradas:
        - Recepciones de mercadería (inventory_entries)
        - Consumos en Órdenes de Trabajo (production_lot_consumptions)
        - Fabricaciones terminadas (production_orders con status Finalizada)
        """
        actions = []
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Recepciones recientes
                cur.execute(
                    """
                    SELECT ie.id, ie.order_number, ie.entry_date, ie.created_at, ie.warehouse,
                           s.name as supplier_name,
                           (SELECT COUNT(*) FROM inventory_entry_items WHERE inventory_entry_id = ie.id) as items_count
                    FROM inventory_entries ie
                    LEFT JOIN suppliers s ON s.id = ie.supplier_id
                    WHERE ie.purchase_order_id IS NOT NULL
                    ORDER BY ie.id DESC
                    LIMIT %s;
                    """,
                    (limit,)
                )
                for r in cur.fetchall():
                    actions.append({
                        "type": "RECEPCION",
                        "title": f"Recepción {r['order_number']}",
                        "subtitle": f"{r['supplier_name'] or 'Proveedor'}",
                        "timestamp": r["created_at"],
                        "date_str": r["entry_date"],
                        "icon": "fa-solid fa-arrow-right",
                        "badge_class": "badge-recepcion",
                        "link": f"/operario/recepcion"
                    })

                # 2. Consumos en OT recientes
                cur.execute(
                    """
                    SELECT plc.id, plc.quantity_consumed, plc.created_at,
                           po.ot_number, p.name as product_name, l.lot_number
                    FROM production_lot_consumptions plc
                    JOIN production_orders po ON po.id = plc.production_order_id
                    JOIN products p ON p.id = plc.input_product_id
                    JOIN lots l ON l.id = plc.input_lot_id
                    ORDER BY plc.id DESC
                    LIMIT %s;
                    """,
                    (limit,)
                )
                for r in cur.fetchall():
                    actions.append({
                        "type": "CONSUMO",
                        "title": f"Consumo {r['ot_number']}",
                        "subtitle": f"{r['quantity_consumed']:g} un {r['product_name']} ({r['lot_number']})",
                        "timestamp": r["created_at"],
                        "date_str": str(r["created_at"])[:10] if r["created_at"] else "",
                        "icon": "fa-solid fa-gear",
                        "badge_class": "badge-consumo",
                        "link": f"/operario/ot"
                    })

                # 3. Fabricaciones terminadas recientes
                cur.execute(
                    """
                    SELECT po.id, po.ot_number, po.quantity, po.completed_at,
                           p.name as product_name, plo.output_lot_id, l.lot_number as output_lot_number
                    FROM production_orders po
                    JOIN products p ON p.id = po.final_product_id
                    LEFT JOIN production_lot_outputs plo ON plo.production_order_id = po.id
                    LEFT JOIN lots l ON l.id = plo.output_lot_id
                    WHERE po.status = 'Finalizada' AND po.completed_at IS NOT NULL
                    ORDER BY po.id DESC
                    LIMIT %s;
                    """,
                    (limit,)
                )
                for r in cur.fetchall():
                    actions.append({
                        "type": "FABRICACION",
                        "title": f"Fabricación {r['ot_number']}",
                        "subtitle": f"{r['quantity']:g} un {r['product_name']}" + (f" ({r['output_lot_number']})" if r['output_lot_number'] else ""),
                        "timestamp": r["completed_at"],
                        "date_str": str(r["completed_at"])[:10] if r["completed_at"] else "",
                        "icon": "fa-solid fa-check",
                        "badge_class": "badge-fabricacion",
                        "link": f"/operario/historial"
                    })

        def _sort_key(item):
            ts = item.get("timestamp")
            if not ts:
                return ""
            return str(ts)

        actions.sort(key=_sort_key, reverse=True)
        return actions[:limit]

    @staticmethod
    def resolve_scanned_code(code_str: str) -> Dict[str, Any]:
        """
        Interpreta un código escaneado y determina su tipo operacional:
        - OC: Ej. 'OC-00015'
        - OT: Ej. 'OT-00023'
        - LOTE: Coincidencia exacta o parcial en tabla lots
        - PRODUCTO: Coincidencia con SKU o código de producto
        """
        code = (code_str or "").strip()
        if not code:
            return {"found": False, "type": "UNKNOWN", "message": "Código vacío"}

        # 1. ¿Es Orden de Compra (OC-XXXX)?
        if code.upper().startswith("OC-"):
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, oc_number, status FROM purchase_orders WHERE oc_number ILIKE %s LIMIT 1", (code,))
                    row = cur.fetchone()
                    if row:
                        return {
                            "found": True,
                            "type": "OC",
                            "id": row["id"],
                            "code": row["oc_number"],
                            "status": row["status"],
                            "redirect_url": f"/operario/recepcion/{row['id']}"
                        }

        # 2. ¿Es Orden de Trabajo (OT-XXXX)?
        if code.upper().startswith("OT-"):
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, ot_number, status FROM production_orders WHERE ot_number ILIKE %s LIMIT 1", (code,))
                    row = cur.fetchone()
                    if row:
                        return {
                            "found": True,
                            "type": "OT",
                            "id": row["id"],
                            "code": row["ot_number"],
                            "status": row["status"],
                            "redirect_url": f"/operario/ot/{row['id']}"
                        }

        # 3. ¿Es Lote registrado en el sistema?
        lot = lot_repo.get_lot_by_number(code)
        if lot:
            return {
                "found": True,
                "type": "LOTE",
                "id": lot["id"],
                "code": lot["lot_number"],
                "lot_id": lot["id"],
                "product_id": lot["product_id"],
                "product_name": lot["product_name"],
                "sku": lot["sku"],
                "available_qty": float(lot.get("available_qty") or 0.0),
                "redirect_url": f"/operario/lote/{lot['id']}"
            }

        # 4. ¿Es SKU de Producto?
        prod = products_repo.get_product_by_sku(code)
        if prod:
            return {
                "found": True,
                "type": "PRODUCTO",
                "id": prod["id"],
                "code": prod["sku"],
                "product_name": prod["name"],
                "requires_lot": prod.get("requires_lot", False),
                "redirect_url": f"/operario/escanear?product_id={prod['id']}"
            }

        # 5. Búsqueda flexible de lote
        lots_found = lot_repo.search_lots(code, limit=1)
        if lots_found:
            first_lot = lots_found[0]
            return {
                "found": True,
                "type": "LOTE",
                "id": first_lot["id"],
                "code": first_lot["lot_number"],
                "lot_id": first_lot["id"],
                "product_name": first_lot.get("product_name"),
                "redirect_url": f"/operario/lote/{first_lot['id']}"
            }

        return {
            "found": False,
            "type": "UNKNOWN",
            "code": code,
            "message": f"No se encontró ninguna entidad para el código '{code}'."
        }

    @staticmethod
    def get_recommended_fifo_lot(product_id: int) -> Optional[Dict[str, Any]]:
        """
        Retorna el lote recomendado por política FIFO (entry_date ASC, id ASC)
        con saldo disponible > 0.
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ls.id, ls.lot_id, ls.lot_number, ls.available_qty, ls.entry_date, ls.warehouse,
                           l.expiry_date
                    FROM lot_stock ls
                    LEFT JOIN lots l ON l.id = ls.lot_id
                    WHERE ls.product_id = %s AND ls.available_qty > 0
                    ORDER BY ls.entry_date ASC, ls.id ASC
                    LIMIT 1;
                    """,
                    (product_id,)
                )
                row = cur.fetchone()
                return dict(row) if row else None

    @staticmethod
    def validate_and_record_consumption(
        ot_id: int,
        input_product_id: int,
        lot_number: str,
        quantity: float
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Valida que el lote físico escaneado corresponda al insumo requerido,
        que tenga saldo suficiente en lot_stock, y registra el consumo atómicamente.
        """
        qty = float(quantity)
        if qty <= 0:
            return False, "La cantidad a consumir debe ser mayor a 0.", {}

        clean_lot = (lot_number or "").strip()
        if not clean_lot:
            return False, "Debe escanear o ingresar el número de lote.", {}

        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Verificar estado de la OT
                cur.execute(
                    "SELECT id, ot_number, status FROM production_orders WHERE id = %s FOR UPDATE",
                    (ot_id,)
                )
                ot = cur.fetchone()
                if not ot:
                    return False, "Orden de Trabajo no encontrada.", {}
                if ot["status"] in ("Finalizada", "Cancelada"):
                    return False, f"La OT {ot['ot_number']} ya se encuentra {ot['status']}.", {}
                if ot["status"] == "Borrador":
                    return False, f"La OT {ot['ot_number']} está en estado Borrador y no puede registrar consumos.", {}

                # 2. Verificar que el insumo pertenezca a la OT
                cur.execute(
                    """
                    SELECT id, quantity_required 
                    FROM production_order_items 
                    WHERE production_order_id = %s AND input_product_id = %s
                    """,
                    (ot_id, input_product_id)
                )
                item = cur.fetchone()
                if not item:
                    return False, "El producto no corresponde a un insumo planificado de esta OT.", {}

                # 3. Buscar lote en lot_stock con bloqueo pesimista
                cur.execute(
                    """
                    SELECT ls.id as stock_id, ls.lot_id, ls.lot_number, ls.available_qty, ls.warehouse,
                           l.id as real_lot_id, p.name as product_name
                    FROM lot_stock ls
                    JOIN products p ON p.id = ls.product_id
                    LEFT JOIN lots l ON l.id = ls.lot_id
                    WHERE ls.product_id = %s AND ls.lot_number = %s
                    FOR UPDATE OF ls;
                    """,
                    (input_product_id, clean_lot)
                )
                stock_row = cur.fetchone()
                if not stock_row:
                    return False, f"LOTE INCORRECTO: El lote '{clean_lot}' no existe o no corresponde a este producto.", {}

                available = float(stock_row["available_qty"])
                if available < qty - 1e-6:
                    return False, f"STOCK INSUFICIENTE: El lote '{clean_lot}' solo dispone de {available:g} unidades.", {}

                lot_id = stock_row.get("real_lot_id") or stock_row.get("lot_id")
                if not lot_id:
                    cur.execute(
                        "SELECT id FROM lots WHERE product_id = %s AND lot_number = %s ORDER BY id DESC LIMIT 1",
                        (input_product_id, clean_lot)
                    )
                    l_match = cur.fetchone()
                    lot_id = l_match["id"] if l_match else None

                if not lot_id:
                    cur.execute(
                        """
                        INSERT INTO lots (product_id, lot_number, lot_type, origin_type, initial_quantity, created_at, status, warehouse)
                        VALUES (%s, %s, 'RAW_MATERIAL', 'ADJUSTMENT', %s, NOW(), 'ACTIVE', %s)
                        RETURNING id;
                        """,
                        (input_product_id, clean_lot, available, stock_row.get("warehouse") or "Principal")
                    )
                    lot_id = cur.fetchone()["id"]

                # 4. Descontar saldo de lot_stock
                new_avail = available - qty
                cur.execute(
                    "UPDATE lot_stock SET available_qty = %s WHERE id = %s",
                    (new_avail, stock_row["stock_id"])
                )

                if new_avail <= 1e-6:
                    cur.execute("UPDATE lots SET status = 'DEPLETED' WHERE id = %s", (lot_id,))

                # 5. Registrar consumo en production_lot_consumptions
                now_iso = datetime.now(timezone.utc).isoformat()
                # Congelar el PPP oficial vigente antes de la salida. La
                # genealogía FIFO identifica el lote consumido, mientras que
                # el Kardex del ERP valoriza las salidas al PPP ponderado.
                from repositories.kardex_repo import get_current_ppp
                input_unit_cost = get_current_ppp(input_product_id, conn=conn)
                cur.execute(
                    """
                    INSERT INTO production_lot_consumptions (
                        production_order_id, input_product_id, input_lot_id, quantity_consumed, created_at
                    ) VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (ot_id, input_product_id, lot_id, qty, now_iso)
                )
                consumption_id = cur.fetchone()["id"]

                # 6. Registrar en Kardex universal (inventory_movements)
                cur.execute(
                    """
                    INSERT INTO inventory_movements (
                        product_id, movement_type, quantity, unit_cost, reference_type, reference_id,
                        notes, lot_id, warehouse, created_at
                    ) VALUES (%s, 'PRODUCTION_INPUT', %s, %s, 'production_order', %s, %s, %s, %s, NOW());
                    """,
                    (
                        input_product_id,
                        -qty,
                        input_unit_cost,
                        ot_id,
                        f"Consumo móvil en {ot['ot_number']} (Lote {clean_lot})",
                        lot_id,
                        stock_row.get("warehouse") or "Principal"
                    )
                )

                # Si la OT estaba Solicitada, pasar a En Proceso
                if ot["status"] == "Solicitada":
                    cur.execute(
                        "UPDATE production_orders SET status = 'En Proceso' WHERE id = %s",
                        (ot_id,)
                    )

            conn.commit()

        return True, "Consumo registrado correctamente.", {
            "consumption_id": consumption_id,
            "lot_number": clean_lot,
            "quantity": qty,
            "remaining_lot_stock": new_avail
        }

    @staticmethod
    def finalize_production(
        ot_id: int,
        actual_quantity: float,
        output_lot_number: str,
        warehouse: str = "Principal",
        expiry_date: Optional[str] = None,
        notes: str = ""
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Finaliza una Orden de Trabajo desde la interfaz móvil:
        - Valida que la OT no esté finalizada.
        - Exige lote de producto terminado si requires_lot=True.
        - Registra el lote en lots, lot_stock, production_lot_outputs e inventory_movements.
        - Actualiza la OT a Finalizada.
        """
        qty = float(actual_quantity)
        if qty <= 0:
            return False, "La cantidad producida debe ser mayor a 0.", {}

        clean_output_lot = (output_lot_number or "").strip()

        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Bloquear OT
                cur.execute(
                    """
                    SELECT po.id, po.ot_number, po.quantity, po.status, po.final_product_id,
                           p.name as product_name, p.sku, COALESCE(p.requires_lot, FALSE) as requires_lot
                    FROM production_orders po
                    JOIN products p ON p.id = po.final_product_id
                    WHERE po.id = %s
                    FOR UPDATE;
                    """,
                    (ot_id,)
                )
                ot = cur.fetchone()
                if not ot:
                    return False, "Orden de Trabajo no encontrada.", {}

                if ot["status"] == "Finalizada":
                    return False, f"ESTA OT YA FUE FINALIZADA previamente.", {}
                if ot["status"] == "Borrador":
                    return False, f"La OT {ot['ot_number']} está en estado Borrador y no puede ser finalizada.", {}

                # Valorar la salida con los costos PPP que quedaron congelados
                # en cada movimiento de consumo. Los consumos históricos de
                # esta ruta guardaban costo 0; para ellos se usa el PPP actual
                # como compatibilidad, sin tocar el Kardex previo.
                cur.execute(
                    """
                    SELECT im.product_id, ABS(im.quantity) AS consumed_qty,
                           COALESCE(r.new_unit_cost, im.unit_cost) AS unit_cost
                    FROM inventory_movements im
                    LEFT JOIN (
                        SELECT DISTINCT ON (movement_id) movement_id, new_unit_cost
                        FROM inventory_cost_revaluations
                        ORDER BY movement_id, id DESC
                    ) r ON r.movement_id = im.id
                    WHERE im.movement_type = 'PRODUCTION_INPUT'
                      AND im.reference_type = 'production_order'
                      AND im.reference_id = %s
                      AND im.quantity < 0
                    ORDER BY im.created_at::timestamptz ASC, im.id ASC
                    """,
                    (ot_id,),
                )
                consumption_rows = cur.fetchall()
                total_consumption_cost = 0.0
                from repositories.kardex_repo import get_current_ppp
                for consumption in consumption_rows:
                    unit_cost = float(consumption.get("unit_cost") or 0.0)
                    if unit_cost <= 0:
                        unit_cost = get_current_ppp(consumption["product_id"], conn=conn)
                    total_consumption_cost += float(consumption["consumed_qty"] or 0.0) * unit_cost
                output_unit_cost = total_consumption_cost / qty if total_consumption_cost > 0 else 0.0

                final_pid = ot["final_product_id"]

                # 2. Validar obligatoriedad de lote
                if ot["requires_lot"] and not clean_output_lot:
                    return False, "LOTE OBLIGATORIO: Este producto requiere trazabilidad de lote para su finalización.", {}

                if not clean_output_lot:
                    clean_output_lot = f"PT-{ot['ot_number']}"

                # 3. Crear Lote en lots
                now_iso = datetime.now(timezone.utc).isoformat()
                cur.execute(
                    """
                    INSERT INTO lots (
                        product_id, lot_number, lot_type, origin_type, origin_id,
                        production_order_id, initial_quantity, created_at, expiry_date,
                        status, warehouse, notes
                    ) VALUES (%s, %s, 'FINISHED_PRODUCT', 'PRODUCTION', %s, %s, %s, %s, %s, 'ACTIVE', %s, %s)
                    RETURNING id;
                    """,
                    (
                        final_pid, clean_output_lot, ot_id, ot_id, qty,
                        now_iso, expiry_date or None, warehouse or "Principal",
                        notes or f"Fabricado en {ot['ot_number']} (Móvil)"
                    )
                )
                output_lot_id = cur.fetchone()["id"]

                # 4. Registrar salida en production_lot_outputs
                cur.execute(
                    """
                    INSERT INTO production_lot_outputs (
                        production_order_id, output_product_id, output_lot_id, quantity_produced, created_at
                    ) VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (ot_id, final_pid, output_lot_id, qty, now_iso)
                )

                # 5. Registrar / actualizar en lot_stock
                cur.execute(
                    """
                    INSERT INTO lot_stock (product_id, lot_number, entry_date, initial_qty, available_qty, warehouse, lot_id)
                    VALUES (%s, %s, CURRENT_DATE, %s, %s, %s, %s)
                    ON CONFLICT (product_id, lot_number) DO UPDATE
                    SET available_qty = lot_stock.available_qty + EXCLUDED.available_qty,
                        initial_qty = lot_stock.initial_qty + EXCLUDED.initial_qty,
                        lot_id = COALESCE(lot_stock.lot_id, EXCLUDED.lot_id);
                    """,
                    (final_pid, clean_output_lot, qty, qty, warehouse or "Principal", output_lot_id)
                )

                # 6. Registrar en Kardex universal (inventory_movements)
                cur.execute(
                    """
                    INSERT INTO inventory_movements (
                        product_id, movement_type, quantity, unit_cost, reference_type, reference_id,
                        notes, lot_id, warehouse, created_at
                    ) VALUES (%s, 'PRODUCTION_OUTPUT', %s, %s, 'production_order', %s, %s, %s, %s, NOW());
                    """,
                    (
                        final_pid, qty, output_unit_cost, ot_id,
                        f"Alta producto terminado OT {ot['ot_number']} (Lote {clean_output_lot})",
                        output_lot_id, warehouse or "Principal"
                    )
                )

                # 7. Actualizar estado de la OT a Finalizada
                cur.execute(
                    """
                    UPDATE production_orders
                    SET status = 'Finalizada', completed_at = NOW(), unit_cost = %s
                    WHERE id = %s;
                    """,
                    (output_unit_cost, ot_id)
                )

            conn.commit()

        return True, "Fabricación finalizada con éxito.", {
            "ot_number": ot["ot_number"],
            "product_name": ot["product_name"],
            "quantity": qty,
            "lot_number": clean_output_lot,
            "lot_id": output_lot_id
        }
