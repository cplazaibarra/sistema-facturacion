"""
tests/unit/test_inventory_phase2.py
Suite de pruebas exhaustivas para la FASE 2: Consistencia y Fuente de Verdad de Inventario.

Verifica:
1. test_purchase_increases_stock
2. test_sale_decreases_stock
3. test_sale_cannot_exceed_stock (INV-001)
4. test_fifo_lot_consumption
5. test_multiple_lots_fifo
6. test_production_consumes_inputs
7. test_production_creates_output
8. test_stock_never_negative (INV-001)
9. test_inventory_reconciliation
10. test_vpp_last_30_days
11. test_vpp_fallback_last_purchase
12. test_product_without_lot_supported
13. test_inventory_invariants_enforced (INV-002, INV-008)
14. test_dual_read_consistency
"""

import pytest
from datetime import datetime, timezone, timedelta
from db import (
    get_connection,
    record_inventory_movement,
    get_relational_stock,
    get_relational_stock_by_sku,
    consume_fifo_lots,
    get_stock_with_dual_read,
    get_product_calculated_cost,
    get_product_available_stock,
    insert_product,
    delete_product
)


@pytest.fixture
def temp_test_product():
    """Crea un producto de prueba temporal aislado y lo elimina al finalizar."""
    sku = f"TEST-P2-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    product_data = {
        "sku": sku,
        "name": f"Producto Test Fase 2 {sku}",
        "description": "Producto para pruebas unitarias de inventario Fase 2",
        "category": "Pruebas",
        "product_type": "Final",
        "cost": 1500.0,
        "price": 2500.0,
        "requires_lot": False,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    }
    prod_id = insert_product(product_data)
    yield {"id": prod_id, "sku": sku, "name": product_data["name"]}

    # Cleanup
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM inventory_movements WHERE product_id = %s;", (prod_id,))
            cur.execute("DELETE FROM inventory_entry_items WHERE product_id = %s;", (prod_id,))
            cur.execute("DELETE FROM lot_stock WHERE product_id = %s;", (prod_id,))
            cur.execute("DELETE FROM products WHERE id = %s;", (prod_id,))
        conn.commit()


@pytest.fixture
def temp_test_product_with_lot():
    """Crea un producto de prueba temporal que requiere lote."""
    sku = f"TEST-LOT-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    product_data = {
        "sku": sku,
        "name": f"Producto Lote Test {sku}",
        "description": "Producto para pruebas unitarias de lotes FIFO",
        "category": "Pruebas Lote",
        "product_type": "Final",
        "cost": 3000.0,
        "price": 5000.0,
        "requires_lot": True,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    }
    prod_id = insert_product(product_data)
    yield {"id": prod_id, "sku": sku, "name": product_data["name"]}

    # Cleanup
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM inventory_movements WHERE product_id = %s;", (prod_id,))
            cur.execute("DELETE FROM inventory_entry_items WHERE product_id = %s;", (prod_id,))
            cur.execute("DELETE FROM lot_stock WHERE product_id = %s;", (prod_id,))
            cur.execute("DELETE FROM products WHERE id = %s;", (prod_id,))
        conn.commit()


# ==============================================================================
# TESTS OBLIGATORIOS FASE 2
# ==============================================================================

def test_purchase_increases_stock(temp_test_product):
    """Verifica que un ingreso de compra aumente el stock relacional."""
    pid = temp_test_product["id"]
    initial_stock = get_relational_stock(pid)
    assert initial_stock == 0.0

    record_inventory_movement(
        product_id=pid,
        movement_type="PURCHASE_RECEIPT",
        quantity=50.0,
        unit_cost=1500.0,
        reference_type="purchase_order",
        reference_id=99991,
        notes="Prueba de compra unitaria"
    )

    new_stock = get_relational_stock(pid)
    assert new_stock == 50.0
    assert get_relational_stock_by_sku(temp_test_product["sku"]) == 50.0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT reference_type, reference_id FROM inventory_movements WHERE product_id=%s ORDER BY id DESC LIMIT 1", (pid,))
            origin = cur.fetchone()
    assert origin["reference_type"] == "purchase_order"
    assert origin["reference_id"] == 99991


def test_sale_decreases_stock(temp_test_product):
    """Verifica que un despacho por venta disminuya el stock relacional."""
    pid = temp_test_product["id"]
    # Ingresar 100 un.
    record_inventory_movement(
        product_id=pid,
        movement_type="PURCHASE_RECEIPT",
        quantity=100.0,
        reference_type="purchase_order",
        reference_id=99992,
        notes="Ingreso base"
    )
    # Vender 30 un.
    record_inventory_movement(
        product_id=pid,
        movement_type="SALE",
        quantity=-30.0,
        reference_type="sale",
        reference_id=88881,
        notes="Venta VTA-TEST"
    )

    current_stock = get_relational_stock(pid)
    assert current_stock == 70.0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT movement_type, reference_type, reference_id FROM inventory_movements WHERE product_id=%s ORDER BY id DESC LIMIT 2", (pid,))
            origins = cur.fetchall()
    assert {(row["movement_type"], row["reference_type"], row["reference_id"]) for row in origins} == {
        ("SALE", "sale", 88881),
        ("PURCHASE_RECEIPT", "purchase_order", 99992),
    }


def test_sale_cannot_exceed_stock(temp_test_product):
    """Verifica el invariante INV-001: no se puede vender más de lo existente."""
    pid = temp_test_product["id"]
    record_inventory_movement(
        product_id=pid,
        movement_type="PURCHASE_RECEIPT",
        quantity=10.0,
        reference_type="purchase_order",
        reference_id=99993,
        notes="Ingreso pequeño"
    )

    with pytest.raises(ValueError, match="INV-001: Stock insuficiente"):
        record_inventory_movement(
            product_id=pid,
            movement_type="SALE",
            quantity=-15.0,
            reference_type="sale",
            reference_id=88882,
            notes="Venta en exceso prohibida"
        )


def test_stock_never_negative(temp_test_product):
    """Verifica que no se permita registrar un movimiento que lleve el stock relacional a negativo."""
    pid = temp_test_product["id"]
    with pytest.raises(ValueError, match="INV-001"):
        record_inventory_movement(
            product_id=pid,
            movement_type="SALE",
            quantity=-1.0,
            reference_type="sale",
            reference_id=88883,
            notes="Intento de venta sin stock"
        )


def test_fifo_lot_consumption(temp_test_product_with_lot):
    """Verifica el consumo FIFO de un único lote."""
    pid = temp_test_product_with_lot["id"]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO lot_stock (product_id, lot_number, entry_date, initial_qty, available_qty)
                VALUES (%s, 'LOT-A', '2026-09-01', 50, 50);
                """,
                (pid,)
            )
        conn.commit()

    consumed = consume_fifo_lots(pid, 20.0)
    assert len(consumed) == 1
    assert consumed[0]["lot_number"] == "LOT-A"
    assert consumed[0]["quantity"] == 20.0

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT available_qty FROM lot_stock WHERE product_id = %s AND lot_number = 'LOT-A'", (pid,))
            row = cur.fetchone()
            assert float(row["available_qty"]) == 30.0


def test_multiple_lots_fifo(temp_test_product_with_lot):
    """Verifica que el consumo FIFO agote primero el lote más antiguo."""
    pid = temp_test_product_with_lot["id"]
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Lote 1 (antiguo): 30 un.
            cur.execute(
                """
                INSERT INTO lot_stock (product_id, lot_number, entry_date, initial_qty, available_qty)
                VALUES (%s, 'LOT-OLD', '2026-08-01', 30, 30);
                """,
                (pid,)
            )
            # Lote 2 (nuevo): 40 un.
            cur.execute(
                """
                INSERT INTO lot_stock (product_id, lot_number, entry_date, initial_qty, available_qty)
                VALUES (%s, 'LOT-NEW', '2026-09-01', 40, 40);
                """,
                (pid,)
            )
        conn.commit()

    # Consumir 45 unidades (debe consumir 30 de LOT-OLD y 15 de LOT-NEW)
    consumed = consume_fifo_lots(pid, 45.0)
    assert len(consumed) == 2
    assert consumed[0]["lot_number"] == "LOT-OLD"
    assert consumed[0]["quantity"] == 30.0
    assert consumed[1]["lot_number"] == "LOT-NEW"
    assert consumed[1]["quantity"] == 15.0

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT lot_number, available_qty FROM lot_stock WHERE product_id = %s ORDER BY entry_date ASC", (pid,))
            rows = cur.fetchall()
            assert rows[0]["lot_number"] == "LOT-OLD"
            assert float(rows[0]["available_qty"]) == 0.0
            assert rows[1]["lot_number"] == "LOT-NEW"
            assert float(rows[1]["available_qty"]) == 25.0


def test_production_consumes_inputs(temp_test_product):
    """Verifica que un insumo de producción registre movimiento negativo y reduzca stock."""
    pid = temp_test_product["id"]
    # Stock inicial del insumo
    record_inventory_movement(
        product_id=pid,
        movement_type="PURCHASE_RECEIPT",
        quantity=200.0,
        reference_type="purchase_order",
        reference_id=99994,
        notes="Insumo recibido"
    )

    # Consumo en OT
    record_inventory_movement(
        product_id=pid,
        movement_type="PRODUCTION_INPUT",
        quantity=-80.0,
        unit_cost=1500.0,
        reference_type="production_order",
        reference_id=77771,
        notes="Consumo OT-TEST"
    )

    assert get_relational_stock(pid) == 120.0


def test_production_creates_output(temp_test_product):
    """Verifica que la fabricación finalizada registre movimiento positivo de producto terminado."""
    pid = temp_test_product["id"]
    record_inventory_movement(
        product_id=pid,
        movement_type="PRODUCTION_OUTPUT",
        quantity=25.0,
        unit_cost=4500.0,
        reference_type="production_order",
        reference_id=77772,
        notes="PT Fabricado OT-TEST-2"
    )

    assert get_relational_stock(pid) == 25.0


def test_product_without_lot_supported(temp_test_product):
    """Verifica que los productos sin lote (requires_lot = False) funcionen plenamente con inventory_movements."""
    pid = temp_test_product["id"]
    # Movimiento con lot_number = None
    record_inventory_movement(
        product_id=pid,
        movement_type="PURCHASE_RECEIPT",
        quantity=500.0,
        unit_cost=100.0,
        lot_number=None,
        reference_type="purchase_order",
        reference_id=99995,
        notes="Envases sin lote"
    )

    record_inventory_movement(
        product_id=pid,
        movement_type="PRODUCTION_INPUT",
        quantity=-200.0,
        lot_number=None,
        reference_type="production_order",
        reference_id=77773,
        notes="Uso de envases en producción"
    )

    assert get_relational_stock(pid) == 300.0


def test_inventory_invariants_enforced(temp_test_product):
    """Verifica la obligatoriedad de INV-008 (magnitud != 0) e INV-002 (salidas con origen)."""
    pid = temp_test_product["id"]
    # INV-008
    with pytest.raises(ValueError, match="INV-008"):
        record_inventory_movement(
            product_id=pid,
            movement_type="PURCHASE_RECEIPT",
            quantity=0.0
        )

    # INV-002: Salida sin referencia ni nota
    with pytest.raises(ValueError, match="INV-002"):
        record_inventory_movement(
            product_id=pid,
            movement_type="SALE",
            quantity=-5.0,
            reference_type=None,
            notes=None
        )


def test_vpp_last_30_days(temp_test_product):
    """Verifica que get_product_calculated_cost calcule el promedio ponderado en ventana de 30 días."""
    pid = temp_test_product["id"]
    today_str = datetime.today().strftime('%Y-%m-%d')
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Crear cabecera de entrada
            cur.execute(
                """
                INSERT INTO inventory_entries (entry_date, order_number, warehouse, total_amount, created_at)
                VALUES (%s, 'OC-VPP-1', 'Principal', 50000, %s) RETURNING id;
                """,
                (today_str, datetime.now(timezone.utc).isoformat())
            )
            entry_id = cur.fetchone()["id"]
            # Item 1: 10 un a $1000 = $10000
            # Item 2: 20 un a $2000 = $40000
            # Total 30 un, Total $50000 -> Promedio ponderado = 50000 / 30 = 1666.6667
            cur.execute(
                """
                INSERT INTO inventory_entry_items (inventory_entry_id, product_id, quantity, unit_price, total)
                VALUES (%s, %s, 10, 1000.0, 10000.0), (%s, %s, 20, 2000.0, 40000.0);
                """,
                (entry_id, pid, entry_id, pid)
            )
        conn.commit()

    cost = get_product_calculated_cost(pid)
    assert cost is not None
    assert round(cost, 2) == 1666.67


def test_vpp_fallback_last_purchase(temp_test_product):
    """Verifica que get_product_calculated_cost haga fallback a la última compra si es más antigua de 30 días."""
    pid = temp_test_product["id"]
    old_date = (datetime.today() - timedelta(days=60)).strftime('%Y-%m-%d')
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO inventory_entries (entry_date, order_number, warehouse, total_amount, created_at)
                VALUES (%s, 'OC-VPP-OLD', 'Principal', 15000, %s) RETURNING id;
                """,
                (old_date, datetime.now(timezone.utc).isoformat())
            )
            entry_id = cur.fetchone()["id"]
            cur.execute(
                """
                INSERT INTO inventory_entry_items (inventory_entry_id, product_id, quantity, unit_price, total)
                VALUES (%s, %s, 5, 3000.0, 15000.0);
                """,
                (entry_id, pid)
            )
        conn.commit()

    cost = get_product_calculated_cost(pid)
    assert cost == 3000.0


def test_inventory_reconciliation():
    """El diagnóstico V2 conserva snapshot ausente separado de stock cero."""
    from tools.reconcile_inventory import reconcile_inventory
    summary, results = reconcile_inventory()
    assert summary["products_analyzed"] >= 111
    assert summary["snapshot_present"] + summary["snapshot_missing"] == summary["products_analyzed"]
    assert summary["automatic_quantity_corrections_identified"] == 0
    for r in results:
        assert isinstance(r["snapshot_present"], bool)
        assert isinstance(r["classifications"], list)
        if not r["snapshot_present"]:
            assert r["snapshot_stock"] is None
            assert "SNAPSHOT_AUSENTE" in r["classifications"]


def test_dual_read_consistency(temp_test_product):
    """Verifica que get_stock_with_dual_read retorne valores coherentes."""
    pid = temp_test_product["id"]
    legacy_st, rel_st, delta = get_stock_with_dual_read(pid)
    assert legacy_st == 0.0
    assert rel_st == 0.0
    assert delta == 0.0
