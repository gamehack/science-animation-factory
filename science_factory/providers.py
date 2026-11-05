"""Explicit provider contracts and free local adapters."""
from __future__ import annotations
import importlib.metadata
from pathlib import Path
from typing import Protocol
from .voice import VoiceCue, generate_voice

class TTSProvider(Protocol):
    name: str
    version: str
    def synthesize(self, text: str, destination: Path, *, language: str,
                   voice: str | None = None, cues_out: list[VoiceCue] | None = None) -> float: ...

class Renderer(Protocol):
    name: str
    version: str
    def render(self, render_plan: Path, output_dir: Path, *,
               quality: str, language: str) -> Path: ...

def _version(package: str) -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"

class KokoroTTSProvider:
    name = "kokoro"
    @property
    def version(self) -> str:
        return _version("kokoro")
    def synthesize(self, text, destination, *, language, voice=None, cues_out=None):
        return generate_voice(text, destination, backend="kokoro",
                              language=language, cues_out=cues_out)

class DiagnosticToneProvider:
    name = "tone"
    version = "builtin-diagnostic-v1"
    def synthesize(self, text, destination, *, language, voice=None, cues_out=None):
        return generate_voice(text, destination, backend="tone",
                              language=language, cues_out=cues_out)

class ManimCairoRenderer:
    name = "manim-cairo"
    @property
    def version(self) -> str:
        return _version("manim")
    def render(self, render_plan, output_dir, *, quality, language):
        from .media import render_manim
        return render_manim(render_plan, output_dir, quality=quality)

class ProviderRegistry:
    def __init__(self):
        self._tts = {}
        self._renderers = {}
    def register_tts(self, provider: TTSProvider):
        if provider.name in self._tts:
            raise ValueError("duplicate TTS provider")
        self._tts[provider.name] = provider
    def register_renderer(self, renderer: Renderer):
        if renderer.name in self._renderers:
            raise ValueError("duplicate renderer")
        self._renderers[renderer.name] = renderer
    def tts(self, name: str) -> TTSProvider:
        if name not in self._tts:
            raise ValueError(f"unknown TTS provider: {name}")
        return self._tts[name]
    def renderer(self, name: str) -> Renderer:
        if name not in self._renderers:
            raise ValueError(f"unknown renderer: {name}")
        return self._renderers[name]

def default_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register_tts(KokoroTTSProvider())
    registry.register_tts(DiagnosticToneProvider())
    registry.register_renderer(ManimCairoRenderer())
    return registry
