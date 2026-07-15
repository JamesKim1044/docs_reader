from __future__ import annotations

from pathlib import Path

from docs_reader.assets import extract_images
from docs_reader.config import Settings
from docs_reader.loaders import load_document
from docs_reader.loaders.tables import rows_to_markdown


def test_rows_to_markdown():
    md = rows_to_markdown([["A", "B"], ["1", "2"], [None, ""]])
    lines = md.splitlines()
    assert lines[0] == "| A | B |"
    assert lines[1] == "| --- | --- |"
    assert lines[2] == "| 1 | 2 |"
    assert len(lines) == 3  # empty row dropped


def test_pdf_table_detected_in_text(table_image_pdf):
    doc = load_document(table_image_pdf, Settings())
    assert doc.route == "text"
    blob = doc.text_blob()
    assert "detected tables" in blob
    assert "Widget A" in blob and "|" in blob
    assert doc.meta.get("tables_detected", 0) >= 1


def test_extract_images_from_pdf(table_image_pdf, tmp_path):
    out = tmp_path / "imgs"
    images = extract_images(table_image_pdf, out)
    assert len(images) == 1
    saved = Path(images[0].path)
    assert saved.exists() and saved.stat().st_size > 0
    assert images[0].page == 1
    assert images[0].mime.startswith("image/")


def test_extract_images_from_docx(docx_with_image, tmp_path):
    images = extract_images(docx_with_image, tmp_path / "imgs")
    assert len(images) >= 1
    assert Path(images[0].path).exists()


def test_load_document_populates_images_meta(table_image_pdf, tmp_path):
    s = Settings()
    s.extract_images = True
    s.images_dir = str(tmp_path / "out")
    doc = load_document(table_image_pdf, s)
    assert len(doc.meta["images"]) == 1
    assert "data" not in doc.meta["images"][0]  # bytes stripped from metadata


def test_figures_vision_attaches_image_parts(table_image_pdf, tmp_path):
    s = Settings()
    s.figures_vision = True
    s.images_dir = str(tmp_path / "out")
    doc = load_document(table_image_pdf, s)
    assert doc.has_images  # figure attached as a vision part
    assert any(p.kind == "image" for p in doc.parts)


def test_docx_table_is_markdown(sample_docx):
    doc = load_document(sample_docx, Settings())
    blob = doc.text_blob()
    assert "| --- |" in blob
    assert "Total" in blob and "42.00" in blob
