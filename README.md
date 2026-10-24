<p align="center">
  <img src="frontend/public/icon.svg" width="72" alt="ImaginePro">
</p>

<h1 align="center">ImaginePro</h1>
<p align="center">Your ideas. In motion.</p>

ImaginePro is an AI video studio for turning footage, voice recordings,
transcripts, and creative direction into polished videos. Import your content,
choose a visual style, describe the result, and generate a finished video
directly on the timeline.

## Create in five steps

1. Open ImaginePro.
2. Import a video, voice recording, or transcript.
3. Choose a style and aspect ratio.
4. Describe your video and press **Enter**.
5. Preview, refine, and export the finished video.

## Features

- **AI video creation** — turn a prompt and imported content into a complete edit.
- **Animated storytelling** — generate illustrations, motion graphics, titles, and smooth transitions.
- **Voice and transcripts** — work with recorded speech or paste a written script.
- **Captions** — add readable subtitles timed to speech.
- **Style library** — choose a visual direction and customize it with your prompt.
- **Simple timeline** — cut, trim, delete, reorder, and adjust clips.
- **Flexible formats** — create portrait reels or landscape videos.
- **Preview and export** — review your edit and download a finished MP4.
- **Enhance Director** — refine creative instructions before generating.
- **Project persistence** — save projects, media, and edit revisions locally.

## Open the studio

[**Launch ImaginePro**](https://imaginepro-demo.vercel.app)

The online demo requires a passcode and an active connection to the rendering
computer. Keep that computer on and connected during generation.

## Run on your computer

Clone this repository and run the setup command from the project folder:

```powershell
git clone https://github.com/VptrCipher/ImaginePRO_.git
cd ImaginePRO_
.\scripts\start.ps1 -Install
```

After setup, open **ImaginePro.exe** to launch the studio. Your local rendering
tools and account connection must be configured before generation. See the
[setup guide](docs/SETUP.md) for requirements and installation details.

## Project structure

- `frontend/` — studio interface and editing controls.
- `backend/` — generation, transcription, rendering, and project management.
- `cloud/` — authenticated online demo connection and deployment utilities.
- `desktop/` — desktop launcher.
- `templates/` and `skills/` — visual styles and animation guides.
- `app_tests/` — application verification.
- `docs/` — setup, workflow, and technical documentation.

## Guides

- [Using ImaginePro](README.app.md)
- [Installation](docs/SETUP.md)
- [Desktop app](docs/DESKTOP.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Online demo](docs/VERCEL-DEMO.md)

Credentials, private media, generated videos, project databases, and installed
dependencies stay outside the repository. New installations require local
setup; the online demo uses its connected rendering computer.
