ALTER TABLE operational_expenses DROP CONSTRAINT IF EXISTS operational_expenses_category_fk;
ALTER TABLE operational_expenses DROP COLUMN IF EXISTS category_id;
DROP INDEX IF EXISTS uq_expense_categories_name_ci;
DROP TABLE IF EXISTS expense_categories;
