"""Deterministic, CPU-only illustrated micro-documentary video renderer.

No model-authored code, networking, or implicit paid provider is executed.
"""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

FPS = 30
TRANSITION = 0.35
SIZES = {"preview": (360, 640), "mobile": (720, 1280), "full": (1080, 1920)}


class EditorialRenderError(RuntimeError):
    pass


def _run(command: list[str], *, cwd: Path | None = None, timeout: int = 2400) -> None:
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EditorialRenderError(f"renderer invocation failed: {exc}") from exc
    if result.returncode:
        raise EditorialRenderError(f"{command[0]} exited {result.returncode}: {result.stderr[-2400:]}")


def _camera_filter(motion: str, frames: int, width: int, height: int) -> str:
    """Zoom/pan overscanned original image, without creating intermediate PNGs."""
    steps = max(1, frames - 1)
    progress = f"on/{steps}"
    if motion == "push_in":
        zoom = f"1+0.13*{progress}"
        x = "(iw-iw/zoom)/2"
    elif motion == "pull_out":
        zoom = f"1.13-0.13*{progress}"
        x = "(iw-iw/zoom)/2"
    elif motion == "pan_left":
        zoom = "1.14"
        x = f"(iw-iw/zoom)*(1-{progress})"
    elif motion == "pan_right":
        zoom = "1.14"
        x = f"(iw-iw/zoom)*{progress}"
    elif motion == "still":
        zoom = "1.06"
        x = "(iw-iw/zoom)/2"
    else:
        raise EditorialRenderError(f"invalid motion: {motion}")
    y = "(ih-ih/zoom)/2"
    zoompan = f"zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s={width}x{height}:fps={FPS}"
    # Pre-crop to portrait, then overscan to allow smooth virtual-camera movement.
    return (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},scale={math.ceil(width*1.25/2)*2}:{math.ceil(height*1.25/2)*2},"
            f"{zoompan},setsar=1,format=yuv420p")


def render_scene(image: Path, target: Path, *, motion: str, seconds: float, quality: str) -> float:
    """Render a scene with a stable CFR, returns the frame-aligned duration."""
    if quality not in SIZES:
        raise EditorialRenderError(f"unsupported quality: {quality}")
    width, height = SIZES[quality]
    frames = math.ceil(seconds * FPS)
    target.parent.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-framerate", str(FPS),
          "-i", str(image), "-vf", _camera_filter(motion, frames, width, height),
          "-frames:v", str(frames), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
          "-preset", "veryfast", "-crf", "21", "-r", str(FPS), "-movflags", "+faststart", str(target)],
         timeout=2400)
    return frames / FPS


def join_scenes(clips: list[Path], lengths: list[float], target: Path, *, transition: float = TRANSITION) -> None:
    """Use FFmpeg xfade. Input lengths include trailing overlap except the last clip."""
    if not clips or len(clips) != len(lengths):
        raise EditorialRenderError("each scene must have a duration")
    if len(clips) == 1:
        raise EditorialRenderError("editorial videos require more than one scene")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for file in clips:
        cmd.extend(["-i", str(file)])
    filters = [f"[{i}:v]settb=AVTB,format=yuv420p[v{i}]" for i in range(len(clips))]
    accumulated = 0.0
    current = "v0"
    for index in range(len(clips) - 1):
        # Scene i contains *transition* seconds of trailing video past its
        # speech-driven timeline beat; its next scene begins at this offset.
        accumulated += lengths[index] - transition
        output = f"x{index}"
        filters.append(f"[{current}][v{index+1}]xfade=transition=fade:duration={transition:.3f}:"
                       f"offset={accumulated:.3f},format=yuv420p[{output}]")
        current = output
    target.parent.mkdir(parents=True, exist_ok=True)
    cmd.extend(["-filter_complex", ";".join(filters), "-map", f"[{current}]",
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                "-pix_fmt", "yuv420p", "-r", str(FPS), "-movflags", "+faststart", str(target)])
    _run(cmd, timeout=2400)


def compose(silent: Path, voice_wavs: list[Path], starts: list[float], captions: Path,
            destination: Path, *, seconds: float, language: str,
            music: Path | None = None, music_volume: float = 0.13) -> None:
    """Narration + bounded music ducking, subtitles and mobile-compatible encoding."""
    if not voice_wavs or len(voice_wavs) != len(starts):
        raise EditorialRenderError("voice files and starts are inconsistent")
    from .media import subtitle_style  # reuse existing subtitle safe-area policy
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(silent)]
    for voice in voice_wavs:
        cmd.extend(["-i", str(voice)])
    music_index = len(voice_wavs) + 1
    if music is not None:
        cmd.extend(["-stream_loop", "-1", "-i", str(music)])
    filters: list[str] = []
    for i, start in enumerate(starts):
        delay = round(start * 1000)
        filters.append(f"[{i+1}:a]adelay={delay}:all=1[v{i}]")
    voices = "".join(f"[v{i}]" for i in range(len(starts)))
    filters.append(f"{voices}amix=inputs={len(starts)}:duration=longest:normalize=0[voice]")
    if music is not None:
        # The soundtrack remains continuous but is attenuated under speech.
        filters.append("[voice]asplit=2[narration][key]")
        filters.append(f"[{music_index}:a]volume={music_volume:.3f},highpass=f=85[music]")
        filters.append("[music][key]sidechaincompress=threshold=0.025:ratio=6:attack=30:release=450[ducked]")
        filters.append("[narration][ducked]amix=inputs=2:duration=longest:normalize=0[mix]")
    else:
        filters.append("[voice]anull[mix]")
    filters.append("[mix]loudnorm=I=-16:TP=-3:LRA=10,alimiter=limit=0.65:attack=5:release=50:level=0,apad[aout]")
    # Subtitle file name is generated locally and cannot be controlled by storyboard JSON.
    style = subtitle_style(language)
    subtitle = f"subtitles={captions.name}:force_style='{style}'"
    cmd.extend(["-filter_complex", ";".join(filters), "-map", "0:v:0", "-map", "[aout]",
                "-vf", subtitle, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "veryfast", "-crf", "21", "-c:a", "aac", "-b:a", "160k",
                "-t", f"{seconds:.3f}", "-movflags", "+faststart", str(destination.resolve())])
    _run(cmd, cwd=captions.parent, timeout=2400)


def inspect_output(file: Path, *, quality: str, expected_seconds: float) -> dict:
    width, height = SIZES[quality]
    probe = subprocess.run(["ffprobe", "-v", "error", "-of", "json",
                            "-show_streams", "-show_format", str(file)],
                           capture_output=True, text=True, check=False, timeout=60)
    if probe.returncode:
        raise EditorialRenderError("final file ffprobe failed")
    parsed = json.loads(probe.stdout)
    streams = parsed["streams"]
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is None or audio is None:
        raise EditorialRenderError("MP4 must contain one video and one audio stream")
    if (video.get("width"), video.get("height"), video.get("codec_name")) != (width, height, "h264"):
        raise EditorialRenderError("video encoding or dimensions invalid")
    if audio.get("codec_name") != "aac":
        raise EditorialRenderError("audio encoding must be AAC")
    length = float(parsed["format"]["duration"])
    if abs(length - expected_seconds) > 0.5:
        raise EditorialRenderError(f"unexpected duration {length} vs {expected_seconds}")
    return {"width": width, "height": height, "fps": FPS, "seconds": round(length, 3),
            "video_codec": "h264", "audio_codec": "aac", "bytes": file.stat().st_size}
