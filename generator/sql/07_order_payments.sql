 CREATE TABLE app.order_payments (
      order_id              TEXT NOT NULL REFERENCES app.orders(order_id),
      payment_sequential    SMALLINT NOT NULL,
      payment_type          TEXT NOT NULL,
      payment_installments  SMALLINT NOT NULL CHECK (payment_installments >= 0),
      payment_value         NUMERIC(10,2) NOT NULL CHECK (payment_value >= 0),
      currency              TEXT DEFAULT 'BRL',
      updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY           (order_id, payment_sequential)
  );