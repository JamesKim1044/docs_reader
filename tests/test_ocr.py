from __future__ import annotations

from docs_reader.config import Settings
from docs_reader.ocr import get_ocr_engine
from docs_reader.ocr.base import NullOCR


def _engine(name: str):
    s = Settings()
    s.ocr_engine = name
    return get_ocr_engine(s)


def test_none_engine():
    assert _engine("none").name == "none"


def test_absent_engine_falls_back_gracefully():
    # easyocr (torch) is not installed in the base env -> NullOCR, never an ImportError.
    engine = _engine("easyocr")
    assert isinstance(engine, NullOCR)
    assert engine.available is False


def test_docling_absent_falls_back():
    assert _engine("docling").available is False


def test_unknown_choice_uses_auto_chain():
    # 'auto' tries rapidocr -> docling; both absent here -> NullOCR.
    assert _engine("auto").available is False


def test_ocr_lang_default_is_korean():
    assert Settings().ocr_lang == "korean"
