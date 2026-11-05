"""Deterministic timeline derived from measured, not predicted, speech duration."""

from __future__ import annotations

import textwrap
import re
from dataclasses import dataclass
from pathlib import Path

from .schema import Storyboard


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
    minimum = storyboard.target_seconds / len(durations)
    cursor = 0.0
    timeline: list[TimedScene] = []
    for index, (scene, audio_duration) in enumerate(zip(storyboard.scenes, durations)):
        if not 0.5 <= audio_duration <= 20.0:
            raise ValueError(f"scene {index}: TTS duration outside supported bounds")
        length = round(max(minimum, audio_duration + 0.65), 3)
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


def captions_srt(timeline: list[TimedScene]) -> str:
    """Phrase-timed subtitles inside each measured narration window.

    These are phrase-level approximations, NOT forced speech alignment.
    """
    entries: list[str] = []
    count = 0
    for scene in timeline:
        if scene.language == "zh-CN":
            # Chinese has no reliable whitespace word boundaries. Respect short
            # clauses, then split long clauses into <=24-character subtitle cards.
            clauses = re.findall(r"[^，。！？；]+[，。！？；]?", scene.narration)
            phrases = [clause[i:i + 24] for clause in clauses
                       for i in range(0, len(clause), 24)]
            weights = [len(phrase) for phrase in phrases]
            wrap_width = 12
        else:
            phrases = []
            words = scene.narration.split()
            current: list[str] = []
            for word in words:
                # Restrict each card to roughly two short lines on a 9:16 phone.
                if current and (len(" ".join(current + [word])) > 38 or len(current) >= 7):
                    phrases.append(" ".join(current))
                    current = []
                current.append(word)
            if current:
                phrases.append(" ".join(current))
            weights = [len(phrase.split()) for phrase in phrases]
            wrap_width = 24
        total_weight = sum(weights)
        elapsed_weight = 0
        for phrase, weight in zip(phrases, weights):
            start = scene.start + scene.audio_duration * elapsed_weight / total_weight
            elapsed_weight += weight
            end = scene.start + scene.audio_duration * elapsed_weight / total_weight
            count += 1
            wrapped = "\n".join(textwrap.wrap(phrase, width=wrap_width,
                       break_long_words=scene.language == "zh-CN", break_on_hyphens=False))
            entries.append(f"{count}\n{_srt_time(start)} --> {_srt_time(end)}\n{wrapped}\n")
    return "\n".join(entries) + "\n"


def save_captions(timeline: list[TimedScene], path: Path) -> None:
    path.write_text(captions_srt(timeline), encoding="utf-8")

