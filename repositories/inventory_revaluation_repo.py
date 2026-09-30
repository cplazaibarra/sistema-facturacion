"""
repositories/inventory_revaluation_repo.py
Repositorio especializado en Revaluación Histórica Inmutable de Movimientos de Inventario.

Principio:
El movimiento original en inventory_movements permanece INTACTO como evidencia histórica.
Una revaluación histórica registra un evento auditable en inventory_cost_revaluations.
No altera cantidades físicas, saldos de lotes en lot_stock, ni registros en lots.
Usa aritmética Decimal para exactitud monetaria.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional
from core.database import get_connection


def revalue_inventory_movement(
    movement_id: int,
    new_unit_cost: float | Decimal,
    reason: str,
    reference_doc: Optional[str] = None,
    created_by: str = "Sistema",
    conn=None
) -> Dict[str, Any]:
    """
    Registra una revaluación histórica auditable e inmutable para un movimiento de inventario.
    
    Validaciones:
    - Adquiere bloqueo FOR UPDATE sobre el movimiento original en inventory_movements.
    - Comprueba que el movimiento exista.
    - Obtiene el costo efectivo vigente actual (sea el unit_cost original o la última revaluación).
    - Valida que new_unit_cost >= 0.
    - Evita revaluación redundante si new_unit_cost == current_effective_cost.
    - Calcula diferencias monetarias con precisión Decimal.
    - Registra el registro inmutable en inventory_cost_revaluations vinculando parent_revaluation_id si aplica.
    - NO modifica quantity, unit_cost, lot_id, lot_number ni warehouse del movimiento original.
    - NO modifica lots ni lot_stock.
    """
    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise ValueError("El motivo de la revaluación es obligatorio.")

    new_cost_dec = Decimal(str(new_unit_cost))
    if new_cost_dec < 0:
        raise ValueError("El nuevo costo unitario no puede ser negativo.")

    def _execute(cur):
        # 1. Bloquear movimiento original
        cur.execute(
            """
            SELECT id, product_id, movement_type, quantity, unit_cost, reference_type, reference_id, lot_id
            FROM inventory_movements
            WHERE id = %s
            FOR UPDATE;
            """,
            (movement_id,)
        )
        mov = cur.fetchone()
        if not mov:
            raise ValueError(f"Movimiento de inventario #{movement_id} no encontrado.")

        raw_qty = float(mov["quantity"] or 0.0)
        if raw_qty <= 0:
            raise ValueError(
                f"No se permite revaluación directa de movimientos de salida (#{movement_id}, cantidad {raw_qty:g}). "
                "Las salidas de inventario se valorizan automáticamente a PPP contable vigente."
            )

        product_id = mov["product_id"]
        qty_dec = Decimal(str(raw_qty))

        # 2. Consultar historial de revaluaciones previas para este movimiento
        cur.execute(
            """
            SELECT id, new_unit_cost, created_at
            FROM inventory_cost_revaluations
            WHERE movement_id = %s
            ORDER BY id DESC
            LIMIT 1
            FOR UPDATE;
            """,
            (movement_id,)
        )
        last_reval = cur.fetchone()

        if last_reval:
            old_cost_dec = Decimal(str(last_reval["new_unit_cost"]))
            parent_id = last_reval["id"]
        else:
            old_cost_dec = Decimal(str(mov["unit_cost"] or 0.0))
            parent_id = None

        if abs(new_cost_dec - old_cost_dec) <= Decimal("0.000001"):
            raise ValueError(
                f"El movimiento #{movement_id} ya posee un costo efectivo de {old_cost_dec:.6f}. Revaluación redundante rechazada."
            )

        diff_unit_cost = new_cost_dec - old_cost_dec
        total_val_diff = diff_unit_cost * qty_dec

        doc_ref = (reference_doc or "").strip() or f"{mov.get('reference_type') or 'mov'}:{mov.get('reference_id') or movement_id}"

        # 3. Insertar revaluación inmutable
        cur.execute(
            """
            INSERT INTO inventory_cost_revaluations (
                movement_id, product_id, old_unit_cost, new_unit_cost,
                difference_unit_cost, total_value_difference, reason,
                reference_doc, created_by, parent_revaluation_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, movement_id, product_id, old_unit_cost, new_unit_cost,
                      difference_unit_cost, total_value_difference, reason,
                      reference_doc, created_by, created_at, parent_revaluation_id;
            """,
            (
                movement_id, product_id, old_cost_dec, new_cost_dec,
                diff_unit_cost, total_val_diff, clean_reason,
                doc_ref, created_by or "Sistema", parent_id
            )
        )
        record = dict(cur.fetchone())
        return record

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                res = _execute(cur)
            c.commit()
            return res


def get_movement_effective_unit_cost(movement_id: int, conn=None) -> float:
    """
    Retorna el costo unitario efectivo vigente de un movimiento específico.
    Si existe una revaluación histórica, retorna la más reciente (cadena determinística).
    De lo contrario, retorna el unit_cost de inventory_movements.
    """
    def _execute(cur):
        cur.execute(
            """
            SELECT r.new_unit_cost
            FROM inventory_cost_revaluations r
            WHERE r.movement_id = %s
            ORDER BY r.id DESC
            LIMIT 1;
            """,
            (movement_id,)
        )
        row = cur.fetchone()
        if row and row.get("new_unit_cost") is not None:
            return float(row["new_unit_cost"])

        cur.execute("SELECT unit_cost FROM inventory_movements WHERE id = %s", (movement_id,))
        mov = cur.fetchone()
        if mov and mov.get("unit_cost") is not None:
            return float(mov["unit_cost"] or 0.0)
        return 0.0

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


def get_effective_cost_map(movement_ids: List[int], conn=None) -> Dict[int, float]:
    """
    Carga de forma eficiente (batch) el mapeo de {movement_id: effective_unit_cost}
    para una lista de movement_ids, resolviendo la última revaluación si existe.
    """
    if not movement_ids:
        return {}

    def _execute(cur):
        # Obtener la última revaluación de cada movimiento
        cur.execute(
            """
            SELECT DISTINCT ON (movement_id) movement_id, new_unit_cost
            FROM inventory_cost_revaluations
            WHERE movement_id = ANY(%s)
            ORDER BY movement_id, id DESC;
            """,
            (movement_ids,)
        )
        reval_map = {r["movement_id"]: float(r["new_unit_cost"]) for r in cur.fetchall()}

        # Movimientos que no tienen revaluación
        missing = [mid for mid in movement_ids if mid not in reval_map]
        if missing:
            cur.execute(
                """
                SELECT id, unit_cost
                FROM inventory_movements
                WHERE id = ANY(%s);
                """,
                (missing,)
            )
            for r in cur.fetchall():
                reval_map[r["id"]] = float(r["unit_cost"] or 0.0)

        return reval_map

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)


def list_revaluations_for_movement(movement_id: int, conn=None) -> List[Dict[str, Any]]:
    """Retorna la auditoría cronológica completa de revaluaciones para un movimiento."""
    def _execute(cur):
        cur.execute(
            """
            SELECT id, movement_id, product_id, old_unit_cost, new_unit_cost,
                   difference_unit_cost, total_value_difference, reason,
                   reference_doc, created_by, created_at, parent_revaluation_id
            FROM inventory_cost_revaluations
            WHERE movement_id = %s
            ORDER BY id ASC;
            """,
            (movement_id,)
        )
        return [dict(r) for r in cur.fetchall()]

    if conn is not None:
        with conn.cursor() as cur:
            return _execute(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                return _execute(cur)
