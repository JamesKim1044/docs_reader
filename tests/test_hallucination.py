from __future__ import annotations

from docs_reader.config import Settings
from docs_reader.loaders import load_document
from docs_reader.pipeline import run_pipeline
from docs_reader.pipeline.hallucination import control, is_grounded
from docs_reader.providers.mock import MockBackend
from docs_reader.schema import load_schema

SOURCE = "TAX INVOICE  공급자: (주)아크메  합계금액 99,000원  Total: 90.00 USD"


def test_is_grounded_strings_and_numbers():
    src = "".join(SOURCE.split()).lower()
    assert is_grounded("(주)아크메", src)
    assert not is_grounded("Ghost Corp", src)
    assert is_grounded(99000, src)      # matches "99,000"
    assert is_grounded(90.0, src)       # matches "90.00"
    assert not is_grounded(12345, src)
    assert is_grounded(None, src)
    assert is_grounded("x", src)        # too short -> not judged


def test_control_drops_judge_unsupported():
    data = {"a": "Acme", "b": "value"}
    clean, dropped = control(data, {"a": 0.1}, "value is here", threshold=0.5, require_grounding=False)
    assert clean["a"] is None
    assert clean["b"] == "value"
    assert dropped[0]["field"] == "a" and "judge_unsupported" in dropped[0]["reasons"][0]


def test_control_drops_ungrounded():
    data = {"name": "Nonexistent Corp"}
    clean, dropped = control(data, {}, SOURCE, threshold=0.5, require_grounding=True)
    assert clean["name"] is None
    assert dropped[0]["reasons"] == ["not_in_source"]


def test_control_keeps_grounded_and_confirmed():
    data = {"supplier": "(주)아크메", "total": 99000}
    clean, dropped = control(data, {"supplier": 1.0, "total": 1.0}, SOURCE, threshold=0.5)
    assert clean == data
    assert dropped == []


def test_control_skips_when_no_source():
    # pure-vision route: no text to ground against -> rely on judge only
    data = {"x": "anything"}
    clean, dropped = control(data, {}, "", threshold=0.5, require_grounding=True)
    assert clean["x"] == "anything"
    assert dropped == []


def test_pipeline_drops_hallucinated_field(text_pdf, schema_py):
    s = Settings()
    s.verify = True
    schema = load_schema(schema_py)
    loaded = load_document(text_pdf, s)
    # extraction hallucinates supplier_name; judge flags it; grounding also fails.
    mock = MockBackend(responses=[
        {"invoice_number": "INV-2024-0091", "supplier_name": "Ghost Corp", "total": 99.0, "line_items": []},
        {"fields": [
            {"name": "supplier_name", "correct": False, "confidence": 0.1},
            {"name": "invoice_number", "correct": True, "confidence": 1.0},
        ]},
    ])
    out = run_pipeline(loaded, schema, s, backend=mock)
    assert out.data["supplier_name"] is None            # hallucination removed
    assert out.data["invoice_number"] == "INV-2024-0091"  # grounded value kept
    dropped = {d["field"] for d in out.meta["dropped_hallucinations"]}
    assert "supplier_name" in dropped


def test_pipeline_keep_flag_disables_control(text_pdf, schema_py):
    s = Settings()
    s.verify = True
    s.drop_hallucinations = False
    schema = load_schema(schema_py)
    loaded = load_document(text_pdf, s)
    mock = MockBackend(responses=[
        {"supplier_name": "Ghost Corp", "line_items": []},
        {"fields": [{"name": "supplier_name", "correct": False, "confidence": 0.1}]},
    ])
    out = run_pipeline(loaded, schema, s, backend=mock)
    assert out.data["supplier_name"] == "Ghost Corp"  # kept when control disabled
