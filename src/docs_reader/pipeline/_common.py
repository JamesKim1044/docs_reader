"""Shared helpers for pipeline stages."""

from __future__ import annotations

from typing import Any


def top_level_keys(schema: dict[str, Any], results: list[dict[str, Any]] | None = None) -> list[str]:
    """Top-level field names from the schema, falling back to keys seen in results."""
    props = schema.get("properties")
    if isinstance(props, dict) and props:
        return list(props.keys())
    keys: list[str] = []
    for r in results or []:
        if isinstance(r, dict):
            for k in r:
                if k not in keys:
                    keys.append(k)
    return keys


def reduced_schema(schema: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    """Return an object schema containing only ``fields`` (for targeted re-extraction)."""
    props = schema.get("properties", {}) if isinstance(schema, dict) else {}
    sub = {k: props[k] for k in fields if k in props}
    out: dict[str, Any] = {
        "title": schema.get("title", "extraction"),
        "type": "object",
        "additionalProperties": False,
        "properties": sub or {k: {} for k in fields},
    }
    # carry $defs so nested refs still resolve
    if "$defs" in schema:
        out["$defs"] = schema["$defs"]
    return out
