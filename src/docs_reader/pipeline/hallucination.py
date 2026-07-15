"""Hallucination control.

Turns the verification stage from advisory into an active filter, and adds a
deterministic source-grounding guard:

1. **Judge suppression** — if the verify pass judged a field unsupported by the
   document (verify confidence < threshold), drop the value (set null / []).
2. **Source grounding** — for scalar values, check the value actually appears in the
   source text/OCR. Values with no textual support (and not judge-confirmed) are
   dropped as likely hallucinations.

Grounding is skipped when there is no source text (pure-vision route) — the judge
pass is the guard there.
"""

from __future__ import annotations

import re
from typing import Any, Optional

_CONFIRM = 0.8  # a value the judge is this confident about survives a failed grounding


def _norm(s: Any) -> str:
    return re.sub(r"\s+", "", str(s)).lower()


def _number_forms(v: float) -> set[str]:
    forms: set[str] = set()
    try:
        f = float(v)
    except (TypeError, ValueError):
        return {_norm(v)}
    if f.is_integer():
        i = int(f)
        forms.update({str(i), f"{i:,}"})
    forms.update({str(v), str(f), (f"{f:.2f}")})
    return {_norm(x) for x in forms}


def is_grounded(value: Any, source_norm: str) -> bool:
    """Whether a scalar value has textual support in the (whitespace-stripped) source."""
    if value is None or isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return any(nf in source_norm for nf in _number_forms(value))
    if isinstance(value, str):
        nv = _norm(value)
        if len(nv) < 2:  # too short to judge reliably
            return True
        return nv in source_norm
    return True  # lists/dicts: handled per-element by the judge, not here


def _is_empty(v: Any) -> bool:
    return v is None or (isinstance(v, (str, list, dict)) and len(v) == 0)


def control(
    data: dict[str, Any],
    verify_conf: dict[str, float],
    source_text: str,
    *,
    threshold: float = 0.5,
    require_grounding: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Drop hallucinated field values. Returns (cleaned_data, dropped_records)."""
    source_norm = _norm(source_text) if source_text else ""
    clean = dict(data)
    dropped: list[dict[str, Any]] = []

    for k, v in list(data.items()):
        if _is_empty(v):
            continue
        reasons: list[str] = []
        vc: Optional[float] = verify_conf.get(k)

        if vc is not None and vc < threshold:
            reasons.append(f"judge_unsupported({vc:.2f})")

        if (
            require_grounding
            and source_norm
            and not isinstance(v, (list, dict))
            and not is_grounded(v, source_norm)
            and (vc is None or vc < _CONFIRM)
        ):
            reasons.append("not_in_source")

        if reasons:
            clean[k] = [] if isinstance(v, list) else None
            dropped.append({"field": k, "value": v, "reasons": reasons})

    return clean, dropped
