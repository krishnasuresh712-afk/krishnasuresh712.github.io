"""Deterministic analytics over order and product data.

Every number the agent reports comes from these functions. The LLM chooses
which function to call and explains the result; it never does the math.
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_data(orders_path: str | Path | None = None, products_path: str | Path | None = None):
    orders = pd.read_csv(orders_path or DATA_DIR / "orders.csv", parse_dates=["order_date"])
    products = pd.read_csv(products_path or DATA_DIR / "products.csv")
    orders["revenue"] = orders["quantity"] * orders["unit_price"]
    orders["cogs"] = orders["quantity"] * orders["unit_cost"]
    orders["gross_profit"] = orders["revenue"] - orders["cogs"]
    return orders, products


def revenue_summary(orders: pd.DataFrame) -> dict:
    revenue = float(orders["revenue"].sum())
    gross_profit = float(orders["gross_profit"].sum())
    return {
        "orders": int(orders["order_id"].nunique()),
        "units": int(orders["quantity"].sum()),
        "revenue": round(revenue, 2),
        "cogs": round(float(orders["cogs"].sum()), 2),
        "gross_profit": round(gross_profit, 2),
        "gross_margin_pct": round(100 * gross_profit / revenue, 1) if revenue else 0.0,
        "avg_order_value": round(revenue / orders["order_id"].nunique(), 2) if len(orders) else 0.0,
        "period_start": orders["order_date"].min().date().isoformat(),
        "period_end": orders["order_date"].max().date().isoformat(),
    }


def product_performance(orders: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    perf = (
        orders.groupby("sku")
        .agg(units=("quantity", "sum"), revenue=("revenue", "sum"), gross_profit=("gross_profit", "sum"))
        .reset_index()
        .merge(products[["sku", "name"]], on="sku", how="left")
    )
    perf["margin_pct"] = (100 * perf["gross_profit"] / perf["revenue"]).round(1)
    perf["revenue_share_pct"] = (100 * perf["revenue"] / perf["revenue"].sum()).round(1)
    perf[["revenue", "gross_profit"]] = perf[["revenue", "gross_profit"]].round(2)
    return perf.sort_values("revenue", ascending=False).reset_index(drop=True)[
        ["sku", "name", "units", "revenue", "gross_profit", "margin_pct", "revenue_share_pct"]
    ]


def weekly_trend(orders: pd.DataFrame) -> pd.DataFrame:
    weekly = (
        orders.set_index("order_date")
        .resample("W-MON", label="left", closed="left")
        .agg({"revenue": "sum", "order_id": "nunique"})
        .rename(columns={"order_id": "orders"})
        .reset_index()
        .rename(columns={"order_date": "week_start"})
    )
    weekly["revenue"] = weekly["revenue"].round(2)
    weekly["wow_change_pct"] = (100 * weekly["revenue"].pct_change()).round(1)
    weekly["week_start"] = weekly["week_start"].dt.date.astype(str)
    return weekly


def reorder_plan(
    orders: pd.DataFrame,
    products: pd.DataFrame,
    lookback_days: int = 60,
    cover_days: int = 30,
    as_of: str | None = None,
) -> pd.DataFrame:
    """Reorder point = average daily demand x (lead time + safety stock days).

    Suggested order quantity brings stock up to cover the lead time, safety
    stock, and `cover_days` of additional demand.
    """
    end = pd.Timestamp(as_of) if as_of else orders["order_date"].max()
    start = end - pd.Timedelta(days=lookback_days - 1)
    window = orders[(orders["order_date"] >= start) & (orders["order_date"] <= end)]
    demand = window.groupby("sku")["quantity"].sum() / lookback_days

    plan = products.copy()
    plan["avg_daily_demand"] = plan["sku"].map(demand).fillna(0.0).round(3)
    horizon = plan["lead_time_days"] + plan["safety_stock_days"]
    plan["reorder_point"] = (plan["avg_daily_demand"] * horizon).round(6).apply(math.ceil)
    plan["days_of_cover"] = plan.apply(
        lambda r: round(r["on_hand"] / r["avg_daily_demand"], 1) if r["avg_daily_demand"] else None, axis=1
    )
    plan["needs_reorder"] = plan["on_hand"] <= plan["reorder_point"]
    target = (plan["avg_daily_demand"] * (horizon + cover_days)).round(6).apply(math.ceil)
    plan["suggested_order_qty"] = (target - plan["on_hand"]).clip(lower=0).where(plan["needs_reorder"], 0)
    return plan.sort_values(["needs_reorder", "days_of_cover"], ascending=[False, True]).reset_index(drop=True)
