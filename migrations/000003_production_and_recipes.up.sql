-- Migración 000003: Recetas de Productos y Órdenes de Producción (Trabajo)

CREATE TABLE IF NOT EXISTS product_recipes (
    id SERIAL PRIMARY KEY,
    final_product_id INTEGER NOT NULL UNIQUE REFERENCES products(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    recipe_code TEXT
);

CREATE TABLE IF NOT EXISTS product_recipe_items (
    id SERIAL PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES product_recipes(id) ON DELETE CASCADE,
    input_product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity_required DOUBLE PRECISION NOT NULL,
    unit TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS production_orders (
    id SERIAL PRIMARY KEY,
    ot_number TEXT NOT NULL UNIQUE,
    final_product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL,
    status TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    completed_at TEXT,
    unit_cost DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS production_order_items (
    id SERIAL PRIMARY KEY,
    production_order_id INTEGER NOT NULL REFERENCES production_orders(id) ON DELETE CASCADE,
    input_product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity_required DOUBLE PRECISION NOT NULL,
    unit_cost DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS production_order_additional_items (
    id SERIAL PRIMARY KEY,
    production_order_id INTEGER NOT NULL REFERENCES production_orders(id) ON DELETE CASCADE,
    input_product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity DOUBLE PRECISION NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    unit_cost DOUBLE PRECISION
);
