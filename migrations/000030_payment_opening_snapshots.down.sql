DO $$ BEGIN IF EXISTS(SELECT 1 FROM purchase_payment_openings) OR EXISTS(SELECT 1 FROM expense_payment_openings) THEN RAISE EXCEPTION 'Downgrade refused: historical snapshots must be preserved'; END IF; END $$;
-- Restore the preceding view definitions before removing additive snapshots.
CREATE OR REPLACE VIEW purchase_payment_events AS
 SELECT p.id AS event_id,p.invoice_id,p.payment_amount,p.payment_date::text,p.payment_method,p.bank_account_id,p.payment_proof_file,'PURCHASE_PAYMENT_ITEM'::text AS reconciliation_type FROM purchase_payment_items p
 UNION ALL SELECT i.id,i.id,COALESCE(i.payment_amount,i.invoice_amount)::numeric,i.payment_date,i.payment_method,i.bank_account_id,i.payment_proof_file,'PURCHASE_PAYMENT'::text FROM purchase_invoices i
 WHERE NULLIF(i.payment_date,'') IS NOT NULL AND COALESCE(i.payment_amount,CASE WHEN i.payment_status IN ('Pagada','Pagado') THEN i.invoice_amount ELSE 0 END)>0
 AND NOT EXISTS(SELECT 1 FROM purchase_payment_items p WHERE p.invoice_id=i.id);
CREATE OR REPLACE VIEW expense_payment_events AS
 SELECT p.id AS event_id,p.occurrence_id,p.payment_amount,p.payment_date AS paid_date,p.bank_account_id,'EXPENSE_PAYMENT_ITEM'::text AS reconciliation_type FROM expense_payment_items p
 UNION ALL SELECT o.id,o.id,COALESCE(o.payment_amount,o.amount),o.paid_date,o.bank_account_id,'EXPENSE'::text FROM operational_expense_occurrences o
 WHERE o.status='Pagado' AND o.paid_date IS NOT NULL AND NOT EXISTS(SELECT 1 FROM expense_payment_items p WHERE p.occurrence_id=o.id);
DROP TABLE IF EXISTS purchase_payment_openings;
DROP TABLE IF EXISTS expense_payment_openings;
