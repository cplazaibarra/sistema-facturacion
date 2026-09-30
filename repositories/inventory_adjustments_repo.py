"""Persistencia transaccional de solicitudes de ajuste de inventario.

Una solicitud es sólo una intención hasta que se aprueba.  El único punto que
escribe el kardex es :func:`approve_adjustment`, que bloquea solicitud y
producto, comprueba el snapshot y genera un único movimiento formal.
"""
import json
from datetime import datetime, timezone
from typing import Any, Optional

from core.database import get_connection
from repositories.inventory_repo import record_inventory_movement
from repositories.kardex_repo import get_current_ppp


def _stock(cur, product_id: int, warehouse: str) -> float:
    cur.execute(
        """SELECT COALESCE(SUM(quantity), 0) AS stock
           FROM inventory_movements
          WHERE product_id = %s AND COALESCE(warehouse, 'Almacén Principal') = %s""",
        (product_id, warehouse),
    )
    return float((cur.fetchone() or {}).get("stock") or 0.0)


def _reserved(cur, product_id: int) -> float:
    """Reserva operativa mínima calculada con las mismas tablas del ERP."""
    total = 0.0
    # Las ventas guardan sus líneas como JSON. Se consideran sólo pendientes,
    # igual que services.stock_context.
    cur.execute(
        """SELECT COALESCE(SUM((line->>'quantity')::double precision), 0) AS qty
             FROM sales s CROSS JOIN LATERAL jsonb_array_elements(s.products_json::jsonb) line
            WHERE s.status = 'Pendiente'
              AND (line->>'product_id') ~ '^[0-9]+$'
              AND (line->>'product_id')::integer = %s""",
        (product_id,),
    )
    total += float((cur.fetchone() or {}).get("qty") or 0.0)
    cur.execute(
        """SELECT COALESCE(SUM(poi.quantity_required), 0) AS qty
             FROM production_order_items poi
             JOIN production_orders po ON po.id = poi.production_order_id
            WHERE po.status = 'Aprobada' AND poi.input_product_id = %s""",
        (product_id,),
    )
    total += float((cur.fetchone() or {}).get("qty") or 0.0)
    cur.execute(
        """SELECT COALESCE(SUM(poai.quantity), 0) AS qty
             FROM production_order_additional_items poai
             JOIN production_orders po ON po.id = poai.production_order_id
            WHERE po.status = 'Aprobada' AND poai.input_product_id = %s""",
        (product_id,),
    )
    total += float((cur.fetchone() or {}).get("qty") or 0.0)
    return total


def _movement_watermark(cur, product_id: int) -> int:
    cur.execute("SELECT COALESCE(MAX(id), 0) AS watermark FROM inventory_movements WHERE product_id=%s", (product_id,))
    return int((cur.fetchone() or {}).get("watermark") or 0)


def create_adjustment(*, product_id: int, warehouse: str, counted_quantity: float,
                      reason: str, observation: str | None, requested_by: int | None,
                      requested_by_name: str) -> dict:
    """Crea una solicitud PENDING sin tocar existencias ni kardex."""
    warehouse = (warehouse or "Almacén Principal").strip()
    reason = (reason or "").strip()
    counted = float(counted_quantity)
    if counted < 0:
        raise ValueError("La cantidad física contada no puede ser negativa")
    if not reason:
        raise ValueError("El motivo es obligatorio")
    if reason.upper() == "OTRO" and not (observation or "").strip():
        raise ValueError("La observación es obligatoria para el motivo OTRO")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, sku, name, requires_lot FROM products WHERE id = %s FOR SHARE", (product_id,))
            product = cur.fetchone()
            if not product:
                raise ValueError("Producto no encontrado")
            snapshot = _stock(cur, product_id, warehouse)
            reserved = _reserved(cur, product_id)
            available = max(0.0, snapshot - reserved)
            watermark = _movement_watermark(cur, product_id)
            cur.execute(
                """INSERT INTO inventory_adjustment_requests
                   (product_id, warehouse, stock_snapshot, available_snapshot, reserved_snapshot,
                    movement_watermark, counted_quantity, reason,
                    observation, requested_by, requested_by_name)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (product_id, warehouse, snapshot, available, reserved, watermark, counted, reason, (observation or "").strip() or None,
                 requested_by, requested_by_name or "Sistema"),
            )
            row = dict(cur.fetchone())
            cur.execute(
                """INSERT INTO inventory_adjustment_audit
                   (adjustment_id, action, actor_id, actor_name, detail)
                   VALUES (%s,'REQUESTED',%s,%s,%s)""",
                (row["id"], requested_by, requested_by_name or "Sistema",
                 f"Snapshot={snapshot}; conteo={counted}; diferencia={float(row['difference'])}"),
            )
        conn.commit()
    return row


def list_adjustments(*, status: str | None = None, product_id: int | None = None,
                     warehouse: str | None = None) -> list[dict]:
    clauses, params = [], []
    if status:
        clauses.append("iar.status = %s"); params.append(status)
    if product_id:
        clauses.append("iar.product_id = %s"); params.append(product_id)
    if warehouse:
        clauses.append("iar.warehouse = %s"); params.append(warehouse)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""SELECT iar.*, p.sku, p.name AS product_name
                FROM inventory_adjustment_requests iar JOIN products p ON p.id = iar.product_id
                {where} ORDER BY iar.requested_at DESC, iar.id DESC""", params)
            return [dict(r) for r in cur.fetchall()]


def get_adjustment(adjustment_id: int, *, for_update: bool = False) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            return _get(cur, adjustment_id, for_update)


def _get(cur, adjustment_id: int, for_update: bool = False) -> Optional[dict]:
    cur.execute("""SELECT iar.*, p.sku, p.name AS product_name, p.requires_lot
                    FROM inventory_adjustment_requests iar JOIN products p ON p.id=iar.product_id
                   WHERE iar.id=%s""" + (" FOR UPDATE" if for_update else ""), (adjustment_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def reject_adjustment(adjustment_id: int, *, actor_id: int | None,
                      actor_name: str, comment: str) -> dict:
    if not (comment or "").strip():
        raise ValueError("El comentario del rechazo es obligatorio")
    with get_connection() as conn:
        with conn.cursor() as cur:
            row = _get(cur, adjustment_id, True)
            if not row: raise ValueError("Solicitud no encontrada")
            if row["status"] != "PENDING": raise ValueError("La solicitud ya fue resuelta")
            cur.execute("""UPDATE inventory_adjustment_requests
                SET status='REJECTED', decided_by=%s, decided_by_name=%s,
                    decided_at=now(), approver_comment=%s WHERE id=%s RETURNING *""",
                        (actor_id, actor_name, comment.strip(), adjustment_id))
            result = dict(cur.fetchone())
            cur.execute("""INSERT INTO inventory_adjustment_audit
                (adjustment_id, action, actor_id, actor_name, detail)
                VALUES (%s,'REJECTED',%s,%s,%s)""", (adjustment_id, actor_id, actor_name, comment.strip()))
        conn.commit()
    return result


def approve_adjustment(adjustment_id: int, *, actor_id: int | None,
                       actor_name: str, approver_may_self_approve: bool = False) -> dict:
    """Aplica atómicamente una solicitud. Un snapshot obsoleto queda PENDING."""
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                row = _get(cur, adjustment_id, True)
                if not row: raise ValueError("Solicitud no encontrada")
                if row["status"] != "PENDING":
                    raise ValueError("La solicitud ya fue resuelta y no puede aplicarse otra vez")
                if not approver_may_self_approve and actor_id and row.get("requested_by") == actor_id:
                    raise ValueError("El solicitante no puede aprobar su propia solicitud")

                # El bloqueo de producto serializa ventas, recepciones y otros movimientos.
                cur.execute("SELECT id, requires_lot, sku, name FROM products WHERE id=%s FOR UPDATE", (row["product_id"],))
                product = cur.fetchone()
                if not product: raise ValueError("Producto no encontrado")
                if product.get("requires_lot"):
                    raise ValueError("Este producto requiere una asignación explícita de lote para ajustar inventario")
                current = _stock(cur, row["product_id"], row["warehouse"])
                current_watermark = _movement_watermark(cur, row["product_id"])
                if abs(current - float(row["stock_snapshot"])) > 1e-6 or current_watermark != int(row.get("movement_watermark") or 0):
                    raise ValueError("El inventario cambió desde el conteo. Revisa la solicitud antes de aprobar.")
                diff = float(row["difference"])
                current_reserved = _reserved(cur, row["product_id"])
                if float(row["counted_quantity"]) < current_reserved:
                    raise ValueError("El conteo físico es inferior al stock reservado; revise la solicitud antes de aprobar.")
                if abs(diff) <= 1e-9:
                    # Diferencia cero no debe fabricar un movimiento (INV-008).
                    cur.execute("""UPDATE inventory_adjustment_requests
                        SET status='APPLIED', decided_by=%s, decided_by_name=%s, decided_at=now(),
                            approver_comment=COALESCE(approver_comment,'Sin diferencia') WHERE id=%s RETURNING *""",
                                (actor_id, actor_name, adjustment_id))
                    result = dict(cur.fetchone())
                else:
                    ppp = get_current_ppp(row["product_id"], conn=conn)
                    movement_type = "ADJUSTMENT_IN" if diff > 0 else "ADJUSTMENT_OUT"
                    mov_id = record_inventory_movement(
                        product_id=row["product_id"], movement_type=movement_type, quantity=diff,
                        unit_cost=ppp, warehouse=row["warehouse"], reference_type="inventory_adjustment",
                        reference_id=adjustment_id,
                        notes=f"AJUSTE DE CONCILIACIÓN #{adjustment_id} — {row['reason']}",
                        created_by=actor_name, conn=conn)
                    _update_legacy_stock(cur, product["sku"], diff)
                    cur.execute("""UPDATE inventory_adjustment_requests
                        SET status='APPLIED', decided_by=%s, decided_by_name=%s, decided_at=now(), movement_id=%s
                        WHERE id=%s RETURNING *""", (actor_id, actor_name, mov_id, adjustment_id))
                    result = dict(cur.fetchone())
                cur.execute("""INSERT INTO inventory_adjustment_audit
                    (adjustment_id, action, actor_id, actor_name, detail)
                    VALUES (%s,'APPLIED',%s,%s,%s)""",
                            (adjustment_id, actor_id, actor_name, f"movement_id={result.get('movement_id')}"))
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise


def _update_legacy_stock(cur, sku: str, delta: float) -> None:
    """Mantiene el snapshot legacy usado por pantallas antiguas, en la misma tx."""
    cur.execute("SELECT json FROM page_data WHERE key='inventory_items' FOR UPDATE")
    row = cur.fetchone()
    if not row or not row.get("json"): return
    items = json.loads(row["json"])
    changed = False
    for item in items:
        if item.get("code") == sku:
            item["stock"] = float(item.get("stock") or 0) + delta
            changed = True; break
    if not changed:
        # Reconstituye sólo la proyección de presentación cuando una limpieza
        # antigua eliminó su fila; el ledger de movimientos sigue siendo la
        # fuente oficial del saldo.
        cur.execute("SELECT name, category, cost, min_stock FROM products WHERE sku=%s", (sku,))
        product = cur.fetchone()
        if product:
            cur.execute("SELECT COALESCE(SUM(quantity),0) AS stock FROM inventory_movements WHERE product_id=(SELECT id FROM products WHERE sku=%s)", (sku,))
            stock = float((cur.fetchone() or {}).get("stock") or 0)
            items.append({"code": sku, "name": product["name"], "desc": product["name"],
                          "stock": stock, "cost": float(product.get("cost") or 0),
                          "min_stock": float(product.get("min_stock") or 0),
                          "category": product.get("category") or ""})
            changed = True
    if changed:
        cur.execute("UPDATE page_data SET json=%s WHERE key='inventory_items'", (json.dumps(items),))
