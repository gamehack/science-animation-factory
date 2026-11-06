"""Isolated editorial pipeline. It does not modify science v1 jobs or renderers."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from .editorial_schema import EditorialStoryboard, EditorialError, asset_path
from .editorial_renderer import SIZES, TRANSITION, render_scene, join_scenes, compose, inspect_output
from .jobs import JobStore, sha256_file
from .timeline import TimedScene, save_captions
from .voice import VoiceCue, generate_voice, wav_duration


def _save_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _timeline(storyboard: EditorialStoryboard, durations: list[float]) -> list[TimedScene]:
    if len(durations) != len(storyboard.scenes):
        raise EditorialError("narration counts do not match scenes")
    timeline: list[TimedScene] = []
    cursor = 0.0
    for i, (scene, duration) in enumerate(zip(storyboard.scenes, durations)):
        if not 0.5 <= duration <= 15:
            raise EditorialError(f"narration for scene {i} is outside supported duration")
        length = math.ceil(max(2.4, duration + 0.40) * 30) / 30
        timeline.append(TimedScene(i, round(cursor, 3), length, duration,
                                   "editorial", scene.title, scene.narration,
                                   {"note": scene.title}, storyboard.language))
        cursor += length
    if not 14.5 <= cursor <= 48:
        raise EditorialError(f"narrated timeline {cursor:.1f}s exceeds editorial short-form bounds")
    return timeline


def build_editorial(storyboard_file: Path, *, assets_dir: Path, output_root: Path,
                    quality: str = "preview", voice: str = "kokoro",
                    job_id: str | None = None) -> Path:
    """Strict storyboard -> TTS -> camera animation -> mix -> checked output.

    A diagnostic tone is accepted only for local, non-publishable render tests.
    """
    storyboard = EditorialStoryboard.from_file(storyboard_file)
    if quality not in SIZES:
        raise EditorialError(f"unsupported quality: {quality}")
    if voice not in ("kokoro", "tone"):
        raise EditorialError("voice must be kokoro or tone")
    if job_id is None:
        job_id = datetime.now(timezone.utc).strftime("editorial-%Y%m%dT%H%M%S%f")
    if not __import__("re").fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", job_id):
        raise EditorialError("unsafe job ID")

    assets = [asset_path(assets_dir, scene.image) for scene in storyboard.scenes]
    music = asset_path(assets_dir, storyboard.music.asset) if storyboard.music else None
    from PIL import Image
    for i, file in enumerate(assets):
        try:
            with Image.open(file) as im:
                if im.width < 500 or im.height < 500 or im.format not in ("JPEG", "PNG"):
                    raise EditorialError(f"scene {i} image too small or wrong format")
                im.verify()
        except (OSError, ValueError) as exc:
            raise EditorialError(f"scene {i} image is invalid: {exc}") from exc

    # Hash *asset contents*, not just their names, so a stable Job ID cannot silently
    # reuse checkpoints after externally supplied illustrations or music change.
    payload = storyboard_file.read_bytes()
    fingerprint = hashlib.sha256(payload + b"\0" + b"\0".join(
        (f.name + ":" + sha256_file(f)).encode("utf-8") for f in (assets + ([music] if music else []))
    )).hexdigest()
    config = {"mode": "editorial", "quality": quality, "voice": voice, "language": storyboard.language,
              "renderer": "ffmpeg-editorial-v1", "transition": TRANSITION}
    root = output_root.resolve() / job_id
    root.mkdir(parents=True, exist_ok=True)
    state = JobStore(root)
    state.create(job_id, fingerprint, config)
    if state.is_complete("ready") and (root / "final.mp4").is_file():
        return root / "final.mp4"
    if state.load()["status"] != "running":
        state.resume()
    evidence = {
        "schema_version": 2, "mode": "editorial", "job_id": job_id,
        "title": storyboard.title, "language": storyboard.language,
        "sources": list(storyboard.sources), "image_assets": [
            {"file": s.image, "rights": s.rights, "credit": s.credit, "sha256": sha256_file(a)}
            for s, a in zip(storyboard.scenes, assets)
        ],
        "music": ({"file": storyboard.music.asset, "rights": storyboard.music.rights,
                   "credit": storyboard.music.credit, "sha256": sha256_file(music)}
                  if music and storyboard.music else None),
        "content_review": "REQUIRED", "can_publish": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "RUNNING", "config": config,
    }
    _save_json(root / "manifest.json", evidence)
    try:
        storyboard_copy = root / "editorial-storyboard.json"
        storyboard_copy.write_bytes(payload)
        if not state.is_complete("validated"):
            state.complete_stage("validated", {"editorial-storyboard.json": sha256_file(storyboard_copy)})
        wavs = [root / f"voice_{i:02d}.wav" for i in range(len(storyboard.scenes))]
        cue_path = root / "voice-cues.json"
        if state.is_complete("audio"):
            cue_data = json.loads(cue_path.read_text(encoding="utf-8"))
            cues = [[VoiceCue(**item) for item in entry] for entry in cue_data]
        else:
            if state.load()["stage"] != "validated":
                state.rewind("audio")
            cues = []
            for scene, wav in zip(storyboard.scenes, wavs):
                entries: list[VoiceCue] = []
                generate_voice(scene.narration, wav, backend=voice,
                               language=storyboard.language, cues_out=entries)
                cues.append(entries)
            _save_json(cue_path, [[{"text": c.text, "start": c.start, "end": c.end}
                                   for c in beat] for beat in cues])
            checksums = {w.name: sha256_file(w) for w in wavs}
            checksums[cue_path.name] = sha256_file(cue_path)
            state.complete_stage("audio", checksums)
        lengths = [wav_duration(wav) for wav in wavs]
        timeline = _timeline(storyboard, lengths)
        duration = timeline[-1].start + timeline[-1].duration
        captions = root / "captions.srt"
        save_captions(timeline, captions, cues_by_scene=cues)
        clips = [root / f"scene_{i:02d}.mp4" for i in range(len(assets))]
        silent = root / "silent.mp4"
        if not state.is_complete("visuals"):
            if state.load()["stage"] != "audio":
                state.rewind("visuals")
            actual = []
            for i, (asset, scene, clip, beat) in enumerate(zip(assets, storyboard.scenes, clips, timeline)):
                seconds = beat.duration + (TRANSITION if i < len(clips) - 1 else 0)
                actual.append(render_scene(asset, clip, motion=scene.motion, seconds=seconds, quality=quality))
            join_scenes(clips, actual, silent)
            state.complete_stage("visuals", {"silent.mp4": sha256_file(silent)})
        final = root / "final.mp4"
        if not state.is_complete("composed"):
            if state.load()["stage"] != "visuals":
                state.rewind("composed")
            compose(silent, wavs, [b.start for b in timeline], captions, final,
                    seconds=duration, language=storyboard.language, music=music,
                    music_volume=(storyboard.music.volume if storyboard.music else 0))
            state.complete_stage("composed", {"final.mp4": sha256_file(final)})
        inspection = inspect_output(final, quality=quality, expected_seconds=duration)
        inspection["music_used"] = bool(music)
        inspection["voice_is_diagnostic"] = voice == "tone"
        _save_json(root / "qa.json", inspection)
        if not state.is_complete("technical_qa"):
            state.complete_stage("technical_qa", {"qa.json": sha256_file(root / "qa.json")})
        evidence.update({"status": "PREVIEW_ONLY" if voice == "tone" else "TECHNICALLY_READY",
                         "content_review": "REQUIRED", "can_publish": False,
                         "inspection": inspection, "duration_seconds": round(duration, 3),
                         "finished_at": datetime.now(timezone.utc).isoformat()})
        _save_json(root / "manifest.json", evidence)
        if not state.is_complete("ready"):
            state.complete_stage("ready", {"final.mp4": sha256_file(final)})
        return final
    except Exception as exc:
        state.fail(str(exc))
        evidence["status"] = "FAILED"
        evidence["failure"] = str(exc)[:300]
        _save_json(root / "manifest.json", evidence)
        raise
