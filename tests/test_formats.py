from __future__ import annotations

import unicodedata

from docs_reader.cli import _resolve_path
from docs_reader.loaders import SUPPORTED_EXTS, is_supported


def test_legacy_and_hwp_formats_supported():
    for ext in (".ppt", ".doc", ".xls", ".pptx", ".docx", ".xlsx", ".hwp", ".hwpx", ".pdf"):
        assert ext in SUPPORTED_EXTS, ext
    assert is_supported("report.ppt")
    assert is_supported("공문서.hwp")
    assert not is_supported("archive.zip")


def test_resolve_path_exact(tmp_path):
    f = tmp_path / "plain.pdf"
    f.write_bytes(b"%PDF-1.4")
    assert _resolve_path(f) == f


def test_resolve_path_unicode_nfc_nfd(tmp_path):
    # Store the file with an NFC Korean name, then ask for it via the NFD form.
    nfc = unicodedata.normalize("NFC", "테스트_문서.hwp")
    f = tmp_path / nfc
    f.write_bytes(b"x")
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfc != nfd  # sanity: the two normalizations differ in bytes
    resolved = _resolve_path(tmp_path / nfd)
    assert resolved.exists()
    assert unicodedata.normalize("NFC", resolved.name) == nfc
