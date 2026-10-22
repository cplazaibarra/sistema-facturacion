-- Down migration 000022: Bank Reconciliation

DROP TABLE IF EXISTS bank_reconciliation_audit CASCADE;
DROP TABLE IF EXISTS bank_transactions CASCADE;
DROP TABLE IF EXISTS bank_transaction_imports CASCADE;
DROP TABLE IF EXISTS bank_transaction_categories CASCADE;
