"""LibreOffice (`soffice`) headless conversion — shared by the Office and HWP loaders.

HWP/HWPX has no reliable pure-Python parser, so the strategy is to convert to PDF
via LibreOffice (which ships an HWP import filter) and then reuse the PDF loader.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional


class ConversionError(RuntimeError):
    pass


def soffice_binary() -> Optional[str]:
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    return None


def soffice_available() -> bool:
    return soffice_binary() is not None


def convert_to_pdf(src: str | Path, out_dir: Optional[str | Path] = None, *, timeout: int = 120) -> Path:
    """Convert ``src`` (docx/xlsx/pptx/hwp/hwpx/...) to PDF, returning the PDF path.

    Uses an isolated ``UserInstallation`` profile so concurrent/locked LibreOffice
    instances don't interfere.
    """
    binary = soffice_binary()
    if binary is None:
        raise ConversionError(
            "LibreOffice not found. Install it (provides `soffice`) to convert Office/HWP files, "
            "e.g. `apt install libreoffice` / `brew install --cask libreoffice`."
        )
    src = Path(src)
    if not src.exists():
        raise ConversionError(f"source file not found: {src}")
    out_dir = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="docsreader_pdf_"))
    out_dir.mkdir(parents=True, exist_ok=True)

    profile = Path(tempfile.mkdtemp(prefix="docsreader_loprofile_"))
    cmd = [
        binary,
        "--headless",
        "--norestore",
        f"-env:UserInstallation=file://{profile}",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_dir),
        str(src),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:  # pragma: no cover - environment dependent
        raise ConversionError(f"LibreOffice conversion timed out after {timeout}s") from e
    finally:
        shutil.rmtree(profile, ignore_errors=True)

    out_pdf = out_dir / (src.stem + ".pdf")
    if proc.returncode != 0 or not out_pdf.exists():
        # LibreOffice may name the output slightly differently; fall back to newest PDF.
        pdfs = sorted(out_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
        if pdfs:
            return pdfs[0]
        raise ConversionError(
            f"LibreOffice failed to convert {src.name} (rc={proc.returncode}).\n"
            f"stdout: {proc.stdout.strip()}\nstderr: {proc.stderr.strip()}"
        )
    return out_pdf
