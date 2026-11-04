"""Validation boundary: storyboard data can never contain executable Python."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SCENE_KINDS = frozenset({"orbit", "comparison", "wave", "force", "scale", "particles"})
ALLOWED_PARAM_KEYS = frozenset({"left", "right", "center", "object", "direction", "note"})


class StoryboardError(ValueError):
    """A storyboard violates the renderer's strict, non-executable contract."""


def _text(value: Any, field: str, max_chars: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StoryboardError(f"{field} must be a non-empty string")
    value = value.strip()
    if len(value) > max_chars or any(ord(ch) < 32 for ch in value):
        raise StoryboardError(f"{field} must be one line, at most {max_chars} chars")
    if "-->" in value or "<" in value or ">" in value:
        raise StoryboardError(f"{field} contains unsupported markup")
    return value


def _record(value: Any, keys: set[str], field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StoryboardError(f"{field} must be an object")
    unknown = set(value) - keys
    if unknown:
        raise StoryboardError(f"{field} has unsupported keys: {sorted(unknown)}")
    return value


@dataclass(frozen=True)
class SceneSpec:
    kind: str
    title: str
    narration: str
    params: dict[str, str]

    @classmethod
    def from_dict(cls, data: Any, index: int) -> SceneSpec:
        obj = _record(data, {"kind", "title", "narration", "params"}, f"scene[{index}]")
        kind = obj.get("kind")
        if kind not in SCENE_KINDS:
            raise StoryboardError(f"scene[{index}].kind is not a supported visual template")
        title = _text(obj.get("title"), f"scene[{index}].title", 65)
        narration = _text(obj.get("narration"), f"scene[{index}].narration", 280)
        params = obj.get("params", {})
        _record(params, set(ALLOWED_PARAM_KEYS), f"scene[{index}].params")
        if len(params) > 6:
            raise StoryboardError("too many scene parameters")
        safe_params = {k: _text(v, f"scene[{index}].params.{k}", 50) for k, v in params.items()}
        return cls(kind=kind, title=title, narration=narration, params=safe_params)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "title": self.title, "narration": self.narration, "params": self.params}


@dataclass(frozen=True)
class Storyboard:
    title: str
    language: str
    target_seconds: int
    sources: tuple[str, ...]
    scenes: tuple[SceneSpec, ...]

    @classmethod
    def from_dict(cls, data: Any) -> Storyboard:
        obj = _record(data, {"title", "language", "target_seconds", "sources", "scenes"}, "storyboard")
        title = _text(obj.get("title"), "title", 100)
        language = obj.get("language")
        if language != "en-US":
            raise StoryboardError("M1 only supports en-US; no implicit translation")
        seconds = obj.get("target_seconds")
        if type(seconds) is not int or not 30 <= seconds <= 60:
            raise StoryboardError("target_seconds must be an integer between 30 and 60")
        sources = obj.get("sources")
        if not isinstance(sources, list) or not 1 <= len(sources) <= 10:
            raise StoryboardError("sources must contain 1 to 10 source URLs")
        urls: list[str] = []
        for source in sources:
            parsed = urlparse(str(source))
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise StoryboardError("every source must be a public https URL")
            urls.append(str(source))
        scene_data = obj.get("scenes")
        if not isinstance(scene_data, list) or not 3 <= len(scene_data) <= 12:
            raise StoryboardError("scenes must contain 3 to 12 visual beats")
        scenes = tuple(SceneSpec.from_dict(scene, i) for i, scene in enumerate(scene_data))
        return cls(title=title, language=language, target_seconds=seconds, sources=tuple(urls), scenes=scenes)

    @classmethod
    def from_file(cls, path: Path) -> Storyboard:
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            raise StoryboardError(f"invalid JSON: {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "language": self.language,
            "target_seconds": self.target_seconds,
            "sources": list(self.sources),
            "scenes": [scene.to_dict() for scene in self.scenes],
        }

