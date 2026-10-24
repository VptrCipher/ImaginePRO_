# Installation and use

## Requirements

Use Python 3.12, Node.js 22.12 or newer, installed Chrome or Edge, a modern FFmpeg/FFprobe build containing libx264, libass and standard audio filters, and a Codex CLI installation. Tested here with Node 25.9, Codex CLI 0.163.0-alpha.10.2 and FFmpeg 9.0.2 on Windows. The app uses documented `codex exec`, strict output schemas and saved authentication, with installed-version feature flags to disable tools. Older CLI versions may need flag compatibility updates; do not bypass sandboxing to resolve a flag error.

On Windows, FFmpeg can be installed with:

```powershell
winget install --id Gyan.FFmpeg --exact --accept-package-agreements --accept-source-agreements
```

Restart your shell after installation. The app also finds the normal Gyan winget package path in an already-running session. Alternatively export FFMPEG_PATH and FFPROBE_PATH to exact executable locations. On macOS/Linux install FFmpeg using your normal package manager.

Install Codex through its official installation instructions, then run `codex login` once and select ChatGPT account authentication. `codex login status` should report ChatGPT. Credentials stay in Codex's supported credential store; the application never reads, copies or embeds them. Account eligibility and usage limits still apply. Transcripts, prompts, skill instructions and sampled reference contact sheets are sent to Codex for planning; speech transcription itself runs locally.

Official references: [Codex authentication](https://learn.chatgpt.com/docs/auth), [noninteractive execution](https://learn.chatgpt.com/docs/non-interactive-mode). Kiro's [headless mode](https://kiro.dev/docs/cli/headless/) requires its own supported authentication, including KIRO_API_KEY where applicable. The Kiro adapter is deliberately marked unavailable rather than presenting an untested provider as working.

## Windows launch

```powershell
cd 'C:\AI Builder\video-editor'
.\scripts\start.ps1 -Install
```

Subsequent starts on this installation: double-click **ImaginePro** on the desktop or in the Start menu. `ImaginePro.exe` starts a windowless background server, verifies the Codex account and opens the editor automatically. Existing CMD aliases forward to that executable. Keep the application folder in place. The [desktop guide](DESKTOP.md) covers logs and rebuilding the launcher.

For development, run `scripts/start.ps1` in a terminal. Use `scripts/start.ps1 -Build` after changing frontend code; Ctrl+C stops this foreground server. No terminal interaction is needed for everyday editing, generation, reference analysis or export.

The first local Whisper job downloads the selected model (base by default, roughly 150 MB). The progress message announces this. Later jobs reuse model weights and a SHA256/model-keyed word cache. Internet access is needed for the initial download and for Codex requests. No Hugging Face token is required for the public model.

Faster-Whisper 1.2.1 is incompatible with PyAV 19's removal of metadata_errors. `requirements-app.txt` pins the tested PyAV 16.1.0 rather than patching installed libraries. See the [upstream issue](https://github.com/SYSTRAN/faster-whisper/issues/1589).

## Other platforms / manual setup

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-app.txt
cd frontend
npm ci
npm run build
cd ..
npm ci --prefix backend/framecraft
python -X utf8 -m uvicorn backend.main:app --host 127.0.0.1 --port 8765 --no-access-log
```

The application is tested on Windows; other-platform setup is provided but has not been verified in this build. For development, run the API on 8765, then `npm run dev` in frontend and open 127.0.0.1:3000. Next's development-only rewrite proxies /api. Production serves Next's static export and FastAPI from the same origin on 8765.

Optional environment variables are documented in `.env.app.example`. Export them before launch; this example file is not automatically loaded. The original `.env.example` and ElevenLabs `.env` behavior remain unchanged for standalone upstream helpers. To use those helpers' filmstrip/waveform utilities, also install the original upstream dependencies with `pip install -e .`.

## Generate a video

1. Open ImaginePro and create or select a project.
2. Import video/audio, upload TXT/SRT/VTT, or click **Paste a transcript**. You do not need to create a blank source video or manually add a clip first.
3. Choose a style and aspect ratio. Describe the story, pacing, edits and animation in the prompt.
4. Press **Enter** or click **Generate**. Shift+Enter inserts a line break. The app transcribes speech locally, asks Codex to direct the edit and draw original scenes, then renders the picture, voice and sound.
5. The verified 1080p video appears on the timeline automatically. Play it, download the finished MP4, or use Cut/Delete and the other manual controls.

For a transcript-only cartoon, try: “Make a five-second hand-drawn cartoon of a small robot discovering a star. Keep the narration and end with Small sparks. Big ideas.” For footage, try: “Keep the speaker visible, remove long pauses, add pop captions and illustrate two key points with compact animated callouts.” Face tracking is not implemented, so review placement.

Transcript narration uses Windows System.Speech. On other platforms, import a recorded voiceover. Standalone animated generation supports up to one minute; edited footage supports the existing three-minute timeline limit. Source upload limits remain 500 MB, five minutes and 4K. Text imports are bounded to 20,000 characters. Longer jobs take more processing time and disk space.

**Settings** contains Provider, API key, Model and Base URL fields. The active execution provider is Codex with its supported ChatGPT login. These fields do not switch execution providers or persist secrets; Kiro/direct API execution is a separate adapter task.

### Enhance Director with Pine Labs AgenticOrg

Type a video prompt and click the separate **Enhance Director** button. The enhanced text replaces the prompt, with Undo available. It does not start generation; Enter/Generate remains the next step. An enhancement failure preserves the original text.

The AgenticOrg section in Settings saves its own API base URL, key, company ID and optional director agent ID. Use the deployment issued with your hackathon key. A single authorized company can be discovered automatically; multiple companies require an explicit ID. The app reuses or creates an `imaginepro_director` agent with no authorized tools or connectors. If workspace policy requires activation approval, complete that process in AgenticOrg; the app does not bypass it. Authentication must work before agent setup can proceed. The current supplied credential returns HTTP 401, so the hackathon organizers need to confirm its deployment or reissue it before live enhancement can be verified.

On Windows, the key is encrypted with owner-bound DPAPI and saved under ignored `storage/secrets/`. It is never returned to the browser. Alternatively export `AGENTICORG_API_KEY` and the other documented variables before launch. Only the prompt, selected style and broad media types go to enhancement; video files and source transcripts are not uploaded by this button. Video generation remains connected to Codex independently.

Integration contract references: [AgenticOrg API documentation](https://app.agenticorg.ai/docs/api-sdk-mcp), [official SDK HTTP client](https://github.com/mishrasanjeev/agentic-org/blob/main/sdk/agenticorg/client.py), and [chat endpoint](https://github.com/mishrasanjeev/agentic-org/blob/main/api/v1/chat.py). Deployed versions and permissions can differ.

## Manual editing and export

1. Create a project with the plus button next to the project selector.
2. Drop video/audio/images onto the media import area or browse. Input limits: 500 MB, five minutes per video/audio source and 4K video. Portrait and landscape H.264/AAC MP4 are the verified outputs. Upload conversion/ingestion fails clearly for invalid media.
3. Click a video's Add button to add it to the timeline, or ask AI to select from imported videos directly.
4. Describe the result, for example: “Remove long pauses and fillers, preserve the meaning, add clean captions, and make a portrait reel.” Optionally select an installed skill/reference profile.
5. Press Enter to generate automatically. The completed output becomes one editable clip; original imported assets remain in the media library. The older explicit plan/approval API remains available for compatibility.
6. Play the rendered preview. Source playback immediately follows clip ranges and sequence; the UI explicitly labels it as source playback until effects have been rendered.
7. The timeline shows video with its source audio below. Select a clip to change In/Out times, fixed zoom and volume. Cut at the playhead, delete a selected clip, drag to reorder, or use left/right buttons. Undo and redo work during the current editing session. Edits autosave; project changes use revision checks to prevent stale overwrites. Reopen from the selector to recover a saved project. Captions, titles and animated overlays are renderer effects, so they do not require extra timeline tracks.
8. Click Render preview after manual changes. Caption/color/title/music effects are included in that verified MP4.
9. Open Export video, set landscape/portrait, grade, caption mode, uploaded music, optional title and end fade. Render 1080p export, then download from the ready export or Activity. Old rendered files remain available in Activity; they are labeled by job rather than silently replacing the current revision.

## Manually installed skills

No automatic SKILL.md creation is performed. Keep manual skills in one of the discovered locations:

- The original repository SKILL.md and `skills/*/SKILL.md`.
- Project `.agents/skills/<name>/SKILL.md`.
- User `~/.agents/skills/<name>/SKILL.md` or `$CODEX_HOME/skills/<name>/SKILL.md` (defaults to ~/.codex/skills).
- Additional skill-root directories listed in VIDEO_EDITOR_SKILL_DIRS (`;` separated on Windows, `:` elsewhere).

Each skill directory is read without changes. The selected text and a list of supporting Markdown resources are supplied to the planner. Supported instructions can affect decisions; arbitrary skill scripts, shell snippets and external animation engines are not automatically executed. Helpers needed by the implemented operations are invoked by the backend adapter. The original video-use CLI workflows remain available separately.

## Reference styles

Open Reference, upload one video or up to eight images, or import a direct public HTTP(S) media URL you have permission to use. Platform watch pages, authentication, DRM, private/internal network addresses, nonstandard ports and excessive redirects are unsupported. Upload a permitted local file as the fallback. Each redirect is revalidated and the connection is pinned to a public IP to avoid DNS rebinding.

Select reference assets and click Analyze & create clean.md. Video analysis uses FFmpeg scene changes, shot midpoints, periodic/transition-adjacent samples and a maximum of 20 frames. Images use at most eight bounded samples. The model receives a contact sheet, measured palette/brightness/saturation, timestamps and stream metadata. It distinguishes measurements, visual estimates and unknowns. Music, beat alignment and precise animation behavior are not inferred from images. Audio is not semantically analyzed.

Profiles are saved to `storage/styles/reference_<id>/clean.md` with metadata.json, sampled_frames/ and contact_sheet.jpg. Saved profiles are available across this local owner's projects. In Styles, View lets you inspect and edit a reference profile; Save clean.md persists human changes. Manual SKILL.md text is read-only. Select the saved profile before generating; target-specific decisions and illustrations are validated before rendering.

## Troubleshooting

- **Codex job fails:** check Settings, `codex login status`, account availability and network access. Re-run `codex login` through the official flow if necessary. No API-key fallback is silently enabled.
- **Model download or transcription fails:** allow access to the public Hugging Face model host, retry, and confirm PyAV 16.1.0 and faster-whisper are installed in the same .venv as the backend. CPU transcription can take time. Progress/cancellation during model loading takes effect after the native loading call returns.
- **FFmpeg missing/filter unavailable:** set executable paths and use a build with libx264, libass, loudnorm and HDR tone-map support. Run health at /api/health for dependency detection.
- **Project changed error:** reopen the project and retry. Generation commits only if the timeline revision still matches its starting snapshot.
- **Unsupported URL:** use the direct file URL or upload. The app deliberately does not scrape sessions or bypass media access restrictions.
- **No captions:** verify speech is audible, select a caption mode and render. A caption request with no detected words fails visibly rather than claiming caption success.
- **Jobs after restart:** unfinished jobs are marked failed with a retry instruction. Queue state is not blindly resumed halfway through a media operation.
- **Full disk:** generated job intermediates are retained for inspection and reproducibility. Back up projects, then manually remove only known unneeded generated job directories. The app does not delete source footage automatically.
- **Source browser playback fails for MOV/MKV codecs:** export/preview rendering normalizes to browser-compatible H.264/AAC; native source playback depends on the browser's decoder support.

Do not expose this server on 0.0.0.0 or put personal subscription execution behind a public multi-user service. A deployed service needs authorized provider billing, authenticated users, per-user storage/quotas and OS/container isolation.


## Original scenes and overlays

The default Generate flow creates original shapes, paths, text, character parts, parented groups and animated poses from the selected style and transcript. A trusted Canvas interpreter draws the scene graph; Markdown examples and model-generated executable code are never run. Footage compositions use transparent backgrounds and retain the original picture and speech. Standalone scripts/voiceovers receive full-frame scenes and a synthesized score. Captions are composited last and no extra timeline tracks are needed.

The following older presets remain supported by the manual timeline/plan API:

The app supports three compact overlay templates through AI prompts: `kinetic_title` (a large editorial headline card), `callout` (compact animated side text), and `lower_third` (a speaker label). Warm cream/terracotta and dark palettes are available. Movement uses eased slide/fade, a rotating accent and a subtle progress stroke. These are rendered on top of the original footage; captions are composited last. No additional timeline tracks are required. The fourth template, [Framecraft](FRAMECRAFT.md), renders a full-frame Canvas illustration with its own synthesized score and uses installed Chrome or Edge.

For example: “Remove long pauses, keep the speaker's meaning, add pop captions, use a cream lower third with the name I supplied, and add two short side callouts for the key points. Keep the face visible.” Review the proposed animation text and output-time windows before approving. Preview is required to judge placement because face tracking is not implemented.

Preset limits: up to 12 overlays, each 0.3–10 seconds, within a single 60-second output window. Original generated scenes instead support up to 20 scenes and 500 elements in a film, with at most 100 elements per scene. Object tracking and photorealistic video synthesis are not implemented.
