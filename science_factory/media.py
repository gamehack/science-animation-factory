"""Isolated subprocess render/mux operations and deterministic media checks."""

from __future__ import annotations

import json
import os
import re
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
    # libass scales SRT font sizes using video height; larger values caused
    # automatic 3-line wraps at 9:16, covering the visual's own annotations.
    size = "11" if language == "zh-CN" else "10"
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
    # Normalize speech across languages; constrain true peak for mobile players.
    filters.append("[mixed]loudnorm=I=-16:TP=-1.5:LRA=11,apad[aout]")
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
    if audios[0].get("codec_name") != "aac":
        raise MediaError("audio must use AAC for broad mobile compatibility")
    actual = float(info["format"]["duration"])
    if abs(actual - target_duration) > 0.6:
        raise MediaError(f"audio/video timeline mismatch: {actual:.2f}s vs {target_duration:.2f}s")
    return {"width": video["width"], "height": video["height"],
            "duration_seconds": round(actual, 3), "video_codec": video["codec_name"],
            "audio_codec": audios[0]["codec_name"], "bytes": path.stat().st_size}


def scan_media_quality(path: Path, *, max_silence: float = 2.6) -> dict:
    """Reject unusually long dead-air intervals and black sections.

    A dark-but-colored astronomy background is not black under pix_th=0.025.
    This remains a technical gate, never a substitute for scientific review.
    """
    require_tools("ffmpeg")
    command = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
               "-vf", "blackdetect=d=0.45:pix_th=0.025:pic_th=0.99",
               "-af", "silencedetect=noise=-38dB:d=1.2",
               "-f", "null", "-"]
    result = subprocess.run(command, text=True, capture_output=True, check=False,
                            timeout=300)
    if result.returncode:
        raise MediaError(f"technical A/V scan failed: {result.stderr[-1000:]}")
    black_segments = [float(x) for x in re.findall(r"black_duration:\s*([0-9.]+)", result.stderr)]
    quiet_segments = [float(x) for x in re.findall(r"silence_duration:\s*([0-9.]+)", result.stderr)]
    if any(duration >= 0.45 for duration in black_segments):
        raise MediaError(f"black video segment detected: {max(black_segments):.2f}s")
    if any(duration > max_silence for duration in quiet_segments):
        raise MediaError(f"excessive speech silence: {max(quiet_segments):.2f}s")
    return {"max_black_seconds": round(max(black_segments, default=0.0), 3),
            "max_silence_seconds": round(max(quiet_segments, default=0.0), 3),
            "silence_threshold_db": -38}


def parse_ebur128_summary(stderr: str) -> tuple[float, float]:
    """Extract integrated loudness and true peak from FFmpeg ebur128 output."""
    integrated = re.findall(r"^\s*I:\s*(-?[0-9]+(?:\.[0-9]+)?)\s*LUFS", stderr, re.MULTILINE)
    peaks = re.findall(r"^\s*Peak:\s*(-?[0-9]+(?:\.[0-9]+)?)\s*dBFS", stderr, re.MULTILINE)
    if not integrated or not peaks:
        raise MediaError("could not parse FFmpeg ebur128 loudness/true-peak summary")
    return float(integrated[-1]), float(peaks[-1])


def measure_audio_quality(path: Path, *, target_lufs: float = -16.0,
                          loudness_tolerance: float = 2.0,
                          max_true_peak_dbfs: float = -1.0) -> dict:
    """Measure final encoded audio; reject unexpected loudness or true peak."""
    require_tools("ffmpeg")
    result = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
                             "-af", "ebur128=peak=true", "-f", "null", "-"],
                            text=True, capture_output=True, check=False, timeout=300)
    if result.returncode:
        raise MediaError(f"audio loudness measurement failed: {result.stderr[-1000:]}")
    integrated, peak = parse_ebur128_summary(result.stderr)
    if abs(integrated - target_lufs) > loudness_tolerance:
        raise MediaError(f"integrated loudness {integrated:.1f} LUFS outside target")
    if peak > max_true_peak_dbfs:
        raise MediaError(f"true peak {peak:.1f} dBFS exceeds ceiling {max_true_peak_dbfs:.1f}")
    return {"integrated_loudness_lufs": round(integrated, 2),
            "true_peak_dbfs": round(peak, 2),
            "loudness_target_lufs": target_lufs,
            "true_peak_ceiling_dbfs": max_true_peak_dbfs}


def extract_scene_stills(video: Path, timeline: list[TimedScene], destination: Path) -> list[str]:
    """Three timed samples per beat reveal entrances, motion and exits."""
    require_tools("ffmpeg")
    names: list[str] = []
    for scene in timeline:
        for label, fraction in (("opening", 0.12), ("middle", 0.50), ("closing", 0.88)):
            name = f"scene_{scene.index:02}_{label}_review.jpg"
            moment = scene.start + scene.duration * fraction
            _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                  "-ss", f"{moment:.3f}", "-i", str(video),
                  "-frames:v", "1", "-q:v", "3", str((destination / name).resolve())], timeout=120)
            names.append(name)
    return names

