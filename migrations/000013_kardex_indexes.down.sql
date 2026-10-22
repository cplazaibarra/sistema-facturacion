-- Migración 000013 (Rollback): Eliminar índice compuesto de Kardex
DROP INDEX IF EXISTS idx_inv_mov_product_created_id;
