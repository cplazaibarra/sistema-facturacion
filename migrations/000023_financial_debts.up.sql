-- Migración 000023: Módulo de Deudas Financieras

-- 1. Catálogo de Tipos de Deuda
CREATE TABLE IF NOT EXISTS debt_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO debt_types (name) VALUES
    ('Crédito Bancario'),
    ('Préstamo'),
    ('Leasing'),
    ('Crédito Proveedor'),
    ('Préstamo Socio/Tercero'),
    ('Financiamiento Vehículo/Equipamiento'),
    ('Otro')
ON CONFLICT (name) DO NOTHING;

-- 2. Deudas Cabecera (Obligación Financiera)
CREATE TABLE IF NOT EXISTS debts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    debt_type_id INTEGER NOT NULL REFERENCES debt_types(id) ON DELETE RESTRICT,
    creditor_name VARCHAR(200) NOT NULL,
    creditor_rut VARCHAR(20),
    contract_number VARCHAR(100),
    original_amount NUMERIC(14,2) NOT NULL CHECK (original_amount > 0),
    currency VARCHAR(10) NOT NULL DEFAULT 'CLP',
    start_date DATE NOT NULL,
    installments_count INTEGER NOT NULL CHECK (installments_count > 0),
    periodicity VARCHAR(20) NOT NULL DEFAULT 'Mensual',
    interest_rate NUMERIC(6,3) DEFAULT 0.0,
    bank_account_id INTEGER REFERENCES bank_accounts(id) ON DELETE SET NULL,
    first_due_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVA' CHECK (status IN ('ACTIVA', 'PAGADA', 'CANCELADA')),
    notes TEXT,
    created_by VARCHAR(150),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_debts_status ON debts(status);
CREATE INDEX IF NOT EXISTS idx_debts_creditor ON debts(creditor_name);
CREATE INDEX IF NOT EXISTS idx_debts_type ON debts(debt_type_id);

-- 3. Cuotas de la Deuda (Compromisos Futuros)
CREATE TABLE IF NOT EXISTS debt_installments (
    id SERIAL PRIMARY KEY,
    debt_id INTEGER NOT NULL REFERENCES debts(id) ON DELETE CASCADE,
    installment_number INTEGER NOT NULL,
    due_date DATE NOT NULL,
    capital NUMERIC(14,2) NOT NULL DEFAULT 0.0 CHECK (capital >= 0),
    interest NUMERIC(14,2) NOT NULL DEFAULT 0.0 CHECK (interest >= 0),
    fees NUMERIC(14,2) NOT NULL DEFAULT 0.0 CHECK (fees >= 0),
    insurance NUMERIC(14,2) NOT NULL DEFAULT 0.0 CHECK (insurance >= 0),
    other_charges NUMERIC(14,2) NOT NULL DEFAULT 0.0 CHECK (other_charges >= 0),
    total_amount NUMERIC(14,2) NOT NULL CHECK (total_amount > 0),
    paid_amount NUMERIC(14,2) NOT NULL DEFAULT 0.0 CHECK (paid_amount >= 0),
    balance NUMERIC(14,2) NOT NULL CHECK (balance >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE' CHECK (status IN ('PENDIENTE', 'PAGO_PARCIAL', 'PAGADA', 'VENCIDA', 'ANULADA')),
    paid_date DATE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_debt_installment_number UNIQUE (debt_id, installment_number)
);

CREATE INDEX IF NOT EXISTS idx_debt_installments_due_date ON debt_installments(due_date);
CREATE INDEX IF NOT EXISTS idx_debt_installments_status ON debt_installments(status);
CREATE INDEX IF NOT EXISTS idx_debt_installments_debt_id ON debt_installments(debt_id);

-- 4. Pagos de Cuotas (Egresos Financieros Reales)
CREATE TABLE IF NOT EXISTS debt_payments (
    id SERIAL PRIMARY KEY,
    debt_installment_id INTEGER NOT NULL REFERENCES debt_installments(id) ON DELETE RESTRICT,
    payment_date DATE NOT NULL,
    payment_amount NUMERIC(14,2) NOT NULL CHECK (payment_amount > 0),
    bank_account_id INTEGER NOT NULL REFERENCES bank_accounts(id) ON DELETE RESTRICT,
    payment_method VARCHAR(50) NOT NULL DEFAULT 'Transferencia',
    reference TEXT,
    proof_file TEXT,
    notes TEXT,
    created_by VARCHAR(150),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_debt_payments_installment ON debt_payments(debt_installment_id);
CREATE INDEX IF NOT EXISTS idx_debt_payments_bank_account ON debt_payments(bank_account_id);
CREATE INDEX IF NOT EXISTS idx_debt_payments_date ON debt_payments(payment_date);

-- 5. Bitácora de Auditoría de Deudas
CREATE TABLE IF NOT EXISTS debt_audit (
    id SERIAL PRIMARY KEY,
    debt_id INTEGER NOT NULL REFERENCES debts(id) ON DELETE CASCADE,
    installment_id INTEGER REFERENCES debt_installments(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    previous_state JSONB,
    new_state JSONB,
    user_name VARCHAR(150) NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_debt_audit_debt ON debt_audit(debt_id);
