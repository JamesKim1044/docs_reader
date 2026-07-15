"""Extraction pipeline orchestration.

Stages, all open-source by default:
  A. (in loaders) OCR/layout for scanned pages.
  B. self-consistency structured extraction  (extract.py)
  C. verification + confidence + low-confidence gating/escalation  (verify.py, confidence.py)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..config import Settings
from ..providers import escalation_backends, select_backend
from ..providers._common import build_instruction
from ..providers.base import LLMBackend
from ..schema import LoadedSchema
from ..types import LoadedDocument
from .confidence import combine_confidence, gate_and_recheck
from .extract import extract_consistent
from .hallucination import control as hallucination_control
from .verify import verify_fields


@dataclass
class ExtractionOutput:
    data: dict[str, Any]
    confidence: dict[str, float]
    evidence: dict[str, str] = field(default_factory=dict)
    provider: str = ""
    model: Optional[str] = None
    route: str = ""
    source_path: str = ""
    passes: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def min_confidence(self) -> float:
        return min(self.confidence.values()) if self.confidence else 1.0


def run_pipeline(
    loaded: LoadedDocument,
    schema: LoadedSchema,
    settings: Settings,
    *,
    backend: Optional[LLMBackend] = None,
) -> ExtractionOutput:
    backend = backend or select_backend(settings)
    instruction = build_instruction(schema.json_schema, schema.examples)

    # Stage B — self-consistency extraction.
    merged, agreement, raw_results, model = extract_consistent(
        backend,
        loaded.parts,
        schema,
        instruction,
        samples=settings.samples,
        base_temperature=settings.temperature,
    )

    # Stage C — verification.
    verify_conf: dict[str, float] = {}
    evidence: dict[str, str] = {}
    if settings.verify:
        verify_conf, evidence = verify_fields(backend, loaded.parts, schema.json_schema, merged)
    confidence = combine_confidence(agreement, verify_conf)

    # Stage C — low-confidence gating / escalation.
    escalation_audit: list[dict[str, Any]] = []
    if settings.escalate:
        esc = escalation_backends(settings)
        merged, confidence, escalation_audit = gate_and_recheck(
            loaded.parts,
            schema,
            merged,
            confidence,
            min_confidence=settings.min_confidence,
            escalation_backends=esc,
        )

    # Hallucination control — drop judge-unsupported / ungrounded values.
    dropped: list[dict[str, Any]] = []
    if settings.drop_hallucinations:
        merged, dropped = hallucination_control(
            merged,
            verify_conf,
            loaded.text_blob(),
            threshold=settings.hallucination_threshold,
            require_grounding=settings.require_grounding,
        )
        for d in dropped:
            confidence[d["field"]] = 0.0

    # Final validation (Pydantic when available).
    validation_error: Optional[str] = None
    try:
        data = schema.validate(merged)
    except Exception as e:  # noqa: BLE001
        data = merged
        validation_error = str(e)

    return ExtractionOutput(
        data=data,
        confidence=confidence,
        evidence=evidence,
        provider=getattr(backend, "name", ""),
        model=model,
        route=loaded.route,
        source_path=loaded.source_path,
        passes={
            "samples": settings.samples,
            "agreement": agreement,
            "verify_confidence": verify_conf,
            "escalation": escalation_audit,
            "dropped_hallucinations": dropped,
        },
        meta={
            "loader": loaded.meta,
            "page_count": loaded.page_count,
            "validation_error": validation_error,
            "images": loaded.meta.get("images", []),
            "tables_detected": loaded.meta.get("tables_detected", 0),
            "dropped_hallucinations": dropped,
        },
    )


__all__ = ["ExtractionOutput", "run_pipeline"]
