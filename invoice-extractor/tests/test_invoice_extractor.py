from decimal import Decimal
from types import SimpleNamespace

from src.invoice_extractor.evaluate import LABELS, SAMPLES, evaluate, score
from src.invoice_extractor.extractors import ClaudeExtractor, RegexExtractor
from src.invoice_extractor.schema import Invoice
from src.invoice_extractor.validate import check_invoice


def label(name: str) -> Invoice:
    return Invoice.model_validate_json((LABELS / f"{name}.json").read_text())


def test_labels_are_internally_consistent():
    for path in LABELS.glob("*.json"):
        assert check_invoice(label(path.stem)) == [], path.name


def test_validation_catches_bad_total():
    inv = label("invoice_01").model_copy(update={"total": Decimal("1.00")})
    assert any("total" in issue for issue in check_invoice(inv))


def test_regex_baseline_handles_layout_a_exactly():
    predicted = RegexExtractor().extract((SAMPLES / "invoice_01.txt").read_text())
    assert all(score(predicted, label("invoice_01")).values())


def test_score_marks_failed_extraction_all_wrong():
    assert not any(score(None, label("invoice_01")).values())


def test_claude_extractor_parses_forced_tool_call():
    expected = label("invoice_02")

    def create(**kwargs):
        assert kwargs["tool_choice"] == {"type": "tool", "name": "record_invoice"}
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=expected.model_dump(mode="json"))])

    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    predicted = ClaudeExtractor(client=client).extract((SAMPLES / "invoice_02.txt").read_text())
    assert predicted == expected


def test_eval_report_shape_and_baseline_gap():
    report = evaluate(RegexExtractor())
    assert report["documents"] == 24
    # Baseline only knows layout A (1 in 3 docs), leaving clear room for the LLM extractor.
    assert report["exact_match_pct"] < 50
    assert set(report["by_field_pct"]) >= {"vendor_name", "total", "line_items"}
