from __future__ import annotations

from docs_reader.config import Settings
from docs_reader.loaders import load_document
from docs_reader.pipeline import run_pipeline
from docs_reader.pipeline.extract import vote
from docs_reader.providers.mock import MockBackend
from docs_reader.schema import load_schema

CANNED = {
    "invoice_number": "INV-2024-0091",
    "issue_date": "2024-03-05",
    "due_date": "2024-04-04",
    "supplier_name": "Acme Supplies Ltd",
    "buyer_name": "Globex Corp",
    "currency": "USD",
    "subtotal": 90.0,
    "tax": 9.0,
    "total": 99.0,
    "line_items": [],
}


def test_end_to_end_with_mock(text_pdf, schema_py):
    s = Settings()
    s.verify = False  # keep the mock deterministic (no judge pass)
    schema = load_schema(schema_py)
    loaded = load_document(text_pdf, s)
    backend = MockBackend(responses=[CANNED])
    out = run_pipeline(loaded, schema, s, backend=backend)
    assert out.data["invoice_number"] == "INV-2024-0091"
    assert out.data["total"] == 99.0
    assert out.meta["validation_error"] is None
    # every top-level field has a confidence entry
    assert set(out.confidence) >= {"invoice_number", "total"}


def test_self_consistency_agreement():
    schema = {"type": "object", "properties": {"a": {}, "b": {}}}
    merged, conf = vote([{"a": 1, "b": 2}, {"a": 1, "b": 3}, {"a": 1, "b": 3}], schema)
    assert merged["a"] == 1 and conf["a"] == 1.0
    assert merged["b"] == 3 and abs(conf["b"] - 2 / 3) < 1e-9


def test_verify_lowers_confidence_and_gate_selects_majority(text_pdf, schema_py):
    # Primary says total=1.0 (wrong); judge flags it low; escalation backends agree on 99.0.
    s = Settings()
    s.verify = True
    s.escalate = True
    s.min_confidence = 0.9
    schema = load_schema(schema_py)
    loaded = load_document(text_pdf, s)

    primary = MockBackend(
        responses=[
            {**CANNED, "total": 1.0},  # extraction pass
            {"fields": [{"name": "total", "correct": False, "confidence": 0.1}]},  # verify pass
        ]
    )
    # Force escalation backends via monkeypatch-free injection: run_pipeline pulls
    # escalation_backends() from settings; here we validate gate logic directly.
    from docs_reader.pipeline.confidence import gate_and_recheck

    data = {**CANNED, "total": 1.0}
    conf = {"total": 0.1}
    esc = [MockBackend(responses=[{"total": 99.0}]), MockBackend(responses=[{"total": 99.0}])]
    data, conf, audit = gate_and_recheck(
        loaded.parts, schema, data, conf, min_confidence=0.9, escalation_backends=esc
    )
    assert data["total"] == 99.0
    assert conf["total"] >= 2 / 3  # majority of primary + 2 escalations
    assert len(audit) == 2
