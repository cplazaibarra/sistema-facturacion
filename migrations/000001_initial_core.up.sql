-- Migración 000001: Tablas nucleares del sistema (Roles, Usuarios, Configuración y Clientes)

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    permissions TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role_id INTEGER NOT NULL REFERENCES roles(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS page_data (
    key TEXT PRIMARY KEY,
    json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bank_accounts (
    id SERIAL PRIMARY KEY,
    bank_name VARCHAR(100) NOT NULL,
    account_number VARCHAR(100) NOT NULL UNIQUE,
    account_type VARCHAR(100) NOT NULL,
    holder_name VARCHAR(255) NOT NULL,
    holder_rut VARCHAR(50),
    email VARCHAR(255),
    status VARCHAR(50) DEFAULT 'Activa',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS client_categories (
    email TEXT PRIMARY KEY,
    category_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
    rut VARCHAR(20),
    dv VARCHAR(5),
    razon_social VARCHAR(255) NOT NULL,
    tipo_compra VARCHAR(100) DEFAULT 'Del Giro',
    direccion TEXT,
    comuna VARCHAR(100),
    ciudad VARCHAR(100),
    giro VARCHAR(255),
    contacto VARCHAR(255),
    rut_solicita VARCHAR(20),
    dv_solicita VARCHAR(5),
    email VARCHAR(255),
    phone VARCHAR(50),
    category_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_unique_rut ON clients(rut) WHERE rut IS NOT NULL AND rut != '';

CREATE TABLE IF NOT EXISTS product_margins (
    product_sku TEXT PRIMARY KEY,
    base_margin DOUBLE PRECISION DEFAULT 20.0,
    category_margins JSONB DEFAULT '{}'::jsonb
);
