-- Migración 000004: Bodega, Recepciones, Lotes, Kardex y Secuencias Transaccionales

CREATE TABLE IF NOT EXISTS inventory_entries (
    id SERIAL PRIMARY KEY,
    entry_date TEXT NOT NULL,
    order_number TEXT NOT NULL,
    purchase_order_id INTEGER REFERENCES purchase_orders(id) ON DELETE SET NULL,
    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE RESTRICT,
    warehouse TEXT NOT NULL,
    notes TEXT,
    total_amount DOUBLE PRECISION NOT NULL,
    created_at TEXT NOT NULL,
    document_type TEXT DEFAULT 'guia_despacho',
    document_number TEXT DEFAULT '',
    document_file TEXT
);

-- Agregar relación de foreign key diferida en purchase_invoices ahora que inventory_entries existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'purchase_invoices_inventory_entry_id_fkey'
    ) THEN
        ALTER TABLE purchase_invoices 
        ADD CONSTRAINT purchase_invoices_inventory_entry_id_fkey 
        FOREIGN KEY (inventory_entry_id) REFERENCES inventory_entries(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS inventory_entry_items (
    id SERIAL PRIMARY KEY,
    inventory_entry_id INTEGER NOT NULL REFERENCES inventory_entries(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL,
    unit_price DOUBLE PRECISION NOT NULL,
    total DOUBLE PRECISION NOT NULL,
    lot_number TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS lot_stock (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    lot_number TEXT NOT NULL,
    entry_id INTEGER REFERENCES inventory_entries(id) ON DELETE SET NULL,
    entry_date TEXT NOT NULL DEFAULT '',
    initial_qty INTEGER NOT NULL DEFAULT 0,
    available_qty INTEGER NOT NULL DEFAULT 0,
    warehouse TEXT DEFAULT 'Principal',
    UNIQUE(product_id, lot_number)
);

CREATE TABLE IF NOT EXISTS sale_lot_movements (
    id SERIAL PRIMARY KEY,
    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    lot_number TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    moved_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory_movements (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    movement_type TEXT NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    unit_cost DOUBLE PRECISION DEFAULT 0.0,
    lot_number TEXT,
    warehouse TEXT DEFAULT 'Almacén Principal',
    reference_type TEXT,
    reference_id INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL,
    created_by TEXT DEFAULT 'Sistema'
);

CREATE INDEX IF NOT EXISTS idx_inv_mov_product_id ON inventory_movements(product_id);
CREATE INDEX IF NOT EXISTS idx_inv_mov_lot_number ON inventory_movements(lot_number);
CREATE INDEX IF NOT EXISTS idx_inv_mov_reference ON inventory_movements(reference_type, reference_id);

-- Secuencias correlativas atómicas (Fase 3)
CREATE SEQUENCE IF NOT EXISTS purchase_order_number_seq;
CREATE SEQUENCE IF NOT EXISTS sales_number_seq;
CREATE SEQUENCE IF NOT EXISTS production_order_number_seq;

SELECT setval('purchase_order_number_seq', GREATEST(COALESCE((SELECT MAX(id) FROM purchase_orders), 0), 1), true);
SELECT setval('sales_number_seq', GREATEST(COALESCE((SELECT MAX(id) FROM sales), 0), 1), true);
SELECT setval('production_order_number_seq', GREATEST(COALESCE((SELECT MAX(id) FROM production_orders), 0), 1), true);
