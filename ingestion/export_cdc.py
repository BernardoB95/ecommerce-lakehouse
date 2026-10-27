"""Export Postgres changes to the Databricks landing volume as JSON lines.

Usage:
    python ingestion/export_cdc.py snapshot [--force]   # once: full copy of every table
    python ingestion/export_cdc.py incremental          # repeatedly: new app.cdc_log rows

Every record is the table row plus three metadata fields:
    _op          S (snapshot), I, U or D
    _change_id   cdc_log.change_id (the watermark for snapshot rows)
    _changed_at  when the change happened (snapshot time for snapshot rows)

Delivery is at-least-once: the watermark in ingestion/state.json only moves after
the upload succeeded, so a crash resends data instead of losing it. Deduplicate
on _change_id downstream.
"""
import argparse
import io
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv
from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = Path(__file__).resolve().parent / "state.json"

load_dotenv(ROOT / ".env")

VOLUME_ROOT = os.getenv("LANDING_VOLUME", "/Volumes/dev/bronze/landing")
BATCH_SIZE = int(os.getenv("CDC_BATCH_SIZE", 10000))
SCHEMA = "app"
TABLES = [
    "customers", "sellers", "products", "orders",
    "order_items", "order_payments", "order_reviews",
]


def connect(**kwargs):
    return psycopg.connect(
        host=os.getenv("PG_HOST", "localhost"),
        port=os.environ["PG_PORT"],
        dbname=os.getenv("PG_DB", "shop"),
        user=os.environ["PG_USER"],
        password=os.environ["PG_PASSWORD"],
        row_factory=dict_row,
        **kwargs,
    )


def load_state():
    if not STATE_FILE.exists():
        return None
    return json.loads(STATE_FILE.read_text())


def save_state(last_change_id):
    state = {
        "last_change_id": last_change_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state))
    tmp.replace(STATE_FILE)  # atomic, so a crash never leaves a half-written file


def upload(w, table, file_name, rows):
    data = "".join(json.dumps(row, default=str) + "\n" for row in rows).encode()
    path = f"{VOLUME_ROOT}/{table}/{file_name}"
    w.files.upload(path, io.BytesIO(data), overwrite=True)
    print(f"  {path}  ({len(rows):,} rows)")


def snapshot(w, force):
    if load_state() and not force:
        sys.exit(f"{STATE_FILE.name} already exists, so a snapshot was already taken. "
                 "Use --force to take another one.")

    snapshot_at = datetime.now(timezone.utc)
    stamp = f"{snapshot_at:%Y%m%dT%H%M%S}"

    # REPEATABLE READ: the watermark and every table are read from the same view
    # of the database, so incremental can continue right after the watermark.
    with connect() as conn:
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(change_id), 0) AS watermark FROM app.cdc_log")
        watermark = cur.fetchone()["watermark"]

        for table in TABLES:
            # to_jsonb gives the same value formats as the rows stored in cdc_log
            cur.execute(
                sql.SQL("SELECT to_jsonb(t) AS row_data FROM {} t").format(
                    sql.Identifier(SCHEMA, table)
                )
            )
            rows = [
                {**r["row_data"], "_op": "S", "_change_id": watermark,
                 "_changed_at": snapshot_at.isoformat()}
                for r in cur.fetchall()
            ]
            print(table)
            upload(w, table, f"{table}_snapshot_{stamp}.json", rows)

    save_state(watermark)  # only after every upload succeeded
    print(f"Snapshot done, watermark = {watermark}")


def incremental(w):
    state = load_state()
    if state is None:
        sys.exit("No state.json found. Run the snapshot first.")
    last = state["last_change_id"]

    with connect(autocommit=True) as conn, conn.cursor() as cur:
        while True:
            cur.execute(
                """SELECT change_id, table_name, op, row_data, changed_at
                   FROM app.cdc_log WHERE change_id > %s
                   ORDER BY change_id LIMIT %s""",
                (last, BATCH_SIZE),
            )
            batch = cur.fetchall()
            if not batch:
                break

            by_table = defaultdict(list)
            for r in batch:
                by_table[r["table_name"]].append({
                    **r["row_data"],
                    "_op": r["op"],
                    "_change_id": r["change_id"],
                    "_changed_at": r["changed_at"].isoformat(),
                })

            max_id = batch[-1]["change_id"]
            print(f"change_id {last + 1} to {max_id}")
            for table, rows in by_table.items():
                upload(w, table, f"{table}_{max_id}.json", rows)

            last = max_id
            save_state(last)  # only after every upload in this batch succeeded

    print(f"Up to date, watermark = {last}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    snap = sub.add_parser("snapshot", help="full copy of every table (run once)")
    snap.add_argument("--force", action="store_true", help="snapshot even if one exists")
    sub.add_parser("incremental", help="export new cdc_log rows")
    args = parser.parse_args()

    w = WorkspaceClient()
    if args.mode == "snapshot":
        snapshot(w, args.force)
    else:
        incremental(w)


if __name__ == "__main__":
    main()
