"""Serialize extraction results to JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

from .pipeline import ExtractionOutput


def to_dict(output: ExtractionOutput, *, include_meta: bool) -> dict[str, Any]:
    if not include_meta:
        return output.data
    return {
        "data": output.data,
        "confidence": output.confidence,
        "evidence": output.evidence,
        "meta": {
            "source_path": output.source_path,
            "provider": output.provider,
            "model": output.model,
            "route": output.route,
            **output.meta,
        },
        "passes": output.passes,
    }


def to_json(output: ExtractionOutput, *, include_meta: bool = True, indent: int = 2) -> str:
    return json.dumps(
        to_dict(output, include_meta=include_meta), ensure_ascii=False, indent=indent, default=str
    )


def write_output(
    output: ExtractionOutput,
    path: Optional[str | Path],
    *,
    include_meta: bool = True,
) -> None:
    text = to_json(output, include_meta=include_meta)
    if path is None or str(path) == "-":
        sys.stdout.write(text + "\n")
    else:
        Path(path).write_text(text + "\n", encoding="utf-8")
