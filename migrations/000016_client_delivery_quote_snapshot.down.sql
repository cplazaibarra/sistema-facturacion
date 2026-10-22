ALTER TABLE sales
    DROP COLUMN IF EXISTS customer_category_snapshot,
    DROP COLUMN IF EXISTS customer_delivery_address;

ALTER TABLE clients
    DROP COLUMN IF EXISTS delivery_address;
