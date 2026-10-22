-- Migración 000009 DOWN: Revertir restricción e índices de estado Borrador

DROP INDEX IF EXISTS idx_production_orders_status;

ALTER TABLE production_orders DROP CONSTRAINT IF EXISTS chk_production_orders_status;
