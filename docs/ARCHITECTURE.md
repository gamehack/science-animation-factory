# M1 architecture and decisions

## Execution path

```text
storyboard.json
   |  schema.py — strict allowlist, no executable scene code
   v
voice.py — Kokoro TTS once per narration beat (or tone diagnostics)
   |  sample-accurate WAV lengths
   v
timeline.py — per-scene start/duration, phrase-level SRT
   |
   +--> render_scenes.py — trusted Manim visual builders -> silent MP4
   |
   +--> media.py — one FFmpeg audio mix + subtitle burn
                      |
                      v
                    final.mp4
                      |
                      v
             ffprobe metadata QA + review JPEGs
                      |
                      v
                  manifest.json
```

**Core invariant:** `scene.start` is the sum of durations before it. Audio is
placed at that absolute time, and the corresponding Manim segment consumes
exactly `scene.duration`. Audio is never individually encoded as AAC per scene.

**Threat boundary:** A model can choose only scene templates and text/parameters
accepted by `schema.py`; it cannot inject imports, Python snippets, file paths,
shell commands or tool names. Manim runs only developer-owned code. Future
external data fetches require SSRF-safe URL and redirect validation.

**Testing boundary:** Unit tests do not need heavyweight render dependencies.
Full visual/video QA needs a machine with Manim, Kokoro and FFmpeg installed.
The CPU/RAM/runtime of the target machine must be measured before scheduling.

## Infrastructure additions (M1.4 foundation)\n\n- JobStore persists monotonic stage state with atomic file replacement.\n- Every completed stage can record output hashes; cache helpers use SHA-256.\n- TTSProvider and Renderer protocols define explicit extension points.\n- QualityReport distinguishes technical pass from visual, semantic and factual\n  approval. Unknown checks cannot silently pass.\n- Build manifests record Python, Manim, Kokoro, NumPy and FFmpeg versions.\n\nThe CLI accepts a stable --job-id. Re-running the same input/configuration resumes\nfrom the last verified stage: audio WAVs and TTS cue records are hash-checked,\ncompleted silent renders are reused, and an existing final MP4 is reused when its\nchecksum matches. A changed input/configuration is rejected for the same job ID.\nIf a checkpoint output is missing or corrupt, that stage and all downstream stages\nare invalidated and rebuilt. A render interrupted before a complete silent MP4 is\nproduced must be rendered again; Manim does not expose a portable frame-level resume.\n\n## M2 decisions still open

1. A scientific source allowlist and evidence/claim schema.
2. LLM adapter with free-only model routing, request quotas and no paid fallback.
3. Persistent SQLite job queue with idempotency, stage checkpoints and retries.
4. Independent visual QA (layout checks, deterministic media checks, optional vision).
5. Review-only output interface; any publishing API is out of scope.

No requirement to use an existing multi-agent skill or the user's other agent
bridges as the runtime. Future deployment must be authorized separately.

