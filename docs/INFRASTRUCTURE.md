# Video production infrastructure contract

## Product boundary
Science Animation Factory is a topic- and publishing-platform-independent
video production engine. Science explainers are its first workload. Research,
storyboard authoring, rendering, quality review, artifact retention and
publishing are separate concerns.

## Execution and job state
GitHub Actions is the MVP worker. Each job has immutable input/configuration
and an output directory. The filesystem JobStore persists atomic job-state.json
with monotonic stages: created, validated, audio, visuals, composed,
technical_qa, ready. Stage hashes must be verified before reuse. A remote queue
can replace this implementation without changing the job contract.

## Providers
science_factory.providers defines TTSProvider and Renderer protocols.
Provider selection is explicit. Default Kokoro and Manim remain local. Every
provider exposes name and version. No implicit network or paid fallback.

## Quality policy
Technical encoding success is not editorial/scientific approval. Unknown
visual, semantic or factual checks route to CONTENT_REVIEW_REQUIRED. READY
means technical checks only. Publishing remains a separate authorized adapter.

## Cache policy
Dependency cache is package-manager cache keyed by OS/Python/lockfile.
Model cache keys include immutable model revision and checksums. Stage cache
keys include input/configuration hashes and verified output checksums.
Artifacts are delivery outputs, not cache or task database.

## Reproducibility and security
Record storyboard/configuration hashes, Python, Manim, FFmpeg, TTS model,
renderer versions, quality profile, output hashes and timestamps. Storyboards
remain declarative data; never execute model-authored Python. Reject invalid
source URLs. Restrict workflow permissions. Pin third-party Actions to full
commit SHAs before production use. Use per-run concurrency groups and bounded
retries only for transient failures.

## Roadmap
M1.4: durable stage state, cache primitives, reproducible config and review states.
M1.5: provider interfaces, renderer adapters, versioned storyboard protocol.
M1.6: forced alignment, visual/layout QA, measured audio QA and semantic review.
M2: research intake, evidence ledger, fact-checking and storyboard generation.
M3: queue service, multi-project tenancy, resource/cost telemetry and publishing adapters.
