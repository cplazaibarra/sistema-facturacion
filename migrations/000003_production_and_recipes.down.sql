-- Reversión de Migración 000003
DROP TABLE IF EXISTS production_order_additional_items CASCADE;
DROP TABLE IF EXISTS production_order_items CASCADE;
DROP TABLE IF EXISTS production_orders CASCADE;
DROP TABLE IF EXISTS product_recipe_items CASCADE;
DROP TABLE IF EXISTS product_recipes CASCADE;
