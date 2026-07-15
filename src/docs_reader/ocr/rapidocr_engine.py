"""Lightweight CPU OCR via rapidocr-onnxruntime (Korean + English).

Installed with the ``ocr`` extra: ``pip install 'docs-reader[ocr]'``.
Produces plain text ordered by detected line boxes. For richer table/layout
structure, use the docling engine instead.
"""

from __future__ import annotations

import io
from typing import Any


class RapidOCREngine:
    name = "rapidocr"
    available = True

    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR  # noqa: F401  (import-time availability check)

        self._engine = RapidOCR()

    def image_to_text(self, image_bytes: bytes) -> str:
        import numpy as np
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img)
        result, _ = self._engine(arr)
        if not result:
            return ""
        # result: list of [box, text, score]; keep detection order (top-to-bottom).
        lines: list[tuple[float, str]] = []
        for item in result:
            box, text = item[0], item[1]
            y = min(pt[1] for pt in box) if box else 0.0
            lines.append((y, text))
        lines.sort(key=lambda t: t[0])
        return "\n".join(text for _, text in lines).strip()
