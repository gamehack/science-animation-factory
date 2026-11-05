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

from science_factory.visuals.celestial_body import earth as make_earth
from science_factory.visuals.celestial_body import moon as make_moon
from science_factory.visuals.orbit_math import inward_arrow


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
    path = Circle(radius=2.05, color=MUTED, stroke_width=2,
                  stroke_opacity=0.65).shift(UP * 0.5)
    planet = make_earth().move_to(path.get_center())
    satellite = make_moon().move_to(path.point_from_proportion(0))

    def gravity_arrow():
        # Earth always pulls the Moon toward Earth's CENTER, regardless of
        # the Moon's position on the orbit. Unlike the old static arrow, this
        # direction updates continuously while the satellite moves.
        # Extend to the rim of Earth so the force remains legible on phones.
        start, end = inward_arrow(planet.get_center(), satellite.get_center(), length=0.85)
        return Arrow(start, end, color=ACCENT, buff=0,
                     stroke_width=4.5, tip_length=0.14)

    pull = always_redraw(gravity_arrow)
    earth_name = _label(params.get("center", "Earth")).next_to(planet, DOWN, buff=0.24)
    moon_name = _label(params.get("object", "Moon"))
    moon_name.add_updater(lambda label: label.next_to(satellite, RIGHT, buff=0.22))
    moon_name.update()
    # Tiny fixed stars add depth without distracting from the science diagram.
    positions = [(-3.0, 2.7), (-2.3, -2.0), (-0.1, 3.1), (2.65, -2.4),
                 (3.05, 2.1), (-3.2, -0.1), (0.4, -3.0), (1.45, 3.0)]
    stars = VGroup(*[Dot(np.array([x, y, 0]), radius=0.025, color="#7896AA",
                        fill_opacity=0.37) for x, y in positions])
    return Group(stars, path, planet, satellite, pull, earth_name, moon_name), MoveAlongPath(satellite, path)


def _orbit_intro(params: dict):
    """A close tracking shot, distinct from the later explanatory orbit."""
    center = LEFT * 1.25 + DOWN * 0.32
    earth = make_earth(radius=1.33).move_to(center)
    path = Arc(radius=2.38, start_angle=17 * DEGREES,
               angle=154 * DEGREES, arc_center=center,
               color=HIGHLIGHT, stroke_width=4, stroke_opacity=0.50)
    moon = make_moon(radius=0.30).move_to(path.get_start())
    gravity = always_redraw(lambda: Arrow(
        *inward_arrow(earth.get_center(), moon.get_center(), length=1.08),
        buff=0, color=ACCENT, stroke_width=5, tip_length=0.16))
    return Group(path, earth, moon, gravity), MoveAlongPath(moon, path)


def _orbit_recap(params: dict):
    """Leave a bright partial trail to emphasize *continuous* free fall."""
    center = UP * 0.45
    path = Circle(radius=2.04, color=MUTED, stroke_width=2,
                  stroke_opacity=0.42).move_to(center)
    earth = make_earth(radius=0.82).move_to(center)
    moon = make_moon(radius=0.27).move_to(path.point_from_proportion(0))
    trace = TracedPath(moon.get_center, stroke_color=HIGHLIGHT,
                       stroke_width=5, dissipating_time=3.2)
    idea = _label(params.get("note", "Always falling, never hitting"),
                  size=26, width=6.6).move_to(DOWN * 2.12)
    return Group(path, trace, earth, moon, idea), MoveAlongPath(moon, path)


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


def _physics_vectors(params: dict):
    """Show centripetal gravity and tangential velocity on one orbital diagram.

    This is a trusted, declarative visual primitive; caller-supplied strings
    only label the two arrows and never become executable drawing code.
    """
    # Keep the diagram above the caption zone used by portrait-video players.
    center = LEFT * 1.1 + UP * 0.62
    planet = make_earth(radius=0.76).move_to(center)
    satellite = make_moon(radius=0.27).move_to(center + RIGHT * 2.05)
    orbit = Circle(radius=2.05, color=MUTED, stroke_width=2,
                   stroke_opacity=0.36).move_to(center)
    gravity = Arrow(satellite.get_center() + LEFT * 0.31,
                    satellite.get_center() + LEFT * 1.28,
                    buff=0, color=ACCENT, stroke_width=6, tip_length=0.19)
    tangent = Arrow(satellite.get_center() + UP * 0.32,
                    satellite.get_center() + UP * 1.72,
                    buff=0, color=HIGHLIGHT, stroke_width=6, tip_length=0.19)
    inward_label = _label(params.get("left", "Gravity: inward"), size=25, width=3.6)
    sideways_label = _label(params.get("right", "Velocity: tangent"), size=25, width=3.6)
    inward_label.move_to(LEFT * 1.8 + DOWN * 1.85)
    sideways_label.move_to(RIGHT * 1.75 + DOWN * 1.85)
    drawing = Group(orbit, planet, satellite, gravity, tangent,
                    inward_label, sideways_label)
    return drawing, LaggedStart(GrowArrow(gravity), GrowArrow(tangent), lag_ratio=0.46)


def _throw_orbit(params: dict):
    """Contrast a short falling trajectory with continued orbital free fall."""
    left_center = LEFT * 1.95 + UP * 0.25
    right_center = RIGHT * 1.95 + UP * 0.25
    slow_earth = make_earth(radius=0.58).move_to(left_center)
    fast_earth = make_earth(radius=0.58).move_to(right_center)
    slow_start = left_center + UP * 0.79
    slow_end = left_center + RIGHT * 0.52 + UP * 0.20
    slow_path = CubicBezier(slow_start, slow_start + RIGHT * 0.6 + UP * 0.54,
                            slow_end + RIGHT * 0.6 + UP * 0.66, slow_end,
                            color=ACCENT, stroke_width=4)
    fast_path = Circle(radius=1.16, color=HIGHLIGHT, stroke_width=4,
                       stroke_opacity=0.9).move_to(right_center)
    slow_ball = Dot(slow_start, radius=0.105, color=ACCENT)
    fast_ball = Dot(fast_path.point_from_proportion(0.25), radius=0.105,
                    color=HIGHLIGHT)
    slow_label = _label(params.get("left", "Slow: lands"), size=25, width=3.5)
    fast_label = _label(params.get("right", "Fast: orbit"), size=25, width=3.5)
    slow_label.move_to(LEFT * 1.95 + DOWN * 1.82)
    fast_label.move_to(RIGHT * 1.95 + DOWN * 1.82)
    drawing = Group(slow_path, fast_path, slow_earth, fast_earth,
                    slow_ball, fast_ball, slow_label, fast_label)
    motion = AnimationGroup(MoveAlongPath(slow_ball, slow_path),
                            MoveAlongPath(fast_ball, fast_path), lag_ratio=0)
    return drawing, motion


def _wave(params: dict):
    baseline = Line(LEFT * 3.5, RIGHT * 3.5, color=MUTED).shift(UP * 0.2)
    curve = FunctionGraph(lambda x: math.sin(2.3 * x), x_range=[-3.3, 3.3, 0.03],
                          color=ACCENT, stroke_width=6).shift(UP * 0.2)
    caption = _label(params.get("note", "A repeating pattern"), size=26, width=6.0)
    caption.next_to(baseline, DOWN, buff=1.3)
    return VGroup(baseline, curve, caption), Create(curve)


def _force(params: dict):
    # Show the same gravity concept with the real celestial imagery used by the
    # orbit scenes, replacing the unrelated square/ground diagram from M1.
    planet = make_earth(radius=0.98).move_to(LEFT * 1.45 + UP * 0.2)
    satellite = make_moon(radius=0.34).move_to(RIGHT * 1.65 + UP * 0.2)
    arrow = Arrow(satellite.get_center() + LEFT * 0.41,
                  planet.get_center() + RIGHT * 1.08,
                  color=ACCENT, buff=0, stroke_width=7, tip_length=0.21)
    label = _label(params.get("direction", "Gravitational pull"), size=28, width=6)
    label.move_to(DOWN * 2.0)
    return Group(planet, satellite, arrow, label), GrowArrow(arrow)


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


def _speaker(x: float = -2.8):
    box = RoundedRectangle(width=0.64, height=1.3, corner_radius=0.13,
                           color=ACCENT, fill_color="#1E455C", fill_opacity=0.95)
    box.move_to(np.array([x - 0.24, 0.55, 0]))
    cone = Polygon(np.array([x, 0.86, 0]), np.array([x + 0.77, 1.25, 0]),
                   np.array([x + 0.77, -0.15, 0]), np.array([x, 0.25, 0]),
                   color=ACCENT, fill_color="#27627E", fill_opacity=0.95)
    return VGroup(box, cone)


def _sound_source(params: dict):
    speaker = _speaker()
    waves = VGroup(*[
        Arc(radius=r, start_angle=-62 * DEGREES, angle=124 * DEGREES,
            arc_center=LEFT * 2.0 + UP * 0.55, color=HIGHLIGHT,
            stroke_width=5, stroke_opacity=1 - i * 0.16)
        for i, r in enumerate((0.85, 1.55, 2.28, 3.0))
    ])
    label = _label(params.get("note", "Vibrations spread through air"),
                   size=27, width=6.3).move_to(DOWN * 2.15)
    return VGroup(speaker, waves, label), LaggedStart(
        *[Create(wave) for wave in waves], lag_ratio=0.25)


def _sound_medium(params: dict):
    """Dots transfer a longitudinal displacement, without bulk matter flow."""
    dots = VGroup()
    for i in range(9):
        for j in (-1, 0, 1):
            dots.add(Dot(np.array([-3 + i * 0.74, j * 0.61 + 0.55, 0]),
                         radius=0.078, color=ACCENT))
    arrow = Arrow(LEFT * 2.9 + DOWN * 0.75, RIGHT * 2.9 + DOWN * 0.75,
                  color=HIGHLIGHT, stroke_width=5, buff=0)
    label = _label(params.get("note", "Energy moves, particles vibrate"),
                   size=27, width=6.6).move_to(DOWN * 2.20)
    motions = [dots[i].animate.shift(RIGHT * (0.22 if (i // 3) % 2 == 0 else -0.16))
               for i in range(len(dots))]
    return VGroup(dots, arrow, label), LaggedStart(*motions, lag_ratio=0.10)


def _sound_vacuum(params: dict):
    """Air has transmitting particles; empty space has none."""
    air = VGroup(*[Dot(np.array([-3.35 + i * 0.48, 0.25 + j * 0.55, 0]),
                       radius=0.072, color=ACCENT)
                   for i in range(7) for j in (-1, 0, 1)])
    border = DashedLine(UP * 1.90, DOWN * 1.30, color=MUTED, dash_length=0.15)
    air_label = _label(params.get("left", "Air"), size=29, width=3).move_to(LEFT * 1.9 + DOWN * 1.65)
    empty_label = _label(params.get("right", "Vacuum"), size=29, width=3).move_to(RIGHT * 1.9 + DOWN * 1.65)
    wave = Arc(radius=0.83, start_angle=-65 * DEGREES,
               angle=130 * DEGREES, arc_center=LEFT * 1.45 + UP * 0.25,
               stroke_width=6, color=HIGHLIGHT)
    blocked = VGroup(Line(RIGHT * 1.30 + UP * 0.95, RIGHT * 2.35 + DOWN * 0.15,
                          color="#F07575", stroke_width=7),
                     Line(RIGHT * 2.35 + UP * 0.95, RIGHT * 1.30 + DOWN * 0.15,
                          color="#F07575", stroke_width=7))
    return (VGroup(air, border, wave, blocked, air_label, empty_label),
            LaggedStart(Create(wave), FadeIn(blocked), lag_ratio=0.55))


def _sound_receiver(params: dict):
    speaker = _speaker(-3.15)
    listener = Circle(radius=0.55, color=HIGHLIGHT,
                      fill_color="#4D4937", fill_opacity=0.50).move_to(RIGHT * 2.8 + UP * 0.55)
    dots = VGroup(*[Dot(np.array([-1.7 + i * 0.45, 0.55, 0]),
                       radius=0.065, color=ACCENT) for i in range(9)])
    signal = Dot(LEFT * 1.85 + UP * 0.55, radius=0.16, color=HIGHLIGHT)
    route = Line(LEFT * 1.85 + UP * 0.55, RIGHT * 2.05 + UP * 0.55)
    label = _label(params.get("note", "Sound reaches a listener through matter"),
                   size=26, width=6.8).move_to(DOWN * 2.15)
    return VGroup(speaker, dots, signal, listener, label), MoveAlongPath(signal, route)


def _sound_recap(params: dict):
    air = VGroup(*[Dot(np.array([-2.7 + i * 0.54, 0.55, 0]), radius=0.07,
                       color=ACCENT) for i in range(6)])
    waves = VGroup(*[Arc(radius=r, start_angle=-70 * DEGREES,
                         angle=140 * DEGREES, arc_center=LEFT * 2.7 + UP * 0.55,
                         color=HIGHLIGHT, stroke_width=5) for r in (0.65, 1.2, 1.85)])
    dividing = DashedLine(UP * 2.0, DOWN * 1.4, color=MUTED)
    cross = Cross(Circle(radius=0.43).move_to(RIGHT * 2 + UP * 0.55),
                  stroke_color="#F07575", stroke_width=8)
    label = _label(params.get("note", "No particles, no sound"),
                   size=30, width=6.7).move_to(DOWN * 2.12)
    return VGroup(air, waves, dividing, cross, label), LaggedStart(
        *[Create(w) for w in waves], FadeIn(cross), lag_ratio=0.21)


BUILDER = {
    "orbit": _orbit,
    "orbit_intro": _orbit_intro,
    "orbit_recap": _orbit_recap,
    "comparison": _comparison,
    "physics_vectors": _physics_vectors,
    "throw_orbit": _throw_orbit,
    "wave": _wave,
    "force": _force,
    "scale": _scale,
    "particles": _particles,
    "sound_source": _sound_source,
    "sound_medium": _sound_medium,
    "sound_vacuum": _sound_vacuum,
    "sound_receiver": _sound_receiver,
    "sound_recap": _sound_recap,
}


class ScienceShort(MovingCameraScene):
    """Single-pass video render with the same durations used for audio offsets."""

    def construct(self):
        plan_path = os.environ.get("SCIENCE_FACTORY_PLAN")
        if not plan_path:
            raise RuntimeError("SCIENCE_FACTORY_PLAN must refer to a validated render plan")
        plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
        self.camera.background_color = BACKGROUND
        for index, scene in enumerate(plan["scenes"]):
            duration = scene["duration"]
            title = _label(scene["title"], size=43, width=7.0).to_edge(UP, buff=1.05)
            underline = Line(LEFT * 0.65, RIGHT * 0.65, color=ACCENT,
                             stroke_width=2.8).next_to(title, DOWN, buff=0.30)
            elements, movement = BUILDER[scene["kind"]](scene["params"])
            # Each stage consumes exactly the precomputed duration. No implicit
            # waits based on narration length or video encoding performance.
            self.camera.frame.save_state()
            self.add(elements)
            self.play(FadeIn(title), Create(underline), run_time=0.45)
            # Slow, bounded 2.5D camera drift gives each scene parallax without
            # hard-coded cuts, GPU rendering or external generative-video APIs.
            drift = RIGHT * (0.10 if index % 2 == 0 else -0.10) + UP * 0.055
            camera_move = self.camera.frame.animate.scale(0.955).shift(drift)
            self.play(movement, camera_move, run_time=duration - 0.9,
                      rate_func=linear)
            fades = [FadeOut(obj) for obj in list(self.mobjects)
                     if obj is not self.camera.frame]
            self.play(*fades, Restore(self.camera.frame), run_time=0.45)

