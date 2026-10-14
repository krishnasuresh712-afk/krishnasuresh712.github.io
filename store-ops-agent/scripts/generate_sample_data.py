"""Generate a realistic, anonymized sample dataset for the store ops agent.

Replace data/orders.csv and data/products.csv with your own store export
(same columns) to run the agent on real data.
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)
DATA = Path(__file__).resolve().parents[1] / "data"

PRODUCTS = [
    # sku, name, unit_price, unit_cost, on_hand, lead_time_days, popularity
    ("SKU-101", "Phone Stand", 14.99, 5.10, 42, 14, 1.6),
    ("SKU-102", "USB-C Cable 2-Pack", 11.99, 3.20, 18, 10, 2.2),
    ("SKU-103", "Laptop Sleeve 14in", 24.99, 11.40, 9, 21, 0.9),
    ("SKU-104", "Desk Cable Organizer", 9.99, 3.75, 60, 12, 1.1),
    ("SKU-105", "Wireless Charging Pad", 21.99, 9.80, 7, 18, 1.3),
    ("SKU-106", "Monitor Light Bar", 34.99, 16.50, 15, 25, 0.6),
    ("SKU-107", "Keyboard Wrist Rest", 16.99, 6.40, 33, 14, 0.8),
    ("SKU-108", "Webcam Privacy Cover 3-Pack", 6.99, 1.10, 80, 7, 1.0),
]


def main() -> None:
    DATA.mkdir(exist_ok=True)
    start = date(2026, 3, 1)
    days = 210
    orders = []
    order_id = 10000
    for d in range(days):
        day = start + timedelta(days=d)
        seasonal = 1.0 + 0.4 * (d / days)          # slow growth over the period
        weekend = 1.3 if day.weekday() >= 5 else 1.0
        n_orders = max(0, round(random.gauss(2.4 * seasonal * weekend, 1.0)))
        for _ in range(n_orders):
            order_id += 1
            weights = [p[6] for p in PRODUCTS]
            for p in random.choices(PRODUCTS, weights=weights, k=random.choice([1, 1, 1, 2])):
                qty = random.choice([1, 1, 1, 2, 3])
                orders.append([f"ORD-{order_id}", day.isoformat(), p[0], qty, p[2], p[3]])

    with open(DATA / "orders.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["order_id", "order_date", "sku", "quantity", "unit_price", "unit_cost"])
        w.writerows(orders)

    with open(DATA / "products.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sku", "name", "on_hand", "lead_time_days", "safety_stock_days"])
        for p in PRODUCTS:
            w.writerow([p[0], p[1], p[4], p[5], 7])

    print(f"Wrote {len(orders)} order lines across {order_id - 10000} orders to {DATA}")


if __name__ == "__main__":
    main()
