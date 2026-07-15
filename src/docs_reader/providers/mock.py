"""Deterministic mock backend for tests and offline `--dry-run`-style smoke checks.

Behavior (in priority order):
1. Scripted responses passed to the constructor (popped per call, then last repeats).
2. ``DOCS_READER_MOCK_JSON`` env var: inline JSON or a path to a JSON file.
3. A schema-shaped skeleton (all scalars null, arrays empty).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

from ..config import Settings
from ..types import ContentPart
from .base import ExtractionResult


def _skeleton(schema: dict[str, Any]) -> Any:
    t = schema.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), t[0])
    if t == "object":
        return {k: _skeleton(v) for k, v in schema.get("properties", {}).items()}
    if t == "array":
        return []
    return None


class MockBackend:
    name = "mock"

    def __init__(self, settings: Optional[Settings] = None, responses: Optional[list[dict]] = None):
        self._settings = settings
        self._responses = list(responses or [])
        self._i = 0

    def is_available(self) -> bool:
        return True

    def _next_scripted(self) -> Optional[dict[str, Any]]:
        if self._responses:
            resp = self._responses[min(self._i, len(self._responses) - 1)]
            self._i += 1
            return resp
        env = os.environ.get("DOCS_READER_MOCK_JSON")
        if env:
            p = Path(env)
            raw = p.read_text(encoding="utf-8") if p.exists() else env
            return json.loads(raw)
        return None

    def extract(
        self,
        parts: list[ContentPart],
        json_schema: dict[str, Any],
        instruction: str,
        *,
        model_cls: Optional[type[BaseModel]] = None,
        temperature: float = 0.0,
    ) -> ExtractionResult:
        data = self._next_scripted()
        if data is None:
            data = _skeleton(json_schema)
        return ExtractionResult(data=data, raw=json.dumps(data), model="mock", provider=self.name)

    def complete_json(self, parts, json_schema, instruction, *, temperature: float = 0.0):
        data = self._next_scripted()
        if data is None:
            data = _skeleton(json_schema)
        return data
