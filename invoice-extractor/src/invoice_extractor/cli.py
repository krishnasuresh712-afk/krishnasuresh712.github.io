"""Extract one invoice to JSON and report validation issues.

Usage: python -m src.invoice_extractor.cli path/to/invoice.pdf [--extractor claude|regex]
"""
import argparse
import json
import sys

from .extractors import ClaudeExtractor, RegexExtractor, read_document
from .validate import check_invoice


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--extractor", choices=["claude", "regex"], default="claude")
    args = parser.parse_args()

    extractor = ClaudeExtractor() if args.extractor == "claude" else RegexExtractor()
    invoice = extractor.extract(read_document(args.path))
    issues = check_invoice(invoice)
    print(json.dumps({"invoice": invoice.model_dump(mode="json"), "validation_issues": issues}, indent=2))
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()
