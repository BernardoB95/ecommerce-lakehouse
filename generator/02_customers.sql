CREATE TABLE app.customers (
    customer_id             TEXT NOT NULL,
    customer_unique_id      TEXT PRIMARY KEY,
    customer_zip_code       TEXT NOT NULL,
    customer_city           TEXT NOT NULL,
    customer_state          TEXT NOT NULL,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);