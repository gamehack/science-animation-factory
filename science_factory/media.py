"""Isolated subprocess render/mux operations and deterministic media checks."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .timeline import TimedScene


class MediaError(RuntimeError):
    pass


def _run(args: list[str], *, cwd: Path | None = None,
         env: dict[str, str] | None = None, timeout: int = 600) -> None:
    try:
        result = subprocess.run(args, cwd=cwd, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MediaError(f"process could not complete: {args[0]}: {exc}") from exc
    if result.returncode:
        raise MediaError(f"{args[0]} exited {result.returncode}: {result.stderr[-3000:]}")


def require_tools(*names: str) -> None:
    unavailable = [name for name in names if shutil.which(name) is None]
    if unavailable:
        raise MediaError(f"missing commands: {', '.join(unavailable)}")


def render_manim(render_plan: Path, directory: Path, *, quality: str) -> Path:
    """Render one silent, portrait video with CPU-friendly Cairo."""
    resolution = "360,640" if quality == "preview" else "1080,1920"
    module = Path(__file__).with_name("render_scenes.py")
    output_dir = directory / "manim_media"
    env = dict(os.environ)
    env["SCIENCE_FACTORY_PLAN"] = str(render_plan.resolve())
    cmd = [sys.executable, "-m", "manim", "render", "--renderer", "cairo",
           "--format", "mp4", "--disable_caching", "--fps", "30",
           "-r", resolution, "--media_dir", str(output_dir.resolve()),
           "-o", "science_silent", str(module.resolve()), "ScienceShort"]
    _run(cmd, env=env, timeout=1800)
    candidates = list(output_dir.rglob("science_silent.mp4"))
    if len(candidates) != 1 or candidates[0].stat().st_size < 1000:
        raise MediaError("Manim did not produce exactly one non-empty silent MP4")
    return candidates[0]


def subtitle_style(language: str) -> str:
    """Keep bilingual captions readable and above short-form app UI overlays.

    libass scales style coordinates with the video frame, so the same normalized
    phone-safe layout works at both 360x640 and 1080x1920.
    """
    if language not in ("en-US", "zh-CN"):
        raise ValueError(f"unsupported subtitle language: {language}")
    font = "Noto Sans CJK SC" if language == "zh-CN" else "DejaVu Sans"
    size = "15" if language == "zh-CN" else "14"
    return (f"FontName={font},FontSize={size},Bold=1,"
            "PrimaryColour=&H00FFFFFF,OutlineColour=&H00101827,"
            "Outline=2,Shadow=0.7,Alignment=2,"
            "MarginV=48,MarginL=26,MarginR=26")


def mux_video(silent_mp4: Path, wav_files: list[Path],
              timeline: list[TimedScene], srt_path: Path, destination: Path) -> None:
    """One-pass audio mix, then burn captions without a paid video service."""
    if not wav_files or len(wav_files) != len(timeline):
        raise MediaError("audio segments do not match the measured timeline")
    require_tools("ffmpeg")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(silent_mp4)]
    for file in wav_files:
        cmd.extend(["-i", str(file)])
    filters: list[str] = []
    labels = []
    for index, scene in enumerate(timeline):
        label = f"a{index}"
        filters.append(f"[{index + 1}:a]adelay={round(scene.start * 1000)}:all=1[{label}]")
        labels.append(f"[{label}]")
    filters.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0[mixed]")
    filters.append("[mixed]apad[aout]")
    total_seconds = timeline[-1].start + timeline[-1].duration
    # Reserve the bottom UI band used by Facebook Reels and similar apps.
    style = subtitle_style(timeline[0].language)
    caption_filter = f"subtitles={srt_path.name}:force_style='{style}'"
    cmd.extend(["-filter_complex", ";".join(filters), "-map", "0:v:0", "-map", "[aout]",
                "-vf", caption_filter, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "veryfast", "-crf", "21", "-c:a", "aac", "-b:a", "160k",
                "-t", f"{total_seconds:.3f}", "-movflags", "+faststart",
                str(destination.resolve())])
    _run(cmd, cwd=srt_path.parent, timeout=1800)


def inspect_mp4(path: Path, *, expected_width: int, expected_height: int,
                target_duration: float) -> dict:
    require_tools("ffprobe")
    if not path.exists() or path.stat().st_size < 1000:
        raise MediaError("output video is missing or empty")
    result = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                             "-of", "json", str(path)], text=True,
                            capture_output=True, check=False, timeout=60)
    if result.returncode:
        raise MediaError(f"ffprobe failed: {result.stderr[-1000:]}")
    info = json.loads(result.stdout)
    videos = [stream for stream in info["streams"] if stream["codec_type"] == "video"]
    audios = [stream for stream in info["streams"] if stream["codec_type"] == "audio"]
    if len(videos) != 1 or len(audios) != 1:
        raise MediaError("final MP4 must contain one video and one audio stream")
    video = videos[0]
    if (video["width"], video["height"]) != (expected_width, expected_height):
        raise MediaError("incorrect output dimensions")
    if video.get("codec_name") != "h264":
        raise MediaError("video must use H.264 for broad mobile compatibility")
    actual = float(info["format"]["duration"])
    if abs(actual - target_duration) > 0.6:
        raise MediaError(f"audio/video timeline mismatch: {actual:.2f}s vs {target_duration:.2f}s")
    return {"width": video["width"], "height": video["height"],
            "duration_seconds": round(actual, 3), "video_codec": video["codec_name"],
            "audio_codec": audios[0]["codec_name"], "bytes": path.stat().st_size}


def extract_scene_stills(video: Path, timeline: list[TimedScene], destination: Path) -> list[str]:
    """One mid-scene JPEG per beat for review without another video render."""
    require_tools("ffmpeg")
    names: list[str] = []
    for scene in timeline:
        name = f"scene_{scene.index:02}_review.jpg"
        moment = scene.start + scene.duration / 2
        _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
              "-ss", f"{moment:.3f}", "-i", str(video),
              "-frames:v", "1", "-q:v", "3", str((destination / name).resolve())], timeout=120)
        names.append(name)
    return names

