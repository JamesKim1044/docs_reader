"""Korean-specialized OCR via PaddleOCR (`lang="korean"`).

Installed with the ``ocr-korean`` extra:
    pip install 'docs-reader[ocr-korean]'
PaddleOCR ships dedicated Korean recognition models (PP-OCRv5 korean) and is a strong
open choice for Korean scans / HWP-origin pages. First use downloads model weights.

Supports both PaddleOCR 3.x (``predict`` pipeline, ``rec_texts`` results) and the
legacy 2.x API (``ocr(img, cls=True)``). MKLDNN/oneDNN is disabled because several
CPU paddlepaddle builds crash in the oneDNN execution path.
"""

from __future__ import annotations

import io
import os
from typing import Any


class PaddleOCREngine:
    name = "paddleocr"
    available = True

    def __init__(self, lang: str = "korean") -> None:
        # Disable oneDNN/MKLDNN globally too (some builds only honor the flag).
        os.environ.setdefault("FLAGS_use_mkldnn", "0")
        try:
            import paddle

            paddle.set_flags({"FLAGS_use_mkldnn": False})
        except Exception:
            pass

        from paddleocr import PaddleOCR  # noqa: F401  (availability check)

        self._api = "3x"
        try:
            # PaddleOCR 3.x — turn off doc-orientation/unwarp models we don't need.
            self._ocr = PaddleOCR(
                lang=lang,
                use_textline_orientation=False,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                enable_mkldnn=False,
            )
        except TypeError:
            # PaddleOCR 2.x fallback.
            self._api = "2x"
            self._ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)

    @staticmethod
    def _sorted_join(boxes: list[tuple[float, float, float, str]]) -> str:
        """Reconstruct reading order from detection boxes.

        boxes: (ymin, x, height, text). Group into visual lines using a tolerance
        derived from median box height (robust to per-box y jitter), order boxes
        left-to-right within a line, and join lines with newlines.
        """
        boxes = [b for b in boxes if b[3]]
        if not boxes:
            return ""
        heights = sorted(b[2] for b in boxes if b[2] > 0)
        med_h = heights[len(heights) // 2] if heights else 12.0
        tol = max(8.0, 0.6 * med_h)

        boxes.sort(key=lambda b: b[0])
        lines: list[list[tuple[float, str]]] = []
        line_ref = None
        for ymin, x, _h, text in boxes:
            if line_ref is None or (ymin - line_ref) > tol:
                lines.append([(x, text)])
                line_ref = ymin
            else:
                lines[-1].append((x, text))
        out = []
        for row in lines:
            row.sort(key=lambda t: t[0])
            out.append(" ".join(t for _, t in row))
        return "\n".join(out).strip()

    @staticmethod
    def _box(poly: Any) -> tuple[float, float, float]:
        """Return (ymin, xmin, height) for a polygon of points."""
        try:
            ys = [float(pt[1]) for pt in poly]
            xs = [float(pt[0]) for pt in poly]
            return min(ys), min(xs), (max(ys) - min(ys))
        except Exception:
            return 0.0, 0.0, 0.0

    def _parse_3x(self, results: Any) -> str:
        boxes: list[tuple[float, float, float, str]] = []
        for res in results or []:
            texts = res["rec_texts"] if "rec_texts" in res else []
            polys = None
            for k in ("rec_polys", "dt_polys", "rec_boxes"):
                if k in res and res[k] is not None:
                    polys = res[k]
                    break
            if polys is None:
                polys = [None] * len(texts)
            for text, poly in zip(texts, polys):
                ymin, xmin, h = self._box(poly)
                boxes.append((ymin, xmin, h, text))
        return self._sorted_join(boxes)

    def _parse_2x(self, results: Any) -> str:
        boxes: list[tuple[float, float, float, str]] = []
        for page in results or []:
            for entry in page or []:
                box, rec = entry[0], entry[1]
                text = rec[0] if isinstance(rec, (list, tuple)) else str(rec)
                ymin, xmin, h = self._box(box)
                boxes.append((ymin, xmin, h, text))
        return self._sorted_join(boxes)

    def image_to_text(self, image_bytes: bytes) -> str:
        import numpy as np
        from PIL import Image

        img = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
        if self._api == "3x":
            return self._parse_3x(self._ocr.predict(img))
        return self._parse_2x(self._ocr.ocr(img, cls=True))
