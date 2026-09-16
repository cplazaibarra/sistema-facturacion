-- Migración 000005: Restricciones de Integridad (CHECK, FK faltantes) e Índices de Rendimiento

-- 1. Restricciones CHECK para Integridad Invariante
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_lot_stock_available_qty') THEN
        ALTER TABLE lot_stock ADD CONSTRAINT chk_lot_stock_available_qty CHECK (available_qty >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_lot_stock_initial_qty') THEN
        ALTER TABLE lot_stock ADD CONSTRAINT chk_lot_stock_initial_qty CHECK (initial_qty >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_inv_mov_quantity') THEN
        ALTER TABLE inventory_movements ADD CONSTRAINT chk_inv_mov_quantity CHECK (quantity <> 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_po_items_qty_ordered') THEN
        ALTER TABLE purchase_order_items ADD CONSTRAINT chk_po_items_qty_ordered CHECK (quantity_ordered > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_inv_entry_items_qty') THEN
        ALTER TABLE inventory_entry_items ADD CONSTRAINT chk_inv_entry_items_qty CHECK (quantity > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_sale_lot_mov_qty') THEN
        ALTER TABLE sale_lot_movements ADD CONSTRAINT chk_sale_lot_mov_qty CHECK (quantity > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_recipe_items_qty') THEN
        ALTER TABLE product_recipe_items ADD CONSTRAINT chk_recipe_items_qty CHECK (quantity_required >= 0);
    END IF;
END $$;

-- 2. Foreign Key de Integridad en purchase_invoices(supplier_id)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'purchase_invoices_supplier_id_fkey'
    ) THEN
        ALTER TABLE purchase_invoices 
        ADD CONSTRAINT purchase_invoices_supplier_id_fkey 
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- 3. Índices de Cobertura en Claves Foráneas y Búsquedas Frecuentes
CREATE INDEX IF NOT EXISTS idx_users_role_id ON users(role_id);
CREATE INDEX IF NOT EXISTS idx_supplier_contacts_supplier_id ON supplier_contacts(supplier_id);
CREATE INDEX IF NOT EXISTS idx_product_suppliers_supplier_id ON product_suppliers(supplier_id);

CREATE INDEX IF NOT EXISTS idx_sales_sale_date ON sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_customer_name ON sales(customer_name);
CREATE INDEX IF NOT EXISTS idx_sales_status ON sales(status);

CREATE INDEX IF NOT EXISTS idx_sale_payment_items_sale_id ON sale_payment_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_payment_items_bank_account_id ON sale_payment_items(bank_account_id);
CREATE INDEX IF NOT EXISTS idx_sales_status_history_sale_id ON sales_status_history(sale_id);
CREATE INDEX IF NOT EXISTS idx_sales_payment_history_sale_id ON sales_payment_history(sale_id);

CREATE INDEX IF NOT EXISTS idx_purchase_orders_supplier_id ON purchase_orders(supplier_id);
CREATE INDEX IF NOT EXISTS idx_purchase_orders_created_by ON purchase_orders(created_by);
CREATE INDEX IF NOT EXISTS idx_purchase_orders_approved_by ON purchase_orders(approved_by);
CREATE INDEX IF NOT EXISTS idx_purchase_orders_status ON purchase_orders(status);

CREATE INDEX IF NOT EXISTS idx_purchase_order_items_po_id ON purchase_order_items(purchase_order_id);
CREATE INDEX IF NOT EXISTS idx_purchase_order_items_product_id ON purchase_order_items(product_id);

CREATE INDEX IF NOT EXISTS idx_purchase_invoices_po_id ON purchase_invoices(purchase_order_id);
CREATE INDEX IF NOT EXISTS idx_purchase_invoices_supplier_id ON purchase_invoices(supplier_id);
CREATE INDEX IF NOT EXISTS idx_purchase_invoices_inventory_entry_id ON purchase_invoices(inventory_entry_id);
CREATE INDEX IF NOT EXISTS idx_purchase_invoices_bank_account_id ON purchase_invoices(bank_account_id);

CREATE INDEX IF NOT EXISTS idx_inventory_entries_po_id ON inventory_entries(purchase_order_id);
CREATE INDEX IF NOT EXISTS idx_inventory_entries_supplier_id ON inventory_entries(supplier_id);

CREATE INDEX IF NOT EXISTS idx_inventory_entry_items_entry_id ON inventory_entry_items(inventory_entry_id);
CREATE INDEX IF NOT EXISTS idx_inventory_entry_items_product_id ON inventory_entry_items(product_id);

CREATE INDEX IF NOT EXISTS idx_lot_stock_entry_id ON lot_stock(entry_id);
CREATE INDEX IF NOT EXISTS idx_sale_lot_movements_sale_id ON sale_lot_movements(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_lot_movements_product_id ON sale_lot_movements(product_id);

CREATE INDEX IF NOT EXISTS idx_product_recipe_items_recipe_id ON product_recipe_items(recipe_id);
CREATE INDEX IF NOT EXISTS idx_product_recipe_items_input_product_id ON product_recipe_items(input_product_id);

CREATE INDEX IF NOT EXISTS idx_production_orders_final_product_id ON production_orders(final_product_id);
CREATE INDEX IF NOT EXISTS idx_production_order_items_po_id ON production_order_items(production_order_id);
CREATE INDEX IF NOT EXISTS idx_production_order_items_input_product_id ON production_order_items(input_product_id);
CREATE INDEX IF NOT EXISTS idx_production_order_additional_items_po_id ON production_order_additional_items(production_order_id);
CREATE INDEX IF NOT EXISTS idx_production_order_additional_items_input_product_id ON production_order_additional_items(input_product_id);
