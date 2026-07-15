"""Higher-fidelity layout/table OCR via docling (IBM).

Installed with the ``ocr-docling`` extra. docling reconstructs reading order and
tables and emits Markdown, which is the preferred Stage A output for complex
Korean government forms / HWP-origin pages.
"""

from __future__ import annotations

import tempfile
from pathlib import Path


class DoclingEngine:
    name = "docling"
    available = True

    def __init__(self) -> None:
        from docling.document_converter import DocumentConverter  # noqa: F401

        self._converter = DocumentConverter()

    def image_to_text(self, image_bytes: bytes) -> str:
        # docling operates on files; write the page image to a temp file and convert.
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(image_bytes)
            tmp = Path(f.name)
        try:
            result = self._converter.convert(str(tmp))
            return result.document.export_to_markdown().strip()
        finally:
            tmp.unlink(missing_ok=True)
