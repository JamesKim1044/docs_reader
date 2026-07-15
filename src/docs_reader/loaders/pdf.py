"""PDF loader with hybrid text-vs-scan routing.

Per page: if a real text layer exists, extract text (cheap path). Otherwise the page
is scanned — render it to a PNG and either OCR it (Stage A, preferred) or emit an
image part for a vision backend. ``force_route`` overrides the per-page decision.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import Settings
from ..ocr import get_ocr_engine
from ..ocr.base import OCREngine
from ..types import ContentPart, LoadedDocument
from .base import MIN_CHARS_PER_PAGE
from .tables import pdf_page_tables_markdown


def _render_png(page, dpi: int) -> bytes:
    import fitz  # PyMuPDF

    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    return pix.tobytes("png")


def load_pdf(
    path: str | Path,
    settings: Settings,
    *,
    ocr: Optional[OCREngine] = None,
    source_label: Optional[str] = None,
) -> LoadedDocument:
    import fitz  # PyMuPDF

    path = Path(path)
    ocr = ocr if ocr is not None else get_ocr_engine(settings)
    force = settings.force_route

    doc = fitz.open(str(path))
    parts: list[ContentPart] = []
    used_text = used_ocr = used_vision = False
    table_count = 0
    try:
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            scanned = len(text.strip()) < MIN_CHARS_PER_PAGE
            use_vision = force == "vision" or (force != "text" and scanned)

            if not use_vision:
                page_text = text
                if settings.tables != "off":
                    tables_md = pdf_page_tables_markdown(page)
                    if tables_md:
                        table_count += len(tables_md)
                        page_text = (
                            text
                            + "\n\n[detected tables (Markdown)]\n"
                            + "\n\n".join(tables_md)
                        )
                parts.append(ContentPart.from_text(page_text, page=i))
                used_text = True
                continue

            png = _render_png(page, settings.dpi)
            if ocr.available:
                try:
                    ocr_text = ocr.image_to_text(png)
                except Exception:
                    ocr_text = ""  # OCR failed at runtime -> fall back to vision
                if ocr_text.strip():
                    parts.append(ContentPart.from_text(ocr_text, page=i))
                    used_ocr = True
                    continue
            # No OCR (or empty) -> hand the image to a vision backend.
            parts.append(ContentPart.from_image(png, "image/png", page=i))
            used_vision = True
        page_count = doc.page_count
    finally:
        doc.close()

    route = "vision" if used_vision else "ocr" if used_ocr else "text"
    return LoadedDocument(
        parts=parts,
        source_path=source_label or str(path),
        route=route,
        page_count=page_count,
        meta={"loader": "pdf", "ocr_engine": ocr.name, "tables_detected": table_count},
    )
