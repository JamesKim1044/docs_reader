"""LLM provider backends and selection.

Selection order when no explicit provider is chosen: open-source (OpenAI-compatible)
first, then Gemini, then Claude.  Gemini/Claude are normally reached only via
low-confidence escalation, not as the default extraction path.
"""

from __future__ import annotations

from typing import Optional

from ..config import ProviderName, Settings
from .base import ExtractionResult, LLMBackend


def build_backend(name: ProviderName, settings: Settings) -> LLMBackend:
    """Instantiate a backend by name. Imports are lazy so optional SDKs are only
    required when that provider is actually used."""
    if name == "opensource":
        from .openai_compat import OpenAICompatBackend

        return OpenAICompatBackend(settings)
    if name == "gemini":
        from .gemini import GeminiBackend

        return GeminiBackend(settings)
    if name == "claude":
        from .claude import ClaudeBackend

        return ClaudeBackend(settings)
    if name == "mock":
        from .mock import MockBackend

        return MockBackend(settings)
    raise ValueError(f"unknown provider: {name}")


def select_backend(settings: Settings) -> LLMBackend:
    """Return the primary extraction backend (default: open-source)."""
    return build_backend(settings.resolved_provider(), settings)


def escalation_backends(settings: Settings) -> list[LLMBackend]:
    """Ordered escalation targets for low-confidence fields: Gemini then Claude,
    but only those with usable credentials."""
    out: list[LLMBackend] = []
    for name in ("gemini", "claude"):
        try:
            backend = build_backend(name, settings)  # type: ignore[arg-type]
        except Exception:
            continue
        if backend.is_available():
            out.append(backend)
    return out


__all__ = [
    "ExtractionResult",
    "LLMBackend",
    "build_backend",
    "select_backend",
    "escalation_backends",
]
