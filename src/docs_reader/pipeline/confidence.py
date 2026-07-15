"""Stage C (part 2) — confidence combination and low-confidence gating.

Fields below the confidence threshold are re-checked by cross-examining escalation
backends (Gemini, then Claude) on a reduced schema containing only those fields, then
voting across the primary + escalation values. Escalation only runs when explicitly
enabled, so an all-open-source run never calls a commercial API.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from ..providers._common import build_instruction
from ..providers.base import LLMBackend
from ..schema import LoadedSchema
from ..types import ContentPart
from ._common import reduced_schema


def combine_confidence(
    agreement: dict[str, float], verify: dict[str, float]
) -> dict[str, float]:
    """Blend self-consistency agreement with the verifier score.

    If only one signal exists, use it; if both, weight the verifier higher (it looks
    at the source, agreement only measures internal stability)."""
    keys = set(agreement) | set(verify)
    out: dict[str, float] = {}
    for k in keys:
        a = agreement.get(k)
        v = verify.get(k)
        if a is not None and v is not None:
            out[k] = round(0.35 * a + 0.65 * v, 4)
        elif v is not None:
            out[k] = round(v, 4)
        elif a is not None:
            out[k] = round(a, 4)
        else:
            out[k] = 1.0
    return out


def _norm(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def gate_and_recheck(
    parts: list[ContentPart],
    schema: LoadedSchema,
    data: dict[str, Any],
    confidence: dict[str, float],
    *,
    min_confidence: float,
    escalation_backends: list[LLMBackend],
) -> tuple[dict[str, Any], dict[str, float], list[dict[str, Any]]]:
    """Re-check low-confidence fields via escalation backends and re-vote."""
    low = [f for f, c in confidence.items() if c < min_confidence]
    audit: list[dict[str, Any]] = []
    if not low or not escalation_backends:
        return data, confidence, audit

    sub_schema = reduced_schema(schema.json_schema, low)
    instruction = build_instruction(
        sub_schema, schema.examples, extra="Extract ONLY the listed fields, precisely."
    )

    values: dict[str, list[Any]] = {f: [data.get(f)] for f in low}
    sources: dict[str, list[str]] = {f: ["primary"] for f in low}
    for backend in escalation_backends:
        try:
            res = backend.extract(parts, sub_schema, instruction, model_cls=None, temperature=0.0)
        except Exception as e:  # noqa: BLE001
            audit.append({"backend": getattr(backend, "name", "?"), "error": str(e)})
            continue
        audit.append({"backend": backend.name, "fields": low, "data": res.data})
        for f in low:
            if isinstance(res.data, dict) and f in res.data:
                values[f].append(res.data[f])
                sources[f].append(backend.name)

    for f in low:
        vals = values[f]
        groups: dict[str, list[int]] = defaultdict(list)
        for idx, v in enumerate(vals):
            groups[_norm(v)].append(idx)
        best = max(groups.values(), key=len)
        data[f] = vals[best[0]]
        confidence[f] = round(len(best) / len(vals), 4)
    return data, confidence, audit
