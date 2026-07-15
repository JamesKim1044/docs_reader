"""stdout hygiene helpers.

Some OCR/ML libraries (PaddleOCR/paddlex, etc.) print progress and advisories to
stdout at the OS file-descriptor level. When the CLI emits JSON on stdout, that
chatter corrupts the output. ``quiet_stdout`` redirects fd 1 -> fd 2 for the
duration of a block so library noise goes to stderr and stdout stays clean.
"""

from __future__ import annotations

import contextlib
import os
import sys


@contextlib.contextmanager
def quiet_stdout():
    """Redirect OS-level stdout (fd 1) to stderr (fd 2) within the block."""
    try:
        sys.stdout.flush()
    except Exception:
        pass
    try:
        saved = os.dup(1)
    except OSError:
        # No real fd (e.g. captured in tests) — nothing to redirect.
        yield
        return
    try:
        os.dup2(2, 1)
        yield
    finally:
        try:
            sys.stdout.flush()
        except Exception:
            pass
        os.dup2(saved, 1)
        os.close(saved)
