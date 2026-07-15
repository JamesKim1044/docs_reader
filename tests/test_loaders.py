from __future__ import annotations

from docs_reader.config import Settings
from docs_reader.loaders import load_document


def test_text_pdf_routes_to_text(text_pdf):
    doc = load_document(text_pdf, Settings())
    assert doc.route == "text"
    assert doc.has_text
    assert "INV-2024-0091" in doc.text_blob()
    assert doc.page_count == 1


def test_scanned_pdf_routes_to_vision_without_ocr(scanned_pdf):
    # No OCR engine installed in the base test env -> image parts (vision path).
    s = Settings()
    s.ocr_engine = "none"
    doc = load_document(scanned_pdf, s)
    assert doc.route == "vision"
    assert doc.has_images


def test_force_vision_on_text_pdf(text_pdf):
    s = Settings()
    s.ocr_engine = "none"
    s.force_route = "vision"
    doc = load_document(text_pdf, s)
    assert doc.route == "vision"
    assert doc.has_images


def test_docx_text_extraction(sample_docx):
    doc = load_document(sample_docx, Settings())
    assert doc.route == "text"
    blob = doc.text_blob()
    assert "INV-DOCX-1" in blob
    assert "Total" in blob and "42.00" in blob


def test_summary_shape(text_pdf):
    doc = load_document(text_pdf, Settings())
    summ = doc.summary()
    assert summ["route"] == "text"
    assert summ["text_parts"] >= 1
