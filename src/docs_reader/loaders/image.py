"""Image loader (png/jpg/scans).

If an OCR engine is available and vision isn't forced, run Stage A OCR to produce
text (cheaper + more precise for a text LLM). Otherwise emit an image part for a
vision backend.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import Settings
from ..ocr import get_ocr_engine
from ..ocr.base import OCREngine
from ..types import ContentPart, LoadedDocument
from .base import image_mime


def load_image(
    path: str | Path, settings: Settings, *, ocr: Optional[OCREngine] = None
) -> LoadedDocument:
    path = Path(path)
    ocr = ocr if ocr is not None else get_ocr_engine(settings)
    data = path.read_bytes()
    mime = image_mime(path)

    if settings.force_route != "vision" and ocr.available:
        try:
            text = ocr.image_to_text(data)
        except Exception:
            text = ""  # OCR failed at runtime -> fall back to vision
        if text.strip():
            return LoadedDocument(
                parts=[ContentPart.from_text(text, page=1)],
                source_path=str(path),
                route="ocr",
                page_count=1,
                meta={"loader": "image", "ocr_engine": ocr.name},
            )

    return LoadedDocument(
        parts=[ContentPart.from_image(data, mime, page=1)],
        source_path=str(path),
        route="vision",
        page_count=1,
        meta={"loader": "image"},
    )
