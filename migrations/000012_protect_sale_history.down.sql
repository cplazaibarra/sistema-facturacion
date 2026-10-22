-- Rollback 000012
ALTER TABLE sale_items
DROP CONSTRAINT IF EXISTS sale_items_sale_id_fkey;

ALTER TABLE sale_items
ADD CONSTRAINT sale_items_sale_id_fkey
FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE RESTRICT;
