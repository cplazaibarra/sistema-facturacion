-- Metadatos auditables para pagos cobrados desde Ventas.
ALTER TABLE sale_payment_items
    ADD COLUMN IF NOT EXISTS payment_method TEXT,
    ADD COLUMN IF NOT EXISTS registered_by TEXT,
    ADD COLUMN IF NOT EXISTS registered_at TEXT,
    ADD COLUMN IF NOT EXISTS bank_name_snapshot TEXT,
    ADD COLUMN IF NOT EXISTS account_number_snapshot TEXT,
    ADD COLUMN IF NOT EXISTS payment_notes TEXT,
    ADD COLUMN IF NOT EXISTS idempotency_key TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS uq_sale_payment_items_idempotency
    ON sale_payment_items(idempotency_key)
    WHERE idempotency_key IS NOT NULL;
