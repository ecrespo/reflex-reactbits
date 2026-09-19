"""React Bits for Reflex - demo gallery.

* ``/``              landing page built only with React Bits components
* ``/playground``    React Bits props and events bound to Reflex state
* ``/category/<x>``  every component of a category
* ``/c/<name>``      live preview, event log, Python usage and props of one component
"""

from __future__ import annotations

import reflex as rx
import reflex_reactbits as rb

from .examples import build_preview, preview_height, python_source
from .state import EventLog, Nav, Playground

CATEGORY_INFO = {
    "TextAnimations": ("text-animations", "Text Animations", "type"),
    "Animations": ("animations", "Animations", "sparkles"),
    "Components": ("components", "Components", "layout-grid"),
    "Backgrounds": ("backgrounds", "Backgrounds", "image"),
    "Micro": ("micro", "Micro Interactions", "mouse-pointer-click"),
}
ENTRIES = [e for e in rb.CATALOG if not e.get("sub")]


def slug(entry: dict) -> str:
    return entry["factory"].replace("_", "-")


NAV_ITEMS = [
    {"label": e["name"], "href": f"/c/{slug(e)}", "category": CATEGORY_INFO[e["category"]][1]}
    for e in sorted(ENTRIES, key=lambda e: (list(CATEGORY_INFO).index(e["category"]), e["name"]))
]


class Sidebar(Nav):
    @rx.var
    def items(self) -> list[dict[str, str]]:
        q = self.query.strip().lower()
        return [i for i in NAV_ITEMS if not q or q in i["label"].lower() or q in i["category"].lower()]


# ---------------------------------------------------------------------------
# Layout

def nav_link(label: str, href: str, icon: str) -> rx.Component:
    return rx.link(
        rx.hstack(rx.icon(icon, size=16), rx.text(label, size="2", weight="medium"), spacing="2", align="center"),
        href=href,
        underline="none",
        color=rx.color("gray", 12),
        padding_y="4px",
    )


def sidebar() -> rx.Component:
    return rx.vstack(
        rx.link(
            rx.hstack(
                rx.icon("atom", size=22, color=rx.color("violet", 10)),
                rx.heading("React Bits", size="4"),
                rx.badge("Reflex", color_scheme="violet"),
                align="center",
                spacing="2",
            ),
            href="/",
            underline="none",
            color=rx.color("gray", 12),
        ),
        nav_link("Home", "/", "house"),
        nav_link("Playground", "/playground", "sliders-horizontal"),
        *[nav_link(title, f"/category/{s}", icon) for s, title, icon in CATEGORY_INFO.values()],
        rx.divider(),
        rx.input(
            rx.input.slot(rx.icon("search", size=14)),
            placeholder=f"Search {len(ENTRIES)} components...",
            value=Nav.query,
            on_change=Nav.set_query,
            size="2",
            width="100%",
        ),
        rx.scroll_area(
            rx.vstack(
                rx.foreach(
                    Sidebar.items,
                    lambda item: rx.link(
                        rx.hstack(
                            rx.text(item["label"], size="2"),
                            rx.spacer(),
                            rx.text(item["category"], size="1", color=rx.color("gray", 9), white_space="nowrap"),
                            width="100%",
                        ),
                        href=item["href"],
                        underline="none",
                        color=rx.color("gray", 11),
                        width="100%",
                        _hover={"color": rx.color("violet", 11)},
                    ),
                ),
                spacing="1",
                width="100%",
                padding_right="12px",
            ),
            type="hover",
            scrollbars="vertical",
            flex="1",
            width="100%",
        ),
        width="260px",
        min_width="260px",
        height="100vh",
        position="sticky",
        top="0",
        padding="1em",
        spacing="2",
        border_right=f"1px solid {rx.color('gray', 4)}",
        background=rx.color("gray", 1),
        display=["none", "none", "flex"],
    )


def layout(*children: rx.Component) -> rx.Component:
    return rx.hstack(
        sidebar(),
        rx.box(*children, flex="1", min_width="0", padding=["1em", "1.5em", "2em"], max_width="1200px"),
        spacing="0",
        align="start",
        width="100%",
    )


# ---------------------------------------------------------------------------
# Home

def category_card(cat: str) -> rx.Component:
    s, title, icon = CATEGORY_INFO[cat]
    items = [e for e in ENTRIES if e["category"] == cat]
    return rx.link(
        rb.spotlight_card(
            rx.vstack(
                rx.hstack(rx.icon(icon, size=22), rx.heading(title, size="5"), align="center"),
                rx.text(f"{len(items)} components", color=rx.color("gray", 10), size="2"),
                rx.text(", ".join(e["name"] for e in items[:6]) + "...", size="2", color=rx.color("gray", 11)),
                spacing="2",
                align="start",
            ),
            spotlight_color="rgba(132, 0, 255, 0.25)",
        ),
        href=f"/category/{s}",
        underline="none",
        color=rx.color("gray", 12),
    )


def index() -> rx.Component:
    return layout(
        rx.box(
            rx.box(
                rb.light_rays(rays_origin="top-center", rays_color="#b497cf", rays_speed=1.2, light_spread=0.9,
                              ray_length=1.4, follow_mouse=True, mouse_influence=0.1, noise_amount=0.05, distortion=0.05),
                position="absolute", inset="0",
            ),
            rx.vstack(
                rx.badge(f"reflex-reactbits · {len(ENTRIES)} components + 4 sub-components", color_scheme="violet", size="2", variant="surface"),
                rb.blur_text(text="React Bits, now in pure Python", delay=120, animate_by="words", direction="top",
                             class_name="hero-title"),
                rb.shiny_text(text="Text animations, backgrounds, UI components and micro interactions for Reflex.",
                              speed=3, class_name="hero-sub"),
                rx.hstack(
                    rx.link(rx.button("Open the playground", size="3"), href="/playground"),
                    rx.link(rx.button("Browse components", size="3", variant="outline"), href="/category/text-animations"),
                    spacing="3",
                ),
                align="center",
                justify="center",
                spacing="5",
                height="100%",
                position="relative",
                text_align="center",
                padding="2em",
            ),
            position="relative",
            height="520px",
            border_radius="24px",
            overflow="hidden",
            background="#060010",
        ),
        rx.hstack(
            *[
                rx.vstack(
                    rx.hstack(rb.count_up(to=n, from_=0, duration=2, separator=","), rx.text(suffix), class_name="stat-value", spacing="0"),
                    rx.text(label, color=rx.color("gray", 10)),
                    align="center",
                    flex="1",
                )
                for n, suffix, label in ((len(ENTRIES), "", "React Bits components"), (4, "", "sub-components"),
                                         (5, "", "categories"), (0, "", "lines of JavaScript you write"))
            ],
            width="100%",
            padding_y="2em",
        ),
        rx.heading("Categories", size="6", margin_bottom="0.5em"),
        rx.grid(*[category_card(c) for c in CATEGORY_INFO], columns=rx.breakpoints(initial="1", sm="2", lg="3"), spacing="4", width="100%"),
        rx.heading("Scroll velocity", size="6", margin_top="1.5em"),
        rb.scroll_velocity(texts=["React Bits", "Reflex"], velocity=60, class_name="velocity-text"),
    )


# ---------------------------------------------------------------------------
# Playground: props and events wired to Reflex state

def panel(title: str, *children: rx.Component, description: str = "") -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.heading(title, size="4"),
            rx.cond(description != "", rx.text(description, size="2", color=rx.color("gray", 10))),
            *children,
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


def playground() -> rx.Component:
    return layout(
        rx.heading("Playground", size="8"),
        rx.text("Every prop below is a Reflex state var and every callback is a Reflex event handler.",
                color=rx.color("gray", 10), margin_bottom="1em"),
        rx.grid(
            panel(
                "BlurText ← state",
                rx.input(value=Playground.headline, on_change=Playground.set_headline, width="100%"),
                rx.hstack(
                    rx.select(["words", "letters"], value=Playground.animate_by, on_change=Playground.set_animate_by),
                    rx.select(["top", "bottom"], value=Playground.direction, on_change=Playground.set_direction),
                ),
                rx.center(
                    rb.blur_text(
                        text=Playground.headline, animate_by=Playground.animate_by, direction=Playground.direction,
                        delay=90, class_name="play-title", on_animation_complete=Playground.on_blur_done,
                        key=Playground.headline + Playground.animate_by + Playground.direction,
                    ),
                    min_height="120px",
                ),
                description="Editing the input re-renders the animation; on_animation_complete fires a toast.",
            ),
            panel(
                "CountUp ← slider",
                rx.slider(default_value=[2026], min=0, max=10000, on_value_commit=Playground.set_count_to),
                rx.center(rb.count_up(to=Playground.count_to, from_=0, duration=1.5, separator=",", class_name="stat-value",
                                      key=Playground.count_to.to_string()), min_height="120px"),
            ),
            panel(
                "Aurora ← color pickers",
                rx.hstack(
                    rx.input(type="color", value=Playground.aurora_a, on_change=Playground.set_aurora_a, width="60px"),
                    rx.input(type="color", value=Playground.aurora_b, on_change=Playground.set_aurora_b, width="60px"),
                    rx.input(type="color", value=Playground.aurora_c, on_change=Playground.set_aurora_c, width="60px"),
                    rx.slider(default_value=[1.0], min=0.2, max=2.5, step=0.1, on_change=Playground.set_amplitude.throttle(100)),
                    width="100%", align="center",
                ),
                rx.box(rb.aurora(color_stops=Playground.aurora_stops, amplitude=Playground.amplitude, blend=0.5),
                       height="220px", width="100%", position="relative", border_radius="12px", overflow="hidden", background="#060010"),
            ),
            panel(
                "Hyperspeed presets",
                rx.select(["one", "two", "three", "four", "five", "six"], value=Playground.preset, on_change=Playground.set_preset),
                rx.box(
                    rx.match(
                        Playground.preset,
                        *[(p, rb.hyperspeed(preset=p, key=p)) for p in ("one", "two", "three", "four", "five", "six")],
                        rb.hyperspeed(preset="one"),
                    ),
                    height="220px", width="100%", position="relative", border_radius="12px", overflow="hidden",
                ),
                description="Click and hold inside to speed up.",
            ),
            panel(
                "Micro interactions → state",
                rx.hstack(rb.squish_switch(on_change=Playground.on_switch), rx.text("switch: ", rx.code(Playground.switch_on.to_string())), align="center", spacing="4"),
                rx.hstack(rb.peek_rating(default_value=3, on_change=Playground.on_rating), rx.text("rating: ", rx.code(Playground.rating)), align="center", spacing="4"),
                rx.hstack(
                    rb.rubber_segment(items=[{"value": "day", "label": "Day"}, {"value": "week", "label": "Week"}, {"value": "month", "label": "Month"}],
                                      default_value="week", on_change=Playground.on_segment),
                    rx.text("segment: ", rx.code(Playground.segment)), align="center", spacing="4",
                ),
                rx.hstack(rb.pulse_heart(default_liked=False, count=128, on_change=Playground.on_like),
                          rx.text("liked: ", rx.code(Playground.liked.to_string()), " · likes: ", rx.code(Playground.likes)), align="center", spacing="4"),
                rx.hstack(rb.hold_button("Hold to confirm", on_hold=Playground.on_hold), align="center"),
            ),
            panel(
                "Inputs → state",
                rb.code_slots(length=6, on_change=Playground.on_code, on_complete=Playground.on_code_complete),
                rx.text("code: ", rx.code(Playground.code)),
                rb.comet_dial(default_value=40, on_change=Playground.on_dial.throttle(150)),
                rx.text("dial: ", rx.code(Playground.dial)),
                rb.slide_commit(label="Slide to confirm", on_confirm=Playground.on_slide_confirm),
            ),
            panel(
                "Stepper events",
                rb.stepper(
                    rb.step(rx.heading("Step 1", size="4"), rx.text("Events go to the Reflex backend.")),
                    rb.step(rx.heading("Step 2", size="4"), rx.text("Current step is stored in state.")),
                    rb.step(rx.heading("Done", size="4"), rx.text("Press Complete to fire on_final_step_completed.")),
                    initial_step=1,
                    on_step_change=Playground.on_step,
                    on_final_step_completed=Playground.on_finish,
                ),
                rx.text("step: ", rx.code(Playground.step), " · finished: ", rx.code(Playground.finished.to_string())),
            ),
            columns=rx.breakpoints(initial="1", lg="2"),
            spacing="4",
            width="100%",
        ),
    )


# ---------------------------------------------------------------------------
# Category and component pages

def component_card(entry: dict) -> rx.Component:
    return rx.link(
        rx.card(
            rx.vstack(
                rx.hstack(rx.heading(entry["name"], size="4"), rx.spacer(), rx.code(f"rb.{entry['factory']}()", size="1"), width="100%", align="center"),
                rx.text(entry["description"], size="2", color=rx.color("gray", 11)),
                spacing="2",
            ),
            height="100%",
            _hover={"border_color": rx.color("violet", 8)},
        ),
        href=f"/c/{slug(entry)}",
        underline="none",
        color=rx.color("gray", 12),
    )


def category_page(cat: str):
    _slug, title, _icon = CATEGORY_INFO[cat]
    items = sorted((e for e in ENTRIES if e["category"] == cat), key=lambda e: e["name"])

    def page() -> rx.Component:
        return layout(
            rx.heading(title, size="8"),
            rx.text(f"{len(items)} components", color=rx.color("gray", 10), margin_bottom="1em"),
            rx.grid(*[component_card(e) for e in items], columns=rx.breakpoints(initial="1", sm="2", lg="3"), spacing="3", width="100%"),
        )

    return page


def props_table(entry: dict) -> rx.Component:
    rows = [
        rx.table.row(
            rx.table.cell(rx.code(p["name"])),
            rx.table.cell(rx.text("event(" + ", ".join(p.get("args") or []) + ")" if p["type"] == "event" else p["type"], size="1")),
            rx.table.cell(rx.text(p.get("default") or "", size="1")),
            rx.table.cell(rx.text(p.get("description") or "", size="1")),
        )
        for p in entry["props"]
    ]
    return rx.table.root(
        rx.table.header(rx.table.row(*[rx.table.column_header_cell(h) for h in ("Prop", "Type", "Default", "Description")])),
        rx.table.body(*rows),
        size="1",
        variant="surface",
        width="100%",
    )


def component_page(entry: dict):
    subs = [e for e in rb.CATALOG if e.get("sub") and e["name"] == entry["name"]]

    def page() -> rx.Component:
        return layout(
            rx.hstack(
                rx.heading(entry["name"], size="8"),
                rx.badge(CATEGORY_INFO[entry["category"]][1], color_scheme="violet"),
                align="center",
                spacing="3",
            ),
            rx.text(entry["description"], color=rx.color("gray", 11), margin_y="0.5em"),
            rx.hstack(
                rx.code(f"rb.{entry['factory']}()"),
                *[rx.code(f"rb.{s['factory']}()") for s in subs],
                *[rx.badge(d, variant="outline", color_scheme="gray") for d in entry["npm"]],
                rx.link(rx.hstack(rx.text("React Bits docs"), rx.icon("external-link", size=14), align="center", spacing="1"),
                        href=entry["docs_url"], is_external=True, size="2"),
                wrap="wrap",
                spacing="2",
                align="center",
            ),
            rx.tabs.root(
                rx.tabs.list(rx.tabs.trigger("Preview", value="preview"), rx.tabs.trigger("Python", value="code"), rx.tabs.trigger("Props", value="props")),
                rx.tabs.content(
                    rx.vstack(
                        rx.box(
                            rx.fragment(build_preview(entry), key=EventLog.replay.to_string()),
                            rx.icon_button(rx.icon("rotate-ccw", size=16), on_click=EventLog.replay_preview, variant="soft",
                                           position="absolute", top="12px", right="12px", z_index="20", title="Replay"),
                            class_name="preview-box preview-" + entry["category"].lower(),
                            height=preview_height(entry),
                        ),
                        rx.card(
                            rx.hstack(rx.icon("activity", size=16), rx.text("Event log", weight="bold"), rx.spacer(),
                                      rx.button("Clear", size="1", variant="ghost", on_click=EventLog.clear), width="100%", align="center"),
                            rx.cond(
                                EventLog.entries.length() > 0,
                                rx.vstack(
                                    rx.foreach(EventLog.entries, lambda e: rx.hstack(
                                        rx.text(e["time"], size="1", color=rx.color("gray", 9)),
                                        rx.code(e["name"], size="1"),
                                        rx.text(e["payload"], size="1", font_family="monospace"),
                                        spacing="2",
                                    )),
                                    spacing="1",
                                    max_height="160px",
                                    overflow_y="auto",
                                    margin_top="0.5em",
                                ),
                                rx.text(
                                    "Interact with the component: its events are handled by a Reflex event handler and listed here."
                                    if any(p["type"] == "event" for p in entry["props"])
                                    else "This component exposes no callbacks.",
                                    size="1", color=rx.color("gray", 9), margin_top="0.5em",
                                ),
                            ),
                            width="100%",
                        ),
                        spacing="3",
                        width="100%",
                        padding_top="1em",
                    ),
                    value="preview",
                ),
                rx.tabs.content(rx.box(rx.code_block(python_source(entry), language="python", show_line_numbers=False, width="100%"), padding_top="1em"), value="code"),
                rx.tabs.content(rx.box(props_table(entry), padding_top="1em", overflow_x="auto"), value="props"),
                default_value="preview",
                margin_top="1em",
                width="100%",
            ),
        )

    return page


app = rx.App(stylesheets=["/demo.css"])
app.add_page(index, title="React Bits for Reflex")
app.add_page(playground, route="/playground", title="Playground · React Bits for Reflex")
for _cat, (_slug, _title, _icon) in CATEGORY_INFO.items():
    app.add_page(category_page(_cat), route=f"/category/{_slug}", title=f"{_title} · React Bits for Reflex")
for _entry in ENTRIES:
    app.add_page(component_page(_entry), route=f"/c/{slug(_entry)}", title=f"{_entry['name']} · React Bits for Reflex",
                 on_load=EventLog.reset_page)
