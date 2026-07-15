"""Table extraction helpers.

Tables are the hardest thing for an LLM to read out of flattened text, so we hand it
proper GitHub-Markdown tables (headers + column alignment preserved). For PDFs this
uses PyMuPDF's built-in table finder (no extra dependency); Office loaders reuse
``rows_to_markdown``.
"""

from __future__ import annotations

import contextlib
import io
import os
from typing import Any, Sequence


@contextlib.contextmanager
def _silenced():
    """Suppress library chatter (e.g. PyMuPDF's find_tables advisory) so it can't
    pollute stdout/stderr, which would corrupt JSON output on stdout."""
    devnull = open(os.devnull, "w")
    try:
        with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
            yield
    finally:
        devnull.close()


def rows_to_markdown(rows: Sequence[Sequence[Any]]) -> str:
    """Render a 2D grid of cells as a Markdown table."""
    norm: list[list[str]] = []
    for r in rows:
        if r is None:
            continue
        cells = [("" if c is None else str(c)).replace("\n", " ").strip() for c in r]
        if any(cells):
            norm.append(cells)
    if not norm:
        return ""
    width = max(len(r) for r in norm)
    norm = [r + [""] * (width - len(r)) for r in norm]
    header = norm[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    for r in norm[1:]:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def pdf_page_tables_markdown(page) -> list[str]:
    """Return Markdown for each table found on a PyMuPDF page (best-effort)."""
    try:
        with _silenced():
            finder = page.find_tables()
            out: list[str] = []
            for table in getattr(finder, "tables", []) or []:
                md = ""
                try:
                    md = table.to_markdown()
                except Exception:
                    try:
                        md = rows_to_markdown(table.extract())
                    except Exception:
                        md = ""
                if md and md.strip():
                    out.append(md.strip())
    except Exception:
        return []
    return out
