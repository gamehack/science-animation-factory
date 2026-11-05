"""Deterministic timeline derived from measured, not predicted, speech duration."""

from __future__ import annotations

import textwrap
import re
from dataclasses import dataclass
from pathlib import Path

from .schema import Storyboard
from .voice import VoiceCue


@dataclass(frozen=True)
class TimedScene:
    index: int
    start: float
    duration: float
    audio_duration: float
    kind: str
    title: str
    narration: str
    params: dict[str, str]
    language: str = "en-US"

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "start": self.start,
            "duration": self.duration,
            "audio_duration": self.audio_duration,
            "kind": self.kind,
            "title": self.title,
            "narration": self.narration,
            "params": self.params,
            "language": self.language,
        }


def make_timeline(storyboard: Storyboard, durations: list[float]) -> list[TimedScene]:
    if len(durations) != len(storyboard.scenes):
        raise ValueError("one voice segment is required for each visual scene")
    cursor = 0.0
    timeline: list[TimedScene] = []
    for index, (scene, audio_duration) in enumerate(zip(storyboard.scenes, durations)):
        if not 0.5 <= audio_duration <= 20.0:
            raise ValueError(f"scene {index}: TTS duration outside supported bounds")
        # A target of 45 seconds must not force six equal 7.5-second holds.
        # The voice determines pacing; 0.4s is an intentional breathing beat.
        length = round(max(3.3, audio_duration + 0.4), 3)
        timeline.append(TimedScene(index, round(cursor, 3), length, audio_duration,
                                   scene.kind, scene.title, scene.narration, scene.params,
                                   storyboard.language))
        cursor += length
    if not 29.5 <= cursor <= 60.5:
        raise ValueError(f"total voice-driven duration {cursor:.1f}s outside 30–60s short format")
    return timeline


def _srt_time(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


def _subtitle_phrases(text: str, language: str) -> tuple[list[str], list[int], int]:
    """Split a narrator-produced grapheme span into phone-friendly cards."""
    if language == "zh-CN":
        clauses = re.findall(r"[^，。！？；]+[，。！？；]?", text)
        phrases = [clause[i:i + 24] for clause in clauses
                   for i in range(0, len(clause), 24)]
        return phrases, [len(phrase) for phrase in phrases], 12
    phrases: list[str] = []
    current: list[str] = []
    for word in text.split():
        if current and (len(" ".join(current + [word])) > 38 or len(current) >= 7):
            phrases.append(" ".join(current))
            current = []
        current.append(word)
    if current:
        phrases.append(" ".join(current))
    return phrases, [len(phrase.split()) for phrase in phrases], 24


def captions_srt(timeline: list[TimedScene], *,
                 cues_by_scene: list[list[VoiceCue]] | None = None) -> str:
    """Time captions to real TTS chunks, dividing only within each chunk.

    This is *chunk alignment*, not word-level forced speech alignment. When
    Kokoro returns one long chunk, its internal timing remains approximate.
    """
    if cues_by_scene is not None and len(cues_by_scene) != len(timeline):
        raise ValueError("voice cue groups must match scene count")
    entries: list[str] = []
    count = 0
    for scene in timeline:
        source_chunks = (cues_by_scene[scene.index] if cues_by_scene else [])
        if not source_chunks:
            source_chunks = [VoiceCue(scene.narration, 0, scene.audio_duration)]
        for chunk in source_chunks:
            start_audio = max(0.0, min(scene.audio_duration, chunk.start))
            end_audio = max(start_audio, min(scene.audio_duration, chunk.end))
            if end_audio - start_audio < 0.08:
                continue
            phrases, weights, wrap_width = _subtitle_phrases(chunk.text, scene.language)
            total_weight = sum(weights)
            if total_weight <= 0:
                continue
            elapsed_weight = 0
            for phrase, weight in zip(phrases, weights):
                start = scene.start + start_audio + (end_audio - start_audio) * elapsed_weight / total_weight
                elapsed_weight += weight
                end = scene.start + start_audio + (end_audio - start_audio) * elapsed_weight / total_weight
                if end - start < 0.08:
                    continue
                count += 1
                wrapped = "\n".join(textwrap.wrap(phrase, width=wrap_width,
                           break_long_words=scene.language == "zh-CN", break_on_hyphens=False))
                entries.append(f"{count}\n{_srt_time(start)} --> {_srt_time(end)}\n{wrapped}\n")
    return "\n".join(entries) + "\n"


def save_captions(timeline: list[TimedScene], path: Path, *,
                  cues_by_scene: list[list[VoiceCue]] | None = None) -> None:
    path.write_text(captions_srt(timeline, cues_by_scene=cues_by_scene), encoding="utf-8")

