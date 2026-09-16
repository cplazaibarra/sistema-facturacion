-- 000006_lot_genealogy.up.sql
-- Fase 5B: Modelo de Genealogía e Identidad Inmutable de Lotes

-- 1. Tabla Maestra de Lotes con identidad inmutable
CREATE TABLE IF NOT EXISTS lots (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    lot_number TEXT NOT NULL,
    lot_type TEXT NOT NULL DEFAULT 'RAW_MATERIAL' CHECK (lot_type IN ('RAW_MATERIAL', 'SEMI_FINISHED', 'FINISHED_PRODUCT', 'SUPPLY', 'OTHER')),
    origin_type TEXT NOT NULL DEFAULT 'PURCHASE' CHECK (origin_type IN ('PURCHASE', 'PRODUCTION', 'INITIAL_MIGRATION', 'ADJUSTMENT')),
    origin_id INTEGER,
    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE RESTRICT,
    purchase_order_id INTEGER REFERENCES purchase_orders(id) ON DELETE RESTRICT,
    inventory_entry_id INTEGER REFERENCES inventory_entries(id) ON DELETE RESTRICT,
    production_order_id INTEGER REFERENCES production_orders(id) ON DELETE RESTRICT,
    initial_quantity DOUBLE PRECISION NOT NULL DEFAULT 0.0 CHECK (initial_quantity >= 0),
    created_at TEXT NOT NULL,
    expiry_date TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'DEPLETED', 'QUARANTINE', 'RECALLED', 'EXPIRED')),
    warehouse TEXT NOT NULL DEFAULT 'Principal',
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_lots_product_lot ON lots(product_id, lot_number);
CREATE INDEX IF NOT EXISTS idx_lots_lot_number ON lots(lot_number);
CREATE INDEX IF NOT EXISTS idx_lots_origin ON lots(origin_type, origin_id);
CREATE INDEX IF NOT EXISTS idx_lots_po ON lots(purchase_order_id);
CREATE INDEX IF NOT EXISTS idx_lots_entry ON lots(inventory_entry_id);
CREATE INDEX IF NOT EXISTS idx_lots_ot ON lots(production_order_id);

-- 2. Consumos de lotes exactos en órdenes de producción (Genealogía Insumos -> OT)
CREATE TABLE IF NOT EXISTS production_lot_consumptions (
    id SERIAL PRIMARY KEY,
    production_order_id INTEGER NOT NULL REFERENCES production_orders(id) ON DELETE RESTRICT,
    input_product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    input_lot_id INTEGER NOT NULL REFERENCES lots(id) ON DELETE RESTRICT,
    quantity_consumed DOUBLE PRECISION NOT NULL CHECK (quantity_consumed > 0),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_plc_ot ON production_lot_consumptions(production_order_id);
CREATE INDEX IF NOT EXISTS idx_plc_lot ON production_lot_consumptions(input_lot_id);
CREATE INDEX IF NOT EXISTS idx_plc_product ON production_lot_consumptions(input_product_id);

-- 3. Productos / lotes generados por órdenes de producción (Genealogía OT -> Producto Terminado)
CREATE TABLE IF NOT EXISTS production_lot_outputs (
    id SERIAL PRIMARY KEY,
    production_order_id INTEGER NOT NULL REFERENCES production_orders(id) ON DELETE RESTRICT,
    output_product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    output_lot_id INTEGER NOT NULL REFERENCES lots(id) ON DELETE RESTRICT,
    quantity_produced DOUBLE PRECISION NOT NULL CHECK (quantity_produced > 0),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_plo_ot ON production_lot_outputs(production_order_id);
CREATE INDEX IF NOT EXISTS idx_plo_lot ON production_lot_outputs(output_lot_id);
CREATE INDEX IF NOT EXISTS idx_plo_product ON production_lot_outputs(output_product_id);

-- 4. Vinculación con tablas operacionales existentes
ALTER TABLE lot_stock ADD COLUMN IF NOT EXISTS lot_id INTEGER REFERENCES lots(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS idx_lot_stock_lot_id ON lot_stock(lot_id);

ALTER TABLE sale_lot_movements ADD COLUMN IF NOT EXISTS lot_id INTEGER REFERENCES lots(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS idx_slm_lot_id ON sale_lot_movements(lot_id);

ALTER TABLE inventory_entry_items ADD COLUMN IF NOT EXISTS lot_id INTEGER REFERENCES lots(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS idx_iei_lot_id ON inventory_entry_items(lot_id);

ALTER TABLE inventory_movements ADD COLUMN IF NOT EXISTS lot_id INTEGER REFERENCES lots(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS idx_im_lot_id ON inventory_movements(lot_id);
