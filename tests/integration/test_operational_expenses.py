"""Cobertura del maestro administrable de gastos operacionales."""

from datetime import date, timedelta
import uuid

from db import get_connection
from repositories.operational_expenses_repo import (
    create_operational_expense,
    delete_operational_expense,
    list_operational_expenses,
    project_operational_expenses,
    set_operational_expense_status,
    update_operational_expense,
)


def _data(marker, amount=1000, category_id=None):
    return {
        'name': f'Gasto QA {marker}', 'category': 'QA', 'category_id': category_id, 'description': 'Prueba',
        'amount': amount, 'amount_type': 'Fijo', 'frequency': 'Mensual',
        'start_date': date.today().replace(day=1), 'due_rule': 'Día del mes',
        'due_day': 5, 'end_date': None, 'bank_account_id': None,
        'beneficiary': 'QA', 'observations': '', 'status': 'Activo',
    }


def test_operational_expense_crud_and_status():
    marker = uuid.uuid4().hex[:8]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO expense_categories (name) VALUES (%s) RETURNING id", (f'QA {marker}',))
            category_id = cur.fetchone()['id']
        conn.commit()
    expense_id = create_operational_expense(_data(marker, category_id=category_id), 1)
    try:
        assert any(e['id'] == expense_id for e in list_operational_expenses(category=f'QA {marker}'))
        changed = _data(marker, 2500, category_id)
        changed['status'] = 'Inactivo'
        assert update_operational_expense(expense_id, changed, 1)
        assert set_operational_expense_status(expense_id, 'Activo', 1)
        projected = project_operational_expenses(date.today(), date.today() + timedelta(days=370))
        assert any(p['expense_id'] == expense_id and p['amount'] == 2500 for p in projected)
        assert delete_operational_expense(expense_id, 1)
        assert not any(e['id'] == expense_id for e in list_operational_expenses())
    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('DELETE FROM operational_expense_audit WHERE expense_id = %s', (expense_id,))
                cur.execute('DELETE FROM operational_expenses WHERE id = %s', (expense_id,))
                cur.execute('DELETE FROM expense_categories WHERE id = %s', (category_id,))
            conn.commit()


def test_inactive_expense_is_not_projected_and_history_prevents_delete():
    marker = uuid.uuid4().hex[:8]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO expense_categories (name) VALUES (%s) RETURNING id", (f'QA {marker}',))
            category_id = cur.fetchone()['id']
        conn.commit()
    expense_id = create_operational_expense(_data(marker, category_id=category_id), 1)
    occurrence_id = None
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO operational_expense_occurrences
                    (expense_id, due_date, amount, status) VALUES (%s,%s,%s,'Pagado') RETURNING id""",
                    (expense_id, date.today(), 1000))
                occurrence_id = cur.fetchone()['id']
            conn.commit()
        assert delete_operational_expense(expense_id, 1) is False
        assert set_operational_expense_status(expense_id, 'Inactivo', 1)
        assert not any(p['expense_id'] == expense_id for p in project_operational_expenses(date.today(), date.today() + timedelta(days=370)))
    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if occurrence_id:
                    cur.execute('DELETE FROM operational_expense_occurrences WHERE id = %s', (occurrence_id,))
                cur.execute('DELETE FROM operational_expense_audit WHERE expense_id = %s', (expense_id,))
                cur.execute('DELETE FROM operational_expenses WHERE id = %s', (expense_id,))
                cur.execute('DELETE FROM expense_categories WHERE id = %s', (category_id,))
            conn.commit()


def test_operational_expenses_screen_is_available(auth_client):
    response = auth_client.get('/administracion/gastos-operacionales')
    assert response.status_code == 200
    assert 'Gastos Operacionales' in response.get_data(as_text=True)


def test_supported_recurrencies_are_persisted():
    marker = uuid.uuid4().hex[:8]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO expense_categories (name) VALUES (%s) RETURNING id", (f'Frecuencias {marker}',))
            category_id = cur.fetchone()['id']
        conn.commit()
    ids = []
    try:
        for frequency in ('Diario', 'Semanal', 'Mensual', 'Anual'):
            data = _data(f'{marker}-{frequency}', category_id=category_id)
            data['frequency'] = frequency
            ids.append(create_operational_expense(data, 1))
        assert len(ids) == 4
    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for expense_id in ids:
                    cur.execute('DELETE FROM operational_expense_audit WHERE expense_id=%s', (expense_id,))
                    cur.execute('DELETE FROM operational_expenses WHERE id=%s', (expense_id,))
                cur.execute('DELETE FROM expense_categories WHERE id=%s', (category_id,))
            conn.commit()
