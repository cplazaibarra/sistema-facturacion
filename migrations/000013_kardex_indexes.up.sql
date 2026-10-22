-- Migración 000013: Índices compuestos optimizados para Kardex Valorizado y PPP
-- Acelera el ordenamiento cronológico determinístico por producto

CREATE INDEX IF NOT EXISTS idx_inv_mov_product_created_id
ON inventory_movements (product_id, created_at ASC, id ASC);
