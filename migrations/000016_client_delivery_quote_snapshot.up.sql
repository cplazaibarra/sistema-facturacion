-- Datos comerciales adicionales del cliente y snapshot histórico de cotizaciones.
ALTER TABLE clients
    ADD COLUMN IF NOT EXISTS delivery_address TEXT;

ALTER TABLE sales
    ADD COLUMN IF NOT EXISTS customer_delivery_address TEXT,
    ADD COLUMN IF NOT EXISTS customer_category_snapshot TEXT;
