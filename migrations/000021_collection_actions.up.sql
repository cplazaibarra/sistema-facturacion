-- Migración 000021: Tabla de acciones y gestiones de cobranza (collection_actions)

CREATE TABLE IF NOT EXISTS collection_actions (
    id SERIAL PRIMARY KEY,
    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    action_type VARCHAR(50) NOT NULL,
    action_date VARCHAR(10) NOT NULL,
    action_time VARCHAR(8) NOT NULL,
    contact_name VARCHAR(255),
    result TEXT NOT NULL,
    next_action TEXT,
    next_action_date VARCHAR(10),
    payment_commitment_date VARCHAR(10),
    payment_commitment_amount DOUBLE PRECISION,
    notes TEXT,
    user_name VARCHAR(150) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_collection_actions_sale_id ON collection_actions(sale_id);
CREATE INDEX IF NOT EXISTS idx_collection_actions_action_date ON collection_actions(action_date);
CREATE INDEX IF NOT EXISTS idx_collection_actions_next_action_date ON collection_actions(next_action_date);
