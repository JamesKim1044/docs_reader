"""Provider-neutral backend interface.

A backend turns normalized :class:`ContentPart` list + a JSON Schema into a
schema-shaped ``dict``.  It also exposes a generic ``complete_json`` used by the
verification / judging stage, so the pipeline can run arbitrary extra LLM passes
for quality without any provider-specific code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable

from pydantic import BaseModel

from ..types import ContentPart


@dataclass
class ExtractionResult:
    """Output of one extraction pass."""

    data: dict[str, Any]
    raw: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    usage: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LLMBackend(Protocol):
    name: str

    def is_available(self) -> bool:
        """Whether this backend has the credentials / endpoint it needs."""
        ...

    def extract(
        self,
        parts: list[ContentPart],
        json_schema: dict[str, Any],
        instruction: str,
        *,
        model_cls: Optional[type[BaseModel]] = None,
        temperature: float = 0.0,
    ) -> ExtractionResult:
        """Run one structured-extraction pass, returning schema-shaped data."""
        ...

    def complete_json(
        self,
        parts: list[ContentPart],
        json_schema: dict[str, Any],
        instruction: str,
        *,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """Generic JSON completion against an arbitrary schema (used by the
        verification / re-check passes)."""
        ...
