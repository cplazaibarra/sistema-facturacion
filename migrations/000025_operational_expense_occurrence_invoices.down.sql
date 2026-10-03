ALTER TABLE operational_expense_occurrences
    DROP COLUMN IF EXISTS invoice_number,
    DROP COLUMN IF EXISTS invoice_date,
    DROP COLUMN IF EXISTS document_file;
