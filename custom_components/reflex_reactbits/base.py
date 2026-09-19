"""Base class shared by every React Bits wrapper."""

from __future__ import annotations

from typing import Any, ClassVar

import reflex as rx
from reflex.components.component import NoSSRComponent
from reflex.vars.function import FunctionStringVar

from .source import ASSETS_SUBDIR, backend_only, ensure_component_source

SAFE_FN_NAME = "reactbitsSafe"

# Event payloads are sent to the backend as JSON. React Bits callbacks sometimes
# pass rich objects (items holding React elements, Errors, Files, DOM events),
# so every event argument goes through this sanitizer first.
SAFE_FN_CODE = """
const reactbitsSafe = (value, depth = 0, seen = new WeakSet()) => {
  if (value === undefined || value === null) return null;
  const kind = typeof value;
  if (kind === "function" || kind === "symbol") return undefined;
  if (kind === "bigint") return Number(value);
  if (kind === "number") return Number.isFinite(value) ? value : null;
  if (kind !== "object") return value;
  if (value.$$typeof) return undefined;
  if (value.nativeEvent) return { type: value.type };
  if (typeof Event !== "undefined" && value instanceof Event) return { type: value.type };
  if (typeof Node !== "undefined" && value instanceof Node) return undefined;
  if (typeof File !== "undefined" && value instanceof File)
    return { name: value.name, size: value.size, type: value.type, lastModified: value.lastModified };
  if (value instanceof Error) return { name: value.name, message: value.message };
  if (value instanceof Date) return value.toISOString();
  if (depth > 8 || seen.has(value)) return undefined;
  // seen tracks the current path, not every value already visited: an object
  // reachable twice (the same option listed twice, two keys sharing a config)
  // is not a cycle and must survive both times, so it is removed again below.
  seen.add(value);
  let out;
  if (Array.isArray(value) || (typeof FileList !== "undefined" && value instanceof FileList)) {
    out = Array.from(value, (item) => reactbitsSafe(item, depth + 1, seen) ?? null);
  } else {
    out = {};
    for (const [key, item] of Object.entries(value)) {
      const safe = reactbitsSafe(item, depth + 1, seen);
      if (safe !== undefined) out[key] = safe;
    }
  }
  seen.delete(value);
  return out;
};
"""


def safe(value: rx.Var) -> rx.Var:
    """Wrap a JS event argument so it is always JSON serializable."""
    return FunctionStringVar.create(SAFE_FN_NAME).call(value)


class ReactBitsComponent(NoSSRComponent):
    """A React Bits component whose source lives in the app's ``assets/reactbits``.

    Subclasses declare the React Bits category/name and the files making up the
    component. The source is copied into the app on first use (see
    :mod:`reflex_reactbits.source`), and the component is imported client-side
    only, since most React Bits components rely on ``window``, WebGL or canvas.
    """

    # React Bits category folder, e.g. "TextAnimations".
    _rb_category: ClassVar[str] = ""
    # React Bits component folder, e.g. "BlurText".
    _rb_name: ClassVar[str] = ""
    # Source files of the component (relative to its folder).
    _rb_files: ClassVar[tuple[str, ...]] = ()
    # Entry module (defaults to "<name>.jsx").
    _rb_entry: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs: Any):
        """Derive the local import path for the component module."""
        if cls.__dict__.get("_rb_name"):
            entry = cls.__dict__.get("_rb_entry") or f"{cls._rb_name}.jsx"
            cls.library = f"$/public/{ASSETS_SUBDIR}/{cls._rb_category}/{cls._rb_name}/{entry}"
        super().__init_subclass__(**kwargs)

    @classmethod
    def create(cls, *children: Any, **props: Any) -> rx.Component:
        """Copy the component source into the app (once) and create the component."""
        # A backend-only process has no frontend to compile, so there is nothing
        # to vendor. The guard lives here and not in ensure_component_source so
        # that the ``reactbits add`` CLI still works in such an environment.
        if cls._rb_name and not backend_only():
            ensure_component_source(cls._rb_category, cls._rb_name, cls._rb_files)
        return super().create(*children, **props)

    def add_custom_code(self) -> list[str]:
        """Add the event payload sanitizer used by the event specs."""
        return [SAFE_FN_CODE]
