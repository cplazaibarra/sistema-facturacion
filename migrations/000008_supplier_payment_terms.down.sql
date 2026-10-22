-- Reversión de Migración 000008
ALTER TABLE purchase_orders DROP CONSTRAINT IF EXISTS chk_purchase_orders_payment_terms;
ALTER TABLE purchase_orders DROP COLUMN IF EXISTS payment_terms;

ALTER TABLE suppliers DROP CONSTRAINT IF EXISTS chk_suppliers_default_payment_terms;
ALTER TABLE suppliers DROP COLUMN IF EXISTS default_payment_terms;
