"""Open-source backend via any OpenAI-compatible endpoint (vLLM, Ollama, LM Studio,
OpenRouter, ...). This is the default and the substrate for the whole open-source
pipeline (Stage B extraction and Stage C verification/re-check).

Structured output is attempted in decreasing order of strictness so it works across
servers with different capabilities:
1. ``response_format`` = json_schema (constrained decoding on vLLM/Ollama)
2. ``extra_body={"guided_json": schema}`` (vLLM guided decoding)
3. ``response_format`` = json_object + schema in prompt
4. plain completion + lenient JSON parse
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from ..config import Settings
from ..types import ContentPart
from .base import ExtractionResult
from ._common import SYSTEM_PROMPT, build_instruction, parse_json_lenient, split_parts


class OpenAICompatBackend:
    name = "opensource"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None  # lazy

    # -- client / availability ------------------------------------------------
    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:  # pragma: no cover
                raise RuntimeError(
                    "The open-source backend needs the OpenAI client: "
                    "pip install 'docs-reader[openai]'"
                ) from e
            self._client = OpenAI(
                base_url=self._settings.os_base_url,
                api_key=self._settings.os_api_key or "not-needed",
            )
        return self._client

    def is_available(self) -> bool:
        try:
            client = self._get_client()
            client.models.list()
            return True
        except Exception:
            return False

    def _model_for(self, images: list[ContentPart]) -> str:
        if self._settings.model_override:
            return self._settings.model_override
        return self._settings.os_vision_model if images else self._settings.os_text_model

    # -- message assembly -----------------------------------------------------
    def _messages(self, parts: list[ContentPart], instruction: str):
        text, images = split_parts(parts)
        content: list[dict[str, Any]] = [{"type": "text", "text": instruction}]
        if text:
            content.append({"type": "text", "text": text})
        for img in images:
            content.append({"type": "image_url", "image_url": {"url": img.data_uri()}})
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ], images

    def _call(
        self, messages, model: str, json_schema: dict[str, Any], temperature: float
    ) -> str:
        client = self._get_client()
        schema_name = (json_schema.get("title") or "extraction").replace(" ", "_")[:40]

        attempts = [
            dict(
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": schema_name, "schema": json_schema, "strict": False},
                }
            ),
            dict(extra_body={"guided_json": json_schema}),
            dict(response_format={"type": "json_object"}),
            dict(),
        ]
        last_err: Optional[Exception] = None
        for kwargs in attempts:
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    **kwargs,
                )
                return resp.choices[0].message.content or ""
            except Exception as e:  # try the next, less strict, strategy
                last_err = e
                continue
        raise RuntimeError(f"all structured-output strategies failed: {last_err}")

    # -- public API -----------------------------------------------------------
    def extract(
        self,
        parts: list[ContentPart],
        json_schema: dict[str, Any],
        instruction: str,
        *,
        model_cls: Optional[type[BaseModel]] = None,
        temperature: float = 0.0,
    ) -> ExtractionResult:
        messages, images = self._messages(parts, instruction)
        model = self._model_for(images)
        raw = self._call(messages, model, json_schema, temperature)
        data = parse_json_lenient(raw)
        return ExtractionResult(data=data, raw=raw, model=model, provider=self.name)

    def complete_json(
        self,
        parts: list[ContentPart],
        json_schema: dict[str, Any],
        instruction: str,
        *,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        messages, images = self._messages(parts, instruction)
        model = self._model_for(images)
        raw = self._call(messages, model, json_schema, temperature)
        return parse_json_lenient(raw)
