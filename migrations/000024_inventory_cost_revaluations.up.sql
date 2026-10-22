-- Migración 000024: Mecanismo de Revaluación Histórica Inmutable de Movimientos de Inventario
-- Permite corregir valoraciones históricas erróneas sin modificar físicamente los registros originales
-- ni alterar cantidades físicas, saldos de lotes o movimientos en inventory_movements.

CREATE TABLE IF NOT EXISTS inventory_cost_revaluations (
    id SERIAL PRIMARY KEY,
    movement_id INTEGER NOT NULL REFERENCES inventory_movements(id) ON DELETE RESTRICT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    old_unit_cost NUMERIC(20, 6) NOT NULL,
    new_unit_cost NUMERIC(20, 6) NOT NULL,
    difference_unit_cost NUMERIC(20, 6) NOT NULL,
    total_value_difference NUMERIC(20, 6) NOT NULL,
    reason TEXT NOT NULL,
    reference_doc TEXT,
    created_by TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    parent_revaluation_id INTEGER REFERENCES inventory_cost_revaluations(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_inv_cost_reval_movement_id ON inventory_cost_revaluations(movement_id);
CREATE INDEX IF NOT EXISTS idx_inv_cost_reval_product_id ON inventory_cost_revaluations(product_id);
CREATE INDEX IF NOT EXISTS idx_inv_cost_reval_created_at ON inventory_cost_revaluations(created_at);
