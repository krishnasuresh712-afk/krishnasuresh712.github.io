import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from src.recall_pipeline import queries
from src.recall_pipeline.ingest import PAGE_SIZE, categorize_reason, connect, fetch_recalls, latest_report_date, load

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "enforcement_sample.json").read_text())["results"]


def loaded_conn():
    conn = connect(":memory:")
    load(conn, FIXTURE)
    return conn


def test_reason_categories():
    got = [categorize_reason(r["reason_for_recall"]) for r in FIXTURE]
    assert got == ["Impurities", "Sterility", "Labeling", "Potency / dissolution", "Contamination"]
    assert categorize_reason(None) == "Other"


def test_load_is_idempotent_and_updates_status():
    conn = loaded_conn()
    changed = [dict(r, status="Terminated") if r["recall_number"] == "D-0101-2026" else r for r in FIXTURE]
    stats = load(conn, changed)
    assert stats == {"records_seen": 5, "records_new": 0, "total_rows": 5}
    status = conn.execute("SELECT status FROM recalls WHERE recall_number = 'D-0101-2026'").fetchone()[0]
    assert status == "Terminated"
    assert conn.execute("SELECT COUNT(*) FROM ingest_runs").fetchone()[0] == 2


def test_dates_normalized_and_latest_date():
    conn = loaded_conn()
    assert conn.execute("SELECT report_date FROM recalls WHERE recall_number = 'D-0102-2026'").fetchone()[0] == "2026-03-11"
    assert latest_report_date(conn) == date(2026, 4, 20)


def test_queries():
    conn = loaded_conn()
    by_class = {r["classification"]: r["recalls"] for r in queries.recalls_by_class(conn)}
    assert by_class == {"Class I": 2, "Class II": 2, "Class III": 1}
    # Tie on recall count is broken by Class I count
    assert queries.top_firms(conn, limit=1) == [
        {"recalling_firm": "Sample Compounding LLC", "recalls": 2, "class_i": 2, "most_recent": "2026-04-20"}
    ]
    assert [r["month"] for r in queries.monthly_trend(conn)] == ["2026-03", "2026-04"]
    assert {r["recall_number"] for r in queries.open_class_i(conn)} == {"D-0102-2026", "D-0105-2026"}
    assert queries.recalls_by_class(conn, since="2026-04-01")[0]["recalls"] == 1


class FakeSession:
    """Serves one full page then a partial page, like a paginated API."""

    def __init__(self):
        self.urls = []

    def get(self, url, timeout):
        self.urls.append(url)
        n = PAGE_SIZE if len(self.urls) == 1 else 3
        payload = {"results": [dict(FIXTURE[0], recall_number=f"D-{len(self.urls)}-{i}") for i in range(n)]}
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: payload)


def test_fetch_paginates_until_short_page():
    session = FakeSession()
    records = list(fetch_recalls(date(2026, 1, 1), session=session))
    assert len(records) == PAGE_SIZE + 3
    assert "skip=0" in session.urls[0] and f"skip={PAGE_SIZE}" in session.urls[1]
    assert "report_date:[20260101+TO+" in session.urls[0]
