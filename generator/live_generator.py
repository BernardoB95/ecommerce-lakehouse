"""Simulate live shop activity against the app.* Postgres tables.

Run `load_olist.py` first: the generator picks customers, products and sellers
from the tables, so it does nothing useful on an empty database.
"""
import os
import random
import time
import unicodedata
import uuid
from datetime import datetime, timedelta

import psycopg
from dotenv import load_dotenv
from faker import Faker

load_dotenv()
fake = Faker("pt_BR")
DSN = f"postgresql://{os.environ['PG_USER']}:{os.environ['PG_PASSWORD']}@localhost:{os.environ['PG_PORT']}/shop"
MESS_RATE = float(os.getenv("MESS_RATE", 0.1))
CANCEL_RATE = float(os.getenv("CANCEL_RATE", 0.03))

# Happy path of an order, plus the timestamp column each step fills in
STATUS_FLOW = ["created", "approved", "invoiced", "processing", "shipped", "delivered"]
STATUS_TIMESTAMP = {
    "approved": "order_approved_at",
    "shipped": "order_delivered_carrier_date",
    "delivered": "order_delivered_customer_date",
}
PAYMENT_TYPES = ["credit_card", "boleto", "voucher", "debit_card"]
PAYMENT_WEIGHTS = [74, 19, 6, 1]


def new_id():
    return uuid.uuid4().hex  # matches Olist's 32-char ids


def messy_text(s):
    ops = [str.lower, str.upper, lambda x: f"  {x} ",
           lambda x: unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode()]
    return random.choice(ops)(s)


def random_ids(cur, table, column, n=1):
    cur.execute(f"SELECT {column} FROM app.{table} ORDER BY random() LIMIT %s", (n,))
    return [row[0] for row in cur.fetchall()]


def create_customer(cur):
    city = fake.city()
    if random.random() < MESS_RATE:
        city = messy_text(city)
    cur.execute(
        """INSERT INTO app.customers
           (customer_id, customer_unique_id, customer_zip_code, customer_city, customer_state)
           VALUES (%s, %s, %s, %s, %s)""",
        (new_id(), new_id(), fake.postcode()[:5], city, fake.estado_sigla()),
    )


def create_order(cur):
    n_items = random.randint(1, 3)
    customers = random_ids(cur, "customers", "customer_id")
    products = random_ids(cur, "products", "product_id", n_items)
    sellers = random_ids(cur, "sellers", "seller_id", n_items)
    if not (customers and products and sellers):
        return

    order_id = new_id()
    now = datetime.now()
    cur.execute(
        """INSERT INTO app.orders
           (order_id, customer_id, order_status, order_purchase_timestamp,
            order_estimated_delivery_date)
           VALUES (%s, %s, 'created', %s, %s)""",
        (order_id, customers[0], now, now + timedelta(days=random.randint(7, 30))),
    )

    total = 0
    for item_id, product_id in enumerate(products, start=1):
        price = round(random.uniform(10, 500), 2)
        freight = round(random.uniform(5, 50), 2)
        total += price + freight
        cur.execute(
            """INSERT INTO app.order_items
               (order_id, order_item_id, product_id, seller_id,
                shipping_limit_date, price, freight_value)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (order_id, item_id, product_id, random.choice(sellers),
             now + timedelta(days=3), price, freight),
        )

    payment_type = random.choices(PAYMENT_TYPES, weights=PAYMENT_WEIGHTS)[0]
    installments = random.randint(1, 10) if payment_type == "credit_card" else 1
    cur.execute(
        """INSERT INTO app.order_payments
           (order_id, payment_sequential, payment_type, payment_installments, payment_value)
           VALUES (%s, 1, %s, %s, %s)""",
        (order_id, payment_type, installments, round(total, 2)),
    )


def advance_order_status(cur):
    cur.execute(
        """SELECT order_id, order_status FROM app.orders
           WHERE order_status = ANY(%s) ORDER BY random() LIMIT 1""",
        (STATUS_FLOW[:-1],),
    )
    row = cur.fetchone()
    if row is None:
        return
    order_id, status = row

    # Orders can only be cancelled before they ship
    can_cancel = STATUS_FLOW.index(status) < STATUS_FLOW.index("shipped")
    if can_cancel and random.random() < CANCEL_RATE:
        next_status = "canceled"
    else:
        next_status = STATUS_FLOW[STATUS_FLOW.index(status) + 1]

    sets, params = ["order_status = %s", "updated_at = NOW()"], [next_status]
    if next_status in STATUS_TIMESTAMP:
        sets.append(f"{STATUS_TIMESTAMP[next_status]} = %s")
        params.append(datetime.now())
    cur.execute(
        f"UPDATE app.orders SET {', '.join(sets)} WHERE order_id = %s",
        (*params, order_id),
    )


def delete_review(cur):
    # Hard delete; your CDC must catch this later
    cur.execute(
        """DELETE FROM app.order_reviews
           WHERE (review_id, order_id) IN (
               SELECT review_id, order_id FROM app.order_reviews
               ORDER BY random() LIMIT 1)"""
    )


ACTIONS = {create_customer: 0.2, create_order: 0.5, advance_order_status: 0.25, delete_review: 0.05}


def main():
    with psycopg.connect(DSN, autocommit=True) as conn:
        while True:
            action = random.choices(list(ACTIONS), weights=list(ACTIONS.values()))[0]
            try:
                # One transaction per action, so an order is never half-written
                with conn.transaction(), conn.cursor() as cur:
                    action(cur)
                print(f"{datetime.now():%H:%M:%S} {action.__name__}")
            except psycopg.Error as e:
                print(f"{action.__name__} failed: {e}")
            time.sleep(float(os.getenv("SLEEP_SECONDS", 1)))


if __name__ == "__main__":
    main()
