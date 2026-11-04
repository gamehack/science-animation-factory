# Science Animation Factory

An independent, MIT-licensed, **no-paid-API** science animation pipeline.
It turns a **validated, declarative storyboard** into an original, portrait-format
Manim animation with local voiceover, burned-in English subtitles, and an MP4.

> **M1 / experimental:** The storyboard is supplied as JSON. Automatic topic
> discovery, research/fact-checking by an LLM, unattended retries, visual
> semantics QA, scheduling, and social publishing are **not implemented yet**.
> The first milestone is a reproducible end-to-end video render.

## Why another project?

Existing agent skills often give the language model the ability to write and run
arbitrary animation code. Our production direction is different:

1. An AI model will eventually output only a constrained `Storyboard` JSON.
2. The renderer accepts **known visual scene types**, never model-authored Python.
3. Measured TTS durations establish the video timeline before frames are rendered.
4. One-pass FFmpeg mixing and metadata QA produce a reviewable artifact.
5. The complete pipeline will eventually run as a restartable unattended job.

The current M1 repository does **not** depend on Manim Skill, Auto Pop-Sci,
Chalkboard, eduvids or Automated Video Generator. It uses Manim CE and Kokoro
as foundational open-source libraries, and FFmpeg as a system tool.

## Output contract

| Field | M1 setting |
| --- | --- |
| Genre | 2D explanatory science diagrams, not character cartoons |
| Language | `en-US` |
| Aspect ratio | 9:16 |
| Duration | 30–60 seconds |
| Resolution | `preview`: 360×640; `full`: 1080×1920 |
| Frame rate | 30 FPS |
| Format | H.264/AAC MP4 |
| Narration | Local Kokoro, `af_heart` |
| Cost | No paid AI, TTS, video or image API |

These outputs still consume local CPU, memory, disk and electricity. Kokoro's
model weights may be downloaded on first use; no paid service is required.

## Quick start (Ubuntu / Debian)

```bash
sudo apt-get install ffmpeg libcairo2-dev libpango1.0-dev pkg-config espeak-ng
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[all]'

# No model load, network request or rendering required:
science-factory validate examples/moon_orbit.json

# Lower-resolution real speech and video:
science-factory build examples/moon_orbit.json --voice kokoro --quality preview

# Only after inspecting the preview:
science-factory build examples/moon_orbit.json --voice kokoro --quality full
```

Manim also needs the operating-system dependencies appropriate to your Python
and Linux distribution; see the [official Manim installation guide](https://docs.manim.community/en/stable/installation.html).

To exercise the pipeline **without downloading a TTS model**, pass `--voice tone`.
This uses a locally generated 220 Hz diagnostic tone instead of human speech.
Tone jobs are marked `PREVIEW_ONLY` and **must not be published**.

```bash
science-factory build examples/moon_orbit.json --voice tone --quality preview
```

### Run the core tests

The schema, duration planning, captions and diagnostic audio tests use only
Python's standard library:

```bash
python -m unittest discover -s tests -v
```

## Storyboard JSON

See [`examples/moon_orbit.json`](examples/moon_orbit.json). A storyboard has:

- `title`, `language`, `target_seconds`;
- `sources`: HTTPS references for a future fact-checking stage;
- `scenes`: 3–12 ordered beats, each with `kind`, `title`, `narration`, `params`.

The scene allowlist is `orbit`, `comparison`, `wave`, `force`, `scale`, and
`particles`. An unknown key, unsupported scene type, multiline/markup text or
unrecognized parameter is rejected before Manim is started.

These scientific illustrations are **schematic, not physically to scale**.
An eventual fact-checking step must verify that a template's use does not
misrepresent the relevant mechanism.

## Files produced by each job

Each run gets its own immutable folder under `output/<timestamp>-<id>/`:

```text
manifest.json          status, source URLs, SHA-256, metadata QA, review frames
storyboard.json        normalized, validated input
render-plan.json       scene timings computed from measured WAV lengths
voice_00.wav ...       individual narration segments
captions.srt           phrase-level estimated subtitle timing
manim_media/           intermediate silent renders
scene_00_review.jpg    one midpoint still per scene
final.mp4              H.264, AAC, burned-in captions
```

The pipeline does **not** publish to Facebook or access a personal profile.
It emits files only. A later, separate publishing integration must be scoped
and authorized independently.

## What M1 QA actually checks

Checks include: input schema, source URL shape, supported scene types, measured
voice duration bounds, final resolution, H.264 format, exactly one audio and one
video stream, output size, and video duration alignment. Generated JPEGs enable
visual review.

**Not yet implemented:** optical overlap detection, scientific factual
verification, AI visual review, actual speech/caption word alignment, black-frame
detection, audio peak measurements, and retry/resume state transitions. Thus
`READY` means **technically encoded**, not scientifically or editorially approved.

## Roadmap

- **M1** (current): JSON → local TTS → Manim → FFmpeg → technical QA → MP4.
- **M2**: scheduled topic intake, cited research, free-model adapter, fact gates,
  storyboard generation, bounded retries, resumable job store, automatic rejection.
- **M3**: 20-topic unattended acceptance test, visual QA, resource profiling,
  1080×1920 quality iteration, and creator review queue.

## Open-source and licensing

Our application: MIT. Manim CE: MIT; Kokoro model: Apache-2.0. FFmpeg's license
depends on its build and components; check requirements before redistributing
its binaries. Source facts and any future third-party assets need independent
commercial-use checks. No external stock footage is used in M1.

This is an independent experimental project, not a production service.

