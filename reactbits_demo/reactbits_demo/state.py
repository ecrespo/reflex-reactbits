"""Demo app state: event log, replay counter, sidebar filter and playground values."""

from __future__ import annotations

import contextlib
import datetime
import json
from typing import Any

import reflex as rx


class EventLog(rx.State):
    """Collects the events fired by the component being previewed."""

    entries: list[dict[str, str]] = []
    replay: int = 0

    @rx.event
    def log(self, name: str, payload: list[Any]):
        """Store one event (newest first, 30 max)."""
        text = json.dumps(payload, default=str)
        self.entries = [
            {
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
                "name": name,
                "payload": text if len(text) < 160 else text[:157] + "...",
            },
            *self.entries,
        ][:30]

    @rx.event
    def clear(self):
        """Clear the log."""
        self.entries = []

    @rx.event
    def replay_preview(self):
        """Remount the preview so entrance animations play again."""
        self.replay += 1

    @rx.event
    def reset_page(self):
        """Reset the log when navigating to another component page."""
        self.entries = []
        self.replay = 0


class Nav(rx.State):
    """Sidebar search."""

    query: str = ""

    @rx.event
    def set_query(self, value: str):
        self.query = value


class Playground(rx.State):
    """Values bound to the interactive playground."""

    headline: str = "Reflex + React Bits"
    animate_by: str = "words"
    direction: str = "top"
    count_to: int = 2026
    aurora_a: str = "#5227FF"
    aurora_b: str = "#7cff67"
    aurora_c: str = "#5227FF"
    amplitude: float = 1.0
    preset: str = "one"
    switch_on: bool = False
    rating: int = 3
    segment: str = "week"
    liked: bool = False
    likes: int = 128
    step: int = 1
    finished: bool = False
    dial: float = 40
    code: str = ""
    toasts: list[str] = []

    @rx.event
    def set_headline(self, value: str):
        self.headline = value

    @rx.event
    def set_animate_by(self, value: str):
        self.animate_by = value

    @rx.event
    def set_direction(self, value: str):
        self.direction = value

    @rx.event
    def set_count_to(self, value: list[int | float]):
        self.count_to = int(value[0])

    @rx.event
    def set_aurora_a(self, value: str):
        self.aurora_a = value

    @rx.event
    def set_aurora_b(self, value: str):
        self.aurora_b = value

    @rx.event
    def set_aurora_c(self, value: str):
        self.aurora_c = value

    @rx.event
    def set_amplitude(self, value: list[int | float]):
        self.amplitude = float(value[0])

    @rx.event
    def set_preset(self, value: str):
        self.preset = value

    @rx.event
    def on_switch(self, value: bool):
        self.switch_on = bool(value)

    @rx.event
    def on_rating(self, value: int | None):
        self.rating = int(value or 0)

    @rx.event
    def on_segment(self, value: str, index: int):
        self.segment = value

    @rx.event
    def on_like(self, liked: bool, count: int):
        self.liked = bool(liked)
        self.likes = int(count)

    @rx.event
    def on_step(self, step: int):
        self.step = int(step)
        self.finished = False

    @rx.event
    def on_finish(self):
        self.finished = True
        return rx.toast.success("Stepper finished - handled by a Reflex event!")

    @rx.event
    def on_dial(self, value: float):
        self.dial = round(float(value), 1)

    @rx.event
    def on_code(self, code: str):
        self.code = code

    @rx.event
    def on_code_complete(self, code: str):
        self.code = code
        return rx.toast.info(f"Code complete: {code}")

    @rx.event
    def on_blur_done(self):
        return rx.toast("BlurText animation finished")

    @rx.event
    def on_hold(self):
        return rx.toast.success("Hold confirmed on the backend")

    @rx.event
    def on_slide_confirm(self):
        return rx.toast.success("SlideCommit confirmed")

    @rx.event
    def set_count_to_text(self, value: str):
        with contextlib.suppress(ValueError):
            self.count_to = int(value)

    @rx.var
    def aurora_stops(self) -> list[str]:
        return [self.aurora_a, self.aurora_b, self.aurora_c]
