CREATE TABLE app.orders (
    order_id                        TEXT PRIMARY KEY,
    customer_id                     TEXT NOT NULL REFERENCES        app.customers(customer_id),
    order_status                    TEXT NOT NULL,
    order_purchase_timestamp        TIMESTAMP,
    order_approved_at               TIMESTAMP,
    order_delivered_carrier_date    TIMESTAMP,
    order_delivered_customer_date   TIMESTAMP,
    order_estimated_delivery_date   TIMESTAMP,
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);