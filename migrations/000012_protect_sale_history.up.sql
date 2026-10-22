-- Migración 000012: Asegurar ON DELETE RESTRICT en FK sale_items -> sales
-- Garantiza que los registros históricos y snapshots contables de ventas no puedan eliminarse en cascada

ALTER TABLE sale_items
DROP CONSTRAINT IF EXISTS sale_items_sale_id_fkey;

ALTER TABLE sale_items
ADD CONSTRAINT sale_items_sale_id_fkey
FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE RESTRICT;
