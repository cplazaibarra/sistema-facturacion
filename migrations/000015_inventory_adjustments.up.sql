-- Solicitudes de ajuste de inventario. El registro es inmutable una vez resuelto;
-- el movimiento oficial sólo se crea durante la aprobación.
CREATE TABLE IF NOT EXISTS inventory_adjustment_requests (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    warehouse TEXT NOT NULL DEFAULT 'Almacén Principal',
    stock_snapshot DOUBLE PRECISION NOT NULL CHECK (stock_snapshot >= 0),
    available_snapshot DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (available_snapshot >= 0),
    reserved_snapshot DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (reserved_snapshot >= 0),
    movement_watermark BIGINT NOT NULL DEFAULT 0 CHECK (movement_watermark >= 0),
    counted_quantity DOUBLE PRECISION NOT NULL CHECK (counted_quantity >= 0),
    difference DOUBLE PRECISION GENERATED ALWAYS AS (counted_quantity - stock_snapshot) STORED,
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    observation TEXT,
    requested_by INTEGER REFERENCES users(id) ON DELETE RESTRICT,
    requested_by_name TEXT NOT NULL DEFAULT 'Sistema',
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPLIED', 'REJECTED')),
    decided_by INTEGER REFERENCES users(id) ON DELETE RESTRICT,
    decided_by_name TEXT,
    decided_at TIMESTAMPTZ,
    approver_comment TEXT,
    movement_id INTEGER REFERENCES inventory_movements(id) ON DELETE RESTRICT,
    CONSTRAINT inventory_adjustment_other_observation
        CHECK (upper(reason) <> 'OTRO' OR length(trim(coalesce(observation, ''))) > 0),
    CONSTRAINT inventory_adjustment_decision_fields
        CHECK (status = 'PENDING' OR (decided_at IS NOT NULL AND decided_by_name IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_inv_adj_status ON inventory_adjustment_requests(status);
CREATE INDEX IF NOT EXISTS idx_inv_adj_product_warehouse ON inventory_adjustment_requests(product_id, warehouse);
CREATE INDEX IF NOT EXISTS idx_inv_adj_requested_at ON inventory_adjustment_requests(requested_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_inv_adj_movement ON inventory_adjustment_requests(movement_id)
    WHERE movement_id IS NOT NULL;

-- El mismo movimiento sólo puede ser generado una vez por solicitud, incluso si
-- dos requests de aprobación llegan simultáneamente.
CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_adjustment_movement_reference
    ON inventory_movements(reference_type, reference_id)
    WHERE reference_type = 'inventory_adjustment' AND reference_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS inventory_adjustment_audit (
    id BIGSERIAL PRIMARY KEY,
    adjustment_id INTEGER NOT NULL REFERENCES inventory_adjustment_requests(id) ON DELETE RESTRICT,
    action TEXT NOT NULL CHECK (action IN ('REQUESTED', 'APPLIED', 'REJECTED')),
    actor_id INTEGER REFERENCES users(id) ON DELETE RESTRICT,
    actor_name TEXT NOT NULL,
    detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_inv_adj_audit_adjustment ON inventory_adjustment_audit(adjustment_id, created_at);
