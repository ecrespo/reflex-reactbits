"""``reactbits`` command line: list, inspect and pre-fetch React Bits sources.

Examples::

    reactbits list --category Backgrounds
    reactbits info BlurText
    reactbits add BlurText Aurora        # copy sources into ./assets/reactbits
    reactbits add --all                  # vendor every component (offline builds)
    reactbits remove Aurora
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .catalog import CATALOG, find_component
from .source import PINNED_REF, component_dir, ensure_component_source, remove_component_source

_CATEGORIES = sorted({e["category"] for e in CATALOG})


def _source_entries(names: list[str], all_: bool) -> list[dict]:
    if all_:
        entries = [e for e in CATALOG if not e.get("sub")]
    else:
        entries = [find_component(n) for n in names]
    # Sub-components share their parent's files.
    seen, out = set(), []
    for e in entries:
        key = (e["category"], e["name"])
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def _files_for(entry: dict) -> tuple[str, ...]:
    import reflex_reactbits

    return getattr(reflex_reactbits, entry["class"])._rb_files


def cmd_list(args: argparse.Namespace) -> int:
    for cat in _CATEGORIES:
        if args.category and cat.lower() != args.category.lower():
            continue
        entries = [e for e in CATALOG if e["category"] == cat]
        print(f"\n{cat} ({len(entries)})")
        for e in entries:
            print(f"  {e['factory']:<28} {e['description'][:70]}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    e = find_component(args.name)
    print(f"{e['class']}  ({e['category']})  ->  reflex_reactbits.{e['factory']}()")
    print(e["description"])
    print(f"Docs: {e['docs_url']}")
    if e["npm"]:
        print("npm:  " + ", ".join(e["npm"]))
    print("\nProps:")
    for p in e["props"]:
        if p["type"] == "event":
            args_ = ", ".join(p.get("args") or [])
            print(f"  {p['name']:<28} event({args_})")
        else:
            print(f"  {p['name']:<28} {p['type']:<22} {(p.get('default') or '')[:30]}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    assets = Path(args.assets_dir) if args.assets_dir else None
    for e in _source_entries(args.names, args.all):
        written = ensure_component_source(
            e["category"], e["name"], _files_for(e), assets_dir=assets, ref=args.ref, force=args.force
        )
        where = component_dir(e["category"], e["name"], assets)
        state = "added" if written else "up to date"
        print(f"{e['name']:<24} {state:<11} {where}")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    assets = Path(args.assets_dir) if args.assets_dir else None
    for e in _source_entries(args.names, False):
        removed = remove_component_source(e["category"], e["name"], assets)
        print(f"{e['name']:<24} {'removed' if removed else 'not present'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reactbits", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="List the available components.")
    p.add_argument("--category", choices=_CATEGORIES, type=str)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("info", help="Show props, events and npm deps of a component.")
    p.add_argument("name")
    p.set_defaults(func=cmd_info)

    for name, func, help_ in (
        ("add", cmd_add, "Copy component sources into the app's assets/reactbits."),
        ("remove", cmd_remove, "Delete copied component sources."),
    ):
        p = sub.add_parser(name, help=help_)
        p.add_argument("names", nargs="*")
        p.add_argument("--assets-dir", help="App assets directory (default: ./assets).")
        if name == "add":
            p.add_argument("--all", action="store_true", help="Add every component.")
            p.add_argument("--ref", default=None, help=f"react-bits git ref (default {PINNED_REF[:10]}).")
            p.add_argument("--force", action="store_true", help="Overwrite existing (possibly edited) files.")
        p.set_defaults(func=func)

    args = parser.parse_args(argv)
    if getattr(args, "names", None) == [] and not getattr(args, "all", False):
        parser.error("give at least one component name" + (" or --all" if args.command == "add" else ""))
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
