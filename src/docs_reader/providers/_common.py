"""Shared helpers for provider backends: prompt assembly and lenient JSON parsing."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from ..types import ContentPart

SYSTEM_PROMPT = (
    "You are a meticulous document information-extraction engine. "
    "Extract the requested fields strictly from the provided document content. "
    "Rules:\n"
    "- Return ONLY a JSON object matching the given JSON Schema.\n"
    "- Ground every value in the document text. Copy values verbatim from the source.\n"
    "- ABSTAIN when unsure: if a field is not explicitly stated in the document, or you are "
    "not certain, return null. A null is always better than a guessed or inferred value.\n"
    "- Never invent, infer, complete, or reformat values that are not present in the text. "
    "Do not fill fields from world knowledge or from what a typical document would contain.\n"
    "- Normalize dates to YYYY-MM-DD only when the date is actually present.\n"
    "- For tables, keep row/column associations correct.\n"
)


def build_instruction(
    json_schema: dict[str, Any],
    examples: Optional[list[dict[str, Any]]] = None,
    extra: str = "",
) -> str:
    """Assemble the user-facing instruction text (schema + few-shot + extra)."""
    parts: list[str] = []
    parts.append(
        "Extract the fields defined by this JSON Schema and return a single JSON object:\n"
        + json.dumps(json_schema, ensure_ascii=False, indent=2)
    )
    if examples:
        parts.append("\nExamples of correct extraction:")
        for ex in examples[:3]:
            inp = ex.get("input")
            out = ex.get("output", ex)
            if inp is not None:
                parts.append("INPUT:\n" + str(inp))
            parts.append("OUTPUT:\n" + json.dumps(out, ensure_ascii=False))
    if extra:
        parts.append("\n" + extra)
    parts.append("\nNow extract from the following document:")
    return "\n".join(parts)


def parse_json_lenient(text: str) -> dict[str, Any]:
    """Parse a JSON object out of a model response that may include prose/fences."""
    if text is None:
        raise ValueError("empty model response")
    s = text.strip()
    # Strip markdown code fences.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, re.DOTALL)
    if fence:
        s = fence.group(1).strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        # Fall back to the first balanced {...} span.
        start = s.find("{")
        end = s.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError(f"no JSON object found in response: {s[:200]!r}")
        obj = json.loads(s[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError(f"expected a JSON object, got {type(obj).__name__}")
    return obj


def split_parts(parts: list[ContentPart]) -> tuple[str, list[ContentPart]]:
    """Return (concatenated_text, image_parts)."""
    text_chunks: list[str] = []
    images: list[ContentPart] = []
    for p in parts:
        if p.kind == "text" and p.text:
            header = f"\n--- page {p.page} ---\n" if p.page else ""
            text_chunks.append(header + p.text)
        elif p.kind == "image":
            images.append(p)
    return "\n".join(text_chunks).strip(), images
