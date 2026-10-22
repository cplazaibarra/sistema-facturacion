-- Migración 000010 Down
DROP INDEX IF EXISTS idx_production_orders_schedule_order;
DROP INDEX IF EXISTS idx_production_orders_scheduled_date;

ALTER TABLE production_orders
DROP COLUMN IF EXISTS schedule_order,
DROP COLUMN IF EXISTS scheduled_date;
