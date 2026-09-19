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
PINNED_REF = "5fc9addb5b2362043332ad6d403bb436f2596318"

#: Directory (inside the app's ``assets/``) that receives the component sources.
ASSETS_SUBDIR = "reactbits"

RAW_URL = "https://raw.githubusercontent.com/DavidHDev/react-bits/{ref}/{path}"

# Files a component loads from the React Bits site's public/ folder at runtime.
# They are copied next to the component and imported with Vite's ``?url``.
EXTRA_FILES: dict[tuple[str, str], dict[str, str]] = {
    ("Components", "FluidGlass"): {
        "lens.glb": "public/assets/3d/lens.glb",
        "cube.glb": "public/assets/3d/cube.glb",
        "bar.glb": "public/assets/3d/bar.glb",
    },
}

_TEXT_SUFFIXES = {".js", ".jsx", ".css", ".ts", ".tsx", ".json"}

# Small, surgical patches so the plain JS-CSS variant runs inside a Reflex app
# (which has no react-router, Chakra UI or Tailwind by default).
PATCHES: dict[tuple[str, str], list[tuple[str, str]]] = {
    # Ballpit renders its own <canvas> through a React ref, so React keeps and
    # reuses that DOM node across remounts. forceContextLoss() loses the context
    # of that canvas permanently: on the next mount getContext() hands back the
    # same lost context, gl.getShaderPrecisionFormat() returns null and three.js
    # throws "Cannot read properties of null (reading 'precision')" while
    # building WebGLCapabilities. dispose() alone already frees the GPU
    # resources, and reusing the live context avoids leaking one per remount.
    ("Backgrounds", "Ballpit.jsx"): [
        (
            "    this.renderer.dispose();\n    this.renderer.forceContextLoss();\n",
            "    this.renderer.dispose();\n",
        ),
    ],
    # Hyperspeed loads its SMAA assets asynchronously and then calls init().
    # If the component unmounts during that window (React StrictMode remounts
    # every effect in dev), the cleanup already ran dispose(), which calls
    # renderer.forceContextLoss(). The pending promise then initialises a dead
    # App: postprocessing reads renderer.getContext().getContextAttributes(),
    # which is null on a lost context, and throws "can't access property alpha".
    ("Backgrounds", "Hyperspeed.jsx"): [
        (
            "      init() {\n        this.initPasses();",
            "      init() {\n        if (this.disposed) return;\n        this.initPasses();",
        ),
    ],
    ("TextAnimations", "BlurText.jsx"): [
        (
            'className="inline-block will-change-[transform,filter,opacity]"',
            "style={{ display: 'inline-block', willChange: 'transform, filter, opacity' }}",
        ),
    ],
    ("Components", "PillNav.jsx"): [
        ("import { Link } from 'react-router-dom';\n", ""),
        ("<Link", "<a"),
        ("</Link>", "</a>"),
        (" to={", " href={"),
    ],
    ("Components", "ElasticSlider.jsx"): [
        ("import { Icon } from '@chakra-ui/react';\n", ""),
        ("<Icon as={RiVolumeDownFill} />", "<RiVolumeDownFill />"),
        ("<Icon as={RiVolumeUpFill} />", "<RiVolumeUpFill />"),
    ],
    ("Components", "Lanyard.jsx"): [
        ("from './card.glb';", "from './card.glb?url';"),
    ],
    ("Components", "FluidGlass.jsx"): [
        (
            "import * as THREE from 'three';\n",
            "import * as THREE from 'three';\n"
            "import lensGlb from './lens.glb?url';\n"
            "import cubeGlb from './cube.glb?url';\n"
            "import barGlb from './bar.glb?url';\n",
        ),
        ('glb="/assets/3d/lens.glb"', "glb={lensGlb}"),
        ('glb="/assets/3d/cube.glb"', "glb={cubeGlb}"),
        ('glb="/assets/3d/bar.glb"', "glb={barGlb}"),
    ],
}


def app_assets_dir() -> Path:
    """Return the ``assets/`` directory of the Reflex app being compiled."""
    return Path.cwd() / "assets"


def component_dir(category: str, name: str, assets_dir: Path | None = None) -> Path:
    """Return where a component's source lives inside the app."""
    return (assets_dir or app_assets_dir()) / ASSETS_SUBDIR / category / name


def _apply_patches(category: str, file: str, data: bytes) -> bytes:
    patches = PATCHES.get((category, file))
    if not patches:
        return data
    text = data.decode("utf-8")
    for old, new in patches:
        if old not in text:
            # The patch anchors on upstream code at PINNED_REF. A miss means the
            # vendored file keeps an import or a call the wrappers do not expect
            # (for instance a dependency listed in DROPPED_DEPS, which is then
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
    """
    target = component_dir(category, name, assets_dir)
    ref = ref or os.environ.get("REACTBITS_REF") or PINNED_REF
    written: list[Path] = []
    for file in [*files, *EXTRA_FILES.get((category, name), {})]:
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
