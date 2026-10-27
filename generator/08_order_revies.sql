CREATE TABLE app.order_reviews (
      review_id                TEXT NOT NULL,
      order_id                 TEXT NOT NULL REFERENCES app.orders(order_id),
      review_score             SMALLINT NOT NULL CHECK (review_score BETWEEN 1 AND 5),
      review_comment_title     TEXT,
      review_comment_message   TEXT,
      review_creation_date     TIMESTAMP,
      review_answer_timestamp  TIMESTAMP,
      updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY              (review_id, order_id)
  );
  
  CREATE INDEX ON app.order_reviews (order_id);