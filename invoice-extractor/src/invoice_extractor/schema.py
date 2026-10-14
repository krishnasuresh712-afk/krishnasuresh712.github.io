from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str
    quantity: Decimal = Field(description="Number of units")
    unit_price: Decimal
    amount: Decimal = Field(description="Line total as printed on the invoice")


class Invoice(BaseModel):
    vendor_name: str
    invoice_number: str
    invoice_date: date
    due_date: date | None = None
    currency: str = Field(default="USD", description="ISO 4217 code, e.g. USD")
    line_items: list[LineItem]
    subtotal: Decimal
    tax: Decimal = Decimal("0")
    total: Decimal


def tool_schema() -> dict:
    """JSON schema handed to Claude as the input schema of a forced tool call."""
    return Invoice.model_json_schema()
