"""Fetch BRL exchange rates from Frankfurter (ECB data) into the landing volume.

Usage:
    python ingestion/fetch_fx.py backfill [--start 2016-09-01] [--end 2018-10-31]
    python ingestion/fetch_fx.py daily

Run it locally: it needs outbound access to the API, which Databricks Free
Edition may block. Output is one JSON line per (date, currency):
    {"date": "2018-10-31", "base": "BRL", "currency": "USD", "rate": 0.2681}
where rate is how many units of `currency` one BRL buys.
"""
import argparse
import io
import json
import os
from pathlib import Path

import requests
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

API = "https://api.frankfurter.dev/v1"
BASE = "BRL"
SYMBOLS = "USD,MXN"
VOLUME_ROOT = os.getenv("LANDING_VOLUME", "/Volumes/dev/bronze/landing")
OLIST_START, OLIST_END = "2016-09-01", "2018-10-31"


def fetch(endpoint):
    resp = requests.get(
        f"{API}/{endpoint}", params={"base": BASE, "symbols": SYMBOLS}, timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def to_rows(rates_by_date):
    """{date: {currency: rate}} -> one row per (date, currency)."""
    return [
        {"date": date, "base": BASE, "currency": currency, "rate": rate}
        for date, rates in sorted(rates_by_date.items())
        for currency, rate in sorted(rates.items())
    ]


def upload(w, file_name, rows):
    data = "".join(json.dumps(row) + "\n" for row in rows).encode()
    path = f"{VOLUME_ROOT}/fx_rates/{file_name}"
    w.files.upload(path, io.BytesIO(data), overwrite=True)
    print(f"{path}  ({len(rows):,} rows)")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    back = sub.add_parser("backfill", help="rates for a date range (run once)")
    back.add_argument("--start", default=OLIST_START)
    back.add_argument("--end", default=OLIST_END)
    sub.add_parser("daily", help="latest rates")
    args = parser.parse_args()

    w = WorkspaceClient()
    if args.mode == "backfill":
        data = fetch(f"{args.start}..{args.end}")
        upload(w, f"fx_rates_{args.start}_{args.end}.json", to_rows(data["rates"]))
    else:
        data = fetch("latest")
        # Re-running on the same day overwrites that day's file, so no duplicates
        upload(w, f"fx_rates_{data['date']}.json", to_rows({data["date"]: data["rates"]}))


if __name__ == "__main__":
    main()
