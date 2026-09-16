-- Migración 000002: Proveedores, Productos, Ventas, Pagos y Compras

CREATE TABLE IF NOT EXISTS suppliers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    website TEXT,
    created_at TEXT NOT NULL,
    rut TEXT,
    dv TEXT,
    razon_social TEXT,
    giro TEXT,
    direccion TEXT,
    comuna TEXT,
    ciudad TEXT,
    email TEXT,
    phone TEXT,
    tipo_compra TEXT
);

CREATE TABLE IF NOT EXISTS supplier_contacts (
    id SERIAL PRIMARY KEY,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    position TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    photo_url TEXT,
    barcode TEXT,
    internal_code TEXT,
    category TEXT,
    expiry_date TEXT,
    width_cm DOUBLE PRECISION,
    height_cm DOUBLE PRECISION,
    depth_cm DOUBLE PRECISION,
    weight_kg DOUBLE PRECISION,
    product_type TEXT DEFAULT 'Final',
    cost DOUBLE PRECISION DEFAULT 0.0,
    is_deleted BOOLEAN DEFAULT FALSE,
    requires_lot BOOLEAN DEFAULT FALSE,
    subcategory_material TEXT,
    line_variety TEXT,
    format_capacity TEXT,
    associated_kg DOUBLE PRECISION,
    unit_of_measure TEXT,
    min_stock DOUBLE PRECISION DEFAULT 0,
    status TEXT DEFAULT 'Activo',
    notes TEXT,
    attachment_url TEXT,
    line TEXT,
    variety TEXT,
    bom_recipe TEXT,
    labeling TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product_suppliers (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    UNIQUE(product_id, supplier_id)
);

CREATE TABLE IF NOT EXISTS sales (
    id SERIAL PRIMARY KEY,
    sale_number TEXT NOT NULL UNIQUE,
    customer_name TEXT NOT NULL,
    customer_email TEXT,
    customer_initials TEXT,
    sale_date TEXT NOT NULL,
    sale_time TEXT NOT NULL,
    products_json TEXT NOT NULL,
    total_amount DOUBLE PRECISION NOT NULL,
    status TEXT NOT NULL,
    seller_name TEXT NOT NULL,
    seller_initials TEXT,
    payment_method TEXT,
    payment_status TEXT,
    delivery_status TEXT,
    notes TEXT,
    quotation_status VARCHAR(50) DEFAULT 'Activa',
    win_probability INTEGER DEFAULT 50,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sales_entries (
    id SERIAL PRIMARY KEY,
    sku TEXT NOT NULL,
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price DOUBLE PRECISION NOT NULL,
    total_price DOUBLE PRECISION NOT NULL,
    sale_date TEXT NOT NULL,
    delivery_date TEXT,
    payment_status TEXT NOT NULL,
    delivery_status TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    seller_name TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sale_payments (
    id SERIAL PRIMARY KEY,
    sale_id INTEGER NOT NULL UNIQUE REFERENCES sales(id),
    invoice_number TEXT,
    invoice_amount DOUBLE PRECISION,
    invoice_due_date TEXT,
    invoice_file TEXT,
    payment_proof_file TEXT,
    payment_amount DOUBLE PRECISION,
    payment_date TEXT,
    seller_uploaded_at TEXT,
    payment_uploaded_at TEXT,
    accounting_approved INTEGER DEFAULT 0,
    accounting_approved_by TEXT,
    accounting_approved_at TEXT,
    accounting_comment TEXT,
    status TEXT NOT NULL DEFAULT 'Factura pendiente',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sale_payment_items (
    id SERIAL PRIMARY KEY,
    sale_id INTEGER NOT NULL REFERENCES sales(id),
    payment_amount DOUBLE PRECISION NOT NULL,
    payment_date TEXT,
    payment_proof_file TEXT,
    created_at TEXT NOT NULL,
    accounting_approved INTEGER DEFAULT 0,
    accounting_approved_by TEXT,
    accounting_approved_at TEXT,
    accounting_comment TEXT,
    bank_account_id INTEGER REFERENCES bank_accounts(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS sales_status_history (
    id SERIAL PRIMARY KEY,
    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    user_name TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    comment TEXT
);

CREATE TABLE IF NOT EXISTS sales_payment_history (
    id SERIAL PRIMARY KEY,
    sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    user_name TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    details TEXT
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id SERIAL PRIMARY KEY,
    oc_number TEXT NOT NULL UNIQUE,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
    order_date TEXT NOT NULL,
    status TEXT NOT NULL,
    total_amount DOUBLE PRECISION NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    payment_method TEXT DEFAULT 'Efectivo'
);

CREATE TABLE IF NOT EXISTS purchase_order_items (
    id SERIAL PRIMARY KEY,
    purchase_order_id INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity_ordered INTEGER NOT NULL,
    quantity_received INTEGER DEFAULT 0,
    unit_price DOUBLE PRECISION NOT NULL,
    total_price DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS purchase_invoices (
    id SERIAL PRIMARY KEY,
    inventory_entry_id INTEGER,
    purchase_order_id INTEGER REFERENCES purchase_orders(id) ON DELETE SET NULL,
    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE RESTRICT,
    invoice_number TEXT NOT NULL DEFAULT '',
    invoice_amount DOUBLE PRECISION DEFAULT 0,
    invoice_date TEXT DEFAULT '',
    due_date TEXT DEFAULT '',
    document_file TEXT,
    payment_status TEXT DEFAULT 'Pendiente',
    payment_date TEXT,
    payment_amount DOUBLE PRECISION,
    payment_method TEXT,
    payment_proof_file TEXT,
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (now())::text,
    bank_account_id INTEGER REFERENCES bank_accounts(id) ON DELETE SET NULL
);
