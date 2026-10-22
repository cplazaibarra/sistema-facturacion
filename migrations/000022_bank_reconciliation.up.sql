-- Migración 000022: Módulo de Conciliación Bancaria

-- 1. Categorías de movimientos bancarios
CREATE TABLE IF NOT EXISTS bank_transaction_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    flow_type VARCHAR(20) NOT NULL CHECK (flow_type IN ('INGRESO', 'EGRESO', 'AMBOS')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed categorías estándar requeridas
INSERT INTO bank_transaction_categories (name, flow_type) VALUES
    ('Ventas / Cobranzas', 'INGRESO'),
    ('Otros Ingresos', 'INGRESO'),
    ('Pago Proveedor', 'EGRESO'),
    ('Gasto Operacional', 'EGRESO'),
    ('Remuneraciones', 'EGRESO'),
    ('Impuestos', 'EGRESO'),
    ('Comisiones Bancarias', 'EGRESO'),
    ('Servicios', 'EGRESO'),
    ('Transferencia entre cuentas', 'AMBOS'),
    ('Otros Egresos', 'EGRESO')
ON CONFLICT (name) DO NOTHING;

-- 2. Historial de importaciones de cartolas bancarias
CREATE TABLE IF NOT EXISTS bank_transaction_imports (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    bank_account_id INTEGER NOT NULL REFERENCES bank_accounts(id) ON DELETE CASCADE,
    imported_by VARCHAR(150) NOT NULL,
    total_rows INTEGER NOT NULL DEFAULT 0,
    new_rows INTEGER NOT NULL DEFAULT 0,
    duplicate_rows INTEGER NOT NULL DEFAULT 0,
    error_rows INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bank_imports_account ON bank_transaction_imports(bank_account_id);

-- 3. Movimientos bancarios reales de cartolas
CREATE TABLE IF NOT EXISTS bank_transactions (
    id SERIAL PRIMARY KEY,
    bank_account_id INTEGER NOT NULL REFERENCES bank_accounts(id) ON DELETE RESTRICT,
    import_id INTEGER REFERENCES bank_transaction_imports(id) ON DELETE SET NULL,
    transaction_date DATE NOT NULL,
    value_date DATE,
    description TEXT NOT NULL,
    reference TEXT,
    doc_number TEXT,
    charge NUMERIC(14,2) NOT NULL DEFAULT 0.0 CHECK (charge >= 0),
    credit NUMERIC(14,2) NOT NULL DEFAULT 0.0 CHECK (credit >= 0),
    amount NUMERIC(14,2) NOT NULL,
    movement_type VARCHAR(20) NOT NULL CHECK (movement_type IN ('ABONO', 'CARGO')),
    balance NUMERIC(14,2),
    currency VARCHAR(10) NOT NULL DEFAULT 'CLP',
    category_id INTEGER REFERENCES bank_transaction_categories(id) ON DELETE SET NULL,
    reconciliation_status VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE' CHECK (reconciliation_status IN ('PENDIENTE', 'CONCILIADO', 'REVISAR')),
    reconciled_type VARCHAR(50),
    reconciled_id INTEGER,
    reconciled_at TIMESTAMP WITH TIME ZONE,
    reconciled_by VARCHAR(150),
    notes TEXT,
    fingerprint VARCHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bank_transactions_account_date ON bank_transactions(bank_account_id, transaction_date);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_status ON bank_transactions(reconciliation_status);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_category ON bank_transactions(category_id);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_fingerprint ON bank_transactions(fingerprint);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_reconciled ON bank_transactions(reconciled_type, reconciled_id);

-- 4. Auditoría de conciliación bancaria
CREATE TABLE IF NOT EXISTS bank_reconciliation_audit (
    id SERIAL PRIMARY KEY,
    bank_transaction_id INTEGER NOT NULL REFERENCES bank_transactions(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL,
    previous_state JSONB,
    new_state JSONB,
    user_name VARCHAR(150) NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bank_audit_tx_id ON bank_reconciliation_audit(bank_transaction_id);
