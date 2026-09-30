"""FIFO físico multicapa y valoración PPP; sólo en el clon autorizado por pytest."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest

from app import app
from core.database import get_connection
from repositories.products_repo import create_product
from repositories.suppliers_repo import insert_supplier
from repositories.purchases_repo import create_purchase_order
from repositories.inventory_repo import register_inventory_entry, consume_fifo_lots
from repositories.production_repo import create_production_order
from repositories.kardex_repo import get_current_ppp, get_product_kardex_history
from repositories.inventory_revaluation_repo import revalue_inventory_movement
from services.operario_service import OperarioService


def rows(query, params=()):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


@pytest.fixture
def scenario(monkeypatch):
    monkeypatch.setitem(app.config, 'TESTING', True)
    monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', False)
    tag = uuid4().hex[:10]
    raw = create_product(sku=f'TEST-FIFO-MP-{tag}', name=f'Insumo FIFO {tag}',
                         product_type='Insumo', requires_lot=True, cost=9999)
    finished = create_product(sku=f'TEST-FIFO-PT-{tag}', name=f'Terminado FIFO {tag}',
                              requires_lot=True, cost=0)
    supplier = insert_supplier({'name': f'TEST-FIFO proveedor {tag}'})

    def receive(qty, cost, day, label):
        line = {'product_id': raw, 'quantity': Decimal(str(qty)),
                'unit_price': Decimal(str(cost)), 'lot_number': f'{tag}-{label}'}
        number = create_purchase_order(supplier, day, f'FIFO {tag}', [line])
        po = rows('SELECT id FROM purchase_orders WHERE oc_number=%s', (number,))[0]['id']
        entry = register_inventory_entry(po, number, day, 'Principal', 'FIFO multicapa', [line])
        return rows('SELECT * FROM lot_stock WHERE entry_id=%s', (entry,))[0]

    def order(qty):
        return create_production_order(finished, qty, status='Aprobada',
            items=[{'input_product_id': raw, 'quantity_required': 1}])[0]

    return raw, finished, receive, order


def finish(ot, barrier=None):
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess.update(user_id=1, username='admin', full_name='Administrador',
                        role_name='Administrativo', permissions={'inventario': True, 'produccion': True})
        if barrier:
            barrier.wait(timeout=10)
        return client.post(f'/produccion/ot/{ot}/finalizar',
                           data={'output_lot_number': f'TEST-FIFO-OUTPUT-{ot}'})


def effects(ot):
    return rows("SELECT id,product_id,movement_type,quantity,unit_cost,lot_id FROM inventory_movements "
                "WHERE reference_type='production_order' AND reference_id=%s ORDER BY id", (ot,))


@pytest.mark.parametrize('same_date', [False, True])
def test_multilayer_fifo_quantity_genealogy_ppp_and_idempotency(scenario, same_date):
    raw, finished, receive, order = scenario
    if same_date:
        a = receive(10, 1000, '2026-01-01', 'A')
        b = receive(10, 1200, '2026-01-01', 'B')
        assert a['id'] < b['id']
    else:
        # Insertar el lote más nuevo primero demuestra que fecha precede al ID.
        b = receive(10, 1200, '2026-01-02', 'B')
        a = receive(10, 1000, '2026-01-01', 'A')
        assert b['id'] < a['id']
    assert get_current_ppp(raw) == 1100
    ot = order(15)
    assert finish(ot).status_code == 302
    movements = effects(ot)
    inputs = [m for m in movements if m['movement_type'] == 'PRODUCTION_INPUT']
    outputs = [m for m in movements if m['movement_type'] == 'PRODUCTION_OUTPUT']
    assert [(m['lot_id'], m['quantity']) for m in inputs] == [(a['lot_id'], -10), (b['lot_id'], -5)]
    assert [m['unit_cost'] for m in inputs] == [1100, 1100]
    assert sum(-Decimal(str(m['quantity'])) * Decimal(str(m['unit_cost'])) for m in inputs) == Decimal('16500')
    assert len(outputs) == 1
    assert (outputs[0]['quantity'], outputs[0]['unit_cost']) == (15, 1100)
    stocks = rows('SELECT ls.lot_id,ls.available_qty,l.status FROM lot_stock ls JOIN lots l ON l.id=ls.lot_id WHERE ls.product_id=%s ORDER BY ls.entry_date,ls.id', (raw,))
    assert [(r['available_qty'], r['status']) for r in stocks] == [(0, 'DEPLETED'), (5, 'ACTIVE')]
    genealogy = rows('SELECT input_lot_id,quantity_consumed FROM production_lot_consumptions WHERE production_order_id=%s ORDER BY id', (ot,))
    assert [(r['input_lot_id'], r['quantity_consumed']) for r in genealogy] == [(a['lot_id'], 10), (b['lot_id'], 5)]
    assert get_current_ppp(finished) == 1100
    kh = get_product_kardex_history(finished)
    assert (kh['current_stock'], kh['current_inventory_value']) == (15, 16500)
    raw_kh = get_product_kardex_history(raw)
    assert (raw_kh['current_stock'], raw_kh['current_inventory_value']) == (5, 5500)
    assert finish(ot).status_code == 302
    assert effects(ot) == movements
    assert rows('SELECT count(*) AS n FROM production_lot_outputs WHERE production_order_id=%s', (ot,))[0]['n'] == 1
    assert rows('SELECT SUM(available_qty) AS q FROM lot_stock WHERE product_id=%s', (finished,))[0]['q'] == 15


def test_insufficient_fifo_and_production_leave_no_partial_effects(scenario):
    raw, finished, receive, order = scenario
    receive(2, 1000, '2026-01-01', 'A')
    receive(3, 1200, '2026-01-02', 'B')
    before = rows('SELECT * FROM lot_stock WHERE product_id=%s ORDER BY id', (raw,))
    with pytest.raises(ValueError, match='INV-004'):
        consume_fifo_lots(raw, 6)
    assert rows('SELECT * FROM lot_stock WHERE product_id=%s ORDER BY id', (raw,)) == before
    ot = order(6)
    # Falta de insumos es error de dominio controlado, nunca HTTP 500.
    assert finish(ot).status_code == 302
    assert effects(ot) == []
    assert rows('SELECT * FROM lot_stock WHERE product_id=%s ORDER BY id', (raw,)) == before
    assert rows('SELECT * FROM lot_stock WHERE product_id=%s', (finished,)) == []
    assert rows('SELECT status FROM production_orders WHERE id=%s', (ot,))[0]['status'] == 'Aprobada'


@pytest.mark.parametrize('same_order', [False, True])
def test_concurrent_production_cannot_double_consume(scenario, same_order):
    raw, finished, receive, order = scenario
    receive(4, 1000, '2026-01-01', 'A')
    receive(6, 1200, '2026-01-02', 'B')
    first = order(8)
    second = first if same_order else order(8)
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(finish, ot, barrier) for ot in (first, second)]
        responses = [future.result(timeout=30) for future in futures]
    assert all(r.status_code == 302 for r in responses)
    assert rows('SELECT SUM(available_qty) AS q,MIN(available_qty) AS minimum FROM lot_stock WHERE product_id=%s', (raw,))[0] == {'q': 2, 'minimum': 0}
    assert rows('SELECT SUM(quantity) AS q FROM inventory_movements WHERE product_id=%s', (raw,))[0]['q'] == 2
    assert rows("SELECT COUNT(*) AS n FROM inventory_movements WHERE product_id=%s AND movement_type='PRODUCTION_OUTPUT'", (finished,))[0]['n'] == 1
    assert rows('SELECT SUM(quantity_consumed) AS q FROM production_lot_consumptions WHERE production_order_id=ANY(%s)', ([first, second],))[0]['q'] == 8


def test_revaluation_changes_cost_not_fifo_selection(scenario):
    raw, finished, receive, order = scenario
    a = receive(10, 1000, '2026-01-01', 'A')
    b = receive(10, 1200, '2026-01-02', 'B')
    before = rows('SELECT * FROM lot_stock WHERE product_id=%s ORDER BY id', (raw,))
    movement = rows('SELECT id FROM inventory_movements WHERE product_id=%s AND lot_id=%s', (raw, a['lot_id']))[0]['id']
    revalue_inventory_movement(movement, Decimal('1400'), 'Regresión aislada costo efectivo FIFO')
    assert rows('SELECT * FROM lot_stock WHERE product_id=%s ORDER BY id', (raw,)) == before
    assert get_current_ppp(raw) == 1300
    ot = order(15)
    assert finish(ot).status_code == 302
    inputs = [m for m in effects(ot) if m['movement_type'] == 'PRODUCTION_INPUT']
    assert [(m['lot_id'], m['quantity'], m['unit_cost']) for m in inputs] == [(a['lot_id'], -10, 1300), (b['lot_id'], -5, 1300)]
    assert get_current_ppp(finished) == 1300


def test_failure_on_second_material_rolls_back_first_fifo_consumption(scenario):
    raw, finished, receive, _ = scenario
    receive(2, 1000, '2026-01-01', 'A')
    receive(3, 1200, '2026-01-02', 'B')
    unavailable = create_product(sku=f'TEST-FIFO-EMPTY-{uuid4().hex[:10]}',
                                 name='Segundo insumo sin stock', requires_lot=True)
    before = rows('SELECT * FROM lot_stock WHERE product_id=%s ORDER BY id', (raw,))
    ot, _ = create_production_order(finished, 4, status='Aprobada', items=[
        {'input_product_id': raw, 'quantity_required': 1},
        {'input_product_id': unavailable, 'quantity_required': 1},
    ])
    assert finish(ot).status_code == 302
    assert effects(ot) == []
    assert rows('SELECT * FROM lot_stock WHERE product_id=%s ORDER BY id', (raw,)) == before
    assert rows('SELECT * FROM production_lot_consumptions WHERE production_order_id=%s', (ot,)) == []
    assert rows('SELECT * FROM production_lot_outputs WHERE production_order_id=%s', (ot,)) == []
    assert rows('SELECT status FROM production_orders WHERE id=%s', (ot,))[0]['status'] == 'Aprobada'


def test_fifo_row_locks_recheck_remaining_stock_without_ot_lock(scenario):
    raw, _, receive, _ = scenario
    receive(4, 1000, '2026-01-01', 'A')
    receive(6, 1200, '2026-01-02', 'B')
    barrier = Barrier(2)

    def consume():
        barrier.wait(timeout=10)
        try:
            return consume_fifo_lots(raw, 8)
        except ValueError as exc:
            assert 'INV-004' in str(exc)
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(consume) for _ in range(2)]
        results = [future.result(timeout=30) for future in futures]
    assert sum(result is not None for result in results) == 1
    assert sum(r['quantity'] for result in results if result for r in result) == 8
    assert rows('SELECT SUM(available_qty) AS q,MIN(available_qty) AS minimum FROM lot_stock WHERE product_id=%s', (raw,))[0] == {'q': 2, 'minimum': 0}


def test_mobile_output_uses_effective_revalued_input_cost(scenario):
    raw, finished, receive, order = scenario
    a = receive(10, 1000, '2026-01-01', 'A')
    b = receive(10, 1200, '2026-01-02', 'B')
    # Revaluar entrada del lote A: 1000 -> 1200. Nuevo PPP insumo: (10*1200 + 10*1200)/20 = 1200.
    in_mov = rows('SELECT id FROM inventory_movements WHERE product_id=%s AND lot_id=%s', (raw, a['lot_id']))[0]['id']
    revalue_inventory_movement(in_mov, Decimal('1200'), 'Revaluación de entrada previa a producción')
    assert get_current_ppp(raw) == 1200

    ot = order(15)
    for lot, qty in [(a, 10), (b, 5)]:
        ok, message, _ = OperarioService.validate_and_record_consumption(ot, raw, lot['lot_number'], qty)
        assert ok, message
    inputs = effects(ot)
    assert [r['unit_cost'] for r in inputs] == [1200, 1200]

    # Regla oficial del ERP: No se permite revaluación directa de movimientos de salida (PRODUCTION_INPUT)
    with pytest.raises(ValueError, match='No se permite revaluación directa de movimientos de salida'):
        revalue_inventory_movement(inputs[0]['id'], Decimal('1300'), 'Intento inválido de revaluar consumo')

    ok, message, _ = OperarioService.finalize_production(ot, 15, f'TEST-MOBILE-{ot}')
    assert ok, message
    output = effects(ot)[-1]
    assert output['unit_cost'] == pytest.approx(1200)
    assert get_current_ppp(finished) == pytest.approx(1200)
    assert not OperarioService.finalize_production(ot, 15, f'TEST-MOBILE-{ot}')[0]
    assert effects(ot)[-1] == output

