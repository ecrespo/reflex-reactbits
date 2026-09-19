"""Build a live preview (and its Python source) for every catalog entry.

Most previews are derived automatically from the usage snippet published in the
React Bits docs (stored in ``catalog.json``). A few components need real
children or icons, so they get hand-written examples below.
"""

from __future__ import annotations

import pprint
import re
import zlib
from collections.abc import Callable
from typing import Any

import reflex as rx
import reflex_reactbits as rb

from .state import EventLog

ICONS = ["house", "archive", "user", "settings", "star", "heart", "bell", "camera", "music", "globe"]
# Local placeholder images (assets/demo/img1..12.jpg) so previews work offline.
IMG_COUNT = 12
IMG_RE = re.compile(r"(picsum\.photos|unsplash\.com|scdn\.co|\.(png|jpe?g|webp|gif|avif)(\?|$))", re.I)


def IMG(i: int | str) -> str:
    # crc32, not hash(): str hashing is salted per process, so the compiled
    # frontend would pick different placeholder images on every `reflex run`.
    return f"/demo/img{(zlib.crc32(str(i).encode()) % IMG_COUNT) + 1}.jpg"

# Preview box height per category (backgrounds and 3D need a sized parent).
HEIGHTS = {"Backgrounds": "520px", "Animations": "460px", "Components": "520px", "TextAnimations": "380px", "Micro": "320px"}
TALL = {"ScrollStack": "600px", "Masonry": "640px", "ChromaGrid": "700px", "Lanyard": "640px", "StaggeredMenu": "600px",
        "FlyingPosters": "600px", "InfiniteMenu": "600px", "DomeGallery": "600px", "CardNav": "520px", "Stepper": "560px",
        "ScrollReveal": "460px", "ScrollFloat": "460px", "ScrollVelocity": "360px", "BubbleMenu": "520px"}


def _materialize(value: Any, counter: list[int]) -> Any:
    """Turn JSX placeholders from the docs usage into Reflex components."""
    if isinstance(value, str) and IMG_RE.search(value) and not value.startswith("data:"):
        counter[1] += 1
        return f"/demo/img{(counter[1] % IMG_COUNT) + 1}.jpg"
    if isinstance(value, dict) and value.get("$jsx"):
        if value.get("text"):
            return rx.text(value["text"], weight="bold")
        counter[0] += 1
        return rx.icon(ICONS[counter[0] % len(ICONS)], size=18)
    if isinstance(value, dict):
        return {k: _materialize(v, counter) for k, v in value.items()}
    if isinstance(value, list):
        return [_materialize(v, counter) for v in value]
    return value


def _source(value: Any) -> Any:
    if isinstance(value, dict) and value.get("$jsx"):
        return f"<{value['$jsx']}>"
    if isinstance(value, dict):
        return {k: _source(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_source(v) for v in value]
    return value


def _card(title: str, body: str) -> rx.Component:
    return rx.box(
        rx.heading(title, size="5"),
        rx.text(body, color_scheme="gray"),
        padding="1.5em",
    )


def _content_card(title: str, body: str, color: str = "#120F17") -> rx.Component:
    return rx.vstack(
        rx.heading(title, size="6"),
        rx.text(body),
        padding="2em",
        background=color,
        border_radius="16px",
        height="100%",
        width="100%",
    )


LOGO = "data:image/svg+xml;utf8," + (
    "<svg xmlns='http://www.w3.org/2000/svg' width='120' height='28'>"
    "<text x='0' y='21' font-family='sans-serif' font-size='20' font-weight='700' fill='white'>Reflex</text></svg>"
)

# ---------------------------------------------------------------------------
# Hand-written examples: name -> (builder, python source)

def _stepper(**events) -> rx.Component:
    return rb.stepper(
        rb.step(rx.heading("Welcome to the React Bits stepper!", size="5"), rx.text("Check out the next step!")),
        rb.step(rx.heading("Step 2", size="5"), rx.image(src=IMG("step"), height="100px", width="100%", object_fit="cover", border_radius="15px")),
        rb.step(rx.heading("How about an input?", size="5"), rx.input(placeholder="Your name?")),
        rb.step(rx.heading("Final step", size="5"), rx.text("You made it!")),
        initial_step=1,
        back_button_text="Previous",
        next_button_text="Next",
        **events,
    )


def _card_swap(**events) -> rx.Component:
    return rx.box(
        rb.card_swap(
            *[rb.card_swap_card(_content_card(f"Card {i}", "Your content here"), key=f"card-{i}") for i in (1, 2, 3)],
            card_distance=60,
            vertical_distance=70,
            delay=5000,
            pause_on_hover=False,
            **events,
        ),
        height="100%",
        width="100%",
        position="relative",
    )


def _scroll_stack(**events) -> rx.Component:
    return rb.scroll_stack(
        *[rb.scroll_stack_item(rx.heading(f"Card {i}", size="7"), rx.text(f"This is card number {i} in the stack")) for i in (1, 2, 3)],
        **events,
    )


def _warm_tooltip(**events) -> rx.Component:
    return rx.hstack(
        *[
            rb.warm_tooltip(rx.button(label, variant="soft"), content=f"{label} tooltip", shortcut=key, **events)
            for label, key in (("Copy", "⌘C"), ("Paste", "⌘V"), ("Cut", "⌘X"))
        ],
        spacing="3",
    )


def _dock(**events) -> rx.Component:
    return rb.dock(
        items=[{"icon": rx.icon(icon, size=18, color="white"), "label": label}
               for icon, label in (("house", "Home"), ("archive", "Archive"), ("user", "Profile"), ("settings", "Settings"))],
        panel_height=68,
        base_item_size=50,
        magnification=70,
        **events,
    )


def _gradual_blur(**events) -> rx.Component:
    return rx.box(
        rx.scroll_area(
            rx.vstack(*[rx.text(f"Scrollable line {i} - gradual blur sits on top of this content.", size="4") for i in range(40)], padding="2em"),
            height="100%",
        ),
        rb.gradual_blur(target="parent", position="bottom", height="7rem", strength=2, div_count=5, curve="bezier", exponential=True, opacity=1, **events),
        position="relative",
        height="100%",
        width="100%",
        overflow="hidden",
    )


def _wrap_content(factory: Callable[..., rx.Component], **kwargs):
    def build(**events):
        return factory(
            rx.box(rx.heading("Animated content", size="7"), rx.text("Any Reflex children work here."), padding="2em", border="1px solid #333", border_radius="16px"),
            **kwargs,
            **events,
        )
    return build


def _click_spark(**events) -> rx.Component:
    return rb.click_spark(
        rx.center(rx.text("Click anywhere in this box", size="5"), height="100%", width="100%"),
        spark_color="#fff", spark_size=10, spark_radius=15, spark_count=8, duration=400, **events,
    )


def _star_border(**events) -> rx.Component:
    return rb.star_border(rx.text("Star border"), as_="button", color="cyan", speed="5s", **events)


def _glare_hover(**events) -> rx.Component:
    return rb.glare_hover(rx.heading("Hover me", size="8"), glare_color="#ffffff", glare_opacity=0.3, glare_angle=-30, glare_size=300, transition_duration=800, **events)


def _spotlight_card(**events) -> rx.Component:
    return rb.spotlight_card(_card("Spotlight card", "Move the cursor over this card."), spotlight_color="rgba(0, 229, 255, 0.2)", **events)


def _electric_border(**events) -> rx.Component:
    return rb.electric_border(_card("Electric border", "An animated electric outline."), color="#7df9ff", speed=1, chaos=0.12, **events)


def _border_glow(**events) -> rx.Component:
    return rb.border_glow(_card("Border glow", "A glowing border that follows your pointer."), **events)


def _tilted_card(**events) -> rx.Component:
    return rb.tilted_card(
        image_src=IMG("tilted"),
        alt_text="Album cover", caption_text="Tilted card", container_height="300px", container_width="300px",
        image_height="300px", image_width="300px", rotate_amplitude=12, scale_on_hover=1.2,
        show_mobile_warning=False, show_tooltip=True, display_overlay_content=True,
        overlay_content=rx.text("Tilted card", weight="bold", padding="1em"), **events,
    )


def _magnet(**events) -> rx.Component:
    return rb.magnet(rx.button("Star React Bits on GitHub!", size="3"), padding=50, disabled=False, magnet_strength=5, **events)


def _pixel_transition(**events) -> rx.Component:
    return rb.pixel_transition(
        first_content=rx.image(src=IMG("pixel"), width="100%", height="100%", object_fit="cover"),
        second_content=rx.center(rx.text("Meow!", size="8", weight="bold"), width="100%", height="100%", background="#111"),
        grid_size=12, pixel_color="#ffffff", once=False, animation_step_duration=0.4, class_name="custom-pixel-card", **events,
    )


def _fade(factory, **kwargs):
    return _wrap_content(factory, **kwargs)


OVERRIDES: dict[str, Callable[..., rx.Component]] = {
    "Stepper": _stepper,
    "CardSwap": _card_swap,
    "ScrollStack": _scroll_stack,
    "WarmTooltip": _warm_tooltip,
    "Dock": _dock,
    "GradualBlur": _gradual_blur,
    "AnimatedContent": _wrap_content(rb.animated_content, distance=150, direction="horizontal", duration=1.2, ease="bounce.out", initial_opacity=0.2, animate_opacity=True, scale=1.1, threshold=0.2, delay=0.3),
    "FadeContent": _wrap_content(rb.fade_content, blur=True, duration=1000, initial_opacity=0),
    "ClickSpark": _click_spark,
    "StarBorder": _star_border,
    "GlareHover": _glare_hover,
    "SpotlightCard": _spotlight_card,
    "ElectricBorder": _electric_border,
    "BorderGlow": _border_glow,
    "TiltedCard": _tilted_card,
    "Magnet": _magnet,
    "PixelTransition": _pixel_transition,
}


def _event_props(entry: dict) -> dict[str, Callable]:
    """Wire every event of the component to the demo's event log."""
    handlers: dict[str, Callable] = {}
    for prop in entry["props"]:
        if prop["type"] != "event":
            continue
        name, n = prop["name"], len(prop.get("args") or [])
        if n == 0:
            handlers[name] = lambda name=name: EventLog.log(name, [])
        elif n == 1:
            handlers[name] = lambda a, name=name: EventLog.log(name, [a])
        elif n == 2:
            handlers[name] = lambda a, b, name=name: EventLog.log(name, [a, b])
        else:
            handlers[name] = lambda a, b, c, name=name: EventLog.log(name, [a, b, c])
    return handlers


def build_preview(entry: dict) -> rx.Component:
    """Return the live preview for a catalog entry."""
    events = _event_props(entry)
    if entry["name"] in OVERRIDES and not entry.get("sub"):
        return OVERRIDES[entry["name"]](**events)
    factory = getattr(rb, entry["factory"])
    example = entry.get("example") or {"props": {}, "children": None}
    counter = [0, 0]
    props = _materialize(example["props"], counter)
    if entry["name"] == "StaggeredMenu":
        props["logo_url"] = LOGO
    children = [
        c if isinstance(c, str) else _materialize(c, counter)
        for c in (example.get("children") or [])
    ]
    return factory(*children, **props, **events)


def python_source(entry: dict) -> str:
    """Python code equivalent to the preview (for the docs panel)."""
    example = entry.get("example") or {"props": {}, "children": None}
    lines = ["import reflex as rx", "import reflex_reactbits as rb", "", f"rb.{entry['factory']}("]
    for child in example.get("children") or []:
        lines.append(f"    {child!r}," if isinstance(child, str) else "    rx.box(...),")
    for key, value in example["props"].items():
        rendered = pprint.pformat(_source(value), width=80, sort_dicts=False).replace("\n", "\n    ")
        lines.append(f"    {key}={rendered},")
    for prop in entry["props"]:
        if prop["type"] == "event":
            args = ", ".join(prop.get("args") or [])
            lines.append(f"    {prop['name']}=State.handle_{prop['name'][3:]},  # receives ({args})")
            break
    lines.append(")")
    return "\n".join(lines)


def preview_height(entry: dict) -> str:
    return TALL.get(entry["name"], HEIGHTS.get(entry["category"], "420px"))
