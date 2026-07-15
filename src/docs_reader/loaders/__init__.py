"""Loader dispatch by file extension.

Every loader returns a :class:`LoadedDocument` of normalized :class:`ContentPart`s,
so downstream code is format-agnostic.
"""

from __future__ import annotations

from pathlib import Path

from ..config import Settings
from ..types import LoadedDocument

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp"}
_OFFICE_EXTS = {".docx", ".xlsx", ".xlsm", ".pptx"}
_LEGACY_OFFICE_EXTS = {".ppt", ".doc", ".xls"}  # binary OLE -> LibreOffice -> PDF
_HWP_EXTS = {".hwp", ".hwpx"}

SUPPORTED_EXTS = (
    {".pdf", ".txt", ".md"} | _IMAGE_EXTS | _OFFICE_EXTS | _LEGACY_OFFICE_EXTS | _HWP_EXTS
)


def is_supported(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTS


def _dispatch(p: Path, ext: str, settings: Settings) -> LoadedDocument:
    if ext == ".pdf":
        from .pdf import load_pdf

        return load_pdf(p, settings)
    if ext in _IMAGE_EXTS:
        from .image import load_image

        return load_image(p, settings)
    if ext in _OFFICE_EXTS:
        from .office import load_office

        return load_office(p, settings)
    if ext in _LEGACY_OFFICE_EXTS:
        from .office import load_legacy_office

        return load_legacy_office(p, settings)
    if ext in _HWP_EXTS:
        from .hwp import load_hwp

        return load_hwp(p, settings)
    if ext in (".txt", ".md"):
        from ..types import ContentPart

        text = p.read_text(encoding="utf-8", errors="replace")
        return LoadedDocument(
            parts=[ContentPart.from_text(text)],
            source_path=str(p),
            route="text",
            meta={"loader": "plaintext", "ext": ext},
        )
    raise ValueError(
        f"unsupported file type {ext!r}. Supported: {', '.join(sorted(SUPPORTED_EXTS))}"
    )


def _extract_assets(loaded: LoadedDocument, p: Path, settings: Settings) -> None:
    """Pull embedded images to files; optionally attach them as vision parts."""
    from ..assets import extract_images
    from ..types import ContentPart

    out_dir = Path(settings.images_dir) if settings.images_dir else Path("extracted_images") / p.stem
    try:
        images = extract_images(p, out_dir)
    except Exception as e:  # best-effort; never fail extraction on asset issues
        loaded.meta["images_error"] = str(e)
        return
    loaded.meta["images"] = [im.meta() for im in images]
    if settings.figures_vision:
        for im in images:
            loaded.parts.append(ContentPart.from_image(im.data, im.mime, page=im.page))
        if images:
            loaded.route = "vision" if loaded.route == "text" else loaded.route


def load_document(path: str | Path, settings: Settings) -> LoadedDocument:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"input file not found: {p}")
    ext = p.suffix.lower()
    loaded = _dispatch(p, ext, settings)
    if settings.extract_images or settings.figures_vision:
        _extract_assets(loaded, p, settings)
    return loaded


__all__ = ["load_document", "is_supported", "SUPPORTED_EXTS"]
