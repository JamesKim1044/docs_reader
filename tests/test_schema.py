from __future__ import annotations

from docs_reader.schema import load_schema


def test_load_pydantic_schema(schema_py):
    ls = load_schema(schema_py)
    assert ls.model_cls is not None
    assert ls.json_schema["type"] == "object"
    assert "invoice_number" in ls.json_schema["properties"]
    # few-shot sidecar picked up
    assert len(ls.examples) >= 1


def test_load_json_schema(schema_json):
    ls = load_schema(schema_json)
    assert ls.model_cls is None
    assert "total" in ls.json_schema["properties"]


def test_validate_with_pydantic(schema_py):
    ls = load_schema(schema_py)
    out = ls.validate(
        {"invoice_number": "X-1", "total": 10.5, "issue_date": "2024-01-02", "line_items": []}
    )
    assert out["invoice_number"] == "X-1"
    assert out["total"] == 10.5


def test_validate_json_only_passthrough(schema_json):
    ls = load_schema(schema_json)
    out = ls.validate({"total": 3})
    assert out == {"total": 3}
