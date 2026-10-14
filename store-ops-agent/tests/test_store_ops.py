from types import SimpleNamespace

import pandas as pd

from src.store_ops import analytics
from src.store_ops.agent import run_agent


def make_data():
    orders = pd.DataFrame(
        {
            "order_id": ["A", "A", "B", "C"],
            "order_date": pd.to_datetime(["2026-01-01", "2026-01-01", "2026-01-05", "2026-01-10"]),
            "sku": ["S1", "S2", "S1", "S1"],
            "quantity": [2, 1, 1, 3],
            "unit_price": [10.0, 20.0, 10.0, 10.0],
            "unit_cost": [4.0, 15.0, 4.0, 4.0],
        }
    )
    for col, expr in [("revenue", "quantity * unit_price"), ("cogs", "quantity * unit_cost")]:
        orders[col] = orders.eval(expr)
    orders["gross_profit"] = orders["revenue"] - orders["cogs"]
    products = pd.DataFrame(
        {"sku": ["S1", "S2"], "name": ["One", "Two"], "on_hand": [1, 50], "lead_time_days": [10, 10], "safety_stock_days": [5, 5]}
    )
    return orders, products


def test_revenue_summary():
    s = analytics.revenue_summary(make_data()[0])
    assert s["orders"] == 3
    assert s["revenue"] == 80.0
    assert s["gross_profit"] == 41.0
    assert s["gross_margin_pct"] == 51.2


def test_product_performance_sorted_and_shares_sum_to_100():
    perf = analytics.product_performance(*make_data())
    assert list(perf["sku"]) == ["S1", "S2"]
    assert abs(perf["revenue_share_pct"].sum() - 100) < 0.2


def test_reorder_plan_flags_low_stock():
    orders, products = make_data()
    plan = analytics.reorder_plan(orders, products, lookback_days=10, cover_days=10).set_index("sku")
    # S1: 6 units / 10 days = 0.6/day; reorder point = ceil(0.6 * 15) = 9
    assert plan.loc["S1", "reorder_point"] == 9
    assert bool(plan.loc["S1", "needs_reorder"]) is True
    assert plan.loc["S1", "suggested_order_qty"] == 14  # ceil(0.6 * 25) - 1
    assert bool(plan.loc["S2", "needs_reorder"]) is False
    assert plan.loc["S2", "suggested_order_qty"] == 0


class FakeClient:
    """Mimics the Anthropic client: first asks for a tool, then answers."""

    def __init__(self):
        self.calls = 0
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            block = SimpleNamespace(type="tool_use", id="t1", name="reorder_plan", input={"lookback_days": 10})
            return SimpleNamespace(stop_reason="tool_use", content=[block])
        tool_result = kwargs["messages"][-1]["content"][0]
        assert tool_result["type"] == "tool_result" and "S1" in tool_result["content"]
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Reorder S1.")])


def test_agent_loop_runs_tool_and_returns_answer():
    orders, products = make_data()
    result = run_agent("What should I reorder?", orders, products, client=FakeClient())
    assert result.answer == "Reorder S1."
    assert result.tool_calls == [{"tool": "reorder_plan", "input": {"lookback_days": 10}, "error": False}]
