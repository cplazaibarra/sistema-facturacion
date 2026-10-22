-- Capture legacy payment metadata only when a new installment is posted.
-- No existing row is backfilled and no historical payment is changed.
CREATE TABLE IF NOT EXISTS purchase_payment_openings (
 invoice_id INTEGER PRIMARY KEY REFERENCES purchase_invoices(id) ON DELETE RESTRICT,
 payment_amount NUMERIC(20,2) NOT NULL CHECK(payment_amount>0),
 payment_date TEXT NOT NULL,
 payment_method TEXT,
 bank_account_id INTEGER REFERENCES bank_accounts(id) ON DELETE RESTRICT,
 payment_proof_file TEXT,
 captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS expense_payment_openings (
 occurrence_id INTEGER PRIMARY KEY REFERENCES operational_expense_occurrences(id) ON DELETE RESTRICT,
 payment_amount NUMERIC(20,2) NOT NULL CHECK(payment_amount>0),
 paid_date DATE NOT NULL,
 bank_account_id INTEGER REFERENCES bank_accounts(id) ON DELETE RESTRICT,
 captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE OR REPLACE VIEW purchase_payment_events AS
 SELECT p.id AS event_id,p.invoice_id,p.payment_amount,p.payment_date::text,
 p.payment_method,p.bank_account_id,p.payment_proof_file,'PURCHASE_PAYMENT_ITEM'::text AS reconciliation_type FROM purchase_payment_items p
 UNION ALL SELECT o.invoice_id,o.invoice_id,o.payment_amount,o.payment_date,o.payment_method,o.bank_account_id,o.payment_proof_file,'PURCHASE_PAYMENT'::text FROM purchase_payment_openings o
 UNION ALL SELECT i.id,i.id,COALESCE(i.payment_amount,i.invoice_amount)::numeric,i.payment_date,i.payment_method,i.bank_account_id,i.payment_proof_file,'PURCHASE_PAYMENT'::text FROM purchase_invoices i
 WHERE NULLIF(i.payment_date,'') IS NOT NULL
 AND COALESCE(i.payment_amount,CASE WHEN i.payment_status IN ('Pagada','Pagado') THEN i.invoice_amount ELSE 0 END)>0
 AND NOT EXISTS(SELECT 1 FROM purchase_payment_items p WHERE p.invoice_id=i.id)
 AND NOT EXISTS(SELECT 1 FROM purchase_payment_openings o WHERE o.invoice_id=i.id);
CREATE OR REPLACE VIEW expense_payment_events AS
 SELECT p.id AS event_id,p.occurrence_id,p.payment_amount,p.payment_date AS paid_date,p.bank_account_id,'EXPENSE_PAYMENT_ITEM'::text AS reconciliation_type FROM expense_payment_items p
 UNION ALL SELECT o.occurrence_id,o.occurrence_id,o.payment_amount,o.paid_date,o.bank_account_id,'EXPENSE'::text FROM expense_payment_openings o
 UNION ALL SELECT o.id,o.id,COALESCE(o.payment_amount,o.amount),o.paid_date,o.bank_account_id,'EXPENSE'::text FROM operational_expense_occurrences o
 WHERE o.paid_date IS NOT NULL AND COALESCE(o.payment_amount,CASE WHEN o.status='Pagado' THEN o.amount ELSE 0 END)>0
 AND NOT EXISTS(SELECT 1 FROM expense_payment_items p WHERE p.occurrence_id=o.id)
 AND NOT EXISTS(SELECT 1 FROM expense_payment_openings p WHERE p.occurrence_id=o.id);
