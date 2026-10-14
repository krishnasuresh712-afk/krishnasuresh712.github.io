"""Build a findings report from an event log.

Usage:
    python -m src.process_mining.report                 # metrics-only report
    python -m src.process_mining.report --summarize     # adds a Claude executive summary
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path

import pandas as pd

from . import analysis

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")

SUMMARY_PROMPT = """You are a process improvement consultant writing for a COO.
Using ONLY the metrics in the JSON below, write an executive summary:
1. One sentence on the overall health of the process.
2. The three highest-impact findings, each with the specific number behind it.
3. One recommended next step per finding, phrased as something a team can pilot in 30 days.
Do not introduce any number that is not in the JSON. Under 200 words. Plain prose and a short numbered list.

<metrics>
{metrics}
</metrics>"""


def compute_metrics(log: pd.DataFrame) -> dict:
    return {
        "cycle_time": analysis.cycle_time_summary(log),
        "conformance": analysis.conformance(log),
        "top_variants": analysis.variants(log, top=5).to_dict(orient="records"),
        "bottlenecks": analysis.bottlenecks(log, top=5).to_dict(orient="records"),
        "rework": analysis.rework(log).to_dict(orient="records"),
        "manual_credit_review_impact": analysis.duration_impact(log, "Manual Credit Review"),
    }


def executive_summary(metrics: dict, client=None, model: str = DEFAULT_MODEL) -> str:
    if client is None:
        from anthropic import Anthropic

        client = Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=800,
        messages=[{"role": "user", "content": SUMMARY_PROMPT.format(metrics=json.dumps(metrics, default=str, indent=2))}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()


def _table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def render_markdown(metrics: dict, summary: str | None = None) -> str:
    ct, conf = metrics["cycle_time"], metrics["conformance"]
    impact = metrics["manual_credit_review_impact"]
    parts = [f"# Order-to-Cash Process Findings\n\n_Generated {date.today().isoformat()} from {ct['cases']} cases._\n"]
    if summary:
        parts.append(f"## Executive summary\n\n{summary}\n")
    parts.append(
        "## Headline metrics\n\n"
        f"- Median order-to-cash cycle: **{ct['median_cycle_days']} days** (90th percentile {ct['p90_cycle_days']} days, "
        f"{ct['completed_cases']} completed cases, {ct['open_cases']} still open)\n"
        f"- Cases following the standard path end to end: **{conf['follow_reference_path_pct']}%**\n"
        f"- Orders shipped without approval: **{conf['skipped_approval_cases']} ({conf['skipped_approval_pct']}%)**\n"
        f"- Manual credit review: {impact['cases_with']} completed cases, median cycle {impact['median_days_with']} days "
        f"vs {impact['median_days_without']} days without\n"
    )
    parts.append("## Where work waits (internal handoffs)\n\n" + _table(pd.DataFrame(metrics["bottlenecks"])) + "\n")
    parts.append("## Rework\n\n" + _table(pd.DataFrame(metrics["rework"])) + "\n")
    parts.append("## Most common process variants\n\n" + _table(pd.DataFrame(metrics["top_variants"])) + "\n")
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default=str(analysis.DATA))
    parser.add_argument("--out", default=str(ROOT / "reports" / "findings.md"))
    parser.add_argument("--summarize", action="store_true", help="add a Claude-written executive summary")
    args = parser.parse_args()

    metrics = compute_metrics(analysis.load_log(args.log))
    summary = executive_summary(metrics) if args.summarize else None
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(metrics, summary))
    (out.with_suffix(".json")).write_text(json.dumps(metrics, indent=2, default=str))
    print(f"Report written to {out}")


if __name__ == "__main__":
    main()
