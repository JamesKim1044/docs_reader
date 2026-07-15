"""Core, provider-neutral data types shared across loaders, providers and pipeline.

Everything a loader produces is normalized into a list of :class:`ContentPart`
(``text`` or ``image``).  Each provider backend knows how to turn those parts into
its own message/content format, so the rest of the codebase never depends on a
specific vendor SDK.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

PartKind = Literal["text", "image"]
Route = Literal["text", "vision", "ocr"]


@dataclass
class ContentPart:
    """A single provider-neutral piece of document content.

    - ``kind="text"``: ``text`` holds the (possibly Markdown) string.
    - ``kind="image"``: ``data`` holds raw bytes and ``mime`` the media type
      (e.g. ``image/png``).
    """

    kind: PartKind
    text: Optional[str] = None
    data: Optional[bytes] = None
    mime: Optional[str] = None
    page: Optional[int] = None  # 1-indexed source page, when known

    @classmethod
    def from_text(cls, text: str, *, page: Optional[int] = None) -> "ContentPart":
        return cls(kind="text", text=text, page=page)

    @classmethod
    def from_image(
        cls, data: bytes, mime: str = "image/png", *, page: Optional[int] = None
    ) -> "ContentPart":
        return cls(kind="image", data=data, mime=mime, page=page)

    def data_uri(self) -> str:
        """Return a ``data:`` URI for an image part (used by OpenAI-compatible/Claude)."""
        if self.kind != "image" or self.data is None:
            raise ValueError("data_uri() is only valid for image parts with data")
        b64 = base64.b64encode(self.data).decode("ascii")
        return f"data:{self.mime or 'image/png'};base64,{b64}"


@dataclass
class LoadedDocument:
    """Result of loading a file: normalized parts plus provenance metadata."""

    parts: list[ContentPart]
    source_path: str
    route: Route = "text"
    page_count: Optional[int] = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def has_images(self) -> bool:
        return any(p.kind == "image" for p in self.parts)

    @property
    def has_text(self) -> bool:
        return any(p.kind == "text" and (p.text or "").strip() for p in self.parts)

    def text_blob(self) -> str:
        """Concatenate all text parts (page-delimited) for text-only backends."""
        chunks = []
        for p in self.parts:
            if p.kind == "text" and p.text:
                header = f"\n\n--- page {p.page} ---\n" if p.page else ""
                chunks.append(header + p.text)
        return "".join(chunks).strip()

    def summary(self) -> dict[str, Any]:
        """Lightweight, LLM-free description of the loaded content (for --dry-run)."""
        text_parts = [p for p in self.parts if p.kind == "text"]
        image_parts = [p for p in self.parts if p.kind == "image"]
        text_chars = sum(len(p.text or "") for p in text_parts)
        return {
            "source_path": self.source_path,
            "route": self.route,
            "page_count": self.page_count,
            "text_parts": len(text_parts),
            "text_chars": text_chars,
            "image_parts": len(image_parts),
            "meta": self.meta,
        }
