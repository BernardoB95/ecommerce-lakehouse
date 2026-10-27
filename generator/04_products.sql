CREATE TABLE app.products (
    product_id                  TEXT PRIMARY KEY,
    product_category_name       TEXT,
    product_name_length         SMALLINT,
    product_description_length  SMALLINT,
    product_photos_qty          SMALLINT,
    product_weight_g            NUMERIC,           
    product_length_cm           NUMERIC,
    product_height_cm           NUMERIC,
    product_width_cm            NUMERIC,
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
)