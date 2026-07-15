"""Gemini backend (google-genai) — used as escalation / cross-check, not the default.

Supports native image input and JSON output. When a Pydantic model is available it
is passed as ``response_schema`` for typed parsing; otherwise the schema is embedded
in the instruction and the JSON text is parsed leniently.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from ..config import Settings
from ..types import ContentPart
from .base import ExtractionResult
from ._common import SYSTEM_PROMPT, parse_json_lenient, split_parts


class GeminiBackend:
    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai
            except ImportError as e:  # pragma: no cover
                raise RuntimeError("Gemini backend needs: pip install 'docs-reader[gemini]'") from e
            if not self._settings.gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY / GOOGLE_API_KEY is not set")
            self._client = genai.Client(api_key=self._settings.gemini_api_key)
        return self._client

    def is_available(self) -> bool:
        if not self._settings.gemini_api_key:
            return False
        try:
            import google.genai  # noqa: F401

            return True
        except ImportError:
            return False

    def _contents(self, parts: list[ContentPart], instruction: str):
        from google.genai import types

        text, images = split_parts(parts)
        blocks = [types.Part.from_text(text=instruction)]
        if text:
            blocks.append(types.Part.from_text(text=text))
        for img in images:
            blocks.append(types.Part.from_bytes(data=img.data, mime_type=img.mime or "image/png"))
        return blocks

    def _run(
        self,
        parts: list[ContentPart],
        json_schema: dict[str, Any],
        instruction: str,
        model_cls: Optional[type[BaseModel]],
        temperature: float,
    ) -> tuple[dict[str, Any], str, str]:
        from google.genai import types

        client = self._get_client()
        model = self._settings.model_override or self._settings.gemini_model
        cfg_kwargs: dict[str, Any] = {
            "system_instruction": SYSTEM_PROMPT,
            "response_mime_type": "application/json",
            "temperature": temperature,
        }
        if model_cls is not None:
            cfg_kwargs["response_schema"] = model_cls
        resp = client.models.generate_content(
            model=model,
            contents=self._contents(parts, instruction),
            config=types.GenerateContentConfig(**cfg_kwargs),
        )
        if model_cls is not None and getattr(resp, "parsed", None) is not None:
            data = resp.parsed.model_dump(mode="json")
        else:
            data = parse_json_lenient(resp.text)
        return data, resp.text, model

    def extract(
        self,
        parts,
        json_schema,
        instruction,
        *,
        model_cls: Optional[type[BaseModel]] = None,
        temperature: float = 0.0,
    ) -> ExtractionResult:
        data, raw, model = self._run(parts, json_schema, instruction, model_cls, temperature)
        return ExtractionResult(data=data, raw=raw, model=model, provider=self.name)

    def complete_json(self, parts, json_schema, instruction, *, temperature: float = 0.0):
        data, _, _ = self._run(parts, json_schema, instruction, None, temperature)
        return data
