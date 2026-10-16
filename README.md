# reflex-reactbits

[Reflex](https://reflex.dev) wrappers for **[React Bits](https://reactbits.dev)** — the
open-source collection of animated, interactive and customizable React components by
David Haz. Every one of the **217 React Bits 2.0 components** (plus 5 sub-components) is
available as a typed Python component: text animations, animations, UI components,
animated WebGL backgrounds and the new *Micro* interactions.

```python
import reflex as rx
import reflex_reactbits as rb


class State(rx.State):
    liked: bool = False

    @rx.event
    def toggle(self, liked: bool, count: int):
        self.liked = liked


def index():
    return rx.box(
        rx.box(rb.aurora(color_stops=["#3A29FF", "#FF94B4", "#FF3232"], amplitude=1.0),
               position="absolute", inset="0"),
        rb.blur_text(text="Hello from Reflex", animate_by="words", delay=120),
        rb.pulse_heart(count=128, on_change=State.toggle),
        position="relative", height="100vh",
    )
```

## Installation

```bash
pip install reflex-reactbits      # or: uv add reflex-reactbits
```

Requires `reflex>=0.9`.

## How it works (and why the JS is not bundled)

React Bits is distributed as **source code you copy into your project** (via the
`shadcn`/`jsrepo` CLIs or by hand), not as an npm package, and its license
(MIT + Commons Clause) does not allow redistributing the components themselves in a
bundle. So this package ships only the Python side:

1. Each wrapper knows the React Bits category, files and npm dependencies of its component.
2. The first time you use a component, its original JS-CSS source is copied into your
   app at `assets/reactbits/<Category>/<Name>/` — the same thing `npx shadcn add` does in
   a React project. The files are pinned to the React Bits commit these wrappers were
   generated from.
3. Reflex imports that file client-side only (`NoSSRComponent`) and installs exact npm
   versions: the ones React Bits is locked to (`ogl`, `matter-js`, Hugeicons, ...), except
   for `motion` 14, `three` 0.186 (with `@react-three/fiber` 9.8 and `@react-three/drei`
   10.7) and `gsap` 3.15, which are newer than React Bits' lockfile (see `DEP_VERSIONS` in
   `scripts/generate_wrappers.py`).

The copied files belong to your app: **edit them freely**, they are never overwritten.
Commit them if you want reproducible offline builds.

Sources are resolved from `REACTBITS_SOURCE_DIR` (a local clone of
[DavidHDev/react-bits](https://github.com/DavidHDev/react-bits)) when set, otherwise from
GitHub raw files at `REACTBITS_REF` (defaults to the pinned commit).

React Bits 2.0 no longer needs React Router, Chakra UI or Tailwind, so the sources are
copied as-is with two exceptions. Components that render their own `<canvas>` keep their
WebGL context on unmount instead of calling `loseContext()`: React StrictMode (on in Reflex
dev mode) re-runs effects on the same canvas, and a lost context would leave the component
frozen or blank. And `color_bends` and `paper_crumple` move off three.js APIs deprecated
after r180 (`THREE.Clock` → `THREE.Timer`, `PCFSoftShadowMap` → `PCFShadowMap`), so the
newer `three` does not log deprecation warnings.

Each copy records the React Bits commit it came from in `.reactbits-ref`. When a newer
version of this package is generated from another commit, existing copies are **not**
replaced (they may hold your edits), but a warning names them and `reactbits add` lists
them as `stale`.

## The `reactbits` CLI

```bash
reactbits list [--category Backgrounds]   # every component and its factory name
reactbits info pulse_heart                # props, types, defaults, events, npm deps
reactbits add BlurText Aurora             # copy sources into ./assets/reactbits now
reactbits add --all                       # vendor all components (offline / CI builds)
reactbits remove Aurora
```

## Upgrading from 0.1.x (React Bits 1.x → 2.0)

0.2.0 wraps React Bits 2.0, which reworked most components. In short:

* **Props changed** on most components (renamed, removed or added). React ignores unknown
  props, so check each component's props (`reactbits info <name>`) when upgrading.
* **Replace the copied sources**: `reactbits add --all --force` in your app (this discards
  local edits to them), or delete `assets/reactbits/` and let it be re-created.
* **New components (15):** `circular_carousel`, `crystalized_ball`, `dither_veil`,
  `electric_logo`, `flex_carousel`, `flip_card`, `flux_lines`, `gradient_ascii`,
  `holo_card`, `micro_slats`, `paper_crumple`, `pattern_waves`, `shredder`, `tear_ticket`,
  `tech_text`; and the `tilted_card_layer` sub-component.
* **Moved to Backgrounds:** `antigravity`, `magic_rings`, `magnet_lines` (same factory names).
* **Removed APIs:** `rb.hyperspeed(preset=...)` (use `curve`, `boosting`, colour props),
  `splash_cursor`'s `SIM_RESOLUTION`-style props, Lanyard/FluidGlass `.glb` assets (the 3D
  geometry is now procedural).
* **Fewer npm dependencies:** lucide-react, react-icons, Chakra UI, react-router,
  postprocessing, lenis, maath, meshline, face-api.js and @react-three/rapier are gone;
  icons come from Hugeicons.
* A prop named like a Python builtin gets a trailing underscore, like `from_`:
  `float` → `float_` (`depth_text`, `model_viewer`).

## Props, events and children

* Props use snake_case and are converted to the React prop names (`animate_by` → `animateBy`,
  `sim_resolution` → `SIM_RESOLUTION`, `from_` → `from`). Unset props keep React Bits' defaults.
* Every prop is typed and documented (hover it in your editor, or run `reactbits info`).
  Numbers accept `int` and `float`; `ReactNode` props accept strings or Reflex components.
* Lists/dicts may contain Reflex components, e.g. dock icons:
  `rb.dock(items=[{"icon": rx.icon("house"), "label": "Home"}])`.
* Callbacks are Reflex event triggers with the right arity — `on_change` of `rubber_segment`
  gives `(value, index)`, `on_send` of `prompt_bar` gives `(text, options)`, and so on.
  Payloads are sanitized before they are sent (React elements, DOM events and functions are
  dropped, `File`s become metadata), so every React Bits callback is safe to bind.
* JS-function props (easing curves, custom renderers) take a JS expression:
  `rb.blur_text(text="Hi", easing=rx.Var("(t) => t * t"))`.
* Wrapper components take Reflex children: `rb.fade_content(rx.text("Hi"), blur=True)`.
* Sub-components: `rb.stepper(rb.step(...), ...)`, `rb.card_swap(rb.card_swap_card(...))`,
  `rb.scroll_stack(rb.scroll_stack_item(...))`, `rb.warm_tooltip_group(...)`.
* `rb.tilted_card(rb.tilted_card_layer(..., depth=30), ...)` floats content above the card;
  `rb.step(..., title="Plan")` labels a stepper step.
* `rb.hyperspeed(curve="racing", boosting=State.loading)` - 2.0 replaced the presets with
  props.
* Backgrounds and canvas effects fill their parent: give the parent a size and
  `position="relative"`.

`rb.CATALOG` / `rb.find_component()` expose the full metadata (props, types, events,
docs URL, npm deps) at runtime.

## Components

**Text animations (33):** `ascii_text`, `blur_text`, `circular_text`, `count_up`, `curved_loop`, `decrypted_text`, `depth_text`, `echo_text`, `falling_text`, `fold_text`, `fuzzy_text`, `glitch_text`, `gradient_text`, `masked_heading`, `particle_text`, `rotating_text`, `scrambled_text`, `scroll_float`, `scroll_reveal`, `scroll_velocity`, `shiny_text`, `shuffle`, `split_flap_text`, `split_text`, `stroke_text`, `tech_text`, `text_cursor`, `text_loop`, `text_pressure`, `text_type`, `true_focus`, `variable_proximity`, `warp_text`

**Animations (38):** `animated_content`, `blob_cursor`, `click_spark`, `crosshair`, `crystalized_ball`, `cubes`, `cursor_grid`, `dither_veil`, `elastic_mesh`, `electric_border`, `electric_logo`, `fade_content`, `ghost_cursor`, `glare_hover`, `glow_cursor`, `gradual_blur`, `halftone_reveal`, `image_trail`, `laser_flow`, `logo_loop`, `magnet`, `meta_balls`, `metallic_paint`, `noise`, `orbit_images`, `pixel_swap`, `pixel_trail`, `pixel_transition`, `ribbons`, `ripple_distortion`, `scroll_expand`, `shape_blur`, `splash_cursor`, `star_border`, `sticker_peel`, `strands`, `swarm_cursor`, `target_cursor`

**Components (48 + 4 sub-components):** `accordion_gallery`, `animated_list`, `border_glow`, `bounce_cards`, `bubble_menu`, `card_nav`, `card_swap`, `card_swap_card`, `carousel`, `chroma_grid`, `circular_carousel`, `circular_gallery`, `counter`, `curved_input`, `decay_card`, `depth_carousel`, `dock`, `dome_gallery`, `drift_wall`, `elastic_slider`, `flex_carousel`, `flowing_menu`, `fluid_glass`, `flying_posters`, `folder`, `glass_icons`, `glass_surface`, `gooey_nav`, `holo_card`, `infinite_menu`, `infinite_spiral`, `lanyard`, `line_sidebar`, `magic_bento`, `masonry`, `model_viewer`, `morph_slider`, `option_wheel`, `pill_nav`, `pixel_card`, `profile_card`, `reflective_card`, `scroll_stack`, `scroll_stack_item`, `specular_button`, `spotlight_card`, `stack`, `staggered_menu`, `step`, `stepper`, `tilted_card`, `tilted_card_layer`

**Backgrounds (64):** `acid_squares`, `aero_shards`, `antigravity`, `aurora`, `balatro`, `ballpit`, `beams`, `color_bends`, `crt_warp`, `dark_veil`, `dither`, `dot_field`, `dot_grid`, `evil_eye`, `faulty_terminal`, `ferrofluid`, `floating_lines`, `flux_lines`, `galaxy`, `ghost_fibers`, `gradient_ascii`, `gradient_blinds`, `gradient_waves`, `grainient`, `grid_distortion`, `grid_motion`, `grid_scan`, `hyperspeed`, `iridescence`, `letter_glitch`, `light_pillar`, `light_rays`, `light_tunnel`, `lightfall`, `lightning`, `line_waves`, `liquid_chrome`, `liquid_ether`, `magic_rings`, `magnet_lines`, `micro_slats`, `molten_metal`, `orb`, `particles`, `pattern_waves`, `pixel_blast`, `pixel_snow`, `plasma`, `plasma_wave`, `prism`, `prismatic_burst`, `radar`, `ripple_grid`, `scanner`, `shape_grid`, `shape_waves`, `side_rays`, `silk`, `sliced_waves`, `soft_aurora`, `threads`, `topography`, `waves`, `web_threads`

**Micro interactions (34 + 1 sub-component):** `bell_toggle`, `branched_menu`, `call_chip`, `code_slots`, `comet_dial`, `dodge_field`, `flip_card`, `folder_float`, `fuse_button`, `glide_select`, `hold_button`, `jelly_radio`, `lattice_loader`, `paper_crumple`, `peek_rating`, `prompt_bar`, `pulse_heart`, `refine_frame`, `rubber_segment`, `scrub_field`, `shredder`, `slide_commit`, `sling_button`, `slosh_gauge`, `spring_check`, `squish_switch`, `status_mark`, `swipe_row`, `swipe_toast`, `tear_ticket`, `thought_line`, `voice_pill`, `wake_slider`, `warm_tooltip`, `warm_tooltip_group`

Full docs, previews and prop descriptions for each component live at
[reactbits.dev](https://reactbits.dev).

## Demo app

`reactbits_demo/` is a gallery with a page per component (live preview, replay, event
log wired to Reflex state, generated Python usage and the props table), a playground
where props are bound to state vars, a *What's new in 2.0* page with live previews of
every new component, and a landing page built only with React Bits.

```bash
uv sync --extra dev
cd reactbits_demo
uv run reflex run
```

## Regenerating the wrappers

The wrappers are generated from the React Bits sources, so new React Bits releases can be
picked up automatically:

```bash
git clone https://github.com/DavidHDev/react-bits /tmp/react-bits
(cd scripts && npm install)
node scripts/extract_metadata.mjs /tmp/react-bits scripts/components.json
python scripts/generate_wrappers.py scripts/components.json /tmp/react-bits
```

Update `PINNED_REF` in `custom_components/reflex_reactbits/source.py` to the new commit.

## Development

```bash
uv sync --extra dev
uv run pytest
# type stubs (.pyi) for editor autocomplete, then sdist + wheel in dist/
(cd custom_components && uv run python -c "from reflex_base.utils.pyi_generator import PyiGenerator; PyiGenerator().scan_all(['reflex_reactbits'])")
uv build
```

## Continuous integration

Three workflows run in `.github/workflows/`:

| Workflow | Runs on | What it checks |
| --- | --- | --- |
| `quality.yml` | push and PR to `main`/`develop` | `ruff check`; `pytest` on Python 3.10-3.13; builds the sdist and wheel, runs `twine check`, and fails if any React Bits source slipped into the distribution or into git |
| `security.yml` | push, PR, and weekly | `pip-audit` on the dependency tree, `bandit` over the hand-written modules, `gitleaks` over the full history, CodeQL, and a dependency review on PRs |

The dependency-review job needs GitHub's dependency graph to be provisioned for the
repository, which it is not yet: until you enable it at *Settings → Code security →
Dependency graph*, that job reports "not supported on this repository" and is marked
`continue-on-error` so it cannot block a merge. Drop that line once it is on. Vulnerable
dependencies are caught by `pip-audit` regardless; the job only adds the diff of what a
given pull request introduces.
| `release.yml` | a `v*` tag, or manually | Rebuilds, refuses a tag that disagrees with the version in `pyproject.toml`, publishes a GitHub release and uploads to PyPI |

## Releasing

```bash
# 1. bump the version
$EDITOR pyproject.toml          # [project] version = "0.2.0"

# 2. tag it; the tag must match that version or release.yml stops
git tag v0.2.0 && git push origin v0.2.0
```

The tag triggers `release.yml`, which builds, creates the GitHub release with the
artifacts attached, and uploads to PyPI. `workflow_dispatch` runs the same thing on
demand and can target TestPyPI instead.


## License

The Python wrappers in this repository are MIT licensed (see `LICENSE`).
React Bits itself is © David Haz under the
[MIT + Commons Clause license](https://github.com/DavidHDev/react-bits/blob/main/LICENSE.md):
you may use the components in your applications, including commercially, but not sell or
redistribute the components themselves. That is why their source is fetched into your
app instead of being bundled here. This project is not affiliated with React Bits.
