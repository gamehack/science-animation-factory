"""M1: input storyboard -> measured voice -> deterministic visual render -> QA."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .media import extract_scene_stills, inspect_mp4, mux_video, render_manim, require_tools
from .schema import Storyboard
from .timeline import make_timeline, save_captions
from .voice import generate_voice


class BuildError(RuntimeError):
    pass


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build(storyboard_file: Path, *, output_root: Path, voice: str = "kokoro",
          quality: str = "preview") -> Path:
    storyboard = Storyboard.from_file(storyboard_file)
    if quality not in ("preview", "full"):
        raise BuildError("quality must be 'preview' or 'full'")
    if voice not in ("kokoro", "tone"):
        raise BuildError("voice must be 'kokoro' or 'tone'")
    require_tools("ffmpeg", "ffprobe")
    try:
        import manim  # noqa: F401
    except ImportError as exc:
        raise BuildError('Manim is missing; install with: pip install -e ".[render]"') from exc

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    directory = output_root.resolve() / run_id
    directory.mkdir(parents=True, exist_ok=False)
    source_bytes = storyboard_file.read_bytes()
    asset_provenance = json.loads((Path(__file__).resolve().parent / "assets" / "provenance.json")
                                  .read_text(encoding="utf-8"))
    manifest = {
        "run_id": run_id,
        "status": "RUNNING",
        "voice_backend": voice,
        "language": storyboard.language,
        "quality": quality,
        "storyboard_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_urls": list(storyboard.sources),
        "visual_asset_credits": {
            name: {"source": item["source"], "credit": item["credit"],
                   "sha256": item["generated_sha256"]}
            for name, item in asset_provenance.items()
        },
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_file = directory / "manifest.json"
    _write_json(manifest_file, manifest)
    _write_json(directory / "storyboard.json", storyboard.to_dict())
    try:
        wavs: list[Path] = []
        audio_durations: list[float] = []
        for index, scene in enumerate(storyboard.scenes):
            file = directory / f"voice_{index:02}.wav"
            duration = generate_voice(scene.narration, file, backend=voice,
                                      language=storyboard.language)
            wavs.append(file)
            audio_durations.append(duration)
        timeline = make_timeline(storyboard, audio_durations)
        total_duration = timeline[-1].start + timeline[-1].duration
        plan = directory / "render-plan.json"
        _write_json(plan, {"scenes": [scene.to_dict() for scene in timeline]})
        subtitles = directory / "captions.srt"
        save_captions(timeline, subtitles)
        silent = render_manim(plan, directory, quality=quality)
        finished = directory / "final.mp4"
        mux_video(silent, wavs, timeline, subtitles, finished)
        width, height = (360, 640) if quality == "preview" else (1080, 1920)
        checks = inspect_mp4(finished, expected_width=width, expected_height=height,
                             target_duration=total_duration)
        stills = extract_scene_stills(finished, timeline, directory)
        manifest.update({"status": "READY" if voice == "kokoro" else "PREVIEW_ONLY",
                         "checks": checks,
                         "review_frames": stills,
                         "duration_seconds": round(total_duration, 3),
                         "finished_at": datetime.now(timezone.utc).isoformat()})
        _write_json(manifest_file, manifest)
        return finished
    except Exception as exc:
        manifest.update({"status": "FAILED", "error": str(exc),
                         "finished_at": datetime.now(timezone.utc).isoformat()})
        _write_json(manifest_file, manifest)
        raise

