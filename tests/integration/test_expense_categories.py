"""Pruebas del catálogo normalizado de categorías de gastos."""

import uuid
from db import get_connection
from repositories.expense_categories_repo import create_expense_category, delete_expense_category, update_expense_category
from repositories.operational_expenses_repo import create_operational_expense


def test_category_create_edit_delete_and_duplicate_guard():
    marker = uuid.uuid4().hex[:8]
    category_id = create_expense_category(f'Electricidad {marker}', 'Servicios', 1)
    try:
        assert update_expense_category(category_id, f'Energía Eléctrica {marker}', 'Actualizada')
        try:
            create_expense_category(f' energía eléctrica {marker} ', None, 1)
            assert False, 'debió rechazar categoría duplicada'
        except ValueError:
            pass
        assert delete_expense_category(category_id) == (True, 0)
    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('DELETE FROM expense_categories WHERE id=%s', (category_id,))
            conn.commit()


def test_category_in_use_cannot_be_deleted_and_relation_survives_rename():
    marker = uuid.uuid4().hex[:8]
    category_id = create_expense_category(f'Sueldos {marker}', None, 1)
    expense_id = None
    try:
        expense_id = create_operational_expense({
            'name': f'Gasto {marker}', 'category': f'Sueldos {marker}', 'category_id': category_id,
            'description': '', 'amount': 10, 'amount_type': 'Fijo', 'frequency': 'Mensual',
            'start_date': '2026-01-01', 'due_rule': 'Día del mes', 'due_day': 1,
            'end_date': None, 'bank_account_id': None, 'beneficiary': '', 'observations': '', 'status': 'Activo'}, 1)
        assert update_expense_category(category_id, f'Salarios {marker}', None)
        assert delete_expense_category(category_id) == (False, 1)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT c.name FROM operational_expenses e JOIN expense_categories c ON c.id=e.category_id WHERE e.id=%s', (expense_id,))
                assert cur.fetchone()['name'] == f'Salarios {marker}'
    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if expense_id:
                    cur.execute('DELETE FROM operational_expense_audit WHERE expense_id=%s', (expense_id,))
                    cur.execute('DELETE FROM operational_expenses WHERE id=%s', (expense_id,))
                cur.execute('DELETE FROM expense_categories WHERE id=%s', (category_id,))
            conn.commit()


def test_categories_screen_and_rbac(auth_client, client):
    response = auth_client.get('/administracion/gastos-operacionales')
    assert response.status_code == 200
    assert 'Administrar Categorías' in response.get_data(as_text=True)
    assert client.get('/administracion/gastos-operacionales').status_code in (302, 403)
