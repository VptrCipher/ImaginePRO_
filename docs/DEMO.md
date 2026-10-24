# Verified demo and current limits

Validated on Windows on 24 October 2026. These are real processing runs, not simulated agent responses. Raw/generated media and machine-specific job reports are kept in Git-ignored storage/.

## Results

- The one-click Windows build passes **80 automated tests** and has an actual desktop/Start menu launcher at `ImaginePro.exe`. A cold start from Downloads with only Windows System32 on PATH started the windowless server and connected to the existing Codex ChatGPT account. Two repeated launches reused the same server PID. Double-clicking the installed desktop shortcut opened the working editor in ordinary Chrome; the launch receipt confirms `opened_browser: true`. Screenshot: `storage/qa/one-click-editor.png`.
- That windowless server generated a fresh **three-second narrated 1920×1080 kinetic typography clip** using real Codex, Windows narration, local Whisper, Canvas and FFmpeg, and placed it on the timeline. `storage/desktop/generation-verification.json` records the result. Exact comparisons confirm all **12 preexisting projects, 21 asset records/files and 3 saved reference styles** are unchanged; see `storage/desktop/preservation-verification.json`. The extra project is the new launcher verification project.

- The current direct-generation build passes **76 automated tests** (including the 26 original upstream tests) and a fresh Next.js production build. New coverage includes original scene validation, centered-text bounds, direct rendering/timeline placement, cancellation/failure recovery and the AgenticOrg integration's success/authentication/scope/secret boundaries.
- A real browser run imported a transcript, selected Hand-drawn Cartoon, and pressed Enter. Codex created an original robot/star illustration with 30 elements and acting poses. The **five-second 1080×1920 narrated MP4** fully decoded and appeared on the editable timeline without a separate approval. Full closing text and sampled motion were visually checked. Output: `storage/exports/ImaginePro-robot-demo.mp4`; proof: `storage/qa/generated-timeline.png`.
- A separate real speech-footage run produced a **four-second 1920×1080 MP4**, preserving the source test picture/audio while adding 17 illustration elements, two Vox-style callouts and three caption cues. The first Codex attempt failed; an explicit retry completed. Output: `storage/exports/ImaginePro-footage-demo.mp4`. This synthetic speech/color-pattern fixture validates the media pipeline; it is not evidence of face tracking or a real talking-head placement review.
- Both direct-generation outputs have matching audio/video stream durations, non-silent audio and full decode verification. The measured report is `storage/generation-workflow-report.json`. These checks do not claim a listening review.
- **Enhance Director** is a separate Pine Labs AgenticOrg button. Its API wiring and failure handling pass contract tests with a mocked provider. A real click returned **HTTP 401** for the supplied hackathon credential, leaving the original prompt intact. Live enhancement is not verified until the issued key/deployment is confirmed. No Codex fallback disguises that failure. The key is stored with Windows DPAPI under ignored storage and is not exposed in the browser, source or error messages.

- The later five-second animation test passes the complete **50-test** suite and a fresh real Codex → local transcription → animated overlay → preview/export run. See [ANIMATION-TEST.md](ANIMATION-TEST.md). Template motion graphics are now supported without adding timeline tracks.

- The full initial **42-test suite** passed. Five follow-up renderer regression checks passed after simplifying the UI and improving final-export encoding, including a new lossless-intermediate test. These cover the original 26 upstream tests and new project persistence, revision conflict, caption mapping/escaping, asset scope, URL rejection, local-request protection, read-only skill handling, restricted runtime configuration, real queue lifecycle, range downloads, music mixing, cross-project profile reuse, 720p render and portrait 1080p export tests.
- The Next.js production build and TypeScript checking passed.
- Final API/database/queue checks passed: 40 tests, with the four already-verified renderer cases excluded from that follow-up run. SQLite transaction contexts now explicitly close their connections, including on error, avoiding retained Windows database handles.
- The first P0 proof used genuine Codex JSON decisions to cut an eight-second source to four seconds, grade it, add a title/fade, render H.264 and fully decode it.
- The A–G acceptance run used real local Whisper words, genuine Codex plans and actual FFmpeg output. A 17-second speech fixture became a 9.2-second edit with four cuts and 14 animated caption cues. The 1920×1080 export fully decoded; audio/video stream durations differed by approximately 23ms.
- Manual split, reorder and trim produced another real preview; save/reopen preserved the exact timeline.
- The original manually installed video-use skill was discovered, selected and used by a real planner call. No skill files were generated or overwritten.
- A video reference generated clean.md from seven sampled frames and was applied to different target footage. A reference image generated its own profile, explicitly marked temporal/audio characteristics unknown, accepted human Markdown edits and guided another render.
- A public direct URL to MDN's CC0 flower video was retrieved and analyzed into clean.md. A loopback URL was rejected. Automated tests additionally reject link-local, credential-bearing, non-HTTP and nonstandard-port inputs.
- A follow-up natural-footage demo used the permitted CC0 flower clip with a synthetic speech track, reused a saved style across projects and preserved the target title **SPRING STORY**. It produced a **9.6-second, 1920×1080 H.264/AAC MP4**, with **14 animated caption cues**, full decode verification and approximately **3ms audio/video duration difference**. The planner retained target wording rather than copying the reference title.
- Browser checks covered project creation, file import, adding media to the timeline, trimming, undo/redo, genuine AI plan generation, approval, playing the verified output, exporting and downloading it. The downloaded MP4's SHA256 matches the verified export. The project reopened after a server restart. A screenshot of the simplified video/audio timeline is saved as `docs/editor-preview.png`.

The detailed source ranges, job IDs, dimensions, durations and checks are in `storage/acceptance-report.json`. The final natural demo is in the **Spring story · creator demo** project. Generated media is not committed to Git.

The timeline is deliberately simple: video with its source audio below, plus cut, delete, trim and reorder controls. Generation places a real MP4 clip on it automatically. Caption/title/motion-graphic effects are composited by the renderer and do not need extra timeline tracks. Merely viewing or moving clips in the UI does not recompress the source or degrade its pixels.

## Reproduce

With the backend running:

```powershell
.\scripts\make-demo.ps1
.\.venv\Scripts\python.exe -X utf8 scripts\foundation_demo.py
.\.venv\Scripts\python.exe -X utf8 scripts\acceptance_demo.py
.\.venv\Scripts\python.exe -X utf8 scripts\natural_demo.py
.\.venv\Scripts\python.exe -X utf8 scripts\generation_demo.py
.\.venv\Scripts\python.exe -X utf8 scripts\footage_generation_demo.py
.\.venv\Scripts\python.exe -X utf8 -m pytest app_tests tests -q
```

The foundation script runs its own database initialization and should be run before other jobs start. It uses real Codex access. The acceptance/natural demos call the already-running API and do not reset the queue. Running them consumes normal Codex subscription capacity and may download public model weights or the explicitly permitted CC0 sample. They create new demo projects rather than changing user projects. The Windows speech-fixture helper needs System.Speech; other platforms can provide a small speech WAV at .fixtures/speech.wav.

Reference footage attribution: [MDN CC0 flower sample](https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4). The speech narration and test-pattern footage are locally synthesized test fixtures.

## Honest limitations

- This is a local, single-owner MVP. It is not deployed publicly and has no multi-user authentication/billing/isolation. Only one media worker runs concurrently.
- Codex CLI is the working video-generation adapter. Settings includes general provider configuration fields, but Kiro/direct API video execution is not implemented. Enhance Director is a separate AgenticOrg integration whose live credential currently returns 401. The CLI uses its supported installed account and limits.
- The GUI supports original generated 2D paths, groups, characters, typography and motion poses through a bounded scene graph, plus the older raster title/caption/graphic presets. General Remotion/Manim/HyperFrames code, face/object tracking, photorealistic synthesis and unrestricted model-generated executable code are not run. Original upstream tools/skills are retained separately.
- Transitions are hard cuts plus final fade; cross-dissolves, beat-synchronized cuts, L/J cuts and speed ramps are not implemented. Zoom is a fixed per-clip crop rather than animated camera tracking.
- Local Whisper diarization is unavailable. ASR can misrecognize words and normalize fillers; filler removal is best effort and requires review. Captions are auto-generated from ASR and are not individually editable as timeline objects.
- Reference analysis uses sampled frames, measured colors and model observations. Exact typography/OCR, audio/music identification, beat alignment and detailed temporal animation classification are unimplemented and marked unknown. Styles influence supported editing parameters; they are not a claim of exact stylistic reproduction.
- Direct public media URLs are supported. Platform watch pages, authenticated downloads, DRM and public-source scraping adapters are unavailable. DNS/private-address protection is implemented, but this does not replace a production egress sandbox.
- Preview uses 720p, 30 fps and fast encoding. Final export uses 1080p, 30 fps, H.264 CRF 20 and AAC. If captions/title/fade require compositing, intermediate graded clips use lossless H.264 before one lossy delivery encode. Without those effects, encoded segments are copy-concatenated/remuxed directly. Output delivery is not lossless; effects/resizing require encoding, independently of whether a timeline is displayed. There is no avoidable encode step just for putting clips in the UI. Lossless intermediates can use more disk space and are retained with the job.
- Direct generation uses final one-pass loudness normalization; manual export measures the mix and uses two-pass normalization when possible. Perceptual listening, transcript accuracy and story quality still need human judgment. Automated duration alignment checks cannot prove perfect lip sync.
- Cancellation is immediate/cooperative for worker subprocesses and between ASR segments; native model loading/inference may finish its current operation first. Queue recovery marks interrupted jobs failed for an explicit retry.
- Undo/redo history is session-local. Saved timeline revisions and original assets persist; a full historical revision browser is not implemented. Generated job intermediates are retained and disk cleanup is manual.
- Native source preview depends on browser codec support. Rendered preview/export normalizes to the verified browser-compatible format. iPhone rotation/HDR inputs and uncommon codecs need additional real-device coverage; upstream orientation tests remain intact.
- FFmpeg build licensing varies; the installed local GPL build and libx264 are not redistributed in the repository. Other-platform installation steps are documented but Windows is the verified environment.
