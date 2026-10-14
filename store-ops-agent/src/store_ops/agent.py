"""Claude tool-calling agent over the deterministic analytics functions."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import pandas as pd

from . import analytics

DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")

SYSTEM_PROMPT = """You are an operations analyst for a small e-commerce store.
Answer questions using ONLY the numbers returned by your tools. Never estimate or
compute figures yourself. If a tool does not cover the question, say so.
Be concise: lead with the answer, then the 2-3 numbers that support it, then one
recommended action when relevant."""

TOOLS = [
    {
        "name": "revenue_summary",
        "description": "Totals for the whole period: orders, units, revenue, COGS, gross profit, gross margin, average order value.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "product_performance",
        "description": "Per-product units, revenue, gross profit, margin and revenue share, sorted by revenue.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "weekly_trend",
        "description": "Revenue and order count by week with week-over-week percent change.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "reorder_plan",
        "description": "Inventory position per product: average daily demand, reorder point, days of cover, whether it needs reorder, and suggested order quantity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lookback_days": {"type": "integer", "minimum": 7, "maximum": 180, "description": "Days of history used to estimate demand (default 60)."},
                "cover_days": {"type": "integer", "minimum": 0, "maximum": 120, "description": "Extra days of demand to cover beyond lead time and safety stock (default 30)."},
            },
            "additionalProperties": False,
        },
    },
]


def _to_json(result) -> str:
    if isinstance(result, pd.DataFrame):
        return result.to_json(orient="records")
    return json.dumps(result, default=str)


def dispatch(name: str, args: dict, orders: pd.DataFrame, products: pd.DataFrame) -> str:
    if name == "revenue_summary":
        return _to_json(analytics.revenue_summary(orders))
    if name == "product_performance":
        return _to_json(analytics.product_performance(orders, products))
    if name == "weekly_trend":
        return _to_json(analytics.weekly_trend(orders))
    if name == "reorder_plan":
        return _to_json(analytics.reorder_plan(orders, products, **args))
    raise ValueError(f"Unknown tool: {name}")


@dataclass
class AgentResult:
    answer: str
    tool_calls: list[dict] = field(default_factory=list)


def run_agent(question: str, orders, products, client=None, model: str = DEFAULT_MODEL, max_turns: int = 6) -> AgentResult:
    if client is None:
        from anthropic import Anthropic  # imported lazily so analytics works without the SDK

        client = Anthropic()

    messages = [{"role": "user", "content": question}]
    calls: list[dict] = []
    for _ in range(max_turns):
        response = client.messages.create(
            model=model, max_tokens=1500, system=SYSTEM_PROMPT, tools=TOOLS, messages=messages
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            text = "".join(block.text for block in response.content if block.type == "text")
            return AgentResult(answer=text.strip(), tool_calls=calls)

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                output, is_error = dispatch(block.name, dict(block.input), orders, products), False
            except Exception as exc:  # report tool errors back to the model instead of crashing
                output, is_error = f"Tool error: {exc}", True
            calls.append({"tool": block.name, "input": dict(block.input), "error": is_error})
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": output, "is_error": is_error})
        messages.append({"role": "user", "content": results})

    raise RuntimeError(f"Agent did not finish within {max_turns} turns")
