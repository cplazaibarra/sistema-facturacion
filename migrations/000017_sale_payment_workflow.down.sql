DROP INDEX IF EXISTS uq_sale_payment_items_idempotency;

ALTER TABLE sale_payment_items
    DROP COLUMN IF EXISTS idempotency_key,
    DROP COLUMN IF EXISTS payment_notes,
    DROP COLUMN IF EXISTS account_number_snapshot,
    DROP COLUMN IF EXISTS bank_name_snapshot,
    DROP COLUMN IF EXISTS registered_at,
    DROP COLUMN IF EXISTS registered_by,
    DROP COLUMN IF EXISTS payment_method;
