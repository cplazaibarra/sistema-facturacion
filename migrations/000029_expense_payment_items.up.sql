CREATE TABLE IF NOT EXISTS expense_payment_items (
 id BIGSERIAL PRIMARY KEY,
 occurrence_id INTEGER NOT NULL REFERENCES operational_expense_occurrences(id) ON DELETE RESTRICT,
 payment_amount NUMERIC(20,2) NOT NULL CHECK(payment_amount > 0 AND payment_amount <> 'NaN'::numeric),
 payment_date DATE NOT NULL,
 bank_account_id INTEGER REFERENCES bank_accounts(id) ON DELETE RESTRICT,
 idempotency_key TEXT NOT NULL,
 created_by INTEGER REFERENCES users(id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(occurrence_id,idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_expense_payment_occurrence ON expense_payment_items(occurrence_id);
CREATE OR REPLACE VIEW expense_payment_events AS
 SELECT p.id AS event_id,p.occurrence_id,p.payment_amount,p.payment_date AS paid_date,p.bank_account_id,
        'EXPENSE_PAYMENT_ITEM'::text AS reconciliation_type
 FROM expense_payment_items p
 UNION ALL
 SELECT o.id,o.id,COALESCE(o.payment_amount,o.amount),o.paid_date,o.bank_account_id,'EXPENSE'::text
 FROM operational_expense_occurrences o
 WHERE o.status='Pagado' AND o.paid_date IS NOT NULL
 AND NOT EXISTS(SELECT 1 FROM expense_payment_items p WHERE p.occurrence_id=o.id);
