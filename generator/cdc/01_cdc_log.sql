-- Trigger-based change capture for the app.* tables.
-- Apply AFTER load_olist.py, otherwise the bulk load is logged row by row.
-- Safe to run more than once.

CREATE TABLE IF NOT EXISTS app.cdc_log (
    change_id   BIGSERIAL PRIMARY KEY,
    table_name  TEXT NOT NULL,
    op          CHAR(1) NOT NULL CHECK (op IN ('I', 'U', 'D')),
    row_data    JSONB NOT NULL,         -- new row for I/U, last known row for D
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION app.capture_change() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        INSERT INTO app.cdc_log (table_name, op, row_data)
        VALUES (TG_TABLE_NAME, 'D', to_jsonb(OLD));
        RETURN OLD;
    END IF;

    INSERT INTO app.cdc_log (table_name, op, row_data)
    VALUES (TG_TABLE_NAME, LEFT(TG_OP, 1), to_jsonb(NEW));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- One trigger per source table (cdc_log itself is not tracked)
DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'customers', 'sellers', 'products', 'orders',
        'order_items', 'order_payments', 'order_reviews'
    ] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_%1$s_cdc ON app.%1$I', t);
        EXECUTE format(
            'CREATE TRIGGER trg_%1$s_cdc
             AFTER INSERT OR UPDATE OR DELETE ON app.%1$I
             FOR EACH ROW EXECUTE FUNCTION app.capture_change()', t);
    END LOOP;
END $$;
