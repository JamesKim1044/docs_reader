"""Accuracy evaluation.

Two layers are scored:

- **Field extraction** (needs an LLM): per-field key-information-extraction metrics —
  precision / recall / F1 over fields whose gold value is present, plus a
  hallucination count (model filled a field that is empty in gold) and overall
  field accuracy (including correctly-left-empty fields).
- **OCR** (no LLM needed): character/word error rate (CER/WER) between the loaded
  document text and a gold transcript.

Gold data lives next to each document: ``<name>.gold.json`` (field labels) and,
optionally, ``<name>.gold.txt`` (OCR transcript).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# --------------------------------------------------------------------------- #
# value normalization + matching
# --------------------------------------------------------------------------- #
def is_empty(v: Any) -> bool:
    return v is None or (isinstance(v, (str, list, dict)) and len(v) == 0)


def _norm_scalar(v: Any) -> Any:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 4)
    s = str(v).strip().lower()
    # numeric-looking string -> number (handles "99,000" / "99.0")
    cleaned = s.replace(",", "").replace("_", "")
    try:
        return round(float(cleaned), 4)
    except ValueError:
        return s


def values_match(gold: Any, pred: Any) -> bool:
    if is_empty(gold) and is_empty(pred):
        return True
    if is_empty(gold) or is_empty(pred):
        return False
    if isinstance(gold, list) or isinstance(pred, list):
        return _list_match(gold or [], pred or [])
    if isinstance(gold, dict) or isinstance(pred, dict):
        return _dict_match(gold or {}, pred or {})
    return _norm_scalar(gold) == _norm_scalar(pred)


def _dict_match(gold: dict, pred: dict) -> bool:
    keys = set(gold) | set(pred)
    return all(values_match(gold.get(k), pred.get(k)) for k in keys)


def _list_match(gold: list, pred: list) -> bool:
    if len(gold) != len(pred):
        return False
    # order-insensitive: greedily match each gold item to an unused pred item
    used = [False] * len(pred)
    for g in gold:
        found = False
        for i, p in enumerate(pred):
            if not used[i] and values_match(g, p):
                used[i] = True
                found = True
                break
        if not found:
            return False
    return True


# --------------------------------------------------------------------------- #
# field scoring
# --------------------------------------------------------------------------- #
@dataclass
class FieldOutcome:
    field: str
    status: str  # correct | correct_null | wrong | missing | hallucinated
    gold: Any = None
    pred: Any = None


@dataclass
class RecordScore:
    outcomes: list[FieldOutcome] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        c = {"correct": 0, "correct_null": 0, "wrong": 0, "missing": 0, "hallucinated": 0}
        for o in self.outcomes:
            c[o.status] += 1
        return c

    def metrics(self) -> dict[str, float]:
        c = self.counts
        total = sum(c.values()) or 1
        tp = c["correct"]
        fn = c["wrong"] + c["missing"]
        fp = c["wrong"] + c["hallucinated"]
        precision = tp / (tp + fp) if (tp + fp) else 1.0
        recall = tp / (tp + fn) if (tp + fn) else 1.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        return {
            "field_accuracy": (c["correct"] + c["correct_null"]) / total,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "hallucinations": c["hallucinated"],
            "total_fields": total,
        }


def score_record(pred: dict, gold: dict, keys: Optional[list[str]] = None) -> RecordScore:
    keys = keys or sorted(set(gold) | set(pred))
    outcomes: list[FieldOutcome] = []
    for k in keys:
        g, p = gold.get(k), pred.get(k)
        if is_empty(g) and is_empty(p):
            status = "correct_null"
        elif is_empty(g) and not is_empty(p):
            status = "hallucinated"
        elif not is_empty(g) and is_empty(p):
            status = "missing"
        elif values_match(g, p):
            status = "correct"
        else:
            status = "wrong"
        outcomes.append(FieldOutcome(k, status, g, p))
    return RecordScore(outcomes)


# --------------------------------------------------------------------------- #
# OCR scoring (CER / WER)
# --------------------------------------------------------------------------- #
def _levenshtein(a: list, b: list) -> int:
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def _clean(t: str) -> str:
    return " ".join(t.split())


def cer(pred: str, gold: str) -> float:
    g = _clean(gold).replace(" ", "")
    p = _clean(pred).replace(" ", "")
    if not g:
        return 0.0 if not p else 1.0
    return _levenshtein(list(p), list(g)) / len(g)


def wer(pred: str, gold: str) -> float:
    g = _clean(gold).split()
    p = _clean(pred).split()
    if not g:
        return 0.0 if not p else 1.0
    return _levenshtein(p, g) / len(g)


def score_ocr(pred_text: str, gold_text: str) -> dict[str, float]:
    c = cer(pred_text, gold_text)
    w = wer(pred_text, gold_text)
    return {"cer": c, "wer": w, "char_accuracy": max(0.0, 1 - c), "word_accuracy": max(0.0, 1 - w)}


# --------------------------------------------------------------------------- #
# dataset-level driver
# --------------------------------------------------------------------------- #
def find_samples(dataset_dir: str | Path) -> list[dict[str, Path]]:
    """Discover (document, gold.json, gold.txt) triples in a directory."""
    d = Path(dataset_dir)
    out: list[dict[str, Path]] = []
    for gold in sorted(d.glob("*.gold.json")):
        stem = gold.name[: -len(".gold.json")]
        docs = [p for p in d.glob(stem + ".*") if not p.name.endswith((".gold.json", ".gold.txt"))]
        if not docs:
            continue
        entry = {"doc": docs[0], "gold_json": gold}
        gtxt = d / (stem + ".gold.txt")
        if gtxt.exists():
            entry["gold_txt"] = gtxt
        out.append(entry)
    return out


def aggregate_field_metrics(records: list[RecordScore]) -> dict[str, float]:
    total = {"correct": 0, "correct_null": 0, "wrong": 0, "missing": 0, "hallucinated": 0}
    for r in records:
        for k, v in r.counts.items():
            total[k] += v
    agg = RecordScore(outcomes=[FieldOutcome("", s) for s, n in total.items() for _ in range(n)])
    return agg.metrics()


def load_gold(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    # allow either flat fields or {"data": {...}}
    return data.get("data", data) if isinstance(data, dict) else data
