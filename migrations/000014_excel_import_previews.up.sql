CREATE TABLE IF NOT EXISTS excel_import_previews (
    import_id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    items JSONB NOT NULL,
    summary JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_excel_import_previews_user ON excel_import_previews(user_id);
CREATE INDEX IF NOT EXISTS idx_excel_import_previews_expires ON excel_import_previews(expires_at);
