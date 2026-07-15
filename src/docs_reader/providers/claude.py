"""Claude backend (anthropic) — escalation / cross-check only (3rd priority).

Prefers ``messages.parse`` with a Pydantic ``output_format`` for validated output;
falls back to ``output_config.format`` (JSON Schema) or a plain call + lenient parse.
"""

from __future__ import annotations

import base64
from typing import Any, Optional

from pydantic import BaseModel

from ..config import Settings
from ..types import ContentPart
from .base import ExtractionResult
from ._common import SYSTEM_PROMPT, parse_json_lenient, split_parts

_MAX_TOKENS = 8192


class ClaudeBackend:
    name = "claude"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as e:  # pragma: no cover
                raise RuntimeError("Claude backend needs: pip install 'docs-reader[claude]'") from e
            # anthropic() resolves key from env / ant profile automatically.
            self._client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key or None)
        return self._client

    def is_available(self) -> bool:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        # A key in env or an `ant` profile both work; assume available if SDK present
        # and either an explicit key or ANTHROPIC creds exist.
        return bool(self._settings.anthropic_api_key) or True

    def _content_blocks(self, parts: list[ContentPart], instruction: str):
        text, images = split_parts(parts)
        blocks: list[dict[str, Any]] = []
        for img in images:
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img.mime or "image/png",
                        "data": base64.b64encode(img.data).decode("ascii"),
                    },
                }
            )
        combined = instruction + (("\n\n" + text) if text else "")
        blocks.append({"type": "text", "text": combined})
        return blocks

    def _model(self) -> str:
        return self._settings.model_override or self._settings.claude_model

    def extract(
        self,
        parts,
        json_schema,
        instruction,
        *,
        model_cls: Optional[type[BaseModel]] = None,
        temperature: float = 0.0,  # noqa: ARG002 (adaptive-thinking models reject sampling params)
    ) -> ExtractionResult:
        client = self._get_client()
        model = self._model()
        messages = [{"role": "user", "content": self._content_blocks(parts, instruction)}]

        if model_cls is not None and hasattr(client.messages, "parse"):
            resp = client.messages.parse(
                model=model,
                max_tokens=_MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=messages,
                output_format=model_cls,
            )
            data = resp.parsed_output.model_dump(mode="json")
            return ExtractionResult(data=data, model=model, provider=self.name)

        resp = client.messages.create(
            model=model,
            max_tokens=_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=messages,
            output_config={"format": {"type": "json_schema", "schema": json_schema}},
        )
        text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")
        return ExtractionResult(data=parse_json_lenient(text), raw=text, model=model, provider=self.name)

    def complete_json(self, parts, json_schema, instruction, *, temperature: float = 0.0):
        return self.extract(parts, json_schema, instruction, model_cls=None, temperature=temperature).data
