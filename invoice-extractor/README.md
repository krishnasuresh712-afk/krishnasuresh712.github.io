# Invoice Extractor

Turns invoice text or PDFs into validated, structured data for an accounts payable workflow, and measures how accurate the extraction is against labeled examples.

Two extractors sit behind one interface so they can be compared on the same documents:

- **Regex baseline** (`RegexExtractor`): a rules-based parser for one known layout, representing the "before" state at many companies.
- **Claude extractor** (`ClaudeExtractor`): forces a tool call whose input schema is the `Invoice` Pydantic model, so output is always structured and schema-validated.

Business-rule checks (`validate.check_invoice`) run on either extractor's output: line quantity x price = amount, line items sum to subtotal, subtotal + tax = total, due date not before invoice date.

## Evaluation set

`eval/samples/` holds 24 **synthetic** invoices in three layouts (8 each): a spaced text table, an "INVOICE / From:" layout, and a pipe-table layout with the vendor on a "Remit to:" line. `eval/labels/` holds the hand-built ground truth. All vendors and amounts are made up.

## Results

Regex baseline, measured by `python -m src.invoice_extractor.evaluate --extractor regex` on all 24 invoices:

| Metric | Regex baseline | Claude |
|---|---|---|
| Field accuracy | 33.3% | _run `--extractor claude` and fill in_ |
| Exact-match invoices | 33.3% | _run `--extractor claude` and fill in_ |
| Pass validation | 33.3% | _run `--extractor claude` and fill in_ |

The baseline only parses layout A, which is why it tops out at one third. The Claude column is intentionally blank until the evaluation has been run with a real API key.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # add ANTHROPIC_API_KEY
pytest
python -m src.invoice_extractor.evaluate --extractor regex
python -m src.invoice_extractor.evaluate --extractor claude
python -m src.invoice_extractor.cli eval/samples/invoice_02.txt --extractor claude
```

Detailed per-document results are written to `eval/results_<extractor>.json`.

## Tests

`tests/test_invoice_extractor.py` checks that labels are internally consistent, that validation catches a bad total, that the baseline parses layout A exactly, and that the Claude extractor sends a forced tool call and parses the result (against a fake client, so no API key is needed).
