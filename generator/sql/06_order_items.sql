CREATE TABLE app.order_items (
      order_id             TEXT NOT NULL REFERENCES app.orders(order_id),
      order_item_id        SMALLINT NOT NULL,
      product_id           TEXT NOT NULL REFERENCES app.products(product_id),
      seller_id            TEXT NOT NULL REFERENCES app.sellers(seller_id),
      shipping_limit_date  TIMESTAMP,
      price                NUMERIC(10,2) NOT NULL CHECK (price >= 0),
      freight_value        NUMERIC(10,2) NOT NULL CHECK (freight_value >= 0),
      updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY           (order_id, order_item_id)
  );
  
  CREATE INDEX ON app.order_items (product_id);
  CREATE INDEX ON app.order_items (seller_id);