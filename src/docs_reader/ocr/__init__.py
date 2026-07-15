"""Stage A: open-source OCR / layout engines.

An OCR engine turns a page image into clean text (ideally Markdown that preserves
tables and reading order).  This is the quality lever for scanned/image/HWP pages:
converting to good text lets a cheap, precise text LLM do the extraction instead of
relying on a single raw VLM pass.  When no engine is available, loaders fall back to
sending page images directly to a vision backend.
"""

from __future__ import annotations

from ..config import Settings
from .base import NullOCR, OCREngine


def get_ocr_engine(settings: Settings) -> OCREngine:
    """Resolve an OCR engine from settings.

    Choices: ``korean`` (PaddleOCR-korean -> EasyOCR-ko, best for Korean scans/HWP),
    ``paddle``, ``easyocr``, ``rapidocr``, ``docling``, ``none``, or ``auto``
    (rapidocr -> docling). Any unavailable engine falls back to the null engine,
    which routes the page to a vision model instead.
    """
    choice = (settings.ocr_engine or "auto").lower()
    lang = getattr(settings, "ocr_lang", "korean") or "korean"

    def try_paddle() -> OCREngine | None:
        try:
            from .paddle_engine import PaddleOCREngine

            return PaddleOCREngine(lang=lang)
        except Exception:
            return None

    def try_easyocr() -> OCREngine | None:
        try:
            from .easyocr_engine import EasyOCREngine

            langs = ("ko", "en") if lang in ("korean", "ko") else (lang, "en")
            return EasyOCREngine(langs=langs)
        except Exception:
            return None

    def try_rapidocr() -> OCREngine | None:
        try:
            from .rapidocr_engine import RapidOCREngine

            return RapidOCREngine()
        except Exception:
            return None

    def try_docling() -> OCREngine | None:
        try:
            from .docling_engine import DoclingEngine

            return DoclingEngine()
        except Exception:
            return None

    if choice in ("none", "off"):
        return NullOCR()
    if choice in ("korean", "ko"):
        return try_paddle() or try_easyocr() or try_rapidocr() or NullOCR()
    if choice in ("paddle", "paddleocr"):
        return try_paddle() or NullOCR()
    if choice == "easyocr":
        return try_easyocr() or NullOCR()
    if choice == "rapidocr":
        return try_rapidocr() or NullOCR()
    if choice == "docling":
        return try_docling() or NullOCR()
    # auto (general): rapidocr -> docling
    return try_rapidocr() or try_docling() or NullOCR()


__all__ = ["OCREngine", "NullOCR", "get_ocr_engine"]
