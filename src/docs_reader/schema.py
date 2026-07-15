"""Load a user-supplied extraction schema from either a Pydantic model (.py) or a
JSON Schema (.json), plus optional few-shot examples.

Both paths converge on a unified :class:`LoadedSchema` carrying:
- ``json_schema``: a plain JSON Schema dict (always present) used for constrained
  decoding and for backends that take raw schemas.
- ``model_cls``: the Pydantic class when available (used for validation and by
  backends that accept Pydantic directly, e.g. Gemini/Claude).
- ``examples``: few-shot examples loaded from a ``<name>.examples.json`` sidecar.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel


@dataclass
class LoadedSchema:
    name: str
    json_schema: dict[str, Any]
    model_cls: Optional[type[BaseModel]] = None
    examples: list[dict[str, Any]] = field(default_factory=list)

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate/coerce extracted data. Uses Pydantic when available; otherwise
        returns the data unchanged (JSON-Schema-only path)."""
        if self.model_cls is not None:
            return self.model_cls.model_validate(data).model_dump(mode="json")
        return data


def _designated_model(module: Any) -> type[BaseModel]:
    """Pick the Pydantic model to use from a loaded module.

    Preference: a module-level ``Schema`` attribute, else a name in ``__schema__``,
    else the single BaseModel subclass defined in the module. Ambiguity is an error.
    """
    explicit = getattr(module, "Schema", None)
    if inspect.isclass(explicit) and issubclass(explicit, BaseModel):
        return explicit

    designated_name = getattr(module, "__schema__", None)
    if designated_name:
        cand = getattr(module, designated_name, None)
        if inspect.isclass(cand) and issubclass(cand, BaseModel):
            return cand
        raise ValueError(f"__schema__ = {designated_name!r} is not a BaseModel in the module")

    defined = [
        obj
        for _, obj in vars(module).items()
        if inspect.isclass(obj)
        and issubclass(obj, BaseModel)
        and obj is not BaseModel
        and obj.__module__ == module.__name__
    ]
    if len(defined) == 1:
        return defined[0]
    if not defined:
        raise ValueError("no pydantic BaseModel subclass found in schema module")
    names = ", ".join(c.__name__ for c in defined)
    raise ValueError(
        f"multiple models found ({names}); set `Schema = YourModel` or `__schema__ = 'YourModel'`"
    )


def _load_python_schema(path: Path) -> tuple[dict[str, Any], type[BaseModel]]:
    mod_name = f"_docs_reader_schema_{path.stem}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot import schema module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(mod_name, None)
    model_cls = _designated_model(module)
    return model_cls.model_json_schema(), model_cls


def _load_json_schema(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON schema must be an object, got {type(data).__name__}")
    return data


def _load_examples(schema_path: Path) -> list[dict[str, Any]]:
    sidecar = schema_path.with_suffix("")  # strip .py/.json
    candidate = Path(str(sidecar) + ".examples.json")
    if not candidate.exists():
        return []
    raw = json.loads(candidate.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and "examples" in raw:
        return raw["examples"]
    raise ValueError(f"examples sidecar must be a list or {{'examples': [...]}}: {candidate}")


def load_schema(path: str | Path) -> LoadedSchema:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"schema file not found: {p}")
    suffix = p.suffix.lower()
    if suffix == ".py":
        json_schema, model_cls = _load_python_schema(p)
    elif suffix in (".json",):
        json_schema, model_cls = _load_json_schema(p), None
    else:
        raise ValueError(f"unsupported schema type {suffix!r}; use .py (Pydantic) or .json")
    return LoadedSchema(
        name=json_schema.get("title", p.stem),
        json_schema=json_schema,
        model_cls=model_cls,
        examples=_load_examples(p),
    )
