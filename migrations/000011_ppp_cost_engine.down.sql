-- Reversión de Migración 000011
DROP TABLE IF EXISTS sale_items CASCADE;
ALTER TABLE sales DROP COLUMN IF EXISTS reversal_applied;
