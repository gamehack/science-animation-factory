"""Strict, non-executable, asset-backed editorial storyboard schema (v2)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

MOTIONS = frozenset({"push_in", "pull_out", "pan_left", "pan_right", "still"})
RIGHTS = frozenset({"original", "licensed", "public_domain"})
ASSET_PATTERN = re.compile(r"[A-Za-z0-9_./-]{1,160}\Z")


class EditorialError(ValueError):
    pass


def _record(value, expected: set[str], name: str) -> dict:
    if not isinstance(value, dict):
        raise EditorialError(f"{name} must be an object")
    unknown = value.keys() - expected
    if unknown:
        raise EditorialError(f"{name} unsupported keys: {sorted(unknown)}")
    return value


def _text(value, name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EditorialError(f"{name} must be nonempty text")
    value = value.strip()
    if len(value) > maximum or any(ord(c) < 32 for c in value):
        raise EditorialError(f"{name} must be single-line, at most {maximum} characters")
    if "<" in value or ">" in value:
        raise EditorialError(f"{name} cannot contain markup")
    return value


def _asset_name(value: object, name: str, extensions: set[str]) -> str:
    if not isinstance(value, str) or not ASSET_PATTERN.fullmatch(value):
        raise EditorialError(f"{name}: unsupported asset path")
    path = Path(value)
    if path.is_absolute() or any(part in (".", "..") for part in path.parts) or path.suffix.lower() not in extensions:
        raise EditorialError(f"{name}: only safe relative asset paths with supported extensions are allowed")
    return value


def asset_path(root: Path, name: str) -> Path:
    """Reject path traversal *including symlinks*, irrespective of the renderer caller."""
    root = root.resolve(strict=True)
    path = (root / name).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise EditorialError(f"asset escapes the approved asset directory: {name}")
    return path


@dataclass(frozen=True)
class EditorialScene:
    title: str
    narration: str
    image: str
    motion: str
    rights: str
    credit: str

    @classmethod
    def from_dict(cls, raw: object, index: int) -> "EditorialScene":
        d = _record(raw, {"title", "narration", "image", "motion", "rights", "credit"}, f"scene[{index}]")
        motion = d.get("motion")
        rights = d.get("rights")
        if motion not in MOTIONS:
            raise EditorialError(f"scene[{index}] invalid camera motion")
        if rights not in RIGHTS:
            raise EditorialError(f"scene[{index}] requires reviewed rights")
        return cls(
            title=_text(d.get("title"), f"scene[{index}].title", 64),
            narration=_text(d.get("narration"), f"scene[{index}].narration", 240),
            image=_asset_name(d.get("image"), f"scene[{index}].image", {".jpg", ".jpeg", ".png"}),
            motion=motion,
            rights=rights,
            credit=_text(d.get("credit"), f"scene[{index}].credit", 160),
        )


@dataclass(frozen=True)
class EditorialMusic:
    asset: str
    rights: str
    credit: str
    volume: float

    @classmethod
    def from_dict(cls, raw: object) -> "EditorialMusic":
        d = _record(raw, {"asset", "rights", "credit", "volume"}, "music")
        rights = d.get("rights")
        if rights not in RIGHTS:
            raise EditorialError("music requires reviewed rights")
        volume = d.get("volume", 0.13)
        if not isinstance(volume, (float, int)) or isinstance(volume, bool) or not 0 <= volume <= 0.35:
            raise EditorialError("music.volume must be between 0 and 0.35")
        return cls(
            asset=_asset_name(d.get("asset"), "music.asset", {".mp3", ".wav", ".m4a", ".flac"}),
            rights=rights,
            credit=_text(d.get("credit"), "music.credit", 160),
            volume=float(volume),
        )


@dataclass(frozen=True)
class EditorialStoryboard:
    title: str
    language: str
    target_seconds: int
    sources: tuple[str, ...]
    scenes: tuple[EditorialScene, ...]
    music: EditorialMusic | None
    schema_version: int = 2
    kind: str = "editorial"

    @classmethod
    def from_dict(cls, raw: object) -> "EditorialStoryboard":
        d = _record(raw, {"schema_version", "kind", "title", "language", "target_seconds", "sources", "scenes", "music"}, "storyboard")
        if type(d.get("schema_version")) is not int or d["schema_version"] != 2 or d.get("kind") != "editorial":
            raise EditorialError("expected schema_version=2 and kind=editorial")
        language = d.get("language")
        if language not in ("en-US", "zh-CN"):
            raise EditorialError("language must be en-US or zh-CN")
        seconds = d.get("target_seconds")
        if type(seconds) is not int or not 15 <= seconds <= 45:
            raise EditorialError("editorial target_seconds must be 15..45")
        sources = d.get("sources")
        if not isinstance(sources, list) or not 1 <= len(sources) <= 10:
            raise EditorialError("1..10 evidence URLs required")
        for url in sources:
            if not isinstance(url, str):
                raise EditorialError("source must be a URL")
            u = urlparse(url)
            if u.scheme != "https" or not u.hostname or u.username or u.password:
                raise EditorialError("sources must use public HTTPS references")
        scenes = d.get("scenes")
        if not isinstance(scenes, list) or not 3 <= len(scenes) <= 8:
            raise EditorialError("editorial expects 3..8 scenes")
        parsed = tuple(EditorialScene.from_dict(scene, i) for i, scene in enumerate(scenes))
        music = EditorialMusic.from_dict(d["music"]) if d.get("music") is not None else None
        return cls(title=_text(d.get("title"), "title", 100), language=language,
                   target_seconds=seconds, sources=tuple(sources), scenes=parsed, music=music)

    @classmethod
    def from_file(cls, path: Path) -> "EditorialStoryboard":
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            raise EditorialError(f"invalid JSON: {exc}") from exc
