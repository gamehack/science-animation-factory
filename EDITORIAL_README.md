# Editorial short-form rendering (v2 beta)

The original `science-factory build` and Storyboard v1/Manim science paths remain unchanged.
This adds an isolated, CPU-only storyboard v2 adapter for illustrated historical micro-documentaries.
The asset paths are *local paths within an explicitly approved folder*; no URLs, Python snippets,
or model-generated commands are executed by the renderer. Every scene must declare visual rights
and provenance; music, when used, must declare rights and credits.

## Usage

```bash
science-factory validate-editorial examples/eas_kodak_1888.json
science-factory build-editorial examples/eas_kodak_1888.json \
  --assets-dir examples/assets/eas --voice kokoro --quality preview --job-id eas-kodak-1888
# When preview quality and editorial review are acceptable, use another stable job-id:
science-factory build-editorial examples/eas_kodak_1888.json \
  --assets-dir examples/assets/eas --voice kokoro --quality full --job-id eas-kodak-1888-full
```

Outputs: `final.mp4`, `captions.srt`, `manifest.json`, `qa.json`, voice WAVs and intermediate video.
`manifest.json` always states `content_review: REQUIRED` and `can_publish: false` until
an external authorized editorial approval process occurs; *technical readiness is not publish approval*.
The optional `--voice tone` output is diagnostic only and must never be uploaded as real content.

Rendering uses FFmpeg's Ken Burns virtual camera (`push_in`, `pull_out`, `pan_left`,
`pan_right`, `still`) and xfade between illustrations, real Kokoro TTS or diagnostic
tone, voice-paced subtitles, licensed music with automatic voice ducking, audio
normalization, and H.264/AAC faststart MP4. `preview`=360x640, `mobile`=720x1280,
`full`=1080x1920, all 30 fps.

This adapter intentionally does **not** solve independent art generation, factual
review, motion segmentation, human music selection, or Facebook/Instagram/Threads publishing.
The Kodak CI example uses *four programmatically drawn technical placeholders*,
only to test the pipeline. A production EAS episode must replace
these with four or more original distinct scene illustrations before publishing.

### Scope and infrastructure

- GitHub Actions build is manual (`render-editorial.yml`); no automatic publication.
- Public standard GitHub-hosted Ubuntu runners can render without paid image/video/TTS API.
  Storage, runner quotas, and externally generated illustration costs must still be monitored.
- Existing science demo workflow and dependencies are unchanged.
- Asset files and soundtrack license metadata belong to the EAS editorial team.
