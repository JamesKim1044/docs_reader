"""Runtime configuration resolved from CLI flags and environment variables.

Precedence for every field: explicit CLI value > environment variable > default.
The open-source (OpenAI-compatible) backend is the default; Gemini and Claude are
only used when explicitly selected or reached via low-confidence escalation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal, Optional

ProviderName = Literal["opensource", "gemini", "claude"]


def _load_dotenv_once() -> None:
    """Load a local .env (cwd or parents) if python-dotenv is available.

    Existing environment variables are never overridden, so real secrets in the
    shell win over the .env file.
    """
    try:
        from dotenv import find_dotenv, load_dotenv
    except Exception:  # dotenv optional; missing is fine
        return
    path = find_dotenv(usecwd=True)
    if path:
        load_dotenv(path, override=False)


_load_dotenv_once()


def _env(*names: str, default: Optional[str] = None) -> Optional[str]:
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return default


@dataclass
class Settings:
    # --- provider selection ---------------------------------------------------
    provider: Optional[ProviderName] = None  # None => auto (opensource first)

    # open-source / OpenAI-compatible endpoint (vLLM, Ollama, LM Studio, OpenRouter, ...)
    os_base_url: str = field(
        default_factory=lambda: _env(
            "DOCS_READER_BASE_URL", "OPENAI_BASE_URL", default="http://localhost:11434/v1"
        )
    )
    os_api_key: str = field(
        default_factory=lambda: _env("DOCS_READER_API_KEY", "OPENAI_API_KEY", default="not-needed")
    )
    os_text_model: str = field(
        default_factory=lambda: _env("DOCS_READER_TEXT_MODEL", default="gemma3:4b")
    )
    os_vision_model: str = field(
        default_factory=lambda: _env("DOCS_READER_VISION_MODEL", default="qwen2.5vl:7b")
    )

    # CUDA / GPU: when enabled, point the open-source backend at a GPU Ollama and
    # auto-start it if needed. Env DOCS_READER_CUDA=1 turns it on by default.
    cuda: bool = field(default_factory=lambda: _env("DOCS_READER_CUDA", default="") not in ("", "0", "false", "False"))

    gemini_api_key: Optional[str] = field(
        default_factory=lambda: _env("GEMINI_API_KEY", "GOOGLE_API_KEY")
    )
    gemini_model: str = field(
        default_factory=lambda: _env("DOCS_READER_GEMINI_MODEL", default="gemini-2.5-flash")
    )

    anthropic_api_key: Optional[str] = field(
        default_factory=lambda: _env("ANTHROPIC_API_KEY")
    )
    claude_model: str = field(
        default_factory=lambda: _env("DOCS_READER_CLAUDE_MODEL", default="claude-opus-4-8")
    )

    # --- quality / pipeline knobs --------------------------------------------
    samples: int = 1            # self-consistency: number of extraction samples to vote over
    verify: bool = True         # Stage C verification (LLM-as-judge)
    escalate: bool = False      # allow Gemini/Claude cross-check on low-confidence fields
    min_confidence: float = 0.7 # confidence gate threshold for re-check / escalation
    temperature: float = 0.0    # base sampling temperature (self-consistency bumps this)

    # --- hallucination control -----------------------------------------------
    drop_hallucinations: bool = True     # null out judge-unsupported / ungrounded values
    hallucination_threshold: float = 0.5 # verify-confidence below this => drop
    require_grounding: bool = True       # drop scalar values absent from the source text

    # --- loader knobs ---------------------------------------------------------
    force_route: Optional[str] = None  # "text" | "vision" — override auto routing
    office_vision: bool = False            # render Office docs to PDF -> vision instead of text
    ocr_engine: str = field(
        default_factory=lambda: _env("DOCS_READER_OCR", default="auto")
    )  # auto | korean | paddle | easyocr | rapidocr | docling | none
    ocr_lang: str = field(
        default_factory=lambda: _env("DOCS_READER_OCR_LANG", default="korean")
    )  # OCR language for korean/paddle/easyocr engines
    dpi: int = 200                          # rasterization DPI for scanned pages
    tables: str = "auto"                    # auto | off — inject detected tables as Markdown

    # --- embedded image / figure extraction ----------------------------------
    extract_images: bool = False            # pull embedded images out to files
    images_dir: Optional[str] = None        # output dir (default: ./extracted_images/<stem>)
    figures_vision: bool = False            # also attach extracted figures as vision parts

    # model / override passthroughs
    model_override: Optional[str] = None

    def resolved_provider(self) -> ProviderName:
        """Auto-select a provider when none is given: opensource > gemini > claude."""
        if self.provider:
            return self.provider
        return "opensource"
