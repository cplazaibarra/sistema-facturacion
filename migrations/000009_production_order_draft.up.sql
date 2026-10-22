-- Migración 000009: Estado Borrador para Órdenes de Trabajo (production_orders)

-- Validar restricción CHECK de estados en production_orders
DO $$
BEGIN
    -- Si existe una restricción check previa de status, eliminarla
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_production_orders_status'
    ) THEN
        ALTER TABLE production_orders DROP CONSTRAINT chk_production_orders_status;
    END IF;

    -- Agregar la restricción formal con 'Borrador' incluido
    ALTER TABLE production_orders
    ADD CONSTRAINT chk_production_orders_status
    CHECK (status IN ('Borrador', 'Solicitada', 'Aprobada', 'En Proceso', 'Finalizada', 'Cancelada'));
END $$;

-- Índice para optimizar búsquedas y filtros por estado
CREATE INDEX IF NOT EXISTS idx_production_orders_status ON production_orders(status);
