# Science Animation Factory

An independent, MIT-licensed, **no-paid-API** science animation pipeline.
It turns a **validated, declarative storyboard** into an original, portrait-format
Manim animation with local voiceover, burned-in English or Simplified Chinese
subtitles, and an MP4.

> **M1.3 / experimental:** Two research-linked topics now have manually
> reviewed bilingual JSON scripts and distinct visuals. Automated *new* topic
> discovery, LLM research/fact-checking, unattended retries, semantic visual
> QA, scheduling, and social publishing are **not implemented**.

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
| Genre | 2.5D schematic science animation with photographic celestial sprites |
| Language | `en-US`, `zh-CN` (separate storyboards, one shared rendering system) |
| Aspect ratio | 9:16 |
| Duration | 30–60 seconds |
| Resolution | `preview`: 360×640; `full`: 1080×1920 |
| Frame rate | 30 FPS |
| Format | H.264/AAC MP4 |
| Narration | Local Kokoro, `af_heart` (English) and `zf_xiaoyi` (Mandarin) |
| Cost | No paid AI, TTS, video or image API |

These outputs still consume local CPU, memory, disk and electricity. Kokoro's
model weights may be downloaded on first use; no paid service is required.

## Quick start (Ubuntu / Debian)

```bash
sudo apt-get install ffmpeg libcairo2-dev libpango1.0-dev pkg-config espeak-ng fonts-dejavu-core fonts-noto-cjk
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[all]'

# No model load, network request or rendering required:
science-factory validate examples/moon_orbit.json

# Lower-resolution real speech and video (use the same --job-id to resume a failed job):
science-factory build examples/moon_orbit.json --voice kokoro --quality preview --job-id moon-demo-01

# Chinese preview; uses Mandarin narration and Chinese fonts/subtitles:
science-factory build examples/moon_orbit.zh-CN.json --voice kokoro --quality preview

# A second independent science topic, using its own five visual primitives:
science-factory build examples/sound_vacuum.json --voice kokoro --quality preview
science-factory build examples/sound_vacuum.zh-CN.json --voice kokoro --quality preview

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

## Render English and Chinese together using GitHub Actions (no local setup)

The repository's **Render bilingual science demo** workflow uses GitHub's
standard Ubuntu runner and downloads the CPU-only PyTorch wheel, Manim,
FFmpeg and Kokoro. Choose a topic (`moon_orbit`, `sound_vacuum`, or `all`) and
the workflow builds English (`en-US`) and Mandarin (`zh-CN`) as separate jobs.
`all` is a four-job science-topic/language acceptance batch. The two versions
of each topic share the same visual vocabulary but have manually reviewed
wording and narration. No API keys or paid model services are required.

1. Open **Actions → Render bilingual science demo → Run workflow** on `main`.
2. Choose `topic=moon_orbit`, `topic=sound_vacuum`, or `topic=all`.
   Keep `quality=preview` for the first attempt (360×640). Select `full` only
   after successfully inspecting a preview.
3. The workflow launches two jobs per topic, up to two at a time.
   When they succeed, download artifacts called
   `science-<topic>-<language>-<runid>-<attempt>`.
4. Each artifact independently contains `final.mp4`, `captions.srt`,
   `manifest.json` and the scene review images. Neither is published.

The workflow also runs when renderer, samples, tests, or workflow files change
on `main`, using Moon previews for normal pushes. Add `[full-render]` to a push
commit message to render **both topics and languages** at 1080×1920, or use
`topic=all, quality=full` manually.

Dependency wheels are cached by `setup-python`; Kokoro model weights use a
separate, versioned GitHub Actions cache and are not placed in video artifacts.
For a **rerun of the same workflow run**, each topic/language has a stable Job ID.
The workflow downloads the previous attempt's one-day checkpoint artifact,
verifies SHA-256 outputs, and resumes from the last valid audio/visual/composition
stage. A newly dispatched workflow is a new job and does not reuse another
run's artifacts. Checkpoint artifacts include WAV segments, TTS cue data, the
silent Manim render, final MP4, manifest and review stills. They expire after
**one day**; copy any deliverable you want to retain.

The workflow is not scheduled and does not publish to any social account.
GitHub-hosted runner compute is free for this public repository; cache and
artifact storage remain separately subject to GitHub plan limits.

### Run the core tests

The schema, duration planning, captions and diagnostic audio tests use only
Python's standard library:

```bash
python -m unittest discover -s tests -v
```

## Storyboard JSON

See [`examples/moon_orbit.json`](examples/moon_orbit.json) and
[`examples/moon_orbit.zh-CN.json`](examples/moon_orbit.zh-CN.json), plus
[`examples/sound_vacuum.json`](examples/sound_vacuum.json) and its
[`Mandarin edition`](examples/sound_vacuum.zh-CN.json).
A storyboard has:

- `schema_version` (currently `1`), `title`, `language`, `target_seconds`;
- `sources`: HTTPS references for a future fact-checking stage;
- `scenes`: 3–12 ordered beats, each with `kind`, `title`, `narration`, `params`.

The scene allowlist includes `orbit`, `comparison`, `wave`, `force`, `scale`,
`particles`, `physics_vectors`, `throw_orbit`, `orbit_intro`, `orbit_recap`,
`sound_source`, `sound_medium`, `sound_vacuum`, `sound_receiver`, and
`sound_recap`. These are trusted, predefined diagrams; JSON parameters contain
only labels. An unknown key, unsupported scene type, multiline/markup text or
unrecognized parameter is rejected before Manim starts.

These scientific illustrations are **schematic, not physically to scale**.
An eventual fact-checking step must verify that a template's use does not
misrepresent the relevant mechanism.

### M1.1 — NASA-image-based celestial visuals

The `orbit` template uses transparent, photographic Earth and Moon discs
prepared from [NASA 3D Resources](https://github.com/nasa/NASA-3D-Resources).
The Moon's actual craters and Earth's land/ocean textures replace the former
flat circles. Atmosphere-inspired glow and a lightweight starfield add depth;
the gravitational arrow updates continuously to point from the orbiting Moon
toward Earth's center. This is still a **2.5D schematic**, not a physically
scaled three-body simulation or a GPU-based 3D renderer.

Both language versions use **identical visual assets**. The two small PNGs are
committed in `science_factory/assets/` and packaged with the application, so
video jobs do not depend on downloading external images. `assets/SOURCES.md`
records the primary sources and provenance. A separate one-time preparation
script can regenerate the discs and verify NASA Git blob hashes.

### M1.2 — camera language, physical explanations and mobile-safe subtitles

The Moon demo now renders the two explanatory beats using actual arrows and
trajectories, rather than generic rectangular comparison cards. The gravity
beat uses the same NASA-image-based Earth/Moon pair as the orbital scenes.

Each segment animates a gently drifting `MovingCameraScene` camera while its
own science motion continues; the camera returns to its original position
between segments. This bounded motion stays compatible with Cairo CPU
rendering, the existing 30–60-second speech timeline and the same JSON schema.

FFmpeg burns subtitles with a larger bilingual font, stronger contrast and
extra bottom margin for short-form mobile playback. The new templates and
subtitle rules have automated contract tests. A full-resolution bilingual run
also records real CPU runtime and artifact sizes. Video quality and scientific
meaning still require human review before publishing.

### M1.3 — pacing, visual variety, sound science, and A/V review

The six Moon beats now open with a closer tracking shot and close with an orbit
trail, breaking up the repetitive full-orbit diagram. Separate source, medium,
vacuum and listener drawings support a second science lesson. The sound-wave
curve is a **pressure-versus-position schematic**, not a depiction of the
individual molecules tracing transverse paths. The sound facts refer to
[NASA's explanation of mechanical sound waves](https://science.nasa.gov/ems/02_anatomy/).

Measured Kokoro audio controls each beat's duration; the old mandatory equal
45-second / six-scene pacing has been removed. Long *leading and trailing*
silence is cautiously trimmed. Subtitle cards use actual TTS chunk boundaries
when present, with approximate timing **within** each chunk. This is **not**
word-level forced alignment. Chinese captions are balanced into short
single-line cards so punctuation is not stranded on its own line. The audio mix uses loudness normalization; final encoded audio is measured with\nFFmpeg ebur128 and must meet an integrated loudness target of -16 LUFS ±2 LU\nand a true-peak ceiling of -1 dBFS. The pipeline also
the final checker requires AAC, flags extended black frames and excess silence,
and exports three QA stills per scene (entrance, middle, exit). The final
editorial/scientific review remains a human responsibility.

## Files produced by each job

Each run gets its own immutable folder under `output/<timestamp>-<id>/`:

```text
manifest.json          technical QA, provenance, hashes, versions and review frames
job-state.json          atomic stage state and attempt/error metadata
storyboard.json        normalized, validated input
render-plan.json       scene timings computed from measured WAV lengths
voice_00.wav ...       individual narration segments
captions.srt           TTS-chunk-anchored phrase timing (not word-aligned)
manim_media/           intermediate silent renders
scene_00_opening_review.jpg / middle / closing (18 stills for six scenes)
final.mp4              H.264, AAC, burned-in captions
```

The pipeline does **not** publish to Facebook or access a personal profile.
It emits files only. A later, separate publishing integration must be scoped
and authorized independently.

## What M1 QA actually checks

Checks include: input schema, source URL shape, supported scene types, measured
voice duration bounds, final resolution, H.264/AAC format, exactly one audio
and one video stream, output size, duration alignment, FFmpeg black-frame and
long-silence scans, and 18 sampled JPEGs for human visual review.

**Not yet implemented:** optical overlap detection, automatic scientific factual
verification, AI visual review, true word-level subtitle alignment, measured
true-peak rejection, and retry/resume state transitions. Thus
`READY` means **technically encoded**, not scientifically or editorially approved.

## Roadmap

- **M1** (complete): JSON → local TTS → Manim → FFmpeg → technical QA → bilingual MP4.
- **M1.1** (complete): NASA-image-based Earth/Moon visuals, atmospheric glow,
  correct moving gravity vector, reusable offline asset package.
- **M1.2** (complete): bounded 2.5D camera drift, richer explanatory
  templates, improved mobile subtitle positioning and 1080×1920 acceptance run.
- **M1.3** (implementation): voice-driven pacing, distinct shots, TTS-chunk
  subtitle cues, silent-edge trim, technical A/V gate, three samples per beat,
  two topics × two languages, pip caching and batch Actions acceptance.
- **M2**: scheduled topic intake, cited research, free-model adapter, fact gates,
  storyboard generation, bounded retries, resumable job store, automatic rejection.
- **M3**: 20-topic unattended acceptance test, visual QA, resource profiling,
  production-grade quality iteration and creator review queue.

## Open-source and licensing

Our application: MIT. Manim CE: MIT; Kokoro model: Apache-2.0. FFmpeg's license
depends on its build and components; check requirements before redistributing
its binaries. Source facts and any future third-party assets need independent
commercial-use checks. No external stock footage is used in M1.

See [Infrastructure Contract](docs/INFRASTRUCTURE.md) and [M1 Architecture](docs/ARCHITECTURE.md).\n\nThis remains an experimental project; automatic scientific/editorial approval and\nfull failed-render resume are not yet production-ready.

