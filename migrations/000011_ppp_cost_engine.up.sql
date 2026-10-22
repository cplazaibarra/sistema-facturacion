-- Migración 000011: Unificación del Motor de Costos PPP y Snapshot Histórico de Ventas
-- Crea tabla formal sale_items y campo para control de reversas idempotentes en sales

CREATE TABLE IF NOT EXISTS sale_items (
    id SERIAL PRIMARY KEY,
    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE RESTRICT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price DOUBLE PRECISION NOT NULL DEFAULT 0.0 CHECK (unit_price >= 0),
    unit_cost_at_sale DOUBLE PRECISION NULL CHECK (unit_cost_at_sale IS NULL OR unit_cost_at_sale >= 0),
    total_cost_at_sale DOUBLE PRECISION NULL CHECK (total_cost_at_sale IS NULL OR total_cost_at_sale >= 0),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sale_items_sale_id ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_product_id ON sale_items(product_id);

ALTER TABLE sales
ADD COLUMN IF NOT EXISTS reversal_applied BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_sales_reversal_applied ON sales(reversal_applied);
