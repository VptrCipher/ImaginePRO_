# Five-second animation test

Generated and verified on 24 October 2026 using the real local application, not a pre-rendered animation passed off as AI output.

Project: **Claude-inspired · five-second motion test**. The raw fixture is a blank cream video plus locally synthesized narration. Codex generated structured decisions for three animated headline cards, captions and a supplied synthetic audio bed. The backend generated a lossless RGBA animation overlay, composited it onto the footage with output-timeline offsets, applied captions last, and exported the final MP4.

Final output: **5.000 seconds, 1920×1080, 30 fps, H.264/AAC**, three animated graphics and three caption cues. Full decode passed; audio/video stream duration difference is about 33ms. This measures stream duration alignment, not perceptual lip-sync accuracy. Delivery uses lossless intermediate video before one final lossy encode.

The full suite now passes **50 tests**. Motion tests cover all three template types, eased opacity changes, actual time-varying animation pixels, transparency outside the graphic, invalid template/code rejection, cancellation, output bounds and real overlay compositing. The frontend production build and TypeScript checks passed. Detailed decisions and checks are saved in `storage/animation-test-report.json`.

## What works with a supplied talking-head clip

- Local speech transcription and timed animated/static captions.
- AI-selected cuts, pause removal, best-effort filler removal, sequence edits and fixed punch-in zoom.
- Animated editorial headline cards, compact side callouts and speaker lower thirds.
- Cream/terracotta or dark graphic palettes; eased slide/fade and rotating accents.
- Color presets, volume changes, imported background music, title/end fades and verified MP4 export.
- The video/audio timeline remains simple. Graphics are approved render settings, not additional timeline tracks.

Example prompt: “Remove long pauses, preserve the meaning, add animated captions and a cream lower third using the speaker name I provide. Add two short side callouts for the main points without covering the face.” Review placement in the rendered preview; face position is not automatically tracked.

## What this test does not establish

No human talking-head footage was supplied for this request. The animation sample uses synthetic narration. It does not test a person's actual voice, face position, lip sync or recording quality. Existing natural-footage and audio tests are retained separately.

These graphics use three supported templates. Arbitrary illustrated scenes, generated characters, 3D animation, charts, face/object tracking, background removal and person cutouts are not implemented. Complex Claude-generated code/Remotion/Manim workflows remain separate upstream capabilities, not automatic features of this GUI.

Overlay limits are 12 entries, 0.3–10 seconds each, within a 60-second composition window. Captions, graphic content and story quality still need human review. Templates are inspired by a warm editorial aesthetic and are not an official Claude/Anthropic asset or affiliation.
