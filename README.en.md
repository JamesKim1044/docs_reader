# docs_reader

*[한국어 README](README.md) · English*

LLM-based document structured-extraction CLI. Pulls a defined **schema (fields)** out of
PDF · Office (docx/xlsx/pptx, legacy ppt/doc/xls) · images/scans · **HWP (Korean Hangul)**
and returns validated **JSON**.
(HWP is parsed directly via pyhwp `hwp5html` — handling government HWP that LibreOffice's
filter fails on. Legacy ppt/doc/xls and hwpx go through LibreOffice conversion.)

Two design principles:

- **Open-source first, provider-neutral.** The default backend is an open model served
  through an OpenAI-compatible endpoint (vLLM/Ollama/…). Gemini and Claude are used only
  as **optional escalation / cross-check** for low-confidence fields.
- **Quality first = multi-pass pipeline.** Not a single LLM call, but
  **(1) open OCR/layout for scans/images/HWP (Stage A) → (2) self-consistency structured
  extraction (Stage B) → (3) verification (LLM-as-judge), confidence, and low-confidence
  re-extraction (Stage C)** to raise accuracy.

## Install

Use either `requirements.txt` (pip) or the `pyproject.toml` extras:

```bash
python -m venv .venv && source .venv/bin/activate

# Option A) requirements.txt — core + default open-source backend
pip install -r requirements.txt
pip install -e .                 # register the CLI (docs-reader)
# dev: pip install -r requirements-dev.txt

# Option B) pyproject extras
pip install -e ".[openai]"       # open-source / OpenAI-compatible backend (default)
pip install -e ".[ocr]"          # Stage A OCR (rapidocr, CPU)
pip install -e ".[ocr-korean]"   # Korean OCR (PaddleOCR-korean)
pip install -e ".[gemini]"       # Gemini escalation
pip install -e ".[claude]"       # Claude escalation
pip install -e ".[hwp]"          # HWP direct parsing (pyhwp)
pip install -e ".[all,dev]"      # everything + pytest
```

System dependency: **LibreOffice (`soffice`)** — needed for Office/HWP → PDF conversion
(`apt install libreoffice` / `brew install --cask libreoffice`).

### Configuration (.env)

Copy `.env.example` to `.env` and fill it in; it is auto-loaded at runtime (python-dotenv).
Real shell environment variables always take precedence over `.env`.

```bash
cp .env.example .env
```

Key variables: `DOCS_READER_BASE_URL`, `DOCS_READER_TEXT_MODEL`, `DOCS_READER_VISION_MODEL`,
`DOCS_READER_OCR`, `DOCS_READER_CUDA`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`.

## Open-source backend server (default)

Any OpenAI-compatible endpoint works. Example with Ollama:

```bash
ollama serve
ollama pull gemma3:4b                     # text extraction (default, best overall)
ollama pull qwen2.5vl:7b                  # vision (scans/images)
export DOCS_READER_BASE_URL=http://localhost:11434/v1
```

**The default model is `gemma3:4b`** (internal benchmark #1: 96.7% accuracy, 100% on Korean).
Change it with `DOCS_READER_TEXT_MODEL`. vLLM / LM Studio / OpenRouter work the same way —
just change `--base-url` / `DOCS_READER_BASE_URL`.

### GPU (CUDA)

A single `--cuda` flag uses the GPU — it **auto-starts a GPU Ollama on :11500** and routes there.

```bash
docs-reader extract doc.pdf --schema schemas/invoice.py --cuda
docs-reader providers                     # show GPU server / model status
```

- Even when the system Ollama is a **snap** (whose sandbox forces CPU), docs_reader runs the
  snap's bundled binary + CUDA libraries outside the sandbox (no sudo), reusing the models.
  Manual start: `bash tools/ollama_gpu.sh`.
- To always use the GPU, set `DOCS_READER_CUDA=1` in `.env`. Point at a different GPU
  endpoint with `--base-url`.
- Measured: **3–4× faster** than CPU on an RTX 4070 Ti SUPER (same accuracy).

## Korean (recommended)

Korean quality is decided at two layers.

**1) OCR (scans/images/HWP)** — the default `rapidocr` is weak on Korean; use a
Korean-specialized OCR:

```bash
pip install -e ".[ocr-korean]"     # PaddleOCR-korean (recommended)  or
pip install -e ".[ocr-easyocr]"    # EasyOCR (simpler install)
docs-reader extract scan.pdf --schema schemas/invoice.py --ocr korean
```

`--ocr korean` auto-selects the first available engine: PaddleOCR-korean → EasyOCR (ko).
(`--ocr paddle` / `--ocr easyocr` to pick explicitly, `--ocr-lang` to change language.)

**2) Extraction LLM** — swap in a Korean-specialized open model (provider-neutral, just change
the model tag):

| Use | Korean-specialized open models (examples) |
| --- | --- |
| Text | EXAONE 3.5 (LG) · SOLAR (Upstage) · Qwen2.5 (good Korean) |
| Vision (docs) | VARCO-VISION (NCSOFT, Korean-doc focused) · Qwen2.5-VL |

```bash
ollama pull exaone3.5:7.8b
export DOCS_READER_TEXT_MODEL=exaone3.5:7.8b
# set the vision model too via DOCS_READER_VISION_MODEL (e.g. varco-vision)
```

Gemini/Claude escalation are also strong at Korean, so cross-checking low-confidence fields
with `--escalate` can push Korean accuracy higher.

## Usage

```bash
# Extract from a single document (default: open-source + verification pass)
docs-reader extract invoice.pdf --schema schemas/invoice.py -o out.json

# Inspect loading/routing only (no LLM call)
docs-reader extract scan.pdf --schema schemas/invoice.py --dry-run

# Max quality: 5-sample self-consistency + commercial cross-check on low-confidence fields
docs-reader extract form.hwp --schema schemas/invoice.py \
    --samples 5 --escalate --min-confidence 0.8

# Batch a directory
docs-reader batch ./docs --schema schemas/invoice.py -o ./out

# Check backends / credentials / GPU
docs-reader providers
```

Key options: `--provider opensource|gemini|claude|mock`, `--model`, `--base-url`, `--cuda`,
`--force-vision/--force-text`, `--office-vision`, `--ocr auto|korean|paddle|easyocr|rapidocr|docling|none`,
`--samples N`, `--verify/--no-verify`, `--escalate`, `--min-confidence`, `--data-only`,
`--tables/--no-tables`, `--extract-images`, `--images-dir DIR`, `--figures-vision`,
`--drop-hallucinations/--keep-hallucinations`, `--grounding/--no-grounding`.

### Table & image extraction

- **Tables**: detected via PyMuPDF `find_tables` (PDF) or the Office table API, converted to
  **Markdown tables** and injected into the LLM input text (much better table-field accuracy
  than flat text). Disable with `--no-tables`. Put an array field like `line_items` in the
  schema and the table is extracted directly into structured JSON.
- **Embedded images/figures**: `--extract-images` pulls images embedded in the document
  (PDF/docx/pptx/xlsx/HWP) to files under `--images-dir` (default `./extracted_images/<name>/`)
  and records path/page/size in the output `meta.images`.
- **Reading figures as values**: `--figures-vision` also feeds extracted figures to the vision
  model, attempting to read values out of charts/figures inside an otherwise-text document.

```bash
# Extract a table into line_items + pull logo/figure images to files
docs-reader extract report.pdf --schema schemas/invoice.py \
    --extract-images --images-dir ./out/imgs -o out.json
```

## Schema definition (both supported)

- **Pydantic** (`.py`): designate the model with `Schema = YourModel` (or a single model in the
  file). Type validation/coercion.
- **JSON Schema** (`.json`): language-agnostic; define without Python.
- **Few-shot** (optional): a `<name>.examples.json` sidecar is injected into the prompt as
  examples.

See `schemas/invoice.py`, `schemas/invoice.json`, `schemas/invoice.examples.json`.

## Hallucination control

Actively removes hallucinated values (values not in the document). Not just a confidence flag —
it **nulls the value**.

- **Abstention prompt**: "If unsure, null. Do not fill from world knowledge or inference."
- **Judge suppression (Stage C)**: fields the LLM-as-judge deems unsupported by the source
  (`verify_confidence < threshold`) are dropped.
- **Deterministic source grounding**: checks that an extracted scalar actually appears in the
  source text/OCR (numbers matched including comma/decimal forms). If absent, it is dropped.
- Dropped items are recorded in the output `meta.dropped_hallucinations` with reasons
  (`judge_unsupported` / `not_in_source`).

Options: `--drop-hallucinations/--keep-hallucinations` (on by default),
`--grounding/--no-grounding`, `--hallucination-threshold 0.5`.

**Measured example (llama3.2:3b, Korean scan)** — a small model hallucinated the string
`"null"` for `currency`; control caught it by both detectors and removed it:

```json
"dropped_hallucinations": [
  {"field": "currency", "value": "null", "reasons": ["judge_unsupported(0.00)", "not_in_source"]}
]
```

## Accuracy evaluation

Measures field accuracy (precision/recall/F1, hallucination count) and OCR accuracy (CER/WER)
against a labeled dataset (`<name>.<ext>` + `<name>.gold.json`; `<name>.gold.txt` for OCR).

```bash
python tools/make_eval_dataset.py            # generate example labeled dataset (eval/dataset)

# OCR accuracy only (no LLM) — real Korean OCR measurement
docs-reader eval eval/dataset --schema schemas/invoice.py --ocr-only --ocr korean

# Field-extraction accuracy (needs an LLM; after connecting a model server/key)
docs-reader eval eval/dataset --schema schemas/invoice.py --provider opensource -o report.json
```

**Metrics**
- Field: `field_accuracy` (value match + correctly-empty), `precision`/`recall`/`f1`,
  `hallucinations` (filled a field that is empty in gold). Numbers/dates/commas/lists
  (order-insensitive) are normalized before comparison.
- OCR: `CER` (character error rate) / `WER` (word error rate) → `char_accuracy`/`word_accuracy`.

**Measured example (this repo's PaddleOCR-korean, Korean scanned invoice)**

```text
[OCR] korean_scan.pdf  char_acc=100.0%  word_acc=71.4%
```

Character recognition is 100%; the word-level gap is pure Korean spacing variance, which does
not affect field extraction.

### Benchmark results

Field-extraction accuracy per open-source model on the labeled dataset (English text / table /
Korean scanned invoice — 3 docs × 10 fields). Hardware: RTX 4070 Ti SUPER (GPU), PaddleOCR-korean.
Reproduce: `python tools/benchmark.py` (GPU server via `tools/ollama_gpu.sh`).

| Model | Accuracy | Precision | Recall | **F1** | Halluc | Time (GPU) |
| --- | --- | --- | --- | --- | --- | --- |
| **gemma3:4b** (default) | **96.7%** | 95.2 | 100.0 | **97.6** | 1 | 22.7s |
| exaone3.5:7.8b (LG, Korean) | 93.3% | 90.5 | 95.0 | 92.7 | 1 | 24.5s |
| qwen2.5:3b (value pick) | 93.3% | 90.5 | 95.0 | 92.7 | 1 | 23.7s |
| qwen2.5:7b-instruct | 90.0% | 86.4 | 95.0 | 90.5 | 2 | 25.3s |
| llama3.2:3b | 83.3% | 81.8 | 90.0 | 85.7 | 3 | 18.7s |
| llama3.1:8b | 80.0% | 76.2 | 80.0 | 78.0 | 2 | 23.5s |

**Korean scanned invoice only** (per field):

| Model | Accuracy | F1 | Note |
| --- | --- | --- | --- |
| gemma3:4b / qwen2.5:3b | **100%** | **100** | all correct |
| exaone3.5:7.8b | 90% | 83.3 | `currency` 원↔KRW normalization diff |
| qwen2.5:7b | 90% | 92.3 | line_items hallucination |
| llama3.1:8b | 60% | 50 | heavy Korean hallucination — not recommended |

**GPU (CUDA) speed** (3 docs/model, CPU → GPU): gemma3:4b 94.0s → **22.7s (4.1×)**,
qwen2.5:7b 107.6s → **25.3s (4.3×)**, llama3.1:8b 102.4s → **23.5s (4.4×)** — same accuracy,
**3–4×** faster.

**Hallucination-control effect** (raw → grounding control): precision rises on hallucination-prone
models (llama3.1: P 76.2→84.2, F1 78→82.1). Strong models may slightly over-drop semantically
normalized values (원→KRW), so use it together with `--verify` (the judge pass).

> Note: this is a small 3-document benchmark. To confirm on your real documents (HWP / statements
> of work), label those documents with gold values and re-measure.

## Architecture

```text
file → loaders (hybrid) ── text layer present → text
                        └─ scan/image/HWP → OCR (Stage A) or image
        → ContentPart[] (text|image, provider-neutral)
        → pipeline: Stage B (self-consistency extraction) → Stage C (verify · confidence · gated re-extraction)
        → Pydantic validation → JSON (+ per-field confidence/evidence)
```

- Loaders: `src/docs_reader/loaders/` (pdf/office/image/hwp) + `convert.py` (soffice)
- OCR Stage A: `src/docs_reader/ocr/` (rapidocr/paddle/easyocr/docling adapters; falls back to vision)
- Providers: `src/docs_reader/providers/` (openai_compat/gemini/claude/mock)
- Pipeline: `src/docs_reader/pipeline/` (extract/verify/confidence/hallucination)

## Development / tests

```bash
pip install -e ".[dev]"
python tools/make_samples.py     # generate demo docs under samples/
pytest -q
```

## License

MIT — see [LICENSE](LICENSE). Note that some **core dependencies are AGPL-3.0** (PyMuPDF, and
the optional pyhwp), which has copyleft implications when distributing. See
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
