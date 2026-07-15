"""Show hallucination control on a real model: keep vs drop on the same document."""

from __future__ import annotations

import json
import sys

from docs_reader._io import quiet_stdout
from docs_reader.config import Settings
from docs_reader.extract import extract_file

MODEL = sys.argv[1] if len(sys.argv) > 1 else "llama3.2:3b"
DOC = "samples/korean_scan.pdf"
SCHEMA = "schemas/invoice.py"


def base() -> Settings:
    s = Settings()
    s.provider = "opensource"
    s.os_base_url = "http://localhost:11434/v1"
    s.os_text_model = MODEL
    s.ocr_engine = "korean"
    return s


# Raw: no verification, no hallucination control.
s_raw = base()
s_raw.verify = False
s_raw.drop_hallucinations = False

# Controlled: verification + grounding + drop.
s_ctl = base()
s_ctl.verify = True
s_ctl.drop_hallucinations = True

with quiet_stdout():
    raw = extract_file(DOC, SCHEMA, s_raw)
    ctl = extract_file(DOC, SCHEMA, s_ctl)

print(f"model: {MODEL}   doc: {DOC}\n")
print("RAW (no control):")
print(json.dumps(raw.data, ensure_ascii=False, indent=2))
print("\nCONTROLLED (verify + grounding + drop):")
print(json.dumps(ctl.data, ensure_ascii=False, indent=2))
print("\nDROPPED as hallucinations:")
print(json.dumps(ctl.meta.get("dropped_hallucinations", []), ensure_ascii=False, indent=2))
