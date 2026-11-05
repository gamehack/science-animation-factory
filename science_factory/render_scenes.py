"""Trusted Manim visual vocabulary (never executes model-authored Python).

Manim imports this module in a separate render process. The only outside input
is a schema-validated JSON plan whose location is passed through the environment.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
from manim import *  # noqa: F403 - Manim's animation vocabulary


config.frame_width = 8
config.frame_height = 8 * 16 / 9

BACKGROUND = "#101827"
ACCENT = "#45D6E8"
HIGHLIGHT = "#F7BE4F"
TEXT = "#F4F7FA"
MUTED = "#98A8BB"


def _label(value: str, *, size: int = 28, width: float = 3.1):
    is_cjk = any("\u3400" <= character <= "\u9fff" for character in value)
    font = "Noto Sans CJK SC" if is_cjk else "DejaVu Sans"
    result = Text(value, font=font, font_size=size, color=TEXT)
    return result.scale_to_fit_width(min(width, result.width)) if result.width > width else result


def _orbit(params: dict):
    path = Circle(radius=2.05, color=MUTED, stroke_width=2).shift(UP * 0.5)
    planet = Circle(radius=0.85, color="#3484B8", fill_opacity=1).move_to(path.get_center())
    moon = Dot(path.point_from_proportion(0), radius=0.22, color=HIGHLIGHT)
    arrow = Arrow(path.get_center() + RIGHT * 1.8, path.get_center() + RIGHT * 1.0,
                  color=ACCENT, buff=0, stroke_width=5)
    names = VGroup(_label(params.get("center", "Earth")), _label(params.get("object", "Moon")))
    names[0].next_to(planet, DOWN, buff=0.3)
    names[1].next_to(moon, RIGHT, buff=0.3)
    return VGroup(path, planet, moon, arrow, names), MoveAlongPath(moon, path)


def _comparison(params: dict):
    left = RoundedRectangle(width=3.5, height=4.0, corner_radius=0.2, color=ACCENT)
    right = RoundedRectangle(width=3.5, height=4.0, corner_radius=0.2, color=HIGHLIGHT)
    left.move_to(LEFT * 1.9 + UP * 0.4)
    right.move_to(RIGHT * 1.9 + UP * 0.4)
    left_label = _label(params.get("left", "Before"), size=27).move_to(left)
    right_label = _label(params.get("right", "After"), size=27).move_to(right)
    left_card = VGroup(left, left_label)
    right_card = VGroup(right, right_label)
    return VGroup(left_card, right_card), LaggedStart(FadeIn(left_card, shift=UP * 0.3),
                                                      FadeIn(right_card, shift=UP * 0.3), lag_ratio=0.4)


def _wave(params: dict):
    baseline = Line(LEFT * 3.5, RIGHT * 3.5, color=MUTED).shift(UP * 0.2)
    curve = FunctionGraph(lambda x: math.sin(2.3 * x), x_range=[-3.3, 3.3, 0.03],
                          color=ACCENT, stroke_width=6).shift(UP * 0.2)
    caption = _label(params.get("note", "A repeating pattern"), size=26, width=6.0)
    caption.next_to(baseline, DOWN, buff=1.3)
    return VGroup(baseline, curve, caption), Create(curve)


def _force(params: dict):
    obj = Square(side_length=1.5, color=HIGHLIGHT, fill_opacity=0.2).shift(UP * 0.3)
    # This M1 force card depicts a falling body near Earth: gravity is down.
    arrow = Arrow(obj.get_center(), obj.get_center() + DOWN * 2.0, color=ACCENT, buff=0.2)
    label = _label(params.get("direction", "Force"), size=28, width=5.0)
    label.next_to(arrow, DOWN)
    return VGroup(obj, arrow, label), GrowArrow(arrow)


def _scale(params: dict):
    large = Circle(radius=1.45, color=ACCENT, fill_opacity=0.24).shift(LEFT * 1.8 + UP * 0.4)
    small = Circle(radius=0.6, color=HIGHLIGHT, fill_opacity=0.24).shift(RIGHT * 2 + UP * 0.4)
    left_label = _label(params.get("left", "Large"), size=26).next_to(large, DOWN, buff=0.5)
    right_label = _label(params.get("right", "Small"), size=26).next_to(small, DOWN, buff=0.5)
    group = VGroup(large, small, left_label, right_label)
    return group, LaggedStart(GrowFromCenter(large), GrowFromCenter(small), lag_ratio=0.3)


def _particles(params: dict):
    dots = VGroup(*[Dot(LEFT * (2.6 + (i % 3) * 0.2) + UP * (i * 0.47 - 1.1),
                        radius=0.11, color=ACCENT) for i in range(7)])
    paths = [Line(dot.get_center(), dot.get_center() + RIGHT * 5.0) for dot in dots]
    label = _label(params.get("note", "Particles in motion"), width=6.0)
    label.move_to(DOWN * 2.1)
    return VGroup(dots, label), AnimationGroup(*[MoveAlongPath(dot, path) for dot, path in zip(dots, paths)])


BUILDER = {
    "orbit": _orbit,
    "comparison": _comparison,
    "wave": _wave,
    "force": _force,
    "scale": _scale,
    "particles": _particles,
}


class ScienceShort(Scene):
    """Single-pass video render with the same durations used for audio offsets."""

    def construct(self):
        plan_path = os.environ.get("SCIENCE_FACTORY_PLAN")
        if not plan_path:
            raise RuntimeError("SCIENCE_FACTORY_PLAN must refer to a validated render plan")
        plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
        self.camera.background_color = BACKGROUND
        for scene in plan["scenes"]:
            duration = scene["duration"]
            title = _label(scene["title"], size=43, width=7.0).to_edge(UP, buff=1.05)
            elements, movement = BUILDER[scene["kind"]](scene["params"])
            # Each stage consumes exactly the precomputed duration. No implicit
            # waits based on narration length or video encoding performance.
            self.add(elements)
            self.play(FadeIn(title), run_time=0.45)
            self.play(movement, run_time=duration - 0.9)
            self.play(*[FadeOut(obj) for obj in list(self.mobjects)], run_time=0.45)

