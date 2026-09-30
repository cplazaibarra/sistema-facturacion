import pytest
from pathlib import Path

from core.database import get_connection
from repositories.inventory_adjustments_repo import (
    create_adjustment, approve_adjustment, reject_adjustment,
)


def _product_id():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM products WHERE sku='PRD001' LIMIT 1")
            return cur.fetchone()['id']


def test_request_rejection_does_not_create_movement():
    pid = _product_id()
    row = create_adjustment(product_id=pid, warehouse=None, counted_quantity=0,
                            reason='CONTEO FISICO', observation='qa', requested_by=1,
                            requested_by_name='QA')
    try:
        rejected = reject_adjustment(row['id'], actor_id=2, actor_name='Aprobador', comment='Rechazo QA')
        assert rejected['status'] == 'REJECTED'
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM inventory_movements WHERE reference_type='inventory_adjustment' AND reference_id=%s", (row['id'],))
                assert cur.fetchone()['n'] == 0
    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM inventory_adjustment_audit WHERE adjustment_id=%s", (row['id'],))
                cur.execute("DELETE FROM inventory_adjustment_requests WHERE id=%s", (row['id'],))
            conn.commit()


def test_positive_adjustment_applies_once_and_generates_movement():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT p.id FROM products p WHERE NOT p.requires_lot AND NOT EXISTS (SELECT 1 FROM inventory_movements m WHERE m.product_id=p.id) ORDER BY p.id LIMIT 1")
            pid = cur.fetchone()['id']
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(quantity),0) AS n FROM inventory_movements WHERE product_id=%s", (pid,))
            stock = float(cur.fetchone()['n'])
    row = create_adjustment(product_id=pid, warehouse=None, counted_quantity=stock + 1,
                            reason='SOBRANTE', observation='qa', requested_by=1,
                            requested_by_name='QA')
    try:
        result = approve_adjustment(row['id'], actor_id=2, actor_name='Aprobador')
        assert result['status'] == 'APPLIED'
        assert result['movement_id'] is not None
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT quantity, reference_type, reference_id FROM inventory_movements WHERE id=%s", (result['movement_id'],))
                movement = cur.fetchone()
                assert float(movement['quantity']) == 1
                assert movement['reference_type'] == 'inventory_adjustment'
                assert movement['reference_id'] == row['id']
        with pytest.raises(ValueError, match='ya fue resuelta'):
            approve_adjustment(row['id'], actor_id=3, actor_name='Otro')
    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE inventory_adjustment_requests SET movement_id=NULL WHERE id=%s", (row['id'],))
                cur.execute("DELETE FROM inventory_movements WHERE reference_type='inventory_adjustment' AND reference_id=%s", (row['id'],))
                cur.execute("DELETE FROM inventory_adjustment_audit WHERE adjustment_id=%s", (row['id'],))
                cur.execute("DELETE FROM inventory_adjustment_requests WHERE id=%s", (row['id'],))
            conn.commit()


def test_negative_adjustment_applies_and_uses_official_movement():
    pid = _product_id()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(quantity),0) AS n FROM inventory_movements WHERE product_id=%s", (pid,))
            stock = float(cur.fetchone()['n'])
            cur.execute("SELECT warehouse FROM inventory_movements WHERE product_id=%s GROUP BY warehouse ORDER BY count(*) DESC LIMIT 1", (pid,))
            warehouse = cur.fetchone()['warehouse']
    row = create_adjustment(product_id=pid, warehouse=warehouse, counted_quantity=stock - 1,
                            reason='MERMA', observation='qa', requested_by=1,
                            requested_by_name='QA')
    try:
        result = approve_adjustment(row['id'], actor_id=2, actor_name='Aprobador')
        assert result['status'] == 'APPLIED'
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT quantity FROM inventory_movements WHERE id=%s", (result['movement_id'],))
                assert float(cur.fetchone()['quantity']) == -1
    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE inventory_adjustment_requests SET movement_id=NULL WHERE id=%s", (row['id'],))
                cur.execute("DELETE FROM inventory_movements WHERE reference_type='inventory_adjustment' AND reference_id=%s", (row['id'],))
                cur.execute("DELETE FROM inventory_adjustment_audit WHERE adjustment_id=%s", (row['id'],))
                cur.execute("DELETE FROM inventory_adjustment_requests WHERE id=%s", (row['id'],))
            conn.commit()


def test_adjustment_form_is_not_cancelled_by_global_submit_guard():
    template = Path(__file__).parents[2] / 'templates' / 'nuevo_ajuste_inventario.html'
    html = template.read_text(encoding='utf-8')
    assert 'data-local-submit-handler="true"' in html
    assert 'action="/inventario/ajustes/nuevo"' in html
    # base.html explicitly skips forms carrying this marker; without it the
    # local handler sets data-submitting before the global listener and the
    # global listener cancels the legitimate POST.
    base = (Path(__file__).parents[2] / 'templates' / 'base.html').read_text(encoding='utf-8')
    assert "if (form.dataset.localSubmitHandler === 'true') return;" in base


def test_pending_detail_renders_approval_actions():
    template = (Path(__file__).parents[2] / 'templates' / 'detalle_ajuste_inventario.html').read_text(encoding='utf-8')
    assert "{% if status == 'PENDING' %}" in template
    assert 'Aprobar ajuste' in template
    assert '/aprobar' in template
    assert '/rechazar' in template
    assert 'class="approval-form" data-local-submit-handler="true"' in template
    assert 'id="reject-adjustment-form" data-local-submit-handler="true"' in template


def test_applied_adjustment_detail_shows_applied_balance_without_stale_warning(auth_client):
    import re
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM products WHERE NOT COALESCE(requires_lot,FALSE) ORDER BY id LIMIT 1")
            pid = cur.fetchone()['id']
            cur.execute("SELECT COALESCE(SUM(quantity),0) AS stock FROM inventory_movements WHERE product_id=%s", (pid,))
            stock = float(cur.fetchone()['stock'])
    adjustment = create_adjustment(product_id=pid, warehouse='Almacén Principal',
                                   counted_quantity=stock + 1, reason='SOBRANTE',
                                   observation='detalle aplicado', requested_by=1,
                                   requested_by_name='QA')
    try:
        result = approve_adjustment(adjustment['id'], actor_id=2, actor_name='Aprobador')
        assert result['status'] == 'APPLIED'
        response = auth_client.get(f"/inventario/ajustes/{adjustment['id']}")
        assert response.status_code == 200
        assert b'El inventario cambi' not in response.data
        body = response.data.decode('utf-8')
        match = re.search(r'Stock resultante</small><strong[^>]*>([-+0-9.]+)</strong>', body)
        assert match and float(match.group(1)) == stock + 1
    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE inventory_adjustment_requests SET movement_id=NULL WHERE id=%s", (adjustment['id'],))
                cur.execute("DELETE FROM inventory_movements WHERE reference_type='inventory_adjustment' AND reference_id=%s", (adjustment['id'],))
                cur.execute("DELETE FROM inventory_adjustment_audit WHERE adjustment_id=%s", (adjustment['id'],))
                cur.execute("DELETE FROM inventory_adjustment_requests WHERE id=%s", (adjustment['id'],))
            conn.commit()


def test_post_adjustment_returns_redirect_and_persists(auth_client):
    from app import app
    previous = app.config.get('WTF_CSRF_ENABLED', True)
    app.config['WTF_CSRF_ENABLED'] = False
    try:
        response = auth_client.post('/inventario/ajustes/nuevo', data={
            'product_id': str(_product_id()),
            'warehouse': 'Almacén Principal',
            'counted_quantity': '0',
            'reason': 'CONTEO FISICO',
            'observation': 'qa post',
        })
        assert response.status_code == 302
        location = response.headers['Location']
        adjustment_id = int(location.rstrip('/').split('/')[-1])
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT status FROM inventory_adjustment_requests WHERE id=%s', (adjustment_id,))
                assert cur.fetchone()['status'] == 'PENDING'
                cur.execute('DELETE FROM inventory_adjustment_audit WHERE adjustment_id=%s', (adjustment_id,))
                cur.execute('DELETE FROM inventory_adjustment_requests WHERE id=%s', (adjustment_id,))
            conn.commit()
    finally:
        app.config['WTF_CSRF_ENABLED'] = previous
