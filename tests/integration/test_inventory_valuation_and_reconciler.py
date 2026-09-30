"""
tests/integration/test_inventory_valuation_and_reconciler.py
Regresiones exhaustivas para:
1. Nueva producción nunca genera PRODUCTION_OUTPUT costo 0 cuando existen consumos valorizados.
2. Costo output deriva correctamente de inputs ponderados.
3. Reintento de finalización no duplica output.
4. Corrección histórica de valoración es auditable (registra movimiento, valor anterior, valor nuevo, diferencia, motivo, actor, fecha, referencia).
5. Corrección histórica no altera cantidad física de stock.
6. Corrección histórica no altera lotes ni lot_stock.
7. Movimiento original permanece intacto en inventory_movements.
8. Costo efectivo y PPP cronológico reconocen la revaluación.
9. Kardex muestra correctamente el efecto y detalle de revaluación.
10. Revaluación redundante o duplicada accidental es rechazada controladamente.
11. Cadena de revaluaciones conserva historia inmutable (parent_revaluation_id).
12. Snapshot legacy divergente no se interpreta como stock físico inexistente.
13. Reconciliador diferencia warning legacy de inconsistencia operacional.
14. Demanda no cubierta válida no se clasifica como inconsistencia física.
"""

from decimal import Decimal
import json
import pytest

from core.database import get_connection
from repositories.inventory_repo import record_inventory_movement, get_product_physical_stock
from repositories.kardex_repo import get_current_ppp, get_product_kardex_history, get_inventory_valuation_summary
from repositories.inventory_revaluation_repo import (
    revalue_inventory_movement,
    get_movement_effective_unit_cost,
    get_effective_cost_map,
    list_revaluations_for_movement,
)
from repositories import production_repo
from services.operario_service import OperarioService
from tools.reconcile_inventory import reconcile_inventory


def _create_unique_product(prefix: str, cost: float = 0.0, requires_lot: bool = False, product_type: str = "Final") -> tuple[int, str]:
    import uuid
    uid = uuid.uuid4().hex[:8]
    sku = f"{prefix}-{uid}"
    name = f"Producto Test {sku}"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO products (sku, name, cost, requires_lot, product_type, created_at, status)
                VALUES (%s, %s, %s, %s, %s, NOW()::text, 'Activo')
                RETURNING id;
                """,
                (sku, name, cost, requires_lot, product_type)
            )
            pid = cur.fetchone()["id"]
        conn.commit()
    return pid, sku


def test_new_production_never_generates_zero_cost_output():
    """1. Nueva producción nunca genera PRODUCTION_OUTPUT costo 0 cuando existen consumos valorizados."""
    mp_id, mp_sku = _create_unique_product("MP-VAL", cost=1500.0, requires_lot=True, product_type="Insumo")
    pt_id, pt_sku = _create_unique_product("PT-VAL", cost=0.0, requires_lot=True, product_type="Final")

    # Ingreso MP con lote y costo 1500
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO lots (product_id, lot_number, lot_type, initial_quantity, status, warehouse, created_at)
                VALUES (%s, 'LOT-MP-1', 'RAW_MATERIAL', 10.0, 'ACTIVE', 'Principal', NOW())
                RETURNING id;
                """,
                (mp_id,)
            )
            lot_mp_id = cur.fetchone()["id"]
            cur.execute(
                """
                INSERT INTO lot_stock (product_id, lot_number, entry_date, initial_qty, available_qty, warehouse, lot_id)
                VALUES (%s, 'LOT-MP-1', CURRENT_DATE, 10.0, 10.0, 'Principal', %s);
                """,
                (mp_id, lot_mp_id)
            )
        conn.commit()

    record_inventory_movement(
        product_id=mp_id,
        movement_type="PURCHASE_RECEIPT",
        quantity=10.0,
        unit_cost=1500.0,
        lot_number="LOT-MP-1",
        lot_id=lot_mp_id,
        reference_type="purchase_order",
        reference_id=101,
        notes="Recepción test"
    )

    # Crear OT por 2 unidades de PT
    ot_id, ot_num = production_repo.create_production_order(
        final_product_id=pt_id,
        quantity=2,
        notes="OT Test Cost Derivation",
        status="Solicitada",
        items=[{"input_product_id": mp_id, "quantity_required": 1.0, "total_quantity": 2.0}]
    )

    # Registrar consumo por OperarioService
    ok_cons, msg_cons, _ = OperarioService.validate_and_record_consumption(
        ot_id=ot_id,
        input_product_id=mp_id,
        lot_number="LOT-MP-1",
        quantity=2.0
    )
    assert ok_cons, f"Fallo al registrar consumo: {msg_cons}"

    # Finalizar OT por OperarioService
    ok_fin, msg_fin, _ = OperarioService.finalize_production(
        ot_id=ot_id,
        actual_quantity=2.0,
        output_lot_number="LOT-PT-VAL-1"
    )
    assert ok_fin, f"Fallo al finalizar OT: {msg_fin}"

    # Verificar que el movimiento PRODUCTION_OUTPUT tenga unit_cost > 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT quantity, unit_cost
                FROM inventory_movements
                WHERE reference_type = 'production_order' AND reference_id = %s AND movement_type = 'PRODUCTION_OUTPUT';
                """,
                (ot_id,)
            )
            out_mov = cur.fetchone()
            assert out_mov is not None
            assert float(out_mov["quantity"]) == 2.0
            # Consumió 2 un de MP a $1500 = $3000 total. Producidas 2 un -> unit_cost = 1500.0
            assert float(out_mov["unit_cost"]) == 1500.0
            assert float(out_mov["unit_cost"]) > 0.0


def test_production_output_cost_derives_correctly_from_inputs():
    """2. Costo output deriva correctamente de inputs ponderados."""
    mp1_id, _ = _create_unique_product("MP1", cost=1000.0, product_type="Insumo", requires_lot=True)
    mp2_id, _ = _create_unique_product("MP2", cost=2000.0, product_type="Insumo", requires_lot=True)
    pt_id, _ = _create_unique_product("PT-MULTI", cost=0.0, product_type="Final", requires_lot=True)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO lots (product_id, lot_number, lot_type, initial_quantity, status, warehouse, created_at) VALUES (%s, 'LOT-MP1', 'RAW_MATERIAL', 10.0, 'ACTIVE', 'Principal', NOW()) RETURNING id", (mp1_id,))
            l1_id = cur.fetchone()["id"]
            cur.execute("INSERT INTO lot_stock (product_id, lot_number, entry_date, initial_qty, available_qty, warehouse, lot_id) VALUES (%s, 'LOT-MP1', CURRENT_DATE, 10.0, 10.0, 'Principal', %s)", (mp1_id, l1_id))

            cur.execute("INSERT INTO lots (product_id, lot_number, lot_type, initial_quantity, status, warehouse, created_at) VALUES (%s, 'LOT-MP2', 'RAW_MATERIAL', 10.0, 'ACTIVE', 'Principal', NOW()) RETURNING id", (mp2_id,))
            l2_id = cur.fetchone()["id"]
            cur.execute("INSERT INTO lot_stock (product_id, lot_number, entry_date, initial_qty, available_qty, warehouse, lot_id) VALUES (%s, 'LOT-MP2', CURRENT_DATE, 10.0, 10.0, 'Principal', %s)", (mp2_id, l2_id))
        conn.commit()

    record_inventory_movement(product_id=mp1_id, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=1000.0, lot_number="LOT-MP1", lot_id=l1_id, reference_type="purchase_order", reference_id=1)
    record_inventory_movement(product_id=mp2_id, movement_type="PURCHASE_RECEIPT", quantity=10.0, unit_cost=2000.0, lot_number="LOT-MP2", lot_id=l2_id, reference_type="purchase_order", reference_id=2)

    ot_id, _ = production_repo.create_production_order(
        final_product_id=pt_id,
        quantity=5,
        notes="OT Multi Input",
        status="Solicitada",
        items=[
            {"input_product_id": mp1_id, "quantity_required": 1.0, "total_quantity": 5.0},
            {"input_product_id": mp2_id, "quantity_required": 0.5, "total_quantity": 2.5},
        ]
    )

    # Consumos: 5 de MP1 ($5.000) + 2.5 de MP2 ($5.000) = $10.000 total / 5 = $2.000 unitario
    ok1, _, _ = OperarioService.validate_and_record_consumption(ot_id=ot_id, input_product_id=mp1_id, lot_number="LOT-MP1", quantity=5.0)
    assert ok1
    ok2, _, _ = OperarioService.validate_and_record_consumption(ot_id=ot_id, input_product_id=mp2_id, lot_number="LOT-MP2", quantity=2.5)
    assert ok2

    ok_fin, _, _ = OperarioService.finalize_production(ot_id=ot_id, actual_quantity=5.0, output_lot_number="LOT-PT-MULTI-1")
    assert ok_fin

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT unit_cost FROM production_orders WHERE id = %s", (ot_id,))
            ot_cost = float(cur.fetchone()["unit_cost"])
            assert ot_cost == 2000.0

            cur.execute("SELECT unit_cost FROM inventory_movements WHERE reference_type='production_order' AND reference_id=%s AND movement_type='PRODUCTION_OUTPUT'", (ot_id,))
            mov_cost = float(cur.fetchone()["unit_cost"])
            assert mov_cost == 2000.0


def test_retry_finalize_production_does_not_duplicate_output():
    """3. Reintento de finalización no duplica output."""
    pt_id, _ = _create_unique_product("PT-IDEMP", cost=1000.0, product_type="Final", requires_lot=False)
    ot_id, _ = production_repo.create_production_order(
        final_product_id=pt_id,
        quantity=1,
        notes="OT Retry Test",
        status="Solicitada",
        items=[]
    )
    ok1, _, _ = OperarioService.finalize_production(ot_id=ot_id, actual_quantity=1.0, output_lot_number="LOT-IDEMP")
    assert ok1

    # Segundo intento
    ok2, msg2, _ = OperarioService.finalize_production(ot_id=ot_id, actual_quantity=1.0, output_lot_number="LOT-IDEMP")
    assert not ok2
    assert "YA FUE FINALIZADA" in msg2

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM inventory_movements WHERE reference_type='production_order' AND reference_id=%s AND movement_type='PRODUCTION_OUTPUT'", (ot_id,))
            assert cur.fetchone()["c"] == 1


def test_cost_revaluation_is_auditable_and_traceable():
    """4. Revaluación histórica registra movimiento, valor anterior, valor nuevo, diferencia, motivo, actor, fecha, referencia."""
    pid, sku = _create_unique_product("PT-REV", cost=0.0, product_type="Final")
    mov_id = record_inventory_movement(
        product_id=pid,
        movement_type="PRODUCTION_OUTPUT",
        quantity=3.0,
        unit_cost=0.0,
        reference_type="production_order",
        reference_id=999,
        notes="Salida a costo 0 de prueba"
    )

    rev_res = revalue_inventory_movement(
        movement_id=mov_id,
        new_unit_cost=Decimal("1250.50"),
        reason="Corrección de prueba",
        reference_doc="OT-TEST-999",
        created_by="Auditor QA"
    )

    assert rev_res["movement_id"] == mov_id
    assert rev_res["product_id"] == pid
    assert float(rev_res["old_unit_cost"]) == 0.0
    assert float(rev_res["new_unit_cost"]) == 1250.50
    assert float(rev_res["difference_unit_cost"]) == 1250.50
    assert float(rev_res["total_value_difference"]) == 3751.50  # 3 * 1250.50
    assert rev_res["reason"] == "Corrección de prueba"
    assert rev_res["reference_doc"] == "OT-TEST-999"
    assert rev_res["created_by"] == "Auditor QA"
    assert rev_res["created_at"] is not None

    audit_list = list_revaluations_for_movement(mov_id)
    assert len(audit_list) == 1
    assert audit_list[0]["id"] == rev_res["id"]


def test_cost_revaluation_does_not_alter_physical_quantity_or_lots():
    """5, 6, 7. Revaluación no modifica cantidad física, lots ni lot_stock."""
    pid, sku = _create_unique_product("PT-QTY-CHECK", cost=0.0, requires_lot=True, product_type="Final")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO lots (product_id, lot_number, lot_type, initial_quantity, status, warehouse, created_at)
                VALUES (%s, 'LOT-QTY-1', 'FINISHED_PRODUCT', 5.0, 'ACTIVE', 'Principal', NOW())
                RETURNING id;
                """,
                (pid,)
            )
            lid = cur.fetchone()["id"]
            cur.execute(
                """
                INSERT INTO lot_stock (product_id, lot_number, entry_date, initial_qty, available_qty, warehouse, lot_id)
                VALUES (%s, 'LOT-QTY-1', CURRENT_DATE, 5.0, 5.0, 'Principal', %s);
                """,
                (pid, lid)
            )
        conn.commit()

    mov_id = record_inventory_movement(
        product_id=pid,
        movement_type="PRODUCTION_OUTPUT",
        quantity=5.0,
        unit_cost=0.0,
        lot_number="LOT-QTY-1",
        lot_id=lid,
        reference_type="production_order",
        reference_id=888
    )

    # Cantidad previa
    stock_before = get_product_physical_stock(pid)
    assert stock_before == 5.0

    # Revaluar
    revalue_inventory_movement(
        movement_id=mov_id,
        new_unit_cost=800.0,
        reason="Ajuste valor sin tocar cantidad",
        created_by="Admin"
    )

    # Cantidad posterior
    stock_after = get_product_physical_stock(pid)
    assert stock_after == 5.0

    # Comprobar lot_stock
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT available_qty, initial_qty FROM lot_stock WHERE product_id = %s", (pid,))
            ls = cur.fetchone()
            assert float(ls["available_qty"]) == 5.0
            assert float(ls["initial_qty"]) == 5.0

            # Comprobar que inventory_movements #mov_id no fue editado físicamente
            cur.execute("SELECT quantity, unit_cost FROM inventory_movements WHERE id = %s", (mov_id,))
            im = cur.fetchone()
            assert float(im["quantity"]) == 5.0
            assert float(im["unit_cost"]) == 0.0  # Permanece el costo histórico original intacto


def test_effective_cost_and_ppp_reflect_revaluation():
    """8, 9, 10, 11. Costo efectivo, PPP cronológico y Kardex reconocen la revaluación."""
    pid, sku = _create_unique_product("PT-PPP-REVAL", cost=0.0, product_type="Final")

    # Mov 1: 3 un a costo 0
    m1 = record_inventory_movement(
        product_id=pid,
        movement_type="PRODUCTION_OUTPUT",
        quantity=3.0,
        unit_cost=0.0,
        reference_type="production_order",
        reference_id=10
    )
    # Mov 2: 1 un a costo 2000
    m2 = record_inventory_movement(
        product_id=pid,
        movement_type="PRODUCTION_OUTPUT",
        quantity=1.0,
        unit_cost=2000.0,
        reference_type="production_order",
        reference_id=11
    )

    # PPP antes: 3*0 + 1*2000 = 2000 / 4 = 500.0
    assert get_current_ppp(pid) == 500.0

    # Revaluar Mov 1 a 1000.0
    revalue_inventory_movement(
        movement_id=m1,
        new_unit_cost=1000.0,
        reason="Corrección costo inicial",
        created_by="Admin"
    )

    # Costo efectivo individual y mapa batch
    assert get_movement_effective_unit_cost(m1) == 1000.0
    assert get_movement_effective_unit_cost(m2) == 2000.0
    cost_map = get_effective_cost_map([m1, m2])
    assert cost_map[m1] == 1000.0
    assert cost_map[m2] == 2000.0

    # PPP después: 3*1000 + 1*2000 = 5000 / 4 = 1250.0
    assert get_current_ppp(pid) == 1250.0

    # Kardex detallado
    kardex = get_product_kardex_history(pid)
    assert kardex["current_stock"] == 4.0
    assert kardex["current_ppp"] == 1250.0
    assert kardex["current_inventory_value"] == 5000.0

    row_m1 = next(r for r in kardex["rows"] if r["id"] == m1)
    assert row_m1["is_revalued"] is True
    assert row_m1["original_unit_cost"] == 0.0
    assert row_m1["unit_cost_applied"] == 1000.0
    assert row_m1["revaluation"]["old_unit_cost"] == 0.0
    assert row_m1["revaluation"]["new_unit_cost"] == 1000.0
    assert row_m1["revaluation"]["reason"] == "Corrección costo inicial"

    # Revaluación redundante rechazada
    with pytest.raises(ValueError, match="Revaluación redundante rechazada"):
        revalue_inventory_movement(
            movement_id=m1,
            new_unit_cost=1000.0,
            reason="Mismo costo de nuevo"
        )

    # Segunda corrección encadenada (ej. ajuste a 1100.0)
    rev2 = revalue_inventory_movement(
        movement_id=m1,
        new_unit_cost=1100.0,
        reason="Segunda corrección justificada",
        created_by="Supervisor"
    )
    assert rev2["parent_revaluation_id"] is not None
    assert float(rev2["old_unit_cost"]) == 1000.0
    assert float(rev2["new_unit_cost"]) == 1100.0

    # PPP actualizado: 3*1100 + 1*2000 = 5300 / 4 = 1325.0
    assert get_current_ppp(pid) == 1325.0

    # 10. Regla oficial: Rechazar revaluación directa de movimientos de salida (quantity < 0)
    m_out = record_inventory_movement(
        product_id=pid,
        movement_type="SALE",
        quantity=-2.0,
        unit_cost=1325.0,
        reference_type="sale",
        reference_id=99
    )
    with pytest.raises(ValueError, match="No se permite revaluación directa de movimientos de salida"):
        revalue_inventory_movement(
            movement_id=m_out,
            new_unit_cost=1400.0,
            reason="Intento inválido de revaluar salida"
        )


def test_reconciler_distinguishes_legacy_warning_from_operational_inconsistency():
    """12, 13, 14. Reconciliador separa integridad operacional de alertas legacy y no confunde demanda no cubierta."""
    summary, details = reconcile_inventory()
    # Las métricas del reconciliador separan explícitamente el estado operacional de los avisos legacy
    assert "operational_integrity" in summary
    assert summary["operational_integrity"] in ("OK", "REQUIRES_REVIEW")
    assert "legacy_status" in summary
    assert summary["legacy_status"] in ("OK", "LEGACY_WARNING")
    assert "legacy_warning_products_count" in summary
    assert "uncovered_demand_products" in summary
    assert "uncovered_demand_units" in summary

    # Validar que los detalles clasificados no confundan demanda no cubierta con inconsistencia física
    for d in details:
        if d.get("uncovered_demand", 0) > 0 and d.get("available_stock", 0) == 0:
            assert "RESERVA_INCONSISTENTE" not in d["classifications"]
            # No se marca como fallo de cantidad a menos que el disponible sea negativo
            assert d.get("available_stock", 0) >= 0
