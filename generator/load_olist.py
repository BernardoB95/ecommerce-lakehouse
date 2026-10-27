"""Load the Olist CSVs into the app.* Postgres tables using COPY.

Usage:
    python generator/load_olist.py              # append
    python generator/load_olist.py --truncate   # empty the tables first
"""
import argparse
import csv
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "olist"
SCHEMA = "app"

load_dotenv(ROOT / ".env")

DSN = (
    f"host={os.getenv('PG_HOST', 'localhost')} "
    f"port={os.environ['PG_PORT']} "
    f"dbname={os.getenv('PG_DB', 'shop')} "
    f"user={os.environ['PG_USER']} "
    f"password={os.environ['PG_PASSWORD']}"
)

# Ordered by foreign-key dependencies
TABLES = [
    ("customers",      "olist_customers_dataset.csv"),
    ("sellers",        "olist_sellers_dataset.csv"),
    ("products",       "olist_products_dataset.csv"),
    ("orders",         "olist_orders_dataset.csv"),
    ("order_items",    "olist_order_items_dataset.csv"),
    ("order_payments", "olist_order_payments_dataset.csv"),
    ("order_reviews",  "olist_order_reviews_dataset.csv"),
]

# CSV header -> table column, where the names differ
COLUMN_RENAMES = {
    "customers": {"customer_zip_code_prefix": "customer_zip_code"},
    "products": {
        "product_name_lenght": "product_name_length",
        "product_description_lenght": "product_description_length",
    },
}


def load_table(cur, table, csv_file):
    path = DATA_DIR / csv_file
    with open(path, newline="", encoding="utf-8") as f:
        header = next(csv.reader([f.readline()]))
        renames = COLUMN_RENAMES.get(table, {})
        columns = [renames.get(col, col) for col in header]

        # Header line was already consumed, so COPY starts at the first data row.
        # In CSV format, unquoted empty fields become NULL.
        query = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv)").format(
            sql.Identifier(SCHEMA, table),
            sql.SQL(", ").join(map(sql.Identifier, columns)),
        )
        with cur.copy(query) as copy:
            while chunk := f.read(1 << 20):
                copy.write(chunk)

    print(f"{table:<16} {cur.rowcount:>8,} rows  <- {csv_file}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--truncate", action="store_true", help="empty all tables before loading"
    )
    args = parser.parse_args()

    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        if args.truncate:
            names = sql.SQL(", ").join(
                sql.Identifier(SCHEMA, table) for table, _ in TABLES
            )
            cur.execute(sql.SQL("TRUNCATE {}").format(names))
            print("Truncated all tables")

        for table, csv_file in TABLES:
            load_table(cur, table, csv_file)
    # Leaving the `with` block commits; any error rolls everything back.


if __name__ == "__main__":
    main()
