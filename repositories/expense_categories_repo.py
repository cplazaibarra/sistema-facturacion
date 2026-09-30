"""Catálogo normalizado de categorías de gastos operacionales."""

from core.database import get_connection


def list_expense_categories():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT c.id, c.name, c.description, c.created_at, c.updated_at,
                              COUNT(e.id) AS expense_count
                       FROM expense_categories c
                       LEFT JOIN operational_expenses e ON e.category_id = c.id
                       GROUP BY c.id ORDER BY LOWER(c.name), c.id""")
            return [dict(row) for row in cur.fetchall()]


def create_expense_category(name, description=None, user_id=None):
    name = (name or '').strip()
    if not name:
        raise ValueError('El nombre de categoría es obligatorio.')
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM expense_categories WHERE LOWER(BTRIM(name))=LOWER(BTRIM(%s))", (name,))
            if cur.fetchone():
                raise ValueError('Ya existe una categoría con ese nombre.')
            cur.execute("INSERT INTO expense_categories (name, description) VALUES (%s,%s) RETURNING id", (name, (description or '').strip() or None))
            category_id = cur.fetchone()['id']
        conn.commit()
    return category_id


def update_expense_category(category_id, name, description=None):
    name = (name or '').strip()
    if not name:
        raise ValueError('El nombre de categoría es obligatorio.')
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM expense_categories WHERE id <> %s AND LOWER(BTRIM(name))=LOWER(BTRIM(%s))", (category_id, name))
            if cur.fetchone():
                raise ValueError('Ya existe una categoría con ese nombre.')
            cur.execute("UPDATE expense_categories SET name=%s, description=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s RETURNING id", (name, (description or '').strip() or None, category_id))
            updated = cur.fetchone()
        conn.commit()
    return bool(updated)


def delete_expense_category(category_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM operational_expenses WHERE category_id=%s", (category_id,))
            count = int(cur.fetchone()['count'])
            if count:
                return False, count
            cur.execute("DELETE FROM expense_categories WHERE id=%s RETURNING id", (category_id,))
            deleted = bool(cur.fetchone())
        conn.commit()
    return deleted, 0
