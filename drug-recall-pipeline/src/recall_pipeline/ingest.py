"""Pull FDA drug recall (enforcement) records from the openFDA API into SQLite.

Usage:
    python -m src.recall_pipeline.ingest --since 2024-01-01
    python -m src.recall_pipeline.ingest --incremental      # only newer than the latest loaded report_date
"""
from __future__ import annotations

import argparse
import sqlite3
import time
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

import requests

API_URL = "https://api.fda.gov/drug/enforcement.json"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "recalls.db"
PAGE_SIZE = 1000          # openFDA maximum per request
MAX_SKIP = 25000          # openFDA maximum offset

# Ordered: the first matching rule wins, most specific first.
REASON_RULES = [
    ("Sterility", ("sterility",)),  # not "steril": "non-sterile products" is a contamination recall
    ("Impurities", ("impurit", "nitrosamine", "ndma", "benzene")),
    ("Contamination", ("contamin", "microbial", "bacteria", "particulate", "foreign matter", "foreign substance")),
    ("Potency / dissolution", ("potency", "subpotent", "superpotent", "dissolution", "content uniformity")),
    ("Labeling", ("label", "mislabel", "package insert")),
    ("cGMP deviations", ("cgmp", "good manufacturing")),
]


def categorize_reason(reason: str | None) -> str:
    text = (reason or "").lower()
    for category, keywords in REASON_RULES:
        if any(k in text for k in keywords):
            return category
    return "Other"


def _iso(yyyymmdd: str | None) -> str | None:
    if not yyyymmdd:
        return None
    return datetime.strptime(yyyymmdd, "%Y%m%d").date().isoformat()


def normalize(record: dict) -> dict:
    return {
        "recall_number": record["recall_number"],
        "report_date": _iso(record.get("report_date")),
        "recall_initiation_date": _iso(record.get("recall_initiation_date")),
        "classification": record.get("classification"),
        "status": record.get("status"),
        "recalling_firm": (record.get("recalling_firm") or "").strip(),
        "state": record.get("state"),
        "country": record.get("country"),
        "voluntary_mandated": record.get("voluntary_mandated"),
        "product_description": record.get("product_description"),
        "reason_for_recall": record.get("reason_for_recall"),
        "reason_category": categorize_reason(record.get("reason_for_recall")),
        "distribution_pattern": record.get("distribution_pattern"),
    }


def fetch_recalls(since: date, session: requests.Session | None = None, max_records: int = MAX_SKIP) -> Iterator[dict]:
    """Page through openFDA results newest first. Stops at the API's offset limit."""
    session = session or requests.Session()
    window = f"report_date:[{since:%Y%m%d}+TO+{date.today():%Y%m%d}]"
    skip = 0
    while skip < min(max_records, MAX_SKIP):
        # openFDA expects literal '+' in the search syntax, so the query string is built by hand.
        url = f"{API_URL}?search={window}&sort=report_date:desc&limit={PAGE_SIZE}&skip={skip}"
        resp = session.get(url, timeout=30)
        if resp.status_code == 404:  # openFDA returns 404 when no records match
            return
        resp.raise_for_status()
        results = resp.json().get("results", [])
        yield from results
        if len(results) < PAGE_SIZE:
            return
        skip += PAGE_SIZE
        time.sleep(0.3)  # stay well under the unauthenticated rate limit


def connect(db_path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    if str(db_path) != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript((ROOT / "sql" / "schema.sql").read_text())
    return conn


UPSERT = """
INSERT INTO recalls (recall_number, report_date, recall_initiation_date, classification, status,
    recalling_firm, state, country, voluntary_mandated, product_description, reason_for_recall,
    reason_category, distribution_pattern)
VALUES (:recall_number, :report_date, :recall_initiation_date, :classification, :status,
    :recalling_firm, :state, :country, :voluntary_mandated, :product_description, :reason_for_recall,
    :reason_category, :distribution_pattern)
ON CONFLICT (recall_number) DO UPDATE SET
    status = excluded.status,
    classification = excluded.classification,
    reason_category = excluded.reason_category,
    loaded_at = CURRENT_TIMESTAMP
"""


def load(conn: sqlite3.Connection, records: list[dict], since: date | None = None) -> dict:
    """Idempotent load: re-running updates status changes instead of duplicating rows."""
    rows = [normalize(r) for r in records if r.get("recall_number") and r.get("report_date")]
    before = conn.execute("SELECT COUNT(*) FROM recalls").fetchone()[0]
    with conn:
        conn.executemany(UPSERT, rows)
        after = conn.execute("SELECT COUNT(*) FROM recalls").fetchone()[0]
        conn.execute(
            "INSERT INTO ingest_runs (since_date, records_seen, records_new) VALUES (?, ?, ?)",
            (since.isoformat() if since else None, len(rows), after - before),
        )
    return {"records_seen": len(rows), "records_new": after - before, "total_rows": after}


def latest_report_date(conn: sqlite3.Connection) -> date | None:
    value = conn.execute("SELECT MAX(report_date) FROM recalls").fetchone()[0]
    return date.fromisoformat(value) if value else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--since", type=date.fromisoformat, default=date(date.today().year - 2, 1, 1))
    parser.add_argument("--incremental", action="store_true", help="start from the latest report_date already loaded")
    args = parser.parse_args()

    conn = connect(args.db)
    since = (latest_report_date(conn) if args.incremental else None) or args.since
    print(f"Fetching recalls reported since {since} ...")
    stats = load(conn, list(fetch_recalls(since)), since)
    print(f"Seen {stats['records_seen']}, new {stats['records_new']}, table now has {stats['total_rows']} rows")


if __name__ == "__main__":
    main()
