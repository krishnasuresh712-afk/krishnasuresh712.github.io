"""Generate a synthetic order-to-cash event log with realistic process problems baked in:
credit-check holds, price-change rework loops, skipped approvals, and a slow
handoff into invoicing. Replace data/event_log.csv with a real export
(case_id, activity, timestamp, resource) to analyze an actual process.
"""
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(11)
OUT = Path(__file__).resolve().parents[1] / "data" / "event_log.csv"

# activity -> (team, median hours of waiting before this step starts)
STEPS = {
    "Create Order": ("Sales", 0),
    "Credit Check": ("Finance", 4),
    "Manual Credit Review": ("Finance", 30),
    "Change Price": ("Sales", 10),
    "Approve Order": ("Sales Ops", 6),
    "Pick": ("Warehouse", 12),
    "Pack": ("Warehouse", 3),
    "Ship": ("Logistics", 8),
    "Create Invoice": ("Billing", 40),   # the bottleneck: billing batches invoices
    "Receive Payment": ("Finance", 24 * 22),
}


def path_for_case() -> list[str]:
    path = ["Create Order", "Credit Check"]
    if random.random() < 0.18:
        path.append("Manual Credit Review")
    for _ in range(random.choices([0, 1, 2], weights=[78, 17, 5])[0]):
        path += ["Change Price", "Credit Check"]   # rework: price change forces a re-check
    if random.random() > 0.08:                      # 8% skip approval: a conformance issue
        path.append("Approve Order")
    path += ["Pick", "Pack", "Ship", "Create Invoice"]
    if random.random() < 0.93:
        path.append("Receive Payment")              # some cases still open at extract time
    return path


def main() -> None:
    OUT.parent.mkdir(exist_ok=True)
    rows = []
    start = datetime(2026, 4, 1, 8)
    for i in range(1, 801):
        t = start + timedelta(hours=random.uniform(0, 24 * 120))
        for activity in path_for_case():
            team, median_wait = STEPS[activity]
            if median_wait:
                t += timedelta(hours=random.lognormvariate(0, 0.6) * median_wait)
            rows.append([f"SO-{i:05d}", activity, t.strftime("%Y-%m-%d %H:%M:%S"), f"{team} {random.randint(1, 4)}"])
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "activity", "timestamp", "resource"])
        w.writerows(rows)
    print(f"Wrote {len(rows)} events for 800 cases to {OUT}")


if __name__ == "__main__":
    main()
