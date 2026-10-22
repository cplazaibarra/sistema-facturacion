-- Migración 000023 Down: Módulo de Deudas Financieras

DROP TABLE IF EXISTS debt_audit CASCADE;
DROP TABLE IF EXISTS debt_payments CASCADE;
DROP TABLE IF EXISTS debt_installments CASCADE;
DROP TABLE IF EXISTS debts CASCADE;
DROP TABLE IF EXISTS debt_types CASCADE;
