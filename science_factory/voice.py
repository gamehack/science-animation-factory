"""Local, API-key-free voice generation. The tone backend is TEST-ONLY."""

from __future__ import annotations

import math
import struct
import wave
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


SAMPLE_RATE = 24_000


class VoiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class VoiceCue:
    text: str
    start: float
    end: float


@lru_cache(maxsize=2)
def _kokoro_pipeline(language: str):
    from kokoro import KPipeline

    return KPipeline(lang_code={"en-US": "a", "zh-CN": "z"}[language])


def generate_voice(text: str, destination: Path, *, backend: str = "kokoro",
                   language: str = "en-US",
                   cues_out: list[VoiceCue] | None = None) -> float:
    """Write mono PCM WAV, returning its sample-exact duration in seconds."""
    if language not in ("en-US", "zh-CN"):
        raise VoiceError(f"unsupported narration language: {language}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if backend == "tone":
        # A non-speech diagnostic sound. Never publish outputs using this backend.
        duration = max(2.5, len(text) / 4.0 if language == "zh-CN" else len(text.split()) / 2.45)
        frames = round(duration * SAMPLE_RATE)
        with wave.open(str(destination), "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(SAMPLE_RATE)
            chunk = bytearray()
            for index in range(frames):
                envelope = min(1.0, index / 1200, (frames - index) / 1200)
                value = int(2700 * envelope * math.sin(2 * math.pi * 220 * index / SAMPLE_RATE))
                chunk.extend(struct.pack("<h", value))
            writer.writeframes(bytes(chunk))
        return frames / SAMPLE_RATE
    if backend != "kokoro":
        raise VoiceError(f"unsupported voice backend: {backend}")
    try:
        import numpy as np
        from kokoro import KPipeline  # noqa: F401 - ensure optional dependency is present
    except ImportError as exc:
        raise VoiceError('Kokoro is not installed. Install with: pip install -e ".[all]"') from exc

    # M1 runs on CPU as well as on GPU; never invokes a metered TTS endpoint.
    try:
        pipeline = _kokoro_pipeline(language)
        voice = "zf_xiaoyi" if language == "zh-CN" else "af_heart"
        chunks = []
        cursor = 0
        for graphemes, _, audio in pipeline(text, voice=voice):
            if hasattr(audio, "detach"):
                audio = audio.detach().cpu().numpy()
            samples_chunk = np.asarray(audio, dtype=np.float32).reshape(-1)
            chunks.append(samples_chunk)
            if cues_out is not None and str(graphemes).strip():
                cues_out.append(VoiceCue(str(graphemes).strip(), cursor / SAMPLE_RATE,
                                         (cursor + len(samples_chunk)) / SAMPLE_RATE))
            cursor += len(samples_chunk)
        if not chunks:
            raise VoiceError("Kokoro produced no audio")
        samples = np.concatenate(chunks)
        pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
        with wave.open(str(destination), "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(SAMPLE_RATE)
            writer.writeframes(pcm.tobytes())
        return len(samples) / SAMPLE_RATE
    except Exception as exc:
        raise VoiceError(f"Kokoro synthesis failed: {exc}") from exc


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as reader:
        if reader.getnframes() == 0 or reader.getframerate() <= 0:
            raise VoiceError(f"empty or malformed WAV: {path}")
        return reader.getnframes() / reader.getframerate()

