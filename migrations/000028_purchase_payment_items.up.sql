-- Additive payment ledger. No historical invoice or payment is rewritten.
CREATE TABLE IF NOT EXISTS purchase_payment_items (
 id BIGSERIAL PRIMARY KEY,
 invoice_id INTEGER NOT NULL REFERENCES purchase_invoices(id) ON DELETE RESTRICT,
 payment_amount NUMERIC(20,2) NOT NULL CHECK(payment_amount > 0 AND payment_amount <> 'NaN'::numeric),
 payment_date DATE NOT NULL,
 payment_method TEXT NOT NULL,
 bank_account_id INTEGER REFERENCES bank_accounts(id) ON DELETE RESTRICT,
 payment_proof_file TEXT,
 notes TEXT NOT NULL DEFAULT '',
 idempotency_key TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(invoice_id,idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_purchase_payment_invoice ON purchase_payment_items(invoice_id);
-- Ledger takes precedence. Legacy records are read, never backfilled or repaired.
CREATE OR REPLACE VIEW purchase_payment_events AS
 SELECT p.id AS event_id,p.invoice_id,p.payment_amount,p.payment_date::text,
        p.payment_method,p.bank_account_id,p.payment_proof_file,'PURCHASE_PAYMENT_ITEM'::text AS reconciliation_type
 FROM purchase_payment_items p
 UNION ALL
 SELECT i.id,i.id,COALESCE(i.payment_amount,i.invoice_amount)::numeric,
        i.payment_date,i.payment_method,i.bank_account_id,i.payment_proof_file,'PURCHASE_PAYMENT'::text
 FROM purchase_invoices i
 WHERE NULLIF(i.payment_date,'') IS NOT NULL
   AND COALESCE(i.payment_amount,CASE WHEN i.payment_status IN ('Pagada','Pagado') THEN i.invoice_amount ELSE 0 END)>0
   AND NOT EXISTS(SELECT 1 FROM purchase_payment_items p WHERE p.invoice_id=i.id);
