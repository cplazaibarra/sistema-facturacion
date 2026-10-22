-- Migración 000007: Consumo y Costo de Cajas / Embalaje en Ventas
CREATE TABLE IF NOT EXISTS sale_packaging_items (
    id SERIAL PRIMARY KEY,
    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE RESTRICT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_cost DOUBLE PRECISION NOT NULL DEFAULT 0.0 CHECK (unit_cost >= 0),
    total_cost DOUBLE PRECISION NOT NULL DEFAULT 0.0 CHECK (total_cost >= 0),
    inventory_movement_id INTEGER REFERENCES inventory_movements(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    created_by TEXT DEFAULT 'Sistema'
);

CREATE INDEX IF NOT EXISTS idx_sale_packaging_sale_id ON sale_packaging_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_packaging_product_id ON sale_packaging_items(product_id);
