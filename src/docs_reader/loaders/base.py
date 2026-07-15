"""Shared loader helpers."""

from __future__ import annotations

from pathlib import Path

# Below this many non-whitespace chars, a PDF page is treated as scanned (image).
MIN_CHARS_PER_PAGE = 20

MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".webp": "image/webp",
}


def image_mime(path: str | Path) -> str:
    return MIME_BY_EXT.get(Path(path).suffix.lower(), "image/png")
