"""Process mining over an event log (one row per case, activity, timestamp).

Answers the questions a process improvement engagement starts with:
how does the process actually run, how long does it take, where does work
wait, where is work redone, and how often is the standard path skipped?
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data" / "event_log.csv"

REFERENCE_PATH = ["Create Order", "Credit Check", "Approve Order", "Pick", "Pack", "Ship", "Create Invoice", "Receive Payment"]


def load_log(path: str | Path = DATA) -> pd.DataFrame:
    log = pd.read_csv(path, parse_dates=["timestamp"])
    missing = {"case_id", "activity", "timestamp"} - set(log.columns)
    if missing:
        raise ValueError(f"event log missing columns: {sorted(missing)}")
    return log.sort_values(["case_id", "timestamp"], kind="stable").reset_index(drop=True)


def traces(log: pd.DataFrame) -> pd.Series:
    """Ordered activity sequence per case."""
    return log.groupby("case_id", sort=False)["activity"].agg(tuple)


def variants(log: pd.DataFrame, top: int = 10) -> pd.DataFrame:
    t = traces(log)
    counts = t.value_counts()
    out = pd.DataFrame({"variant": [" > ".join(v) for v in counts.index], "cases": counts.values})
    out["share_pct"] = (100 * out["cases"] / len(t)).round(1)
    out["cumulative_pct"] = out["share_pct"].cumsum().round(1)
    return out.head(top)


def case_durations(log: pd.DataFrame, end_activity: str | None = "Receive Payment") -> pd.DataFrame:
    """Cycle time per case in days. Cases that never reach end_activity are open and excluded from stats."""
    g = log.groupby("case_id")
    d = pd.DataFrame({"start": g["timestamp"].min(), "end": g["timestamp"].max(), "events": g.size()})
    d["completed"] = g["activity"].apply(lambda a: end_activity in set(a)) if end_activity else True
    d["cycle_days"] = ((d["end"] - d["start"]).dt.total_seconds() / 86400).round(2)
    return d


def cycle_time_summary(log: pd.DataFrame) -> dict:
    d = case_durations(log)
    done = d[d["completed"]]["cycle_days"]
    return {
        "cases": int(len(d)),
        "completed_cases": int(len(done)),
        "open_cases": int((~d["completed"]).sum()),
        "median_cycle_days": round(float(done.median()), 1),
        "p90_cycle_days": round(float(done.quantile(0.9)), 1),
    }


def transitions(log: pd.DataFrame) -> pd.DataFrame:
    """Directly-follows graph with waiting time between consecutive activities."""
    nxt = log.groupby("case_id")[["activity", "timestamp"]].shift(-1)
    df = pd.DataFrame(
        {
            "source": log["activity"],
            "target": nxt["activity"],
            "wait_hours": (nxt["timestamp"] - log["timestamp"]).dt.total_seconds() / 3600,
        }
    ).dropna(subset=["target"])
    out = (
        df.groupby(["source", "target"])["wait_hours"]
        .agg(count="size", median_wait_hours="median", total_wait_hours="sum")
        .reset_index()
    )
    out["median_wait_hours"] = out["median_wait_hours"].round(1)
    out["share_of_total_wait_pct"] = (100 * out["total_wait_hours"] / out["total_wait_hours"].sum()).round(1)
    out["total_wait_hours"] = out["total_wait_hours"].round(0)
    return out.sort_values("total_wait_hours", ascending=False).reset_index(drop=True)


def bottlenecks(log: pd.DataFrame, top: int = 5, exclude_targets: tuple[str, ...] = ("Receive Payment",)) -> pd.DataFrame:
    """Handoffs where the most total waiting accumulates.

    Customer payment terms are excluded by default: waiting on the customer is
    not an internal process delay you can fix with a workflow change.
    """
    t = transitions(log)
    t = t[~t["target"].isin(exclude_targets)].copy()
    t["share_of_internal_wait_pct"] = (100 * t["total_wait_hours"] / t["total_wait_hours"].sum()).round(1)
    return t.head(top).drop(columns=["share_of_total_wait_pct"]).reset_index(drop=True)


def rework(log: pd.DataFrame) -> pd.DataFrame:
    """Activities executed more than once in the same case."""
    per_case = log.groupby(["case_id", "activity"]).size().reset_index(name="executions")
    repeated = per_case[per_case["executions"] > 1]
    n_cases = log["case_id"].nunique()
    out = (
        repeated.groupby("activity")
        .agg(cases_with_rework=("case_id", "nunique"), extra_executions=("executions", lambda s: int((s - 1).sum())))
        .reset_index()
    )
    out["rework_rate_pct"] = (100 * out["cases_with_rework"] / n_cases).round(1)
    return out.sort_values("cases_with_rework", ascending=False).reset_index(drop=True)


def conformance(log: pd.DataFrame, reference: list[str] = REFERENCE_PATH) -> dict:
    t = traces(log)
    happy = tuple(reference)
    skipped_approval = t.apply(lambda tr: "Approve Order" not in tr)
    approval_after_pick = t.apply(lambda tr: "Approve Order" in tr and "Pick" in tr and tr.index("Approve Order") > tr.index("Pick"))
    n = len(t)
    return {
        "cases": int(n),
        "follow_reference_path_pct": round(100 * float((t == happy).mean()), 1),
        "skipped_approval_cases": int(skipped_approval.sum()),
        "skipped_approval_pct": round(100 * float(skipped_approval.mean()), 1),
        "approval_after_pick_cases": int(approval_after_pick.sum()),
    }


def duration_impact(log: pd.DataFrame, activity: str) -> dict:
    """Median cycle time for completed cases with vs without an activity (e.g. a review step)."""
    d = case_durations(log)
    d = d[d["completed"]]
    has = log[log["activity"] == activity]["case_id"].unique()
    with_ = d[d.index.isin(has)]["cycle_days"]
    without = d[~d.index.isin(has)]["cycle_days"]
    return {
        "activity": activity,
        "cases_with": int(len(with_)),
        "median_days_with": round(float(with_.median()), 1) if len(with_) else None,
        "median_days_without": round(float(without.median()), 1) if len(without) else None,
    }
