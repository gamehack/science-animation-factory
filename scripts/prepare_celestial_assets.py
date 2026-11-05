"""One-time asset preparation from NASA's official public GitHub repository.

The generated transparent discs are committed to science_factory/assets/ after
visual review. Normal video renders never download images from the network.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
from PIL import Image


NASA_ASSETS = {
    "earth": {
        "url": "https://raw.githubusercontent.com/nasa/NASA-3D-Resources/master/Images%20and%20Textures/Earth%20(A)/Earth%20(A).jpg",
        "blob_sha1": "6adcb9237e3240b804bc4b932aadd8a08635054d",
        "center_longitude": -25.0,
    },
    "moon": {
        "url": "https://raw.githubusercontent.com/nasa/NASA-3D-Resources/master/Images%20and%20Textures/Moon/Moon.jpg",
        "blob_sha1": "e39f899b3f37e39c75acbe405018157dcfba8b0b",
        "center_longitude": 0.0,
    },
}


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def _download(source: dict[str, str]) -> bytes:
    request = Request(source["url"], headers={"User-Agent": "science-animation-factory/1.1"})
    with urlopen(request, timeout=40) as response:
        data = response.read(12_000_001)
    if len(data) > 12_000_000:
        raise ValueError("NASA texture exceeds the bounded download size")
    if git_blob_sha1(data) != source["blob_sha1"]:
        raise ValueError("NASA source bytes changed; verify the upstream license and asset")
    return data


def orthographic_disc(texture: Image.Image, *, longitude_deg: float,
                      size: int = 512) -> Image.Image:
    """Project equirectangular satellite imagery onto a lit transparent disc."""
    texture = texture.convert("RGB")
    width, height = texture.size
    if not 1.75 <= width / height <= 2.25:
        raise ValueError(f"expected 2:1 equirectangular map; got {width}x{height}")
    pixels = np.asarray(texture, dtype=np.float32)
    coords = (np.arange(size, dtype=np.float64) + 0.5) / size * 2 - 1
    x, y = np.meshgrid(coords, coords)
    radius_squared = x * x + y * y
    z = np.sqrt(np.maximum(0, 1 - radius_squared))
    longitude = np.deg2rad(longitude_deg) + np.arctan2(x, z)
    latitude = np.arcsin(np.clip(-y, -1, 1))
    horizontal = ((longitude / (2 * math.pi) + 0.5) % 1) * width
    vertical = np.clip((0.5 - latitude / math.pi) * height, 0, height - 1)
    x0 = np.floor(horizontal).astype(int) % width
    x1 = (x0 + 1) % width
    y0 = np.floor(vertical).astype(int)
    y1 = np.minimum(y0 + 1, height - 1)
    fx = (horizontal - np.floor(horizontal))[..., None]
    fy = (vertical - np.floor(vertical))[..., None]
    color = ((pixels[y0, x0] * (1 - fx) + pixels[y0, x1] * fx) * (1 - fy)
             + (pixels[y1, x0] * (1 - fx) + pixels[y1, x1] * fx) * fy)

    # Light from above-left. A nonzero ambient term reveals the night-side edge
    # without requiring heavy real-time 3D lighting or a GPU in GitHub Actions.
    light = np.array([-0.48, -0.35, 0.80], dtype=np.float64)
    light /= np.linalg.norm(light)
    lambert = np.maximum(0, x * light[0] + y * light[1] + z * light[2])
    shade = 0.23 + 0.87 * lambert
    color = np.clip(color * shade[..., None], 0, 255).astype(np.uint8)
    # 1.5px anti-alias along the rim; outside the disc remains fully transparent.
    edge = 1.5 / size * 2
    alpha = np.clip((1 - np.sqrt(radius_squared)) / edge, 0, 1)
    rgba = np.dstack((color, np.round(alpha * 255).astype(np.uint8)))
    return Image.fromarray(rgba, mode="RGBA")


def build(output: Path, *, size: int = 512) -> None:
    output.mkdir(parents=True, exist_ok=True)
    provenance = {}
    discs = {}
    for name, source in NASA_ASSETS.items():
        data = _download(source)
        # The binary format is restricted to JPEG, and Pillow decodes it locally.
        from io import BytesIO
        texture = Image.open(BytesIO(data))
        disc = orthographic_disc(texture, longitude_deg=source["center_longitude"], size=size)
        path = output / f"{name}_disc.png"
        disc.save(path, optimize=True)
        provenance[name] = {
            "source": source["url"],
            "source_git_blob_sha1": source["blob_sha1"],
            "source_sha256": hashlib.sha256(data).hexdigest(),
            "generated_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "center_longitude_deg": source["center_longitude"],
            "credit": "NASA 3D Resources",
        }
        discs[name] = disc
    (output / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    comparison = Image.new("RGB", (size * 2 + 90, size + 60), "#101827")
    comparison.paste(discs["earth"], (20, 25), discs["earth"])
    comparison.paste(discs["moon"], (size + 70, 25), discs["moon"])
    comparison.save(output / "planet_preview.jpg", quality=90)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("generated_assets"))
    parser.add_argument("--size", type=int, default=512)
    args = parser.parse_args()
    if not 256 <= args.size <= 1024:
        parser.error("size must be 256–1024")
    build(args.output, size=args.size)
