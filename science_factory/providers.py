"""Explicit provider contracts. No implicit paid-service fallback."""
from __future__ import annotations
from pathlib import Path
from typing import Protocol

class TTSProvider(Protocol):
    name:str
    version:str
    def synthesize(self,text:str,destination:Path,*,language:str,voice:str|None=None)->float: ...

class Renderer(Protocol):
    name:str
    version:str
    def render(self,render_plan:Path,output_dir:Path,*,quality:str,language:str)->Path: ...

class ProviderRegistry:
    def __init__(self):
        self._tts={}; self._renderers={}
    def register_tts(self,provider:TTSProvider):
        if provider.name in self._tts: raise ValueError("duplicate TTS provider")
        self._tts[provider.name]=provider
    def register_renderer(self,renderer:Renderer):
        if renderer.name in self._renderers: raise ValueError("duplicate renderer")
        self._renderers[renderer.name]=renderer
    def tts(self,name:str)->TTSProvider:
        if name not in self._tts: raise ValueError(f"unknown TTS provider: {name}")
        return self._tts[name]
    def renderer(self,name:str)->Renderer:
        if name not in self._renderers: raise ValueError(f"unknown renderer: {name}")
        return self._renderers[name]
