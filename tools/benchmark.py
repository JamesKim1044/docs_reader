"""Quantitative accuracy benchmark across models on a labeled dataset.

Runs the real extraction pipeline for each model over eval/dataset and reports
field-level precision/recall/F1/accuracy + latency, so open-source (incl. Korean-
specialized) and Gemini can be compared head-to-head.

Usage:
    python tools/benchmark.py                       # default model set
    python tools/benchmark.py exaone3.5:7.8b qwen2.5:7b-instruct gemini
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from docs_reader._io import quiet_stdout
from docs_reader.config import Settings
from docs_reader.evaluate import aggregate_field_metrics, find_samples, load_gold, score_record
from docs_reader.loaders import load_document
from docs_reader.pipeline import run_pipeline
from docs_reader.pipeline.hallucination import control as hallucination_control
from docs_reader.schema import load_schema

import os

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "eval" / "dataset"
SCHEMA = ROOT / "schemas" / "invoice.py"
# Default to the GPU ollama on :11500; override with BENCH_OLLAMA.
OLLAMA = os.environ.get("BENCH_OLLAMA", "http://127.0.0.1:11500/v1")

DEFAULT_MODELS = [
    "exaone3.5:7.8b",       # LG EXAONE — Korean-specialized
    "hf.co/mykor/A.X-4.0-Light-gguf:Q4_K_M",  # SKT A.X — Korean-specialized
    "qwen2.5:7b-instruct",  # general, decent Korean
    "gemma3:4b",            # small general
    "llama3.1:8b",          # general
    "gemini",               # Gemini API (escalation tier)
]


def make_settings(model: str) -> Settings:
    s = Settings()
    s.verify = False
    s.samples = 1
    s.ocr_engine = "korean"
    s.drop_hallucinations = False  # get RAW model output; control is applied in-benchmark
    if model == "gemini":
        s.provider = "gemini"
    else:
        s.provider = "opensource"
        s.os_base_url = OLLAMA
        s.os_text_model = model
        s.os_vision_model = model
    return s


def run_model(model: str, schema, entries, keys) -> dict:
    settings = make_settings(model)
    raw_records, ctl_records = [], []
    t0 = time.time()
    for e in entries:
        gold = load_gold(e["gold_json"])
        try:
            with quiet_stdout():
                loaded = load_document(e["doc"], settings)
                result = run_pipeline(loaded, schema, settings)  # raw (no control)
            raw = result.data
            # Apply deterministic grounding control (no extra LLM call) for comparison.
            ctl, _ = hallucination_control(dict(raw), {}, loaded.text_blob(),
                                           threshold=0.5, require_grounding=True)
            raw_records.append(score_record(raw, gold, keys))
            ctl_records.append(score_record(ctl, gold, keys))
        except Exception as ex:  # noqa: BLE001
            print(f"  {e['doc'].name}: ERROR {str(ex)[:80]}")
    return {
        "model": model,
        "raw": aggregate_field_metrics(raw_records) if raw_records else {},
        "ctl": aggregate_field_metrics(ctl_records) if ctl_records else {},
        "seconds": time.time() - t0,
    }


def main() -> None:
    models = sys.argv[1:] or DEFAULT_MODELS
    schema = load_schema(SCHEMA)
    keys = list(schema.json_schema.get("properties", {}).keys())
    entries = find_samples(DATASET)
    print(f"dataset: {len(entries)} samples, {len(keys)} fields each  ({DATASET})")
    print(f"samples: {', '.join(e['doc'].name for e in entries)}")
    print("raw = model output as-is | ctl = + grounding hallucination control\n")

    results = []
    for m in models:
        print(f"running {m} ...", flush=True)
        try:
            results.append(run_model(m, schema, entries, keys))
        except Exception as ex:  # noqa: BLE001
            print(f"  skipped ({ex})")

    print("\n" + "=" * 92)
    print(f"{'model':<40} {'mode':<4} {'acc%':>6} {'P%':>6} {'R%':>6} {'F1%':>6} {'halluc':>7} {'sec':>7}")
    print("-" * 92)
    for r in sorted(results, key=lambda x: x["ctl"].get("f1", 0), reverse=True):
        for mode in ("raw", "ctl"):
            a = r[mode]
            if not a:
                print(f"{r['model']:<40} {mode:<4} {'(errored)':>28}")
                continue
            sec = f"{r['seconds']:7.1f}" if mode == "raw" else ""
            print(f"{r['model']:<40} {mode:<4} {a['field_accuracy']*100:6.1f} {a['precision']*100:6.1f} "
                  f"{a['recall']*100:6.1f} {a['f1']*100:6.1f} {a['hallucinations']:7d} {sec:>7}")
    print("=" * 92)


if __name__ == "__main__":
    main()
