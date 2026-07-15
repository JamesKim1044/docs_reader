"""Korean OCR via EasyOCR (languages default to Korean + English).

Installed with the ``ocr-easyocr`` extra:
    pip install 'docs-reader[ocr-easyocr]'
Simpler to install than PaddleOCR; good Korean recognition. First use downloads
model weights.
"""

from __future__ import annotations

import io
from typing import Sequence


class EasyOCREngine:
    name = "easyocr"
    available = True

    def __init__(self, langs: Sequence[str] = ("ko", "en"), gpu: bool = False) -> None:
        import easyocr  # noqa: F401  (availability check)

        self._reader = easyocr.Reader(list(langs), gpu=gpu, verbose=False)

    def image_to_text(self, image_bytes: bytes) -> str:
        import numpy as np
        from PIL import Image

        img = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
        results = self._reader.readtext(img, detail=1, paragraph=False)
        lines: list[tuple[float, float, str]] = []
        for box, text, *_ in results:
            ys = [pt[1] for pt in box]
            xs = [pt[0] for pt in box]
            lines.append((min(ys), min(xs), text))
        lines.sort(key=lambda t: (t[0], t[1]))
        return "\n".join(text for _, _, text in lines).strip()
