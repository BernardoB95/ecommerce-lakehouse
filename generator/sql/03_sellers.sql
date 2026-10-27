CREATE TABLE app.sellers (
    seller_id               TEXT PRIMARY KEY,
    seller_zip_code_prefix  TEXT NOT NULL,
    seller_city             TEXT NOT NULL,
    seller_state            TEXT NOT NULL,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);