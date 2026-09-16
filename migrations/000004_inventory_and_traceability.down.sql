-- Reversión de Migración 000004
DROP SEQUENCE IF EXISTS production_order_number_seq CASCADE;
DROP SEQUENCE IF EXISTS sales_number_seq CASCADE;
DROP SEQUENCE IF EXISTS purchase_order_number_seq CASCADE;
DROP TABLE IF EXISTS inventory_movements CASCADE;
DROP TABLE IF EXISTS sale_lot_movements CASCADE;
DROP TABLE IF EXISTS lot_stock CASCADE;
DROP TABLE IF EXISTS inventory_entry_items CASCADE;
ALTER TABLE IF EXISTS purchase_invoices DROP CONSTRAINT IF EXISTS purchase_invoices_inventory_entry_id_fkey;
DROP TABLE IF EXISTS inventory_entries CASCADE;
