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
    assert len(main) == 217
    assert {e["category"] for e in main} == {"TextAnimations", "Animations", "Components", "Backgrounds", "Micro"}


def test_props_are_camel_cased():
    out = str(rb.blur_text(text="Hi", animate_by="letters", step_duration=0.5))
    assert "animateBy" in out and "stepDuration" in out


def test_sub_components():
    out = str(rb.stepper(rb.step(rx.text("A"), title="First", description="Intro")))
    assert "ReactBitsStep" in out and 'title:"First"' in out
    out = str(rb.tilted_card(rb.tilted_card_layer(rx.text("Up"), depth=28), image_src="/a.png"))
    assert "ReactBitsTiltedCardLayer" in out and "depth:28" in out
    assert "tiltedCardLayer" not in out and "TiltedCardLayer:" not in out


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


def test_components_moved_between_categories_keep_their_factory():
    """React Bits 2.0 moved Antigravity, MagicRings and MagnetLines to Backgrounds."""
    for name in ("Antigravity", "MagicRings", "MagnetLines"):
        entry = rb.find_component(name)
        assert entry["category"] == "Backgrounds"
        assert getattr(rb, entry["class"]).library.startswith(f"$/public/reactbits/Backgrounds/{name}/")


def test_new_2_0_components_are_exposed():
    for factory in ("tech_text", "flip_card", "holo_card", "flux_lines", "shredder"):
        assert callable(getattr(rb, factory))


def test_find_component():
    assert rb.find_component("blur-text")["class"] == "BlurText"
    assert rb.find_component("BlurText")["factory"] == "blur_text"
    with pytest.raises(KeyError):
        rb.find_component("nope")


def test_source_copy_never_overwrites(tmp_path, monkeypatch):
    monkeypatch.delenv("REFLEX_BACKEND_ONLY")
    repo = tmp_path / "react-bits" / "src" / "content" / "Components" / "PillNav"
    repo.mkdir(parents=True)
    (repo / "PillNav.jsx").write_text("export default () => null;\n")
    (repo / "PillNav.css").write_text(".a{}")
    monkeypatch.setenv("REACTBITS_SOURCE_DIR", str(tmp_path / "react-bits"))
    assets = tmp_path / "app" / "assets"
    written = source.ensure_component_source(
        "Components", "PillNav", ("PillNav.css", "PillNav.jsx"), assets_dir=assets
    )
    assert len(written) == 2
    # Existing (possibly user-edited) files are never overwritten.
    (assets / "reactbits" / "Components" / "PillNav" / "PillNav.css").write_text("/* mine */")
    assert source.ensure_component_source(
        "Components", "PillNav", ("PillNav.css", "PillNav.jsx"), assets_dir=assets
    ) == []
    assert "mine" in (assets / "reactbits" / "Components" / "PillNav" / "PillNav.css").read_text()


@pytest.mark.parametrize(
    "cleanup",
    [
        "gl.getExtension('WEBGL_lose_context')?.loseContext();",
        "if (!gl.isContextLost()) gl.getExtension('WEBGL_lose_context')?.loseContext();",
    ],
)
def test_canvas_components_keep_context_usable_across_remounts(tmp_path, monkeypatch, cleanup):
    """A component must not force-lose the context of a <canvas> React owns.

    StrictMode re-runs the effect on the same DOM node, and a canvas only ever
    has one context: once lost, the next getContext() returns that lost context
    and every shader fails to compile, so the component renders blank.
    """
    monkeypatch.delenv("REFLEX_BACKEND_ONLY")
    repo = tmp_path / "react-bits" / "src" / "content" / "Backgrounds" / "Aurora"
    repo.mkdir(parents=True)
    # Verbatim shape of the upstream 2.0 effect cleanup.
    (repo / "Aurora.jsx").write_text(
        "    return () => {\n      gl.deleteProgram(program);\n"
        f"      {cleanup}\n    }};\n"
        "  return <canvas ref={canvasRef} />;\n"
    )
    monkeypatch.setenv("REACTBITS_SOURCE_DIR", str(tmp_path / "react-bits"))
    assets = tmp_path / "app" / "assets"
    source.ensure_component_source("Backgrounds", "Aurora", ("Aurora.jsx",), assets_dir=assets)
    jsx = (assets / "reactbits" / "Backgrounds" / "Aurora" / "Aurora.jsx").read_text()
    assert "loseContext" not in jsx
    assert "gl.deleteProgram(program);" in jsx


def test_offscreen_canvas_cleanup_is_left_alone(tmp_path, monkeypatch):
    """Components that create their canvas in JS own it, so their cleanup stays."""
    monkeypatch.delenv("REFLEX_BACKEND_ONLY")
    repo = tmp_path / "react-bits" / "src" / "content" / "Backgrounds" / "MicroSlats"
    repo.mkdir(parents=True)
    code = "const c = document.createElement('canvas');\ngl.getExtension('WEBGL_lose_context')?.loseContext();\n"
    (repo / "MicroSlats.jsx").write_text(code)
    monkeypatch.setenv("REACTBITS_SOURCE_DIR", str(tmp_path / "react-bits"))
    assets = tmp_path / "app" / "assets"
    source.ensure_component_source("Backgrounds", "MicroSlats", ("MicroSlats.jsx",), assets_dir=assets)
    assert (assets / "reactbits" / "Backgrounds" / "MicroSlats" / "MicroSlats.jsx").read_text() == code


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


def _fake_repo(tmp_path, monkeypatch, text="export default () => null;\n"):
    repo = tmp_path / "react-bits" / "src" / "content" / "Backgrounds" / "Silk"
    repo.mkdir(parents=True)
    (repo / "Silk.jsx").write_text(text)
    (repo / "Silk.css").write_text(".silk{}")
    monkeypatch.setenv("REACTBITS_SOURCE_DIR", str(tmp_path / "react-bits"))
    monkeypatch.delenv("REFLEX_BACKEND_ONLY")
    monkeypatch.setattr(source, "_warned_stale", set())
    return tmp_path / "app" / "assets"


def test_copied_source_records_its_ref(tmp_path, monkeypatch):
    assets = _fake_repo(tmp_path, monkeypatch)
    source.ensure_component_source("Backgrounds", "Silk", ("Silk.css", "Silk.jsx"), assets_dir=assets)
    assert source.vendored_ref("Backgrounds", "Silk", assets) == source.PINNED_REF


def test_source_from_an_older_release_is_kept_but_reported(tmp_path, monkeypatch, caplog):
    """Upgrading must not overwrite user files, nor hide that they are 1.x sources.

    A 1.x copy of Silk had only Silk.jsx; 2.0 adds Silk.css. Writing the new file
    must not stamp the directory as current while the old JSX is still there.
    """
    assets = _fake_repo(tmp_path, monkeypatch)
    old = assets / "reactbits" / "Backgrounds" / "Silk"
    old.mkdir(parents=True)
    (old / "Silk.jsx").write_text("// 1.x\n")
    with caplog.at_level("WARNING", logger="reflex_reactbits"):
        written = source.ensure_component_source(
            "Backgrounds", "Silk", ("Silk.css", "Silk.jsx"), assets_dir=assets
        )
    assert [p.name for p in written] == ["Silk.css"]
    assert (old / "Silk.jsx").read_text() == "// 1.x\n"
    assert source.vendored_ref("Backgrounds", "Silk", assets) is None
    assert "reactbits add Silk --force" in caplog.text

    source.ensure_component_source(
        "Backgrounds", "Silk", ("Silk.css", "Silk.jsx"), assets_dir=assets, force=True
    )
    assert (old / "Silk.jsx").read_text() == "export default () => null;\n"
    assert source.vendored_ref("Backgrounds", "Silk", assets) == source.PINNED_REF


def test_cli_add_reports_stale_copies(tmp_path, monkeypatch, capsys):
    from reflex_reactbits import cli

    assets = _fake_repo(tmp_path, monkeypatch)
    (assets / "reactbits" / "Backgrounds" / "Silk").mkdir(parents=True)
    (assets / "reactbits" / "Backgrounds" / "Silk" / "Silk.jsx").write_text("// 1.x\n")
    assert cli.main(["add", "Silk", "--assets-dir", str(assets)]) == 0
    assert "stale" in capsys.readouterr().out
    assert cli.main(["add", "Silk", "--force", "--assets-dir", str(assets)]) == 0
    assert "added" in capsys.readouterr().out


def _plain(value):
    """Docs examples mark JSX values as {"$jsx": ...}; a string is a valid ReactNode."""
    if isinstance(value, dict) and value.get("$jsx"):
        return value.get("text") or "x"
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


@pytest.mark.parametrize("entry", [e for e in rb.CATALOG if e.get("example")], ids=lambda e: e["class"])
def test_official_usage_example_is_accepted(entry):
    """The wrapper types must accept every value the React Bits docs pass."""
    props = _plain(entry["example"]["props"])
    getattr(rb, entry["factory"])(**props)


def test_literal_members_named_like_types_are_kept():
    rb.scroll_float("Hi", effect="float")
