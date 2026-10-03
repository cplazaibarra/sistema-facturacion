"""Maestro y proyecciones de gastos operacionales."""

import calendar
import json
from datetime import date, timedelta

from core.database import get_connection


def list_operational_expenses(search=None, category=None, status=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            clauses, params = ["1=1"], []
            if search:
                clauses.append("(e.name ILIKE %s OR e.description ILIKE %s OR e.beneficiary ILIKE %s)")
                params.extend([f"%{search}%"] * 3)
            if category:
                clauses.append("c.name = %s")
                params.append(category)
            if status:
                clauses.append("e.status = %s")
                params.append(status)
            cur.execute(f"""
                SELECT e.*, c.name AS category, c.name AS category_name, ba.bank_name, ba.account_number
                FROM operational_expenses e
                JOIN expense_categories c ON c.id = e.category_id
                LEFT JOIN bank_accounts ba ON ba.id = e.bank_account_id
                WHERE {' AND '.join(clauses)}
                ORDER BY e.status DESC, e.name ASC, e.id ASC
            """, params)
            return [dict(row) for row in cur.fetchall()]


def get_operational_expense(expense_id, conn=None):
    owns = conn is None
    conn = conn or get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT e.*, c.name AS category, c.name AS category_name, ba.bank_name, ba.account_number
                           FROM operational_expenses e
                           JOIN expense_categories c ON c.id = e.category_id
                           LEFT JOIN bank_accounts ba ON ba.id = e.bank_account_id
                           WHERE e.id = %s""", (expense_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        if owns:
            conn.close()


def _audit(cur, expense_id, action, user_id, details=None):
    cur.execute("INSERT INTO operational_expense_audit (expense_id, action, changed_by, details) VALUES (%s,%s,%s,%s::jsonb)", (expense_id, action, user_id, json.dumps(details or {}, ensure_ascii=False, default=str)))


def create_operational_expense(data, user_id=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM expense_categories WHERE id=%s", (data['category_id'],))
            category = cur.fetchone()
            if not category:
                raise ValueError('La categoría seleccionada no existe.')
            cur.execute("""INSERT INTO operational_expenses
                (name, category, category_id, description, amount, amount_type, frequency, start_date,
                 due_rule, due_day, end_date, bank_account_id, beneficiary, observations,
                 status, created_by, updated_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (data['name'], category['name'], data['category_id'], data.get('description'), data['amount'], data['amount_type'],
                 data['frequency'], data['start_date'], data['due_rule'], data.get('due_day'), data.get('end_date'),
                 data.get('bank_account_id'), data.get('beneficiary'), data.get('observations'), data.get('status', 'Activo'), user_id, user_id))
            expense_id = cur.fetchone()['id']
            _audit(cur, expense_id, 'CREATED', user_id, data)
        conn.commit()
    return expense_id


def update_operational_expense(expense_id, data, user_id=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM expense_categories WHERE id=%s", (data['category_id'],))
            category = cur.fetchone()
            if not category:
                raise ValueError('La categoría seleccionada no existe.')
            cur.execute("SELECT id FROM operational_expenses WHERE id = %s FOR UPDATE", (expense_id,))
            if not cur.fetchone():
                return False
            cur.execute("""UPDATE operational_expenses SET name=%s, category=%s, category_id=%s, description=%s,
                amount=%s, amount_type=%s, frequency=%s, start_date=%s, due_rule=%s, due_day=%s,
                end_date=%s, bank_account_id=%s, beneficiary=%s, observations=%s, status=%s,
                updated_by=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s""",
                (data['name'], category['name'], data['category_id'], data.get('description'), data['amount'], data['amount_type'], data['frequency'],
                 data['start_date'], data['due_rule'], data.get('due_day'), data.get('end_date'), data.get('bank_account_id'),
                 data.get('beneficiary'), data.get('observations'), data.get('status', 'Activo'), user_id, expense_id))
            _audit(cur, expense_id, 'UPDATED', user_id, data)
        conn.commit()
    return True


def set_operational_expense_status(expense_id, status, user_id=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE operational_expenses SET status=%s, updated_by=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s RETURNING id", (status, user_id, expense_id))
            row = cur.fetchone()
            if not row:
                return False
            _audit(cur, expense_id, 'ACTIVATED' if status == 'Activo' else 'DEACTIVATED', user_id, {'status': status})
        conn.commit()
    return True


def delete_operational_expense(expense_id, user_id=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM operational_expense_occurrences WHERE expense_id=%s", (expense_id,))
            if int(cur.fetchone()['n']) > 0:
                return False
            cur.execute("DELETE FROM operational_expenses WHERE id=%s RETURNING id", (expense_id,))
            deleted = cur.fetchone()
            if deleted:
                _audit(cur, None, 'DELETED', user_id, {'expense_id': expense_id})
        conn.commit()
    return bool(deleted)


def list_operational_expense_audit(expense_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT a.*, u.full_name AS user_name FROM operational_expense_audit a LEFT JOIN users u ON u.id=a.changed_by WHERE a.expense_id=%s ORDER BY a.created_at DESC", (expense_id,))
            return [dict(row) for row in cur.fetchall()]


def _occurrence_dates(expense, from_date, to_date):
    current = max(from_date, expense['start_date'])
    end = min(to_date, expense['end_date']) if expense.get('end_date') else to_date
    if current > end:
        return []
    dates = []
    if expense['frequency'] == 'Diario':
        while current <= end:
            dates.append(current)
            current += timedelta(days=1)
    elif expense['frequency'] == 'Semanal':
        target = int(expense.get('due_day') or 0) % 7
        current += timedelta(days=(target - current.weekday()) % 7)
        while current <= end:
            dates.append(current); current += timedelta(days=7)
    elif expense['frequency'] in {'Quincenal', 'Mensual', 'Bimestral', 'Trimestral', 'Semestral'}:
        step = {'Quincenal': 0, 'Mensual': 1, 'Bimestral': 2, 'Trimestral': 3, 'Semestral': 6}[expense['frequency']]
        if step == 0:
            while current <= end:
                dates.append(current)
                current += timedelta(days=15)
            return dates
        cursor = current.replace(day=1)
        while cursor <= end:
            day = min(int(expense.get('due_day') or 1), calendar.monthrange(cursor.year, cursor.month)[1])
            value = cursor.replace(day=day)
            if value >= current and value <= end: dates.append(value)
            for _ in range(step):
                cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    else:
        # Anual siempre conserva el mes de inicio y utiliza el día configurado
        # (o el día de inicio), evitando saltos de año y fechas imposibles.
        month = expense['start_date'].month
        day = int(expense.get('due_day') or expense['start_date'].day)
        for year in range(current.year, end.year + 1):
            value = date(year, month, min(day, calendar.monthrange(year, month)[1]))
            if current <= value <= end:
                dates.append(value)
    return dates


def project_operational_expenses(from_date, to_date):
    return [
        {
            'expense_id': e['id'], 'name': e['name'], 'category': e['category'],
            'due_date': due, 'amount': float(e['amount']), 'amount_type': e['amount_type'],
            'status': e['status'], 'bank_account_id': e.get('bank_account_id'),
            'bank_name': e.get('bank_name'), 'account_number': e.get('account_number'),
            'beneficiary': e.get('beneficiary'),
        }
        for e in list_operational_expenses(status='Activo')
        for due in _occurrence_dates(e, from_date, to_date)
    ]


def calculate_next_occurrence_date(expense, as_of=None):
    """Calcula la próxima fecha de pago a partir de una fecha de referencia (por defecto hoy)."""
    if expense.get('status') != 'Activo':
        return None
    if not as_of:
        as_of = date.today()
    exp_copy = dict(expense)
    if isinstance(exp_copy.get('start_date'), str):
        from datetime import datetime
        try:
            exp_copy['start_date'] = datetime.strptime(exp_copy['start_date'].split('T')[0], '%Y-%m-%d').date()
        except Exception:
            pass
    if isinstance(exp_copy.get('end_date'), str):
        from datetime import datetime
        try:
            exp_copy['end_date'] = datetime.strptime(exp_copy['end_date'].split('T')[0], '%Y-%m-%d').date()
        except Exception:
            pass
    dates = _occurrence_dates(exp_copy, as_of, date(as_of.year + 2, 12, 31))
    return dates[0] if dates else None

