"""Command-line interface (Typer)."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Optional

import typer


def _resolve_path(p: Path) -> Path:
    """Resolve a path robustly across Korean filename Unicode normalization (NFC/NFD).

    Filenames on disk may be stored in a different normalization form than the one a
    user pastes on the command line, so a byte-for-byte match can fail even though the
    file exists. Fall back to comparing NFC-normalized names within the parent dir.
    """
    if p.exists():
        return p
    for form in ("NFC", "NFD"):
        cand = Path(unicodedata.normalize(form, str(p)))
        if cand.exists():
            return cand
    parent = p.parent if str(p.parent) else Path(".")
    if parent.exists():
        target = unicodedata.normalize("NFC", p.name)
        for child in parent.iterdir():
            if unicodedata.normalize("NFC", child.name) == target:
                return child
    raise typer.BadParameter(f"file not found: {p}")


def _start_cuda_if_needed(settings: Settings) -> None:
    """Start (and point at) the GPU Ollama when --cuda is on and no custom URL given."""
    if not settings.cuda:
        return
    from .cuda import GPU_BASE_URL, ensure_gpu_server

    if settings.os_base_url == GPU_BASE_URL:
        typer.echo("[cuda] ensuring GPU Ollama on :11500 ...", err=True)
        settings.os_base_url = ensure_gpu_server()

from ._io import quiet_stdout
from .config import Settings
from .loaders import SUPPORTED_EXTS, is_supported, load_document
from .output import to_json, write_output
from .pipeline import run_pipeline
from .schema import load_schema

app = typer.Typer(
    add_completion=False,
    help="LLM-based structured extraction from documents into schema-validated JSON.",
    no_args_is_help=True,
)


def _settings_from_opts(
    *,
    provider: Optional[str],
    model: Optional[str],
    base_url: Optional[str],
    cuda: bool = False,
    force_vision: bool,
    force_text: bool,
    office_vision: bool,
    ocr: Optional[str],
    ocr_lang: Optional[str],
    dpi: int,
    samples: int,
    verify: bool,
    escalate: bool,
    min_confidence: float,
    temperature: float,
    tables: bool = True,
    extract_images: bool = False,
    images_dir: Optional[str] = None,
    figures_vision: bool = False,
    drop_hallucinations: bool = True,
    hallucination_threshold: float = 0.5,
    grounding: bool = True,
) -> Settings:
    s = Settings()
    if provider:
        s.provider = provider  # type: ignore[assignment]
    if model:
        s.model_override = model
    # CUDA: route the open-source backend at the GPU Ollama endpoint (started lazily
    # before the pipeline runs). --base-url still wins if given explicitly.
    if cuda or s.cuda:
        from .cuda import GPU_BASE_URL

        s.cuda = True
        s.provider = "opensource"  # type: ignore[assignment]
        s.os_base_url = base_url or GPU_BASE_URL
    elif base_url:
        s.os_base_url = base_url
    if force_vision:
        s.force_route = "vision"
    elif force_text:
        s.force_route = "text"
    if ocr:
        s.ocr_engine = ocr
    if ocr_lang:
        s.ocr_lang = ocr_lang
    s.office_vision = office_vision
    s.dpi = dpi
    s.samples = samples
    s.verify = verify
    s.escalate = escalate
    s.min_confidence = min_confidence
    s.temperature = temperature
    s.tables = "auto" if tables else "off"
    s.extract_images = extract_images
    s.images_dir = images_dir
    s.figures_vision = figures_vision
    s.drop_hallucinations = drop_hallucinations
    s.hallucination_threshold = hallucination_threshold
    s.require_grounding = grounding
    return s


@app.command()
def extract(
    file: Path = typer.Argument(..., help="Document to extract from"),
    schema: Path = typer.Option(..., "--schema", "-s", exists=True, help="Pydantic .py or JSON .json schema"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON path ('-' = stdout)"),
    provider: Optional[str] = typer.Option(None, "--provider", help="opensource|gemini|claude|mock"),
    model: Optional[str] = typer.Option(None, "--model", help="Override model id"),
    base_url: Optional[str] = typer.Option(None, "--base-url", help="OpenAI-compatible endpoint URL"),
    cuda: bool = typer.Option(False, "--cuda", help="Use GPU Ollama (auto-starts it on :11500)"),
    force_vision: bool = typer.Option(False, "--force-vision", help="Force scanned/vision path"),
    force_text: bool = typer.Option(False, "--force-text", help="Force text-layer path"),
    office_vision: bool = typer.Option(False, "--office-vision", help="Office -> PDF -> vision/OCR"),
    ocr: Optional[str] = typer.Option(None, "--ocr", help="auto|korean|paddle|easyocr|rapidocr|docling|none"),
    ocr_lang: Optional[str] = typer.Option(None, "--ocr-lang", help="OCR language for korean/paddle/easyocr (default: korean)"),
    dpi: int = typer.Option(200, "--dpi", help="Rasterization DPI for scanned pages"),
    samples: int = typer.Option(1, "--samples", help="Self-consistency samples (vote over N)"),
    verify: bool = typer.Option(True, "--verify/--no-verify", help="Stage C verification pass"),
    escalate: bool = typer.Option(False, "--escalate", help="Allow Gemini/Claude on low-confidence fields"),
    min_confidence: float = typer.Option(0.7, "--min-confidence", help="Confidence gate threshold"),
    temperature: float = typer.Option(0.0, "--temperature", help="Base sampling temperature"),
    tables: bool = typer.Option(True, "--tables/--no-tables", help="Inject detected tables as Markdown"),
    extract_images: bool = typer.Option(False, "--extract-images", help="Pull embedded images to files"),
    images_dir: Optional[Path] = typer.Option(None, "--images-dir", help="Where to write extracted images"),
    figures_vision: bool = typer.Option(False, "--figures-vision", help="Also feed extracted figures to the vision model"),
    drop_hallucinations: bool = typer.Option(True, "--drop-hallucinations/--keep-hallucinations", help="Null out judge-unsupported / ungrounded values"),
    hallucination_threshold: float = typer.Option(0.5, "--hallucination-threshold", help="Verify-confidence below this is dropped"),
    grounding: bool = typer.Option(True, "--grounding/--no-grounding", help="Drop scalar values absent from the source text"),
    data_only: bool = typer.Option(False, "--data-only", help="Emit only extracted data (no meta/confidence)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Load + route only; no LLM calls"),
) -> None:
    """Extract structured JSON from a single document."""
    settings = _settings_from_opts(
        provider=provider, model=model, base_url=base_url, cuda=cuda, force_vision=force_vision,
        force_text=force_text, office_vision=office_vision, ocr=ocr, ocr_lang=ocr_lang,
        dpi=dpi, samples=samples,
        verify=verify, escalate=escalate, min_confidence=min_confidence, temperature=temperature,
        tables=tables, extract_images=extract_images,
        images_dir=str(images_dir) if images_dir else None, figures_vision=figures_vision,
        drop_hallucinations=drop_hallucinations, hallucination_threshold=hallucination_threshold,
        grounding=grounding,
    )
    file = _resolve_path(file)
    loaded_schema = load_schema(schema)
    if not dry_run:
        _start_cuda_if_needed(settings)
    with quiet_stdout():  # keep library/OCR chatter off stdout so JSON stays clean
        loaded = load_document(file, settings)
        result = None if dry_run else run_pipeline(loaded, loaded_schema, settings)

    if dry_run:
        payload = {
            "document": loaded.summary(),
            "schema": {"name": loaded_schema.name, "has_pydantic": loaded_schema.model_cls is not None,
                       "examples": len(loaded_schema.examples)},
            "provider": settings.resolved_provider(),
        }
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    write_output(result, output, include_meta=not data_only)


@app.command()
def batch(
    directory: Path = typer.Argument(..., exists=True, file_okay=False, help="Directory of documents"),
    schema: Path = typer.Option(..., "--schema", "-s", exists=True),
    output_dir: Path = typer.Option(..., "--output", "-o", help="Directory for <name>.json results"),
    provider: Optional[str] = typer.Option(None, "--provider"),
    model: Optional[str] = typer.Option(None, "--model"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
    cuda: bool = typer.Option(False, "--cuda", help="Use GPU Ollama (auto-starts it on :11500)"),
    samples: int = typer.Option(1, "--samples"),
    verify: bool = typer.Option(True, "--verify/--no-verify"),
    escalate: bool = typer.Option(False, "--escalate"),
    min_confidence: float = typer.Option(0.7, "--min-confidence"),
) -> None:
    """Extract from every supported file in a directory."""
    settings = _settings_from_opts(
        provider=provider, model=model, base_url=base_url, cuda=cuda, force_vision=False,
        force_text=False, office_vision=False, ocr=None, ocr_lang=None, dpi=200, samples=samples,
        verify=verify, escalate=escalate, min_confidence=min_confidence, temperature=0.0,
    )
    _start_cuda_if_needed(settings)
    loaded_schema = load_schema(schema)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in directory.iterdir() if p.is_file() and is_supported(p))
    if not files:
        typer.echo(f"No supported files in {directory} ({', '.join(sorted(SUPPORTED_EXTS))})")
        raise typer.Exit(1)
    for f in files:
        try:
            with quiet_stdout():
                loaded = load_document(f, settings)
                result = run_pipeline(loaded, loaded_schema, settings)
            out_path = output_dir / (f.stem + ".json")
            out_path.write_text(to_json(result) + "\n", encoding="utf-8")
            lo = result.min_confidence()
            typer.echo(f"[ok]   {f.name} -> {out_path.name}  (min_conf={lo:.2f})")
        except Exception as e:  # noqa: BLE001
            typer.echo(f"[fail] {f.name}: {e}")


@app.command("eval")
def evaluate_cmd(
    dataset: Path = typer.Argument(..., exists=True, file_okay=False, help="Dir with <name>.<ext> + <name>.gold.json (+ optional <name>.gold.txt)"),
    schema: Path = typer.Option(..., "--schema", "-s", exists=True),
    provider: Optional[str] = typer.Option(None, "--provider"),
    model: Optional[str] = typer.Option(None, "--model"),
    base_url: Optional[str] = typer.Option(None, "--base-url"),
    cuda: bool = typer.Option(False, "--cuda", help="Use GPU Ollama (auto-starts it on :11500)"),
    ocr: Optional[str] = typer.Option(None, "--ocr", help="auto|korean|paddle|easyocr|rapidocr|docling|none"),
    ocr_lang: Optional[str] = typer.Option(None, "--ocr-lang"),
    samples: int = typer.Option(1, "--samples"),
    verify: bool = typer.Option(True, "--verify/--no-verify"),
    escalate: bool = typer.Option(False, "--escalate"),
    ocr_only: bool = typer.Option(False, "--ocr-only", help="Only score OCR (CER/WER); no LLM extraction"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write full JSON report"),
) -> None:
    """Evaluate accuracy against a labeled dataset (field P/R/F1 + OCR CER/WER)."""
    from .evaluate import (
        aggregate_field_metrics,
        find_samples,
        load_gold,
        score_ocr,
        score_record,
    )

    settings = _settings_from_opts(
        provider=provider, model=model, base_url=base_url, cuda=cuda, force_vision=False,
        force_text=False, office_vision=False, ocr=ocr, ocr_lang=ocr_lang, dpi=200, samples=samples,
        verify=verify, escalate=escalate, min_confidence=0.7, temperature=0.0,
    )
    if not ocr_only:
        _start_cuda_if_needed(settings)
    schema_obj = load_schema(schema)
    keys = list(schema_obj.json_schema.get("properties", {}).keys()) or None
    entries = find_samples(dataset)
    if not entries:
        typer.echo(f"No '<name>.gold.json' labeled samples found in {dataset}")
        raise typer.Exit(1)

    report: dict = {"samples": [], "provider": settings.resolved_provider()}
    field_records = []
    ocr_scores = []

    for e in entries:
        name = e["doc"].name
        row: dict = {"name": name}
        with quiet_stdout():
            loaded = load_document(e["doc"], settings)
        row["route"] = loaded.route

        if "gold_txt" in e:
            gold_txt = e["gold_txt"].read_text(encoding="utf-8")
            import re as _re
            pred_text = _re.sub(r"---\s*page\s*\d+\s*---", " ", loaded.text_blob())
            om = score_ocr(pred_text, gold_txt)
            row["ocr"] = om
            ocr_scores.append(om)
            typer.echo(f"[OCR ] {name:22s} route={loaded.route:6s} "
                       f"char_acc={om['char_accuracy']*100:5.1f}%  word_acc={om['word_accuracy']*100:5.1f}%")

        if not ocr_only:
            gold = load_gold(e["gold_json"])
            try:
                with quiet_stdout():
                    result = run_pipeline(loaded, schema_obj, settings)
                rs = score_record(result.data, gold, keys)
                m = rs.metrics()
                row["fields"] = m
                row["field_counts"] = rs.counts
                field_records.append(rs)
                typer.echo(f"[FLD ] {name:22s} acc={m['field_accuracy']*100:5.1f}%  "
                           f"P={m['precision']*100:5.1f}  R={m['recall']*100:5.1f}  F1={m['f1']*100:5.1f}  "
                           f"halluc={m['hallucinations']}")
            except Exception as ex:  # noqa: BLE001
                row["fields_error"] = str(ex)
                typer.echo(f"[FLD ] {name:22s} ERROR: {ex}")
        report["samples"].append(row)

    typer.echo("-" * 64)
    if ocr_scores:
        avg_char = sum(s["char_accuracy"] for s in ocr_scores) / len(ocr_scores)
        avg_word = sum(s["word_accuracy"] for s in ocr_scores) / len(ocr_scores)
        report["ocr_aggregate"] = {"char_accuracy": avg_char, "word_accuracy": avg_word, "n": len(ocr_scores)}
        typer.echo(f"OCR   avg char_acc={avg_char*100:.1f}%  word_acc={avg_word*100:.1f}%  (n={len(ocr_scores)})")
    if field_records:
        agg = aggregate_field_metrics(field_records)
        report["field_aggregate"] = agg
        typer.echo(f"FIELD acc={agg['field_accuracy']*100:.1f}%  P={agg['precision']*100:.1f}  "
                   f"R={agg['recall']*100:.1f}  F1={agg['f1']*100:.1f}  halluc={agg['hallucinations']}  "
                   f"(n={len(field_records)})")

    if output:
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        typer.echo(f"report -> {output}")


@app.command()
def providers() -> None:
    """Show which backends are usable (credentials / endpoint reachable)."""
    from .providers import build_backend

    from .cuda import GPU_BASE_URL, server_up, uses_gpu

    settings = Settings()
    typer.echo(f"Default provider: {settings.resolved_provider()}")
    typer.echo(f"Default model: {settings.os_text_model}")
    typer.echo(f"Open-source endpoint: {settings.os_base_url}")
    gpu = server_up()
    typer.echo(f"CUDA/GPU Ollama ({GPU_BASE_URL}): {'running' if gpu else 'not running'}"
               + (" [GPU]" if gpu and uses_gpu() else ""))
    for name in ("opensource", "gemini", "claude"):
        try:
            backend = build_backend(name, settings)  # type: ignore[arg-type]
            ok = backend.is_available()
        except Exception as e:  # noqa: BLE001
            ok = False
            typer.echo(f"  {name:11s}: unavailable ({e})")
            continue
        typer.echo(f"  {name:11s}: {'available' if ok else 'unavailable'}")


if __name__ == "__main__":  # pragma: no cover
    app()
