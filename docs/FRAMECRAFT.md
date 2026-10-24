# Default Framecraft template

The user's `Framecraft.md` is bundled unchanged at
`templates/framecraft/Framecraft.md`. It appears first in Styles as a **Default
template**, is selected when a project opens, and can be inspected read-only.
Reference `clean.md` profiles remain editable and manual SKILL.md discovery is
unchanged. No SKILL.md is generated from the attachment.

The Markdown is creative guidance supplied to the edit planner and original-scene composer. Its example scripts
are never executed. Supported operations still come from the validated schema.
The older bundled `framecraft` preset adds a full-frame handmade print bloom with drawn
orbits, staggered petal plates, misregistration, halftone, paper fibres, seeded
grain, a breath, a payoff and a closing poster held for the last second.

For that older preset, use one scene per edit, 3–10 seconds, with `text` for the closing headline and
`detail` for the subtitle. Select portrait or landscape using the existing export
settings. It replaces the picture within its window, so the planner uses it for
standalone animation on a blank source. Talking-head edits use compact callouts
and lower thirds while preserving the person. The timeline stays video/audio
only. This preset is a curated illustration. The default **Generate** flow now
creates original subject-specific paths, character parts and animated poses with
the Framecraft style as guidance, without a blank source carrier. It does not run
generated JavaScript or provide face/object tracking.
If a manual trim/delete leaves less than three seconds for a Framecraft scene,
the UI removes that scene from the shortened edit, retaining valid clip cuts.

Node 22.12+ and installed Chrome/Edge are required. `scripts/start.ps1 -Install`
installs pinned `puppeteer-core`; it does not download a browser. For manual setup:
`npm ci --prefix backend/framecraft`. `FRAMECRAFT_BROWSER_PATH` can select an
installed browser executable. Official implementation reference:
[Puppeteer launch options](https://pptr.dev/api/puppeteer.launchoptions).

Each job uses a fresh browser profile, bundled local HTML, a restrictive page CSP
and request interception blocking all page requests. Only typed text, duration
and dimensions are passed as serialized data. Frame capture is pure and seeded;
random-access repeat-frame checks verify determinism. Generated graphics are
encoded to lossless RGBA PNG video, then composited with one final lossy encode.
Cancellation on Windows stops the owned renderer process tree. This browser is
a local media engine, independent of the user's open browser sessions.

The shared timeline drives a deterministic 48 kHz stereo score: harmonic plucks,
inharmonic bells, a detuned pad, filtered-noise whooshes, an impact and short stereo
delay taps. Non-finite/silent output is rejected. The score is mixed at a lower
level when source audio is present, then the existing final two-pass loudness
normalizer measures the actual mix. A source containing any audio is treated
conservatively as possible speech; there is no semantic speech-based ducking.

Run `.venv/Scripts/python.exe scripts/framecraft_lookdev.py` for eight stills
before full video. Inspect `.fixtures/framecraft/lookdev.jpg`. Run
`.venv/Scripts/python.exe scripts/framecraft_demo.py` with the server running to
create a four-second source carrier, use the genuine Codex planner with the
default template, approve, preview, export and verify the result. It saves a
shareable MP4 to `storage/exports` and Downloads, plus a measured report at
`storage/framecraft-test-report.json`. The style and beat sheet are in
`templates/framecraft/STYLE.md` and `CONCEPT.md`.

The demo's score is synthesized and numerically checked; it has not been
listened to. Full decode, AV duration, resolution and sampled-frame checks do not
replace a viewer's aesthetic judgment.
