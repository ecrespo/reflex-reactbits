"""Smoke tests for the generated React Bits wrappers (no network needed)."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest
import reflex as rx
import reflex_reactbits as rb
from reflex_reactbits import base, source


@pytest.fixture(autouse=True)
def _no_fetch(monkeypatch):
    # Creating components must not touch the network in tests.
    monkeypatch.setenv("REFLEX_BACKEND_ONLY", "1")


@pytest.mark.parametrize("entry", rb.CATALOG, ids=lambda e: e["class"])
def test_every_component_renders(entry):
    cls = getattr(rb, entry["class"])
    component = getattr(rb, entry["factory"])()
    assert isinstance(component, cls)
    rendered = str(component)
    assert f"ReactBits{entry['class']}" in rendered
    assert cls.library.startswith("$/public/reactbits/")


def test_catalog_counts():
    main = [e for e in rb.CATALOG if not e.get("sub")]
    assert len(main) == 202
    assert {e["category"] for e in main} == {"TextAnimations", "Animations", "Components", "Backgrounds", "Micro"}


def test_props_are_camel_cased():
    out = str(rb.blur_text(text="Hi", animate_by="letters", step_duration=0.5))
    assert "animateBy" in out and "stepDuration" in out


def test_screaming_case_props_are_renamed():
    out = str(rb.splash_cursor(sim_resolution=64, rainbow_mode=False))
    assert "SIM_RESOLUTION:64" in out and "RAINBOW_MODE:false" in out


def test_keyword_props():
    out = str(rb.count_up(to=10, from_=5))
    assert "from:5" in out


def test_numbers_accept_int_and_float():
    rb.aurora(amplitude=1)
    rb.aurora(amplitude=1.5)


def test_component_props_accept_components_and_strings():
    rb.slide_commit(label="Slide")
    rb.slide_commit(label=rx.text("Slide"))


def test_events_are_sanitized():
    class S(rx.State):
        @rx.event
        def changed(self, value: str, index: int):
            pass

    out = str(rb.rubber_segment(items=["a", "b"], on_change=S.changed))
    assert "reactbitsSafe" in out


def test_hyperspeed_preset():
    out = str(rb.hyperspeed(preset="two"))
    assert 'hyperspeedPresets["two"]' in out


def test_find_component():
    assert rb.find_component("blur-text")["class"] == "BlurText"
    assert rb.find_component("BlurText")["factory"] == "blur_text"
    with pytest.raises(KeyError):
        rb.find_component("nope")


def test_source_copy_and_patches(tmp_path, monkeypatch):
    monkeypatch.delenv("REFLEX_BACKEND_ONLY")
    repo = tmp_path / "react-bits" / "src" / "content" / "Components" / "PillNav"
    repo.mkdir(parents=True)
    (repo / "PillNav.jsx").write_text(
        "import { Link } from 'react-router-dom';\n<Link to={x}>a</Link>\n"
    )
    (repo / "PillNav.css").write_text(".a{}")
    monkeypatch.setenv("REACTBITS_SOURCE_DIR", str(tmp_path / "react-bits"))
    assets = tmp_path / "app" / "assets"
    written = source.ensure_component_source(
        "Components", "PillNav", ("PillNav.css", "PillNav.jsx"), assets_dir=assets
    )
    assert len(written) == 2
    jsx = (assets / "reactbits" / "Components" / "PillNav" / "PillNav.jsx").read_text()
    assert "react-router-dom" not in jsx and "<a href={x}>a</a>" in jsx
    # Existing (possibly user-edited) files are never overwritten.
    (assets / "reactbits" / "Components" / "PillNav" / "PillNav.css").write_text("/* mine */")
    assert source.ensure_component_source(
        "Components", "PillNav", ("PillNav.css", "PillNav.jsx"), assets_dir=assets
    ) == []
    assert "mine" in (assets / "reactbits" / "Components" / "PillNav" / "PillNav.css").read_text()


def test_hyperspeed_init_guarded_against_disposed_app(tmp_path, monkeypatch):
    """Hyperspeed must not initialise an App whose WebGL context was released.

    ``loadAssets()`` is async and ``init`` runs in its ``.then``. If the
    component unmounts meanwhile (React StrictMode remounts every effect in
    dev), the cleanup already ran ``dispose()`` -> ``forceContextLoss()``, so
    ``renderer.getContext().getContextAttributes()`` is null and postprocessing
    throws "can't access property 'alpha'" when ``initPasses`` adds a pass.
    """
    monkeypatch.delenv("REFLEX_BACKEND_ONLY")
    repo = tmp_path / "react-bits" / "src" / "content" / "Backgrounds" / "Hyperspeed"
    repo.mkdir(parents=True)
    # Verbatim shape of the upstream method the patch anchors on.
    (repo / "Hyperspeed.jsx").write_text(
        "      init() {\n        this.initPasses();\n        const options = this.options;\n      }\n"
    )
    (repo / "Hyperspeed.css").write_text(".a{}")
    monkeypatch.setenv("REACTBITS_SOURCE_DIR", str(tmp_path / "react-bits"))
    assets = tmp_path / "app" / "assets"
    source.ensure_component_source(
        "Backgrounds", "Hyperspeed", ("Hyperspeed.css", "Hyperspeed.jsx"), assets_dir=assets
    )
    jsx = (assets / "reactbits" / "Backgrounds" / "Hyperspeed" / "Hyperspeed.jsx").read_text()
    assert "      init() {\n        if (this.disposed) return;\n        this.initPasses();" in jsx


def test_ballpit_keeps_context_usable_across_remounts(tmp_path, monkeypatch):
    """Ballpit must not force-lose the context of a canvas React owns.

    Its <canvas> comes from a React ref, so React reuses that DOM node when the
    component remounts. forceContextLoss() loses that canvas' context for good:
    the next getContext() hands back the same lost context, and three.js throws
    "Cannot read properties of null (reading 'precision')" in WebGLCapabilities.
    """
    monkeypatch.delenv("REFLEX_BACKEND_ONLY")
    repo = tmp_path / "react-bits" / "src" / "content" / "Backgrounds" / "Ballpit"
    repo.mkdir(parents=True)
    (repo / "Ballpit.jsx").write_text(
        "  dispose() {\n    this.renderer.dispose();\n    this.renderer.forceContextLoss();\n    this.isDisposed = true;\n  }\n"
    )
    monkeypatch.setenv("REACTBITS_SOURCE_DIR", str(tmp_path / "react-bits"))
    assets = tmp_path / "app" / "assets"
    source.ensure_component_source("Backgrounds", "Ballpit", ("Ballpit.jsx",), assets_dir=assets)
    jsx = (assets / "reactbits" / "Backgrounds" / "Ballpit" / "Ballpit.jsx").read_text()
    assert "forceContextLoss" not in jsx
    assert "this.renderer.dispose();" in jsx


def test_reflective_card_declares_lucide_react():
    """Its JSX imports lucide-react, which Reflex only installs for rx.icon."""
    jsx_import_is_undeclared = "lucide-react" not in rb.ReflectiveCard.lib_dependencies
    assert not jsx_import_is_undeclared
    imports = rb.reflective_card()._get_all_imports()
    assert any("lucide-react" in str(k) for k in imports)


def test_cli_add_still_vendors_when_backend_only(tmp_path, monkeypatch):
    """`reactbits add` must work in a backend-only process (e.g. offline images)."""
    from reflex_reactbits import cli

    monkeypatch.setenv("REFLEX_BACKEND_ONLY", "1")
    repo = tmp_path / "react-bits" / "src" / "content" / "TextAnimations" / "BlurText"
    repo.mkdir(parents=True)
    (repo / "BlurText.jsx").write_text("export default () => null;\n")
    monkeypatch.setenv("REACTBITS_SOURCE_DIR", str(tmp_path / "react-bits"))
    assets = tmp_path / "app" / "assets"
    assert cli.main(["add", "BlurText", "--assets-dir", str(assets)]) == 0
    assert (assets / "reactbits" / "TextAnimations" / "BlurText" / "BlurText.jsx").exists()


def test_component_creation_skips_vendoring_when_backend_only(tmp_path, monkeypatch):
    """The backend-only short circuit still applies where it belongs: rendering."""
    monkeypatch.setenv("REFLEX_BACKEND_ONLY", "1")
    monkeypatch.chdir(tmp_path)
    rb.blur_text()
    assert not (tmp_path / "assets").exists()


def test_event_payload_sanitizer_keeps_repeated_objects():
    """seen must track the current path, not every value already visited.

    An object reachable twice (the same option listed twice, two keys sharing a
    config) is not a cycle: dropping it silently corrupts the event payload.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to exercise the JS sanitizer")
    script = (
        base.SAFE_FN_CODE
        + """
const opt = { value: 'day' };
const cfg = { theme: 'dark' };
const cyc = { name: 'x' }; cyc.self = cyc;
console.log(JSON.stringify({
  repeatedInArray: reactbitsSafe([opt, opt]),
  sharedAcrossKeys: reactbitsSafe({ a: cfg, b: cfg }),
  realCycle: reactbitsSafe(cyc),
}));
"""
    )
    out = subprocess.run(
        [node, "--input-type=module", "-e", script], capture_output=True, text=True, check=True
    )
    result = json.loads(out.stdout)
    assert result["repeatedInArray"] == [{"value": "day"}, {"value": "day"}]
    assert result["sharedAcrossKeys"] == {"a": {"theme": "dark"}, "b": {"theme": "dark"}}
    assert result["realCycle"] == {"name": "x"}
