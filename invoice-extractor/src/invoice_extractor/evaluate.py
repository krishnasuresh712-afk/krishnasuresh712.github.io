"""Field-level evaluation of an extractor against labeled invoices.

Usage:
    python -m src.invoice_extractor.evaluate --extractor regex
    python -m src.invoice_extractor.evaluate --extractor claude
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

from .extractors import ClaudeExtractor, RegexExtractor, read_document
from .schema import Invoice
from .validate import check_invoice

ROOT = Path(__file__).resolve().parents[2]
SAMPLES, LABELS = ROOT / "eval" / "samples", ROOT / "eval" / "labels"
SCALAR_FIELDS = ["vendor_name", "invoice_number", "invoice_date", "due_date", "subtotal", "tax", "total"]


def _norm(value):
    if isinstance(value, str):
        return " ".join(value.lower().split())
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    return value


def score(predicted: Invoice | None, expected: Invoice) -> dict[str, bool]:
    fields = SCALAR_FIELDS + ["line_items"]
    if predicted is None:
        return {f: False for f in fields}
    result = {f: _norm(getattr(predicted, f)) == _norm(getattr(expected, f)) for f in SCALAR_FIELDS}
    result["line_items"] = len(predicted.line_items) == len(expected.line_items) and all(
        _norm(p.amount) == _norm(e.amount) and _norm(p.quantity) == _norm(e.quantity)
        for p, e in zip(predicted.line_items, expected.line_items)
    )
    return result


def evaluate(extractor, limit: int | None = None) -> dict:
    docs = sorted(SAMPLES.glob("*.txt"))[:limit]
    per_doc, field_hits = [], {}
    for path in docs:
        expected = Invoice.model_validate_json((LABELS / f"{path.stem}.json").read_text())
        try:
            predicted, error = extractor.extract(read_document(path)), None
        except Exception as exc:
            predicted, error = None, f"{type(exc).__name__}: {exc}"
        fields = score(predicted, expected)
        for f, ok in fields.items():
            field_hits.setdefault(f, []).append(ok)
        per_doc.append(
            {
                "document": path.name,
                "fields_correct": sum(fields.values()),
                "fields_total": len(fields),
                "exact_match": all(fields.values()),
                "validation_issues": check_invoice(predicted) if predicted else ["extraction failed"],
                "error": error,
            }
        )
    n = len(per_doc)
    return {
        "extractor": extractor.name,
        "documents": n,
        "field_accuracy_pct": round(100 * sum(d["fields_correct"] for d in per_doc) / sum(d["fields_total"] for d in per_doc), 1) if n else 0,
        "exact_match_pct": round(100 * sum(d["exact_match"] for d in per_doc) / n, 1) if n else 0,
        "passes_validation_pct": round(100 * sum(not d["validation_issues"] for d in per_doc) / n, 1) if n else 0,
        "by_field_pct": {f: round(100 * sum(v) / len(v), 1) for f, v in field_hits.items()},
        "per_document": per_doc,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extractor", choices=["regex", "claude"], default="regex")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    extractor = ClaudeExtractor() if args.extractor == "claude" else RegexExtractor()
    report = evaluate(extractor, args.limit)

    print(f"\n{report['extractor']} on {report['documents']} invoices")
    print(f"  field accuracy     {report['field_accuracy_pct']}%")
    print(f"  exact-match docs   {report['exact_match_pct']}%")
    print(f"  pass validation    {report['passes_validation_pct']}%")
    print("  by field:")
    for f, pct in report["by_field_pct"].items():
        print(f"    {f:<16}{pct}%")
    out = ROOT / "eval" / f"results_{args.extractor}.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nDetailed results: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
