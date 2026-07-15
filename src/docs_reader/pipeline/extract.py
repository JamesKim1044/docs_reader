"""Stage B — structured extraction with self-consistency.

Runs N extraction passes (temperature diversified for N>1) and votes per top-level
field. The agreement ratio becomes a first confidence signal, later combined with the
Stage C verification score.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from ..providers.base import LLMBackend
from ..schema import LoadedSchema
from ..types import ContentPart
from ._common import top_level_keys


def _norm_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def vote(results: list[dict[str, Any]], schema: dict[str, Any]) -> tuple[dict[str, Any], dict[str, float]]:
    """Majority-vote each top-level field across sample results.

    Returns (merged_data, per_field_agreement_confidence).
    """
    n = len(results) or 1
    keys = top_level_keys(schema, results)
    merged: dict[str, Any] = {}
    confidence: dict[str, float] = {}
    for k in keys:
        present = [r[k] for r in results if isinstance(r, dict) and k in r]
        if not present:
            merged[k] = None
            confidence[k] = 0.0
            continue
        groups: dict[str, list[Any]] = defaultdict(list)
        for v in present:
            groups[_norm_key(v)].append(v)
        best = max(groups.values(), key=len)
        merged[k] = best[0]
        confidence[k] = len(best) / n
    return merged, confidence


def extract_consistent(
    backend: LLMBackend,
    parts: list[ContentPart],
    schema: LoadedSchema,
    instruction: str,
    *,
    samples: int = 1,
    base_temperature: float = 0.0,
) -> tuple[dict[str, Any], dict[str, float], list[dict[str, Any]], str | None]:
    samples = max(1, samples)
    raw_results: list[dict[str, Any]] = []
    model: str | None = None
    for i in range(samples):
        # Single pass: honor base temperature. Multiple passes: diversify to make
        # self-consistency meaningful.
        temp = base_temperature if samples == 1 else min(0.8, 0.2 + 0.2 * i)
        res = backend.extract(
            parts, schema.json_schema, instruction, model_cls=schema.model_cls, temperature=temp
        )
        model = res.model or model
        raw_results.append(res.data if isinstance(res.data, dict) else {})
    merged, confidence = vote(raw_results, schema.json_schema)
    return merged, confidence, raw_results, model
