"""Stage C (part 1) — verification via LLM-as-judge.

A judge pass re-reads the document plus the extracted values and rates each field's
correctness/confidence with a short evidence quote. This catches hallucinations and
table misreads that a single extraction pass misses.
"""

from __future__ import annotations

import json
from typing import Any

from ..providers.base import LLMBackend
from ..types import ContentPart
from ._common import top_level_keys

_VERIFY_SCHEMA = {
    "title": "verification",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "correct": {"type": "boolean"},
                    "confidence": {"type": "number"},
                    "evidence": {"type": "string"},
                },
                "required": ["name", "confidence"],
            },
        }
    },
    "required": ["fields"],
}


def verify_fields(
    backend: LLMBackend,
    parts: list[ContentPart],
    schema_json: dict[str, Any],
    extracted: dict[str, Any],
) -> tuple[dict[str, float], dict[str, str]]:
    """Return (per_field_confidence, per_field_evidence)."""
    field_names = top_level_keys(schema_json, [extracted])
    instruction = (
        "You are verifying a structured extraction against the source document.\n"
        "For EACH field below, decide whether the extracted value is correct and actually "
        "supported by the document. Return confidence in [0,1] (1 = clearly correct, "
        "0 = wrong or unsupported) and a short evidence quote from the document.\n\n"
        f"Fields to check: {', '.join(field_names)}\n\n"
        "Extracted values:\n" + json.dumps(extracted, ensure_ascii=False, indent=2) + "\n\n"
        "Return JSON: " + json.dumps(_VERIFY_SCHEMA) + "\n\n"
        "Document content follows:"
    )
    try:
        verdict = backend.complete_json(parts, _VERIFY_SCHEMA, instruction, temperature=0.0)
    except Exception:
        # Verification is best-effort; on failure, don't block extraction.
        return {}, {}

    conf: dict[str, float] = {}
    evidence: dict[str, str] = {}
    for item in verdict.get("fields", []) or []:
        name = item.get("name")
        if not name:
            continue
        c = item.get("confidence")
        if item.get("correct") is False and c is None:
            c = 0.0
        if c is not None:
            try:
                conf[name] = max(0.0, min(1.0, float(c)))
            except (TypeError, ValueError):
                pass
        ev = item.get("evidence")
        if ev:
            evidence[name] = str(ev)
    return conf, evidence
