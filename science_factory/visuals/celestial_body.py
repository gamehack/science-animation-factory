"""NASA-image-based 2.5D celestial discs for the safe Manim scene vocabulary.

Assets are verified and committed once; video rendering never fetches images.
Only trusted, static asset filenames are accepted here.
"""

from pathlib import Path

from manim import Circle, Group, ImageMobject


ASSETS = Path(__file__).resolve().parents[1] / "assets"


def earth(radius: float = 0.85) -> Group:
    asset = ASSETS / "earth_disc.png"
    if not asset.is_file():
        raise FileNotFoundError(f"verified NASA Earth disc missing: {asset}")
    disk = ImageMobject(str(asset)).set_width(2 * radius)
    # Three subtle rings approximate atmospheric scattering without a GPU.
    glow = Group(
        Circle(radius=radius * 1.04, stroke_color="#71BEF8",
               stroke_width=12, stroke_opacity=0.17),
        Circle(radius=radius * 1.10, stroke_color="#54A3E8",
               stroke_width=13, stroke_opacity=0.08),
        Circle(radius=radius * 1.17, stroke_color="#2C79C9",
               stroke_width=16, stroke_opacity=0.045),
    )
    return Group(glow, disk)


def moon(radius: float = 0.29) -> Group:
    asset = ASSETS / "moon_disc.png"
    if not asset.is_file():
        raise FileNotFoundError(f"verified NASA Moon disc missing: {asset}")
    disk = ImageMobject(str(asset)).set_width(2 * radius)
    rim = Circle(radius=radius * 1.018, stroke_color="#D3D5D7",
                 stroke_width=1.4, stroke_opacity=0.45)
    return Group(rim, disk)
