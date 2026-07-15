"""High-level convenience API.

    from docs_reader.extract import extract_file
    out = extract_file("invoice.pdf", "schemas/invoice.py")
    print(out.data)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import Settings
from .loaders import load_document
from .pipeline import ExtractionOutput, run_pipeline
from .providers.base import LLMBackend
from .schema import load_schema


def extract_file(
    file_path: str | Path,
    schema_path: str | Path,
    settings: Optional[Settings] = None,
    *,
    backend: Optional[LLMBackend] = None,
) -> ExtractionOutput:
    settings = settings or Settings()
    schema = load_schema(schema_path)
    loaded = load_document(file_path, settings)
    return run_pipeline(loaded, schema, settings, backend=backend)


__all__ = ["extract_file"]
