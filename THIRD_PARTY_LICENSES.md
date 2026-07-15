# Third-Party Licenses

docs_reader's own source code is licensed under **MIT** (see `LICENSE`). It relies on
third-party packages that carry their own licenses. This file summarizes them and
flags the ones with copyleft (AGPL/GPL) terms that affect how a combined/derived work
may be distributed.

> This is an informational summary, not legal advice. Verify each dependency's license
> for your distribution scenario. Licenses can change between versions.

## ⚠️ Copyleft (AGPL-3.0) — read before distributing

These are **core** dependencies (not optional extras). AGPL-3.0 is a strong copyleft
license: if you distribute docs_reader — or offer it as a network service — the AGPL
terms extend to the combined work, which typically requires offering the complete
corresponding source under AGPL-3.0.

| Package | License | Used for |
| --- | --- | --- |
| **PyMuPDF** (`pymupdf`, aka fitz) | AGPL-3.0 or commercial (Artifex) | PDF text/render, table detection, embedded-image extraction |
| **pyhwp** (`hwp` extra) | GNU AGPL-3.0 | HWP (Korean Hangul) parsing via `hwp5html`/`hwp5txt` |

**If AGPL is not acceptable for your use:**

- **PDF**: swap PyMuPDF for a non-AGPL stack — `pypdfium2` (Apache/BSD) for
  render/text and `pdfplumber` (MIT) for tables. This requires code changes in
  `loaders/pdf.py`, `assets.py`, and `loaders/tables.py`.
- **HWP**: `pyhwp` is an optional `[hwp]` extra — omit it and rely on LibreOffice
  (MPL-2.0) conversion for HWP instead (works for `.hwpx` and many `.hwp`).
- Or obtain a **commercial PyMuPDF license** from Artifex.

## Permissive dependencies

Commonly under MIT / BSD / Apache-2.0 (permissive; compatible with MIT redistribution):

| Package | License (typical) |
| --- | --- |
| typer | MIT |
| pydantic | MIT |
| python-dotenv | BSD-3-Clause |
| pillow | MIT-CMU (HPND) |
| python-docx | MIT |
| openpyxl | MIT |
| python-pptx | MIT |
| openai (SDK) | Apache-2.0 |
| anthropic (SDK) | MIT |
| google-genai | Apache-2.0 |
| rapidocr-onnxruntime | Apache-2.0 |
| paddleocr / paddlepaddle | Apache-2.0 |
| easyocr | Apache-2.0 |
| docling | MIT |

## External tools & models (not bundled)

- **LibreOffice** (`soffice`) — MPL-2.0 (system dependency invoked as a subprocess for
  Office/HWP → PDF conversion; not linked or redistributed).
- **Ollama** — MIT (runs models; invoked over HTTP).
- **Models** (gemma3, qwen2.5, exaone3.5, llama3.x, PaddleOCR-korean, …) — each has its
  own model license/terms (e.g. Gemma Terms, Qwen license, EXAONE AI Model License,
  Llama Community License). Review the license of any model you deploy; some restrict
  commercial use or require attribution.

## How to regenerate a precise report

```bash
pip install pip-licenses
pip-licenses --format=markdown --with-urls --with-license-file
```
