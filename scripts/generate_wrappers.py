"""Generate the Reflex wrappers from React Bits metadata.

Usage (from the repository root):

    git clone https://github.com/DavidHDev/react-bits /tmp/react-bits
    (cd scripts && npm install typescript@5)
    node scripts/extract_metadata.mjs /tmp/react-bits scripts/components.json
    python scripts/generate_wrappers.py scripts/components.json
    reflex component build          # regenerate the .pyi stubs

The metadata extractor reads each component's JSX source (props, defaults,
callback call sites, npm imports) and its demo page (prop table with types and
descriptions). This script turns that into typed ``rx.Component`` subclasses.

The last step matters: this script writes the ``.py`` modules and
``catalog.json`` but not the ``.pyi`` stubs, which pyproject ships as package
data. Skipping it leaves type checkers and IDE autocomplete on the previous
prop set while the runtime already has the new one.
"""

from __future__ import annotations

import json
import keyword
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "custom_components" / "reflex_reactbits"

CATEGORY_MODULES = {
    "TextAnimations": ("text_animations", "Text animations"),
    "Animations": ("animations", "Animations"),
    "Components": ("components", "UI components"),
    "Backgrounds": ("backgrounds", "Animated backgrounds"),
    "Micro": ("micro", "Micro interactions"),
}

# Component fields / methods a prop may not shadow.
RESERVED = {
    "state", "alias", "children", "class_name", "custom_attrs", "event_triggers", "id",
    "is_default", "key", "lib_dependencies", "library", "ref", "special_props", "style",
    "tag", "create", "render", "get_fields", "add_style", "add_imports", "add_hooks",
    "add_custom_code", "transpile_packages",
}
DEFAULT_TRIGGERS = {
    "on_blur", "on_click", "on_context_menu", "on_double_click", "on_focus", "on_mount",
    "on_mouse_down", "on_mouse_enter", "on_mouse_leave", "on_mouse_move", "on_mouse_out",
    "on_mouse_over", "on_mouse_up", "on_scroll", "on_scroll_end", "on_unmount",
}
SKIP_PROPS = {"className", "style", "children", "'aria-label'", "aria-label",
              # typos / sub-components that only exist in the docs prop tables
              "dissappearAfter", "imgageSrc", "WarmTooltipGroup"}

# npm imports removed by the source patches in reflex_reactbits/source.py, plus
# lucide-react, which is declared unpinned by EXTRA_DEPS below (pinning React
# Bits' older copy would break rx.icon).
DROPPED_DEPS = {"react-router-dom", "@chakra-ui/react", "lucide-react"}

# Packages a component imports that the docs' dependency table does not list.
# Declared without a version so they resolve against whatever Reflex installs:
# ReflectiveCard imports lucide-react, which only reaches package.json when the
# app happens to use rx.icon somewhere, so an app using just this component
# fails to build with "Failed to resolve import lucide-react".
EXTRA_DEPS = {"ReflectiveCard": ["lucide-react"]}

# Props that start with "on" but are plain values, not callbacks.
NOT_EVENTS = {("BellToggle", "onLabel"), ("BellToggle", "onColor"), ("BellToggle", "onBackground"),
              ("CircularText", "onHover")}

# Extra exported sub-components: (parent, js export, python class, docs, props)
SUBCOMPONENTS = {
    "Stepper": [("Step", "Step", "A single step inside a Stepper; wrap the step content with it.", [])],
    "ScrollStack": [("ScrollStackItem", "ScrollStackItem", "A card inside a ScrollStack.",
                     [("itemClassName", "str", "Extra class name for the card.", "''")])],
    "CardSwap": [("Card", "CardSwapCard", "A card inside a CardSwap.",
                  [("customClass", "str", "Extra class name for the card.", "undefined")])],
    "WarmTooltip": [("WarmTooltipGroup", "WarmTooltipGroup",
                     "Groups WarmTooltips so moving between them skips the open delay.",
                     [("delay", "int | float", "Open delay in ms.", "undefined"),
                      ("warmWindow", "int | float", "How long (ms) the group stays warm.", "undefined")])],
}

# Event argument overrides: component -> event -> list of python arg names.
EVENT_ARGS: dict[tuple[str, str], list[str]] = {
    ("PromptBar", "onSend"): ["text", "options"],
    ("VoicePill", "onStart"): ["info"],
    ("VoicePill", "onStop"): ["info"],
    ("ShapeWaves", "onError"): ["error"],
    ("AeroShards", "onError"): ["error"],
    ("CometDial", "onChangeEnd"): ["value", "detail"],
    ("PeekRating", "onPreview"): ["value"],
    ("FuseButton", "onCommit"): ["reason"],
    ("ThoughtLine", "onSettle"): ["seconds"],
    ("SloshGauge", "onChange"): ["value"],
    ("BellToggle", "onChange"): ["checked"],
    ("TextType", "onSentenceComplete"): ["sentence", "index"],
    ("RubberSegment", "onChange"): ["value", "index"],
    ("JellyRadio", "onChange"): ["value", "index"],
    ("GlideSelect", "onChange"): ["value", "option"],
    ("FolderFloat", "onSelect"): ["value", "index"],
    ("ScrubField", "onCommit"): ["value"],
    ("OptionWheel", "onChange"): ["index", "item"],
    ("DepthCarousel", "onChange"): ["index", "item"],
    ("PixelSwap", "onComplete"): ["active"],
    ("PixelSwap", "onActiveChange"): ["active"],
}
NO_ARG_EVENTS = {("BlurText", "onAnimationComplete"), ("ModelViewer", "onModelLoaded")}

EXTRA_CODE: dict[str, str] = {
    "Hyperspeed": '''
    @classmethod
    def create(cls, *children, preset: str | None = None, **props):
        """Create the component.

        Args:
            *children: Children (unused).
            preset: Name of a built-in React Bits preset ("one" .. "six"). Ignored if
                ``effect_options`` is given.
            **props: Component props.

        Returns:
            The component.
        """
        if preset is not None and "effect_options" not in props:
            ensure_component_source(cls._rb_category, cls._rb_name, cls._rb_files)
            props["effect_options"] = rx.Var(
                f"hyperspeedPresets[{json.dumps(preset)}]",
                _var_data=VarData(
                    imports={
                        f"$/public/{ASSETS_SUBDIR}/Backgrounds/Hyperspeed/HyperSpeedPresets.js": [
                            ImportVar(tag="hyperspeedPresets")
                        ]
                    }
                ),
            )
        return super().create(*children, **props)
''',
}
EXTRA_IMPORTS: dict[str, str] = {
    "backgrounds": "import json\n\nfrom reflex.utils.imports import ImportVar\nfrom reflex.vars.base import VarData\n\nfrom .source import ASSETS_SUBDIR, ensure_component_source\n",
}


def snake(name: str) -> str:
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.replace("-", "_").lower()


def camel(py: str) -> str:
    words = py.replace("-", "_").split("_")
    return words[0] + "".join(w.capitalize() for w in words[1:]) if len(words) > 1 else words[0]


def py_prop_name(js: str) -> str:
    name = snake(js)
    if keyword.iskeyword(name) or name in RESERVED:
        name += "_"
    return name


STRING_LITERAL = re.compile(r"""^\s*(['"])([^'"]*)\1\s*$""")


def literal_members(t: str) -> list[str] | None:
    parts = [p.strip() for p in t.split("|")]
    out = []
    for p in parts:
        m = STRING_LITERAL.match(p)
        if not m:
            return None
        out.append(m.group(2))
    return out if len(out) > 1 else None


def _py_type(js_type: str | None, kind: str | None) -> str:
    """Map a documented TS type (and the kind of the JS default) to a Var type."""
    t = (js_type or "").strip()
    tl = t.lower()
    if t:
        if "=>" in t or tl in {"function", "string | function"} or "handler" in tl:
            return "Any"
        if ("ref" in tl and "object" in tl) or t.startswith("RefObject") or "HTMLElement" in t:
            return "Any"
        lits = literal_members(t)
        if lits:
            return "Literal[" + ", ".join(json.dumps(x) for x in lits) + "]"
        if re.fullmatch(r"\d+( \| \d+)+", t):
            return "int"
        if "reactnode" in tl or "reactelement" in tl or "jsx" in tl or tl in {"component", "elementtype"}:
            if "[]" in t:
                return "list[Any]"
            # A plain string is a valid ReactNode too.
            return "rx.Component | str"
        if tl in {"string[]", "string[] | null", "[string, string]", "[string, string, string]"}:
            return "list[str]"
        if tl in {"number[]", "array<number>", "[number, number]", "[number, number, number]", "rgb array (number[3])"}:
            return "list[float]"
        if tl == "string | string[]":
            return "str | list[str]"
        if tl == "number | number[]":
            return "float | list[float]"
        if "[]" in t or tl.startswith("array"):
            return "list[Any]"
        if "cssproperties" in tl and "mixblendmode" not in tl:
            return "dict[str, Any]"
        if tl in {"string", "css text-align", "css mix-blend-mode", "blendmode"} or "mixblendmode" in tl:
            return "str"
        if tl in {"number", "number | undefined", "number | null"}:
            return "float"
        if tl == "boolean":
            return "bool"
        if tl in {"number | string", "string | number", 'number | "100%"', 'number | "auto"'}:
            return "float | str"
        if tl in {"boolean | string", "string | false"}:
            return "bool | str"
        if tl == "number | boolean":
            return "float | bool"
        if tl == "number | object":
            return "float | dict[str, Any]"
        if t.startswith("{") or tl in {"object", "springoptions", "vec2", "raysorigin"} or tl.startswith("partial"):
            if kind == "list":
                return "list[Any]"
            if kind == "str":
                return "str"
            return "dict[str, Any]"
        if "string" in tl and "{" in t:
            return "str | dict[str, Any]"
    return {
        "str": "str", "number": "float", "bool": "bool", "list": "list[Any]",
        "dict": "dict[str, Any]", "function": "Any", "node": "rx.Component | str",
    }.get(kind or "", "Any")


NUMBER = "int | float"


def py_type(js_type: str | None, kind: str | None) -> str:
    """Like ``_py_type`` but lets every numeric prop accept ints and floats."""
    t = _py_type(js_type, kind)
    return re.sub(r"\bfloat\b", NUMBER, t)


def widen_for_example(typ: str, value) -> str:
    """Widen a type when the official usage example passes another kind of value."""
    if value is None or typ == "Any":
        return typ
    if isinstance(value, bool):
        needed = "bool"
    elif isinstance(value, (int, float)):
        needed = NUMBER
    elif isinstance(value, str):
        needed = "str"
    elif isinstance(value, list):
        needed = "list[Any]"
    elif isinstance(value, dict):
        needed = "rx.Component" if value.get("$jsx") else "dict[str, Any]"
    else:
        return typ
    base = needed.split("[")[0]
    if base in typ or (needed == NUMBER and "float" in typ) or (typ.startswith("Literal") and needed == "str"):
        return typ
    return f"{typ} | {needed}"


def event_arg_names(comp: str, prop: str, calls, js_type: str | None) -> list[str]:
    if (comp, prop) in NO_ARG_EVENTS:
        return []
    if (comp, prop) in EVENT_ARGS:
        return EVENT_ARGS[(comp, prop)]
    sites = calls or []
    if any(s and s[0].startswith("<jsx:") for s in sites):
        return []
    n = max((len(s) for s in sites), default=0)
    if n == 0:
        return []
    # Prefer names from the documented signature "(a: T, b) => void".
    names: list[str] = []
    m = re.match(r"^\(([^)]*)\)\s*=>", js_type or "")
    if m:
        for part in m.group(1).split(","):
            ident = re.match(r"\s*\{?\s*([A-Za-z_]\w*)", part)
            if ident:
                names.append(snake(ident.group(1)))
    if len(names) < n:
        first = max(sites, key=len)
        for arg in first[len(names):n]:
            names.append(snake(arg) if re.fullmatch(r"[A-Za-z_]\w*", arg) else f"arg{len(names)}")
    names = names[:n]
    fixed = []
    for i, nm in enumerate(names):
        nm = {"e": "event", "v": "value", "s": "value", "a": "action", "i": "index", "val": "value", "n": "value"}.get(nm, nm)
        if keyword.iskeyword(nm) or nm in fixed:
            nm = f"{nm}{i}"
        fixed.append(nm)
    return fixed


def fmt_default(text) -> str | None:
    if text is None:
        return None
    text = " ".join(str(text).split())
    return text if len(text) <= 60 else text[:57] + "..."


def docstring_text(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace('"""', "'''").strip()


def build_component(c: dict) -> tuple[str, list[dict]]:
    name = c["name"]
    table = {r["name"]: r for r in c["table"] or []}
    source = {p["name"]: p for p in c["sourceProps"]}
    names = list(source)
    for tname in table:
        if tname in source:
            continue
        # Documented props missing from the destructuring are kept only when the
        # component actually reads them (rest props / props.foo / config merge).
        if c["rest"] or name == "GradualBlur" or re.search(rf"\b{re.escape(tname)}\b", c.get("_src", "")):
            names.append(tname)
    lines: list[str] = []
    events: list[str] = []
    renames: dict[str, str] = {}
    prop_docs: list[dict] = []
    for js in names:
        if js in SKIP_PROPS or js.startswith("'"):
            continue
        row = table.get(js, {})
        sp = source.get(js, {})
        desc = row.get("description") or ""
        default = fmt_default(sp.get("defaultText")) or fmt_default(row.get("default"))
        is_event = re.match(r"^on[A-Z]", js) and (name, js) not in NOT_EVENTS
        py = py_prop_name(js)
        if is_event:
            if py in DEFAULT_TRIGGERS:
                # Forwarded to a DOM element: the built-in trigger already fits.
                continue
            args = event_arg_names(name, js, c["calls"].get(js), row.get("type"))
            if args:
                spec = "lambda " + ", ".join(args) + ": [" + ", ".join(f"safe({a})" for a in args) + "]"
            else:
                spec = "no_args_event_spec"
            doc = desc or f"Fired by the component's {js} callback."
            if args:
                doc += f" Handler receives: {', '.join(args)}."
            events.append(f"    {py}: rx.EventHandler[{spec}] = field(\n        doc={json.dumps(doc)}\n    )\n")
            prop_docs.append({"name": py, "js": js, "type": "event", "args": args, "description": desc})
        else:
            typ = widen_for_example(py_type(row.get("type"), sp.get("kind")),
                                    (c.get("example") or {}).get("props", {}).get(js))
            doc = (desc.rstrip() if desc else f"The `{js}` prop.")
            if doc and doc[-1] not in ".!?":
                doc += "."
            if default and default not in {"undefined", "null", '""', "''"}:
                doc += f" Default: {default}."
            if typ == "Any" and ("=>" in (row.get("type") or "") or sp.get("kind") == "function"):
                doc += " Pass a JS function with rx.Var('(...) => ...')."
            lines.append(f"    {py}: rx.Var[{typ}] = field(\n        doc={json.dumps(doc)}\n    )\n")
            prop_docs.append({"name": py, "js": js, "type": typ, "default": default, "description": desc})
        if camel(py) != js:
            renames[camel(py)] = js
    deps = [f"{d['name']}@{d['version']}" if d["version"] else d["name"]
            for d in c["npm"] if d["name"] not in DROPPED_DEPS]
    deps += [d for d in EXTRA_DEPS.get(name, []) if d not in deps]
    out = [f"class {name}(ReactBitsComponent):\n"]
    doc = docstring_text(c["description"])
    out.append(f'    """{doc}\n\n    Docs: {c["docsUrl"]}\n    """\n\n')
    out.append(f'    tag = "{name}"\n')
    out.append(f'    alias = "ReactBits{name}"\n')
    out.append(f"    is_default = {bool(c['isDefault'])}\n")
    out.append(f'    _rb_category = "{c["category"]}"\n')
    out.append(f'    _rb_name = "{name}"\n')
    out.append(f"    _rb_files = {tuple(c['files'])!r}\n")
    if deps:
        out.append(f"    lib_dependencies: list[str] = {deps!r}\n")
    if renames:
        out.append(f"    _rename_props = {renames!r}\n")
    out.append("\n")
    out.extend(lines)
    out.extend(events)
    if name in EXTRA_CODE:
        out.append(EXTRA_CODE[name])
    js_to_py = {d["js"]: d["name"] for d in prop_docs if d["type"] != "event"}
    example = None
    if c.get("example"):
        ex_props = {js_to_py[k]: v for k, v in c["example"]["props"].items() if k in js_to_py}
        example = {"props": ex_props, "children": c["example"].get("children")}
    classes = [{
        "class": name, "factory": snake(name), "category": c["category"], "name": name,
        "description": c["description"], "docs_url": c["docsUrl"], "npm": deps, "props": prop_docs,
        "example": example,
    }]
    code = "".join(out)
    for js_export, cls, sdoc, sprops in SUBCOMPONENTS.get(name, []):
        sub = [f"\n\nclass {cls}(ReactBitsComponent):\n", f'    """{sdoc}"""\n\n',
               f'    tag = "{js_export}"\n', f'    alias = "ReactBits{cls}"\n', "    is_default = False\n",
               f'    _rb_category = "{c["category"]}"\n', f'    _rb_name = "{name}"\n',
               f"    _rb_files = {tuple(c['files'])!r}\n"]
        if deps:
            sub.append(f"    lib_dependencies: list[str] = {deps!r}\n")
        if sprops:
            sub.append("\n")
        for js, typ, pdoc, _default in sprops:
            # Defaults live in the catalog (and in the docs table), not on the
            # Python field: the JS component applies its own.
            sub.append(f"    {py_prop_name(js)}: rx.Var[{typ}] = field(doc={json.dumps(pdoc)})\n")
        code += "".join(sub)
        classes.append({"class": cls, "factory": snake(cls), "category": c["category"], "name": name,
                        "description": sdoc, "docs_url": c["docsUrl"], "npm": deps, "sub": True,
                        "props": [{"name": py_prop_name(js), "js": js, "type": typ,
                                    "default": default, "description": pdoc}
                                   for js, typ, pdoc, default in sprops]})
    return code, classes


def main(meta_path: str, react_bits_root: str | None = None):
    comps = json.loads(Path(meta_path).read_text())
    if react_bits_root:
        for c in comps:
            files = Path(react_bits_root, "src/content", c["category"], c["name"])
            c["_src"] = "\n".join(p.read_text() for p in files.glob("*.jsx"))
    catalog = []
    exports: dict[str, list[str]] = {}
    for cat, (module, title) in CATEGORY_MODULES.items():
        items = sorted([c for c in comps if c["category"] == cat], key=lambda c: c["name"])
        chunks = []
        names = []
        for c in items:
            code, classes = build_component(c)
            chunks.append(code)
            for k in classes:
                catalog.append({**k, "module": module})
                names += [k["class"], k["factory"]]
        factories = "".join(f"{k['factory']} = {k['class']}.create\n" for c in items for k in build_component(c)[1])
        header = (
            f'"""React Bits - {title}.\n\n'
            "AUTO-GENERATED by scripts/generate_wrappers.py - do not edit by hand.\n"
            '"""\n\n'
            "# ruff: noqa: E501\n"
            "from __future__ import annotations\n\n"
            "from typing import Any, Literal\n\n"
            "import reflex as rx\n"
            # Only some modules declare a callback that takes no arguments.
            + ("from reflex.event import no_args_event_spec\n"
               if "no_args_event_spec]" in "".join(chunks) else "")
            + "from reflex_base.components.component import field\n"
            + (EXTRA_IMPORTS.get(module, ""))
            + "\nfrom .base import ReactBitsComponent, safe\n\n"
            f"__all__ = {sorted(names)!r}\n\n\n"
        )
        (PKG / f"{module}.py").write_text(header + "\n\n".join(chunks) + "\n\n" + factories)
        exports[module] = names
        print(f"{module}: {len(items)} components")
    (PKG / "catalog.json").write_text(json.dumps(catalog, indent=1))
    init = ['"""Reflex wrappers for React Bits (https://reactbits.dev)."""\n\n']
    for module in exports:
        init.append(f"from .{module} import *  # noqa: F403\n")
    init.append("from .base import ReactBitsComponent\n")
    init.append("from .catalog import CATALOG, find_component\n")
    init.append("from .source import ensure_component_source\n\n")
    all_names = sorted({n for v in exports.values() for n in v} | {"ReactBitsComponent", "CATALOG", "find_component", "ensure_component_source"})
    init.append(f"__all__ = {all_names!r}\n")
    (PKG / "__init__.py").write_text("".join(init))


if __name__ == "__main__":
    main(*sys.argv[1:])
