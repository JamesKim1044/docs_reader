"""HWP / HWPX loader (Korean Hangul word processor).

Real-world Korean government HWP files often fail LibreOffice's HWP import filter,
so we try multiple backends in order and use the first that yields content:

- ``.hwp``  : pyhwp ``hwp5html`` (parses HWP5 binary incl. tables) → LibreOffice PDF → hwp5txt
- ``.hwpx`` : LibreOffice PDF (XML format it handles well) → hwp5html → hwp5txt

pyhwp is installed with the ``hwp`` extra: ``pip install 'docs-reader[hwp]'``.
"""

from __future__ import annotations

import html as _html
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..config import Settings
from ..convert import ConversionError, convert_to_pdf, soffice_available
from ..types import ContentPart, LoadedDocument


def _hwp5html_text(path: Path) -> str:
    """Convert HWP5 -> XHTML via pyhwp and flatten to text, preserving table rows."""
    if shutil.which("hwp5html") is None:
        raise ConversionError("hwp5html not found (pip install 'docs-reader[hwp]')")
    out_dir = Path(tempfile.mkdtemp(prefix="docsreader_hwp_"))
    proc = subprocess.run(
        ["hwp5html", "--output", str(out_dir), str(path)],
        capture_output=True, text=True, timeout=120,
    )
    index = out_dir / "index.xhtml"
    if proc.returncode != 0 or not index.exists():
        raise ConversionError(f"hwp5html failed: {proc.stderr.strip()[:200]}")
    raw = index.read_text(encoding="utf-8", errors="replace")
    # Drop style/script, then turn table/paragraph structure into text layout.
    raw = re.sub(r"<style[^>]*>.*?</style>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"</t[dh]>", " | ", raw, flags=re.IGNORECASE)
    raw = re.sub(r"</tr>", "\n", raw, flags=re.IGNORECASE)
    raw = re.sub(r"</p\s*>|<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    text = _html.unescape(re.sub(r"<[^>]+>", " ", raw))
    lines = [re.sub(r"[ \t]+", " ", ln).strip(" |").strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def _hwp5txt_text(path: Path) -> str:
    if shutil.which("hwp5txt") is None:
        raise ConversionError("hwp5txt not found (pip install 'docs-reader[hwp]')")
    proc = subprocess.run(["hwp5txt", str(path)], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise ConversionError(f"hwp5txt failed: {proc.stderr.strip()[:200]}")
    return proc.stdout.strip()


def _via_libreoffice(path: Path, settings: Settings) -> LoadedDocument:
    if not soffice_available():
        raise ConversionError("LibreOffice (soffice) not available")
    from .pdf import load_pdf

    pdf_path = convert_to_pdf(path)
    doc = load_pdf(pdf_path, settings, source_label=str(path))
    doc.meta = {**doc.meta, "loader": "hwp->pdf", "original_ext": path.suffix.lower()}
    return doc


def _via_hwp5html(path: Path, settings: Settings) -> LoadedDocument:
    text = _hwp5html_text(path)
    if not text.strip():
        raise ConversionError("hwp5html produced no text")
    return LoadedDocument(
        parts=[ContentPart.from_text(text)],
        source_path=str(path),
        route="text",
        meta={"loader": "hwp-hwp5html"},
    )


def _via_hwp5txt(path: Path, settings: Settings) -> LoadedDocument:
    text = _hwp5txt_text(path)
    if not text.strip():
        raise ConversionError("hwp5txt produced no text")
    return LoadedDocument(
        parts=[ContentPart.from_text(text)],
        source_path=str(path),
        route="text",
        meta={"loader": "hwp-hwp5txt"},
    )


def load_hwp(path: str | Path, settings: Settings) -> LoadedDocument:
    path = Path(path)
    ext = path.suffix.lower()
    # pyhwp handles the binary .hwp best (and LibreOffice often fails on it);
    # LibreOffice handles the XML .hwpx better.
    if ext == ".hwpx":
        chain = [_via_libreoffice, _via_hwp5html, _via_hwp5txt]
    else:
        chain = [_via_hwp5html, _via_libreoffice, _via_hwp5txt]

    errors: list[str] = []
    for backend in chain:
        try:
            doc = backend(path, settings)
            if doc.has_text or doc.has_images:
                return doc
        except Exception as e:  # noqa: BLE001
            errors.append(f"{backend.__name__}: {e}")
            continue
    raise ConversionError(
        "Could not read HWP with any backend.\n  " + "\n  ".join(errors)
        + "\nInstall pyhwp (`pip install 'docs-reader[hwp]'`) and/or LibreOffice."
    )
