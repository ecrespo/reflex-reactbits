"""Machine-readable catalog of every wrapped React Bits component."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: One entry per wrapper class: class/factory names, category, docs URL, npm deps and props.
CATALOG: list[dict[str, Any]] = json.loads(
    (Path(__file__).parent / "catalog.json").read_text(encoding="utf-8")
)


def find_component(name: str) -> dict[str, Any]:
    """Look up a catalog entry by React name, class name or factory name (case-insensitive)."""
    key = name.lower().replace("-", "").replace("_", "")
    for entry in CATALOG:
        candidates = {entry["class"], entry["factory"], entry["name"]}
        if key in {c.lower().replace("_", "") for c in candidates}:
            return entry
    msg = f"Unknown React Bits component: {name!r}"
    raise KeyError(msg)
