"""Dependency-free speech edge trimming for deterministic video timing."""

from __future__ import annotations

from array import array
from dataclasses import dataclass
import math
import sys
import wave
from pathlib import Path


@dataclass(frozen=True)
class AudioTrim:
    duration: float
    removed_start: float
    removed_end: float


def trim_wav_edges(path: Path, *, db_threshold: float = -42.0,
                   keep_seconds: float = 0.16,
                   min_trim_seconds: float = 0.26) -> AudioTrim:
    """Trim long *edge* silences only, preserving pauses between spoken words.

    Operates on mono 16-bit PCM at any sample rate and never normalizes audio.
    Each 10ms window is checked against an RMS threshold; a short lead-in and
    tail are deliberately preserved to protect low-amplitude consonants.
    """
    with wave.open(str(path), "rb") as reader:
        channels, width, rate = (reader.getnchannels(), reader.getsampwidth(),
                                 reader.getframerate())
        if channels != 1 or width != 2 or rate <= 0:
            raise ValueError("edge trim requires a mono 16-bit PCM WAV")
        samples = array("h")
        samples.frombytes(reader.readframes(reader.getnframes()))
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        raise ValueError("cannot trim an empty WAV")
    window = max(1, round(rate / 100))
    cutoff = 32767 * 10 ** (db_threshold / 20)
    audible: list[int] = []
    for start in range(0, len(samples), window):
        block = samples[start:start + window]
        rms = math.sqrt(sum(value * value for value in block) / len(block))
        if rms >= cutoff:
            audible.append(start)
    if not audible:
        raise ValueError("no audible content detected in WAV")
    padding = round(keep_seconds * rate)
    first = max(0, audible[0] - padding)
    last = min(len(samples), audible[-1] + window + padding)
    if first / rate < min_trim_seconds:
        first = 0
    if (len(samples) - last) / rate < min_trim_seconds:
        last = len(samples)
    if first or last < len(samples):
        with wave.open(str(path), "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(rate)
            writer.writeframes(samples[first:last].tobytes())
    return AudioTrim((last - first) / rate, first / rate, (len(samples) - last) / rate)
