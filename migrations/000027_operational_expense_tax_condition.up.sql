ALTER TABLE operational_expenses
    ADD COLUMN IF NOT EXISTS tax_condition TEXT NOT NULL DEFAULT 'IVA incluido'
    CHECK (tax_condition IN ('IVA incluido', 'Exento de IVA'));
