CREATE TABLE IF NOT EXISTS operational_expenses (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    amount NUMERIC(14,2) NOT NULL CHECK (amount >= 0),
    amount_type TEXT NOT NULL DEFAULT 'Fijo' CHECK (amount_type IN ('Fijo', 'Estimado')),
    frequency TEXT NOT NULL CHECK (frequency IN ('Semanal', 'Mensual', 'Trimestral', 'Anual')),
    start_date DATE NOT NULL,
    due_rule TEXT NOT NULL,
    due_day INTEGER,
    end_date DATE,
    bank_account_id INTEGER REFERENCES bank_accounts(id) ON DELETE SET NULL,
    beneficiary TEXT,
    observations TEXT,
    status TEXT NOT NULL DEFAULT 'Activo' CHECK (status IN ('Activo', 'Inactivo')),
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS operational_expense_occurrences (
    id SERIAL PRIMARY KEY,
    expense_id INTEGER NOT NULL REFERENCES operational_expenses(id) ON DELETE RESTRICT,
    due_date DATE NOT NULL,
    amount NUMERIC(14,2) NOT NULL CHECK (amount >= 0),
    status TEXT NOT NULL DEFAULT 'Proyectado' CHECK (status IN ('Proyectado', 'Pagado', 'Anulado')),
    paid_date DATE,
    payment_amount NUMERIC(14,2),
    bank_account_id INTEGER REFERENCES bank_accounts(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(expense_id, due_date)
);

CREATE TABLE IF NOT EXISTS operational_expense_audit (
    id BIGSERIAL PRIMARY KEY,
    expense_id INTEGER REFERENCES operational_expenses(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    changed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_operational_expenses_status ON operational_expenses(status);
CREATE INDEX IF NOT EXISTS idx_operational_expenses_start_date ON operational_expenses(start_date);
CREATE INDEX IF NOT EXISTS idx_operational_expense_occurrences_due_date ON operational_expense_occurrences(due_date);
CREATE INDEX IF NOT EXISTS idx_operational_expense_audit_expense ON operational_expense_audit(expense_id);
