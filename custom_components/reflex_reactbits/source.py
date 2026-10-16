"""Fetch React Bits component sources into the Reflex app that uses them.

React Bits (https://reactbits.dev) is distributed as copy-paste source code,
not as an npm package, and its license (MIT + Commons Clause) does not allow
redistributing the components themselves in a bundle. This package therefore
ships only the Python wrappers: the first time a component is used, its
original JSX/CSS source is copied into the app's ``assets/reactbits/``
directory, exactly as the official ``shadcn``/``jsrepo`` CLIs would copy it
into a React project. The files are then owned by the app and can be edited
freely; existing files are never overwritten.

Sources are resolved in this order:

1. ``REACTBITS_SOURCE_DIR`` - path to a local clone of the React Bits repository.
2. GitHub raw files of ``DavidHDev/react-bits`` at ``REACTBITS_REF`` (defaults to
   the commit these wrappers were generated and tested against).
"""

from __future__ import annotations

import logging
import os
import shutil
import urllib.error
import urllib.request
from collections.abc import Iterable
from pathlib import Path

logger = logging.getLogger("reflex_reactbits")

#: Commit of DavidHDev/react-bits the wrappers were generated from.
PINNED_REF = "963f4d21dca65326a470956c42b7b467804f3c14"  # React Bits 2.0

#: Directory (inside the app's ``assets/``) that receives the component sources.
ASSETS_SUBDIR = "reactbits"

RAW_URL = "https://raw.githubusercontent.com/DavidHDev/react-bits/{ref}/{path}"

# Files a component loads from the React Bits site's public/ folder at runtime.
# They are copied next to the component and imported with Vite's ``?url``.
# React Bits 2.0 builds its 3D geometry procedurally (FluidGlass, Lanyard), so
# no component needs one today.
EXTRA_FILES: dict[tuple[str, str], dict[str, str]] = {}

_TEXT_SUFFIXES = {".js", ".jsx", ".css", ".ts", ".tsx", ".json"}

# Small, surgical patches so the plain JS-CSS variant runs inside a Reflex app.
# React Bits 2.0 no longer imports react-router, Chakra UI or Tailwind classes,
# so the per-file patches the 1.x sources needed are gone. The ones left move
# off three.js APIs deprecated after r180 (React Bits is locked to r180, the
# wrappers install r186), which otherwise log a console warning.
PATCHES: dict[tuple[str, str], list[tuple[str, str]]] = {
    # THREE.Clock is deprecated since r183 in favour of THREE.Timer, which only
    # advances when update() is called.
    ("Backgrounds", "ColorBends.jsx"): [
        ("const clock = new THREE.Clock();", "const clock = new THREE.Timer();"),
        (
            "const dt = clock.getDelta();\n      const elapsed = clock.elapsedTime;",
            "clock.update();\n      const dt = clock.getDelta();\n      const elapsed = clock.getElapsed();",
        ),
    ],
    # WebGLRenderer dropped PCFSoftShadowMap in r182: three falls back to
    # PCFShadowMap (now soft as well), so this only silences the warning.
    ("Micro", "PaperCrumple.jsx"): [
        ("renderer.shadowMap.type = THREE.PCFSoftShadowMap;", "renderer.shadowMap.type = THREE.PCFShadowMap;"),
    ],
}

# Patches applied to every component file that renders its own ``<canvas>``.
#
# React StrictMode (on by default in Reflex dev mode) runs each effect's cleanup
# and then the effect again while keeping the same DOM nodes. The 2.0 WebGL
# components end their cleanup with WEBGL_lose_context.loseContext(); a canvas
# only ever owns one context, so on the second run getContext() hands back that
# lost context, every shader fails to compile and the component renders blank
# or frozen (seen in Firefox; Chromium happens to recover the context).
# The cleanup already deletes the buffers, programs and textures it created, so
# dropping the forced loss only leaves the (empty) context to the GC.
CANVAS_PATCHES: list[tuple[str, str]] = [
    (
        "if (!gl.isContextLost()) gl.getExtension('WEBGL_lose_context')?.loseContext();",
        "/* reflex-reactbits: context kept for StrictMode remounts */",
    ),
    (
        "gl.getExtension('WEBGL_lose_context')?.loseContext();",
        "/* reflex-reactbits: context kept for StrictMode remounts */",
    ),
]


def app_assets_dir() -> Path:
    """Return the ``assets/`` directory of the Reflex app being compiled."""
    return Path.cwd() / "assets"


def component_dir(category: str, name: str, assets_dir: Path | None = None) -> Path:
    """Return where a component's source lives inside the app."""
    return (assets_dir or app_assets_dir()) / ASSETS_SUBDIR / category / name


def _apply_patches(category: str, file: str, data: bytes) -> bytes:
    patches = PATCHES.get((category, file))
    text = data.decode("utf-8")
    if "<canvas" in text:
        for old, new in CANVAS_PATCHES:
            text = text.replace(old, new)
    for old, new in patches or ():
        if old not in text:
            # The patch anchors on upstream code at PINNED_REF. A miss means the
            # vendored file keeps an import or a call the wrappers do not expect
            # (for instance a dependency the generator dropped, which is then
            # never installed), so say so here rather than fail later in Vite.
            logger.warning(
                "React Bits patch for %s/%s no longer matches upstream and was skipped; "
                "the vendored source may not work with this wrapper.", category, file,
            )
            continue
        text = text.replace(old, new)
    return text.encode("utf-8")


def _repo_path(category: str, name: str, file: str) -> str:
    extra = EXTRA_FILES.get((category, name), {})
    return extra.get(file) or f"src/content/{category}/{name}/{file}"


def _read_local(repo_path: str) -> bytes | None:
    root = os.environ.get("REACTBITS_SOURCE_DIR")
    if not root:
        return None
    path = Path(root).expanduser() / repo_path
    return path.read_bytes() if path.exists() else None


def _read_remote(repo_path: str, ref: str) -> bytes:
    url = RAW_URL.format(ref=ref, path=repo_path)
    # RAW_URL is a constant https template, so the scheme can never be attacker-chosen.
    request = urllib.request.Request(url, headers={"User-Agent": "reflex-reactbits"})  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310  # nosec B310
            return response.read()
    except urllib.error.URLError as err:
        msg = (
            f"Could not download React Bits source {url}: {err}. Run "
            "`reactbits add <Name>` with network access, or set REACTBITS_SOURCE_DIR "
            "to a local clone of https://github.com/DavidHDev/react-bits."
        )
        local = os.environ.get("REACTBITS_SOURCE_DIR")
        if local:
            msg = (
                f"REACTBITS_SOURCE_DIR is set to {local}, but it has no {repo_path}, "
                f"so the download from {url} was attempted and failed: {err}. Check that "
                "the clone is complete and matches the expected layout."
            )
        raise RuntimeError(msg) from err


def backend_only() -> bool:
    """Whether this process runs without a frontend to copy component sources for."""
    return os.environ.get("REFLEX_BACKEND_ONLY", "").lower() in {"1", "true", "yes"}


#: File, next to a component's copied source, that records the React Bits ref
#: it was copied from. Copies made before 0.2.0 have none: they are 1.x sources.
REF_MARKER = ".reactbits-ref"

_warned_stale: set[tuple[str, str]] = set()


def resolve_ref(ref: str | None = None) -> str:
    """The React Bits ref to copy from: explicit, then ``REACTBITS_REF``, then the pinned one."""
    return ref or os.environ.get("REACTBITS_REF") or PINNED_REF


def vendored_ref(category: str, name: str, assets_dir: Path | None = None) -> str | None:
    """Return the React Bits ref a component's copied source came from, if recorded."""
    marker = component_dir(category, name, assets_dir) / REF_MARKER
    return marker.read_text().strip() if marker.exists() else None


def ensure_component_source(
    category: str,
    name: str,
    files: Iterable[str],
    *,
    assets_dir: Path | None = None,
    ref: str | None = None,
    force: bool = False,
) -> list[Path]:
    """Make sure the component's source files exist in the app's assets.

    Args:
        category: React Bits category folder (e.g. ``TextAnimations``).
        name: Component folder name (e.g. ``BlurText``).
        files: File names that make up the component.
        assets_dir: Override the app assets directory.
        ref: Git ref of the React Bits repository to download from.
        force: Re-download and overwrite existing files.

    Returns:
        The list of files written during this call.

    Existing files are kept even when they come from another React Bits ref (an
    upgrade of this package does not touch them), but that case is logged once
    per component, because wrappers generated for one React Bits release do not
    match the props of another.
    """
    target = component_dir(category, name, assets_dir)
    ref = resolve_ref(ref)
    all_files = [*files, *EXTRA_FILES.get((category, name), {})]
    previous = vendored_ref(category, name, assets_dir)
    kept = [f for f in all_files if (target / f).exists() and not force]
    written: list[Path] = []
    for file in all_files:
        dest = target / file
        if dest.exists() and not force:
            continue
        repo_path = _repo_path(category, name, file)
        data = _read_local(repo_path)
        if data is None:
            data = _read_remote(repo_path, ref)
        if Path(file).suffix in _TEXT_SUFFIXES:
            data = _apply_patches(category, file, data)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(dest)
        written.append(dest)
    if not kept:
        (target / REF_MARKER).write_text(ref + "\n")
    elif previous != ref and (category, name) not in _warned_stale:
        _warned_stale.add((category, name))
        logger.warning(
            "reflex-reactbits: %s keeps the React Bits source it copied earlier (%s), but "
            "this version of the wrappers was generated from %s, so props may not match. "
            "Run `reactbits add %s --force` to replace it (local edits are lost).",
            target, previous[:10] if previous else "React Bits 1.x", ref[:10], name,
        )
    if written:
        logger.info("reflex-reactbits: added %s/%s to %s", category, name, target)
    return written


def remove_component_source(category: str, name: str, assets_dir: Path | None = None) -> bool:
    """Delete a component's copied source from the app assets."""
    target = component_dir(category, name, assets_dir)
    if target.exists():
        shutil.rmtree(target)
        return True
    return False
