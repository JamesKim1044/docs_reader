"""OCR engine interface and the null (no-op) fallback."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class OCREngine(Protocol):
    name: str
    available: bool

    def image_to_text(self, image_bytes: bytes) -> str:
        """Return recognized text (ideally Markdown) for a single page image."""
        ...


class NullOCR:
    """No OCR available. Signals callers to fall back to the vision path."""

    name = "none"
    available = False

    def image_to_text(self, image_bytes: bytes) -> str:  # noqa: ARG002
        return ""
