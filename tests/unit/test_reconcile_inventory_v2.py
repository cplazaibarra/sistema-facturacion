"""Synthetic, database-free cases for the read-only V2 inventory audit."""
from tools.reconcile_inventory import (
    calculate_reservations,
    classify_product,
    classify_reference_type,
    is_analyzable_product,
)


def product(**overrides):
    row = {
        "id": 1,
        "sku": "SKU-1",
        "name": "Producto 1",
        "requires_lot": False,
        "snapshot_present": False,
        "snapshot_value_present": False,
        "snapshot_stock": None,
        "ledger_stock": 100,
        "movement_count": 1,
        "lot_stock": None,
        "lot_rows": 0,
    }
    row.update(overrides)
    return row


def test_missing_snapshot_with_ledger_is_not_quantity_inconsistency():
    result = classify_product(product(), reserved=0)
    assert "SNAPSHOT_AUSENTE" in result["classifications"]
    assert "SNAPSHOT_VS_LEDGER" not in result["classifications"]
    assert result["snapshot_stock"] is None
    assert result["quantity_investigation"] is False
    assert result["physical_stock"] == 100


def test_explicit_zero_snapshot_and_ledger_is_legacy_warning():
    result = classify_product(product(snapshot_present=True, snapshot_value_present=True,
                                     snapshot_stock=0))
    assert "SNAPSHOT_VS_LEDGER" in result["classifications"]
    assert "ALERTA_LEGACY" in result["classifications"]
    assert result["has_legacy_warning"] is True
    assert result["operational_inconsistent"] is False
    assert result["delta_snapshot_ledger"] == -100
    assert result["quantity_investigation"] is False


def test_matching_snapshot_and_ledger_is_consistent():
    result = classify_product(product(snapshot_present=True, snapshot_value_present=True,
                                     snapshot_stock=100))
    assert result["classifications"] == ["OK"]
    assert result["delta_snapshot_ledger"] == 0


def test_lot_controlled_matching_ledger_and_lots_is_consistent():
    result = classify_product(product(requires_lot=True, lot_stock=100, lot_rows=1))
    assert "LEDGER_VS_LOTES" not in result["classifications"]
    assert result["physical_source"] == "lot_stock"
    assert result["quantity_investigation"] is False


def test_lot_controlled_delta_is_reported_without_adjusting():
    result = classify_product(product(requires_lot=True, lot_stock=80, lot_rows=1))
    assert result["delta_ledger_lots"] == 20
    assert "LEDGER_VS_LOTES" in result["classifications"]
    assert result["quantity_investigation"] is True


def test_missing_snapshot_with_matching_lots_and_ledger_is_not_quantity_issue():
    result = classify_product(product(requires_lot=True, lot_stock=100, lot_rows=1))
    assert "SNAPSHOT_AUSENTE" in result["classifications"]
    assert "LEDGER_VS_LOTES" not in result["classifications"]
    assert result["quantity_investigation"] is False


def test_reservation_keeps_physical_reserved_and_available_separate():
    result = classify_product(product(), reserved=10)
    assert result["physical_stock"] == 100
    assert result["reserved_stock"] == 10
    assert result["available_stock"] == 90
    # The getter's fallback and a view that adds reserve again expose a current
    # application semantic discrepancy; V2 reports it without using it as a check.
    assert result["erp_stock_lookup"] == 100
    assert result["erp_display_physical_if_adds_reserve"] == 110


def test_out_of_stock_sale_is_uncovered_demand_not_inconsistent_reservation():
    result = classify_product(product(ledger_stock=0, movement_count=0), reserved=1)
    assert result["reservation_demand"] == 1
    assert result["reserved_stock"] == 1
    assert result["physical_reserved_stock"] == 0
    assert result["uncovered_demand"] == 1
    assert result["available_stock"] == 0
    assert "RESERVA_INCONSISTENTE" not in result["classifications"]
    assert result["quantity_investigation"] is False


def test_uncovered_reservation_does_not_turn_zero_snapshot_into_quantity_delta():
    result = classify_product(product(
        ledger_stock=0, movement_count=0,
        snapshot_present=True, snapshot_value_present=True, snapshot_stock=0,
    ), reserved=1)
    assert result["physical_reserved_stock"] == 0
    assert result["uncovered_demand"] == 1
    assert "SNAPSHOT_VS_LEDGER" not in result["classifications"]


def test_soft_deleted_policy_matches_reconciler_query():
    assert is_analyzable_product(False)
    assert is_analyzable_product(None)
    assert not is_analyzable_product(True)


def test_unreferenced_movement_is_traceability_alert_not_quantity_adjustment():
    result = classify_product(product(), reference_flags={"legacy_generic"})
    assert "MOVIMIENTOS_SIN_ORIGEN" in result["classifications"]
    assert result["traceability_investigation"] is True
    assert result["quantity_investigation"] is False
    assert result["ledger_stock"] == 100


def test_orphan_and_unverifiable_references_are_distinguished():
    assert classify_reference_type("purchase_order", 99, False) == "orphan"
    assert classify_reference_type("purchase_order", None, False) == "reference_absent"
    assert classify_reference_type("new_unknown_type", 99, None) == "unverifiable"
    assert classify_reference_type(None, None, None) == "legacy_generic"
    orphaned = classify_product(product(), reference_flags={"orphan"})
    assert "REFERENCIAS_HUERFANAS" in orphaned["classifications"]
    assert orphaned["traceability_investigation"] is True
    assert orphaned["quantity_investigation"] is False


def test_sales_reservation_mapping_follows_id_sku_exact_then_unique_legacy_name():
    products = [{"id": 1, "sku": "SKU-1", "name": "Producto Uno"}]
    sales = [{"products": [{"product_id": 1, "product_name": "", "quantity": 10},
                            {"product_name": "Producto Uno", "quantity": 2},
                            "Producto Uno (3)"]}]
    reservations, audit = calculate_reservations(products, sales, [])
    assert reservations == {"SKU-1": 15}
    assert audit["matched_sale_lines"] == {"product_id": 1, "exact_name": 2}
    assert audit["ambiguous_sale_lines"] == 0


def test_ambiguous_partial_reservation_is_not_assigned():
    products = [
        {"id": 1, "sku": "SKU-1", "name": "Producto Uno"},
        {"id": 2, "sku": "SKU-2", "name": "Producto Uno Grande"},
    ]
    reservations, audit = calculate_reservations(
        products, [{"products": [{"product_name": "Producto Uno Grand", "quantity": 4}]}], []
    )
    assert reservations == {}
    assert audit["ambiguous_sale_lines"] == 1


def test_classify_product_separates_operational_integrity_from_legacy_warning():
    """Separación de banderas operacionales vs advertencias de snapshot legacy."""
    # Producto con ledger y lotes concordantes, pero snapshot legacy divergente
    p_legacy = product(
        requires_lot=True,
        ledger_stock=50,
        lot_stock=50,
        lot_rows=1,
        snapshot_present=True,
        snapshot_value_present=True,
        snapshot_stock=20,  # snapshot discrepante
    )
    result = classify_product(p_legacy, reserved=0)
    assert "SNAPSHOT_VS_LEDGER" in result["classifications"]
    assert "SNAPSHOT_VS_LOTES" in result["classifications"]
    assert "ALERTA_LEGACY" in result["classifications"]
    assert "REQUIERE_REVISION" not in result["classifications"]
    assert result["has_legacy_warning"] is True
    assert result["operational_inconsistent"] is False
    assert result["quantity_investigation"] is False
    assert result["traceability_investigation"] is False

    # Producto con inconsistencia operacional real (ledger vs lotes)
    p_inconsistent = product(
        requires_lot=True,
        ledger_stock=50,
        lot_stock=40,  # Discrepancia real en bodega
        lot_rows=1,
        snapshot_present=False,
    )
    res_incons = classify_product(p_inconsistent, reserved=0)
    assert "LEDGER_VS_LOTES" in res_incons["classifications"]
    assert "REQUIERE_REVISION" in res_incons["classifications"]
    assert res_incons["operational_inconsistent"] is True
    assert res_incons["quantity_investigation"] is True

