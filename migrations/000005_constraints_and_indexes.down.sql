-- Reversión de Migración 000005: Eliminar índices creados y restricciones CHECK / FK

DROP INDEX IF EXISTS idx_production_order_additional_items_input_product_id;
DROP INDEX IF EXISTS idx_production_order_additional_items_po_id;
DROP INDEX IF EXISTS idx_production_order_items_input_product_id;
DROP INDEX IF EXISTS idx_production_order_items_po_id;
DROP INDEX IF EXISTS idx_production_orders_final_product_id;

DROP INDEX IF EXISTS idx_product_recipe_items_input_product_id;
DROP INDEX IF EXISTS idx_product_recipe_items_recipe_id;

DROP INDEX IF EXISTS idx_sale_lot_movements_product_id;
DROP INDEX IF EXISTS idx_sale_lot_movements_sale_id;
DROP INDEX IF EXISTS idx_lot_stock_entry_id;

DROP INDEX IF EXISTS idx_inventory_entry_items_product_id;
DROP INDEX IF EXISTS idx_inventory_entry_items_entry_id;

DROP INDEX IF EXISTS idx_inventory_entries_supplier_id;
DROP INDEX IF EXISTS idx_inventory_entries_po_id;

DROP INDEX IF EXISTS idx_purchase_invoices_bank_account_id;
DROP INDEX IF EXISTS idx_purchase_invoices_inventory_entry_id;
DROP INDEX IF EXISTS idx_purchase_invoices_supplier_id;
DROP INDEX IF EXISTS idx_purchase_invoices_po_id;

DROP INDEX IF EXISTS idx_purchase_order_items_product_id;
DROP INDEX IF EXISTS idx_purchase_order_items_po_id;

DROP INDEX IF EXISTS idx_purchase_orders_status;
DROP INDEX IF EXISTS idx_purchase_orders_approved_by;
DROP INDEX IF EXISTS idx_purchase_orders_created_by;
DROP INDEX IF EXISTS idx_purchase_orders_supplier_id;

DROP INDEX IF EXISTS idx_sales_payment_history_sale_id;
DROP INDEX IF EXISTS idx_sales_status_history_sale_id;
DROP INDEX IF EXISTS idx_sale_payment_items_bank_account_id;
DROP INDEX IF EXISTS idx_sale_payment_items_sale_id;

DROP INDEX IF EXISTS idx_sales_status;
DROP INDEX IF EXISTS idx_sales_customer_name;
DROP INDEX IF EXISTS idx_sales_sale_date;

DROP INDEX IF EXISTS idx_product_suppliers_supplier_id;
DROP INDEX IF EXISTS idx_supplier_contacts_supplier_id;
DROP INDEX IF EXISTS idx_users_role_id;

ALTER TABLE IF EXISTS purchase_invoices DROP CONSTRAINT IF EXISTS purchase_invoices_supplier_id_fkey;

ALTER TABLE IF EXISTS product_recipe_items DROP CONSTRAINT IF EXISTS chk_recipe_items_qty;
ALTER TABLE IF EXISTS sale_lot_movements DROP CONSTRAINT IF EXISTS chk_sale_lot_mov_qty;
ALTER TABLE IF EXISTS inventory_entry_items DROP CONSTRAINT IF EXISTS chk_inv_entry_items_qty;
ALTER TABLE IF EXISTS purchase_order_items DROP CONSTRAINT IF EXISTS chk_po_items_qty_ordered;
ALTER TABLE IF EXISTS inventory_movements DROP CONSTRAINT IF EXISTS chk_inv_mov_quantity;
ALTER TABLE IF EXISTS lot_stock DROP CONSTRAINT IF EXISTS chk_lot_stock_initial_qty;
ALTER TABLE IF EXISTS lot_stock DROP CONSTRAINT IF EXISTS chk_lot_stock_available_qty;
