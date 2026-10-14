from types import SimpleNamespace

import pandas as pd

from src.process_mining import analysis
from src.process_mining.report import compute_metrics, executive_summary, render_markdown


def make_log() -> pd.DataFrame:
    rows = [
        # case 1: reference path
        ("C1", "Create Order", "2026-01-01 08:00"), ("C1", "Credit Check", "2026-01-01 10:00"),
        ("C1", "Approve Order", "2026-01-01 12:00"), ("C1", "Pick", "2026-01-02 08:00"),
        ("C1", "Pack", "2026-01-02 09:00"), ("C1", "Ship", "2026-01-02 12:00"),
        ("C1", "Create Invoice", "2026-01-04 12:00"), ("C1", "Receive Payment", "2026-01-11 12:00"),
        # case 2: price change rework, re-check, approval skipped, still open
        ("C2", "Create Order", "2026-01-01 08:00"), ("C2", "Credit Check", "2026-01-01 09:00"),
        ("C2", "Change Price", "2026-01-01 19:00"), ("C2", "Credit Check", "2026-01-02 01:00"),
        ("C2", "Pick", "2026-01-02 07:00"), ("C2", "Pack", "2026-01-02 08:00"),
        ("C2", "Ship", "2026-01-02 10:00"), ("C2", "Create Invoice", "2026-01-05 10:00"),
    ]
    df = pd.DataFrame(rows, columns=["case_id", "activity", "timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.sort_values(["case_id", "timestamp"]).reset_index(drop=True)


def test_variants_and_conformance():
    log = make_log()
    v = analysis.variants(log)
    assert v["cases"].sum() == 2 and v["share_pct"].tolist() == [50.0, 50.0]
    c = analysis.conformance(log)
    assert c["follow_reference_path_pct"] == 50.0
    assert c["skipped_approval_cases"] == 1


def test_cycle_time_excludes_open_cases():
    s = analysis.cycle_time_summary(make_log())
    assert s == {"cases": 2, "completed_cases": 1, "open_cases": 1, "median_cycle_days": 10.2, "p90_cycle_days": 10.2}


def test_transitions_wait_times():
    t = analysis.transitions(make_log()).set_index(["source", "target"])
    assert t.loc[("Ship", "Create Invoice"), "count"] == 2
    assert t.loc[("Ship", "Create Invoice"), "median_wait_hours"] == 60.0  # 48h and 72h


def test_bottlenecks_exclude_customer_payment_wait():
    b = analysis.bottlenecks(make_log())
    assert "Receive Payment" not in set(b["target"])
    assert tuple(b.iloc[0][["source", "target"]]) == ("Ship", "Create Invoice")


def test_rework_detects_repeated_credit_check():
    r = analysis.rework(make_log())
    assert r.to_dict(orient="records") == [
        {"activity": "Credit Check", "cases_with_rework": 1, "extra_executions": 1, "rework_rate_pct": 50.0}
    ]


def test_report_renders_and_summary_uses_metrics():
    metrics = compute_metrics(make_log())
    seen = {}

    def create(**kwargs):
        seen["prompt"] = kwargs["messages"][0]["content"]
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="Invoicing is the bottleneck.")])

    summary = executive_summary(metrics, client=SimpleNamespace(messages=SimpleNamespace(create=create)))
    assert '"skipped_approval_cases": 1' in seen["prompt"]
    md = render_markdown(metrics, summary)
    assert "## Executive summary" in md and "Invoicing is the bottleneck." in md
    assert "| Ship | Create Invoice |" in md
