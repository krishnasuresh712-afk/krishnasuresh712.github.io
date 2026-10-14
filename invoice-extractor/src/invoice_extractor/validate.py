"""Business-rule checks that catch extraction errors before data reaches a downstream system."""
from __future__ import annotations

from decimal import Decimal

from .schema import Invoice

TOLERANCE = Decimal("0.01")


def check_invoice(inv: Invoice) -> list[str]:
    issues: list[str] = []
    for i, item in enumerate(inv.line_items, start=1):
        if abs(item.quantity * item.unit_price - item.amount) > TOLERANCE:
            issues.append(f"line {i}: quantity x unit price ({item.quantity * item.unit_price}) != amount ({item.amount})")
    line_sum = sum((item.amount for item in inv.line_items), Decimal("0"))
    if abs(line_sum - inv.subtotal) > TOLERANCE:
        issues.append(f"line items sum to {line_sum}, subtotal is {inv.subtotal}")
    if abs(inv.subtotal + inv.tax - inv.total) > TOLERANCE:
        issues.append(f"subtotal + tax ({inv.subtotal + inv.tax}) != total ({inv.total})")
    if inv.due_date and inv.due_date < inv.invoice_date:
        issues.append("due date is before invoice date")
    if not inv.line_items:
        issues.append("no line items extracted")
    return issues
