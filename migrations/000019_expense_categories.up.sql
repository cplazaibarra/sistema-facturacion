CREATE TABLE IF NOT EXISTS expense_categories (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_expense_categories_name_ci
    ON expense_categories (LOWER(BTRIM(name)));

INSERT INTO expense_categories (name)
SELECT DISTINCT BTRIM(category)
FROM operational_expenses
WHERE NULLIF(BTRIM(category), '') IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM expense_categories c
      WHERE LOWER(BTRIM(c.name)) = LOWER(BTRIM(operational_expenses.category))
  );

ALTER TABLE operational_expenses
    ADD COLUMN IF NOT EXISTS category_id INTEGER;

UPDATE operational_expenses e
SET category_id = c.id
FROM expense_categories c
WHERE e.category_id IS NULL
  AND LOWER(BTRIM(e.category)) = LOWER(BTRIM(c.name));

ALTER TABLE operational_expenses
    ADD CONSTRAINT operational_expenses_category_fk
    FOREIGN KEY (category_id) REFERENCES expense_categories(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_operational_expenses_category_id
    ON operational_expenses(category_id);
