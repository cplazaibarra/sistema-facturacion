-- Migración 000008: Forma de pago predeterminada de proveedores y términos de pago en órdenes de compra

-- 1. Agregar default_payment_terms a suppliers
ALTER TABLE suppliers
ADD COLUMN IF NOT EXISTS default_payment_terms VARCHAR(20) NOT NULL DEFAULT 'NET_30';

-- Validar restricción check en suppliers
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_suppliers_default_payment_terms'
    ) THEN
        ALTER TABLE suppliers
        ADD CONSTRAINT chk_suppliers_default_payment_terms
        CHECK (default_payment_terms IN ('CASH', 'NET_30', 'NET_60'));
    END IF;
END $$;

-- 2. Agregar payment_terms a purchase_orders
ALTER TABLE purchase_orders
ADD COLUMN IF NOT EXISTS payment_terms VARCHAR(20) NOT NULL DEFAULT 'NET_30';

-- Validar restricción check en purchase_orders
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_purchase_orders_payment_terms'
    ) THEN
        ALTER TABLE purchase_orders
        ADD CONSTRAINT chk_purchase_orders_payment_terms
        CHECK (payment_terms IN ('CASH', 'NET_30', 'NET_60'));
    END IF;
END $$;

-- 3. Documentación y aseguramiento para datos históricos
-- Todos los proveedores y órdenes de compra históricas quedan estandarizados inicialmente con 'NET_30'
UPDATE suppliers SET default_payment_terms = 'NET_30' WHERE default_payment_terms IS NULL OR default_payment_terms NOT IN ('CASH', 'NET_30', 'NET_60');
UPDATE purchase_orders SET payment_terms = 'NET_30' WHERE payment_terms IS NULL OR payment_terms NOT IN ('CASH', 'NET_30', 'NET_60');
