-- 000006_lot_genealogy.down.sql
-- Revertir Fase 5B: Modelo de Genealogía e Identidad Inmutable de Lotes

DROP INDEX IF EXISTS idx_im_lot_id;
ALTER TABLE inventory_movements DROP COLUMN IF EXISTS lot_id;

DROP INDEX IF EXISTS idx_iei_lot_id;
ALTER TABLE inventory_entry_items DROP COLUMN IF EXISTS lot_id;

DROP INDEX IF EXISTS idx_slm_lot_id;
ALTER TABLE sale_lot_movements DROP COLUMN IF EXISTS lot_id;

DROP INDEX IF EXISTS idx_lot_stock_lot_id;
ALTER TABLE lot_stock DROP COLUMN IF EXISTS lot_id;

DROP TABLE IF EXISTS production_lot_outputs CASCADE;
DROP TABLE IF EXISTS production_lot_consumptions CASCADE;
DROP TABLE IF EXISTS lots CASCADE;
