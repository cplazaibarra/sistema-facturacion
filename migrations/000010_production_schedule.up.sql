-- Migración 000010: Programación y Calendario Semanal de Producción (production_orders)

ALTER TABLE production_orders
ADD COLUMN IF NOT EXISTS scheduled_date DATE NULL,
ADD COLUMN IF NOT EXISTS schedule_order INTEGER NULL;

-- Índices para búsquedas eficientes por fecha y ordenamiento diario
CREATE INDEX IF NOT EXISTS idx_production_orders_scheduled_date ON production_orders(scheduled_date);
CREATE INDEX IF NOT EXISTS idx_production_orders_schedule_order ON production_orders(scheduled_date, schedule_order);
