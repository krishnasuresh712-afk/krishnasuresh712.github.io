"""Two extractors behind one interface so they can be evaluated side by side.

- RegexExtractor: a rules-based baseline, the "before" state at many clients.
- ClaudeExtractor: forces a tool call whose input schema is the Invoice model,
  so the output is always structured and validated by Pydantic.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from .schema import Invoice, LineItem, tool_schema

DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")


class Extractor(Protocol):
    name: str

    def extract(self, text: str) -> Invoice: ...


def read_document(path: str | Path) -> str:
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    return path.read_text()


def _money(s: str) -> Decimal:
    return Decimal(re.sub(r"[^\d.\-]", "", s))


def _date(s: str):
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%d %b %Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date: {s!r}")


class RegexExtractor:
    """Handles one known layout. Breaks on anything else, which is the point of the comparison."""

    name = "regex-baseline"

    def extract(self, text: str) -> Invoice:
        def grab(pattern: str) -> str:
            m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if not m:
                raise ValueError(f"pattern not found: {pattern}")
            return m.group(1).strip()

        items = [
            LineItem(description=d.strip(), quantity=Decimal(q), unit_price=_money(p), amount=_money(a))
            for d, q, p, a in re.findall(r"^\s*(.+?)\s{2,}(\d+)\s{2,}\$?([\d,]+\.\d{2})\s{2,}\$?([\d,]+\.\d{2})\s*$", text, re.MULTILINE)
        ]
        due = re.search(r"^Due Date:\s*(.+)$", text, re.MULTILINE)
        return Invoice(
            vendor_name=text.strip().splitlines()[0].strip(),
            invoice_number=grab(r"^Invoice #:\s*(\S+)"),
            invoice_date=_date(grab(r"^Invoice Date:\s*(.+)$")),
            due_date=_date(due.group(1)) if due else None,
            line_items=items,
            subtotal=_money(grab(r"^Subtotal:\s*(.+)$")),
            tax=_money(grab(r"^Tax[^:]*:\s*(.+)$")),
            total=_money(grab(r"^Total(?: Due)?:\s*(.+)$")),
        )


SYSTEM_PROMPT = """You extract structured data from invoices for an accounts payable system.
Copy values exactly as printed. Use ISO dates (YYYY-MM-DD). Amounts are plain numbers
without currency symbols or thousands separators. If a field is absent, use null where
the schema allows it. Do not compute values that are not printed, except currency, which
defaults to USD when no other currency is indicated."""


class ClaudeExtractor:
    name = "claude"

    def __init__(self, client=None, model: str = DEFAULT_MODEL):
        if client is None:
            from anthropic import Anthropic

            client = Anthropic()
        self.client = client
        self.model = model

    def extract(self, text: str) -> Invoice:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=[{"name": "record_invoice", "description": "Record the extracted invoice.", "input_schema": tool_schema()}],
            tool_choice={"type": "tool", "name": "record_invoice"},
            messages=[{"role": "user", "content": f"<invoice>\n{text}\n</invoice>"}],
        )
        block = next(b for b in response.content if b.type == "tool_use")
        return Invoice.model_validate(block.input)
