import importlib.util
import json
import mimetypes
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from . import db, jobs
from .config import ROOT, binary, project_dir, MAX_UPLOAD, INSTALLATION_ID, animation_browser
from .models import ProjectCreate, TimelineSave, JobCreate, MarkdownSave, URLImport, Timeline, TranscriptCreate
from .media import ingest, validate_timeline
from .styles import list_styles, style_text, save_style
from .reference import fetch_direct
from . import director


@asynccontextmanager
async def lifespan(app):
    db.init()
    yield


app = FastAPI(title="ImaginePro · local editor", lifespan=lifespan)


@app.middleware("http")
async def local_only(request: Request, call_next):
    host = request.headers.get("host", "").split(":")[0]
    if host not in {"127.0.0.1", "localhost", "testserver"}:
        return JSONResponse({"detail": "This application accepts local-owner requests only"}, status_code=403)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        length = request.headers.get("content-length")
        if length and int(length) > MAX_UPLOAD + 1024 * 1024:
            return JSONResponse({"detail": "Upload exceeds 500 MB"}, status_code=413)
        origin = request.headers.get("origin")
        if origin and origin not in {"http://127.0.0.1:8765", "http://localhost:8765", "http://127.0.0.1:3000", "http://localhost:3000"}:
            return JSONResponse({"detail": "Untrusted origin"}, status_code=403)
        if request.headers.get("x-editor-client") != "video-use":
            return JSONResponse({"detail": "Missing local editor request header"}, status_code=403)
    return await call_next(request)


@app.exception_handler(KeyError)
async def missing(request, error):
    return JSONResponse({"detail": str(error)}, status_code=404)


@app.exception_handler(ValueError)
async def invalid(request, error):
    return JSONResponse({"detail": str(error)}, status_code=409 if "Project changed" in str(error) else 400)


@app.exception_handler(RuntimeError)
async def unavailable(request, error):
    return JSONResponse({"detail": str(error)}, status_code=503)


@app.get("/api/health")
def health():
    tools = {}
    for name in ["ffmpeg", "ffprobe", "codex", "node"]:
        try:
            binary(name)
            tools[name] = True
        except RuntimeError:
            tools[name] = False
    tools["faster_whisper"] = bool(importlib.util.find_spec("faster_whisper"))
    tools['animation_browser'] = bool(animation_browser())
    tools['animation_engine'] = (ROOT/'backend/framecraft/node_modules/puppeteer-core/package.json').is_file()
    tools['frontend'] = (ROOT/'frontend/out/index.html').is_file()
    return {"status": "ok", "application": "ImaginePro", "installation_id": INSTALLATION_ID,
            "mode": "local-owner", "tools": tools,
            "capabilities": {"motion_graphics": ["kinetic_title", "callout", "lower_third", "framecraft"], "framecraft_score": True, "generated_2d_animation": True, "transcript_to_video": True, "voiceover_to_video": True, "automatic_timeline_placement": True, "face_tracking": False, "arbitrary_character_animation": False},
            "providers": [{"id": "codex", "name": "Codex · ChatGPT account", "available": tools["codex"]},
                          {"id": "kiro", "name": "Kiro adapter", "available": False},
                          {"id": "api", "name": "External API providers", "available": False}]}


@app.get("/api/runtime")
def runtime():
    try:
        status = subprocess.run([binary("codex"), "login", "status"], capture_output=True, text=True, timeout=15,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        authenticated = status.returncode == 0 and "ChatGPT" in status.stdout + status.stderr
    except (RuntimeError, subprocess.TimeoutExpired):
        authenticated = False
    return {"provider": "codex", "authenticated_with_chatgpt": authenticated,
            "message": "ChatGPT subscription session detected" if authenticated else "Run codex login once on this computer; select ChatGPT account sign-in.",
            "model": "CLI default", "transcription": "Local faster-whisper CPU int8", "diarization": "unsupported"}


@app.get('/api/director/config')
def director_config():
    return director.public_configuration()


@app.put('/api/director/config')
def save_director_config(body: director.DirectorConfiguration):
    return director.save_configuration(body)


@app.post('/api/projects/{project_id}/enhance')
def enhance_prompt(project_id: str,body: director.EnhanceRequest):
    project=db.project(project_id)
    for asset_id in body.input_asset_ids:db.asset(asset_id,project_id)
    style=style_text(body.style_id,project_id)
    try:return director.enhance(project,body,style)
    except director.DirectorError as exc:raise HTTPException(exc.status,str(exc)) from None


@app.get("/api/projects")
def projects():
    with db.connect() as c:
        return [dict(r) for r in c.execute("SELECT id,name,revision,created FROM projects ORDER BY created DESC")]


@app.post("/api/projects")
def create_project(body: ProjectCreate):
    return db.create_project(body.name)


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    return db.project(project_id)


@app.put("/api/projects/{project_id}/timeline")
def timeline(project_id: str, body: TimelineSave):
    validate_timeline(body.timeline, project_id)
    return db.save_timeline(project_id, body.revision, body.timeline)


def accept_file(project_id, name, stream):
    db.project(project_id)
    key = db.uid()
    suffix = Path(name).suffix.lower()
    if suffix not in {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac", ".png", ".jpg", ".jpeg", ".webp", ".txt", ".srt", ".vtt"}:
        raise ValueError("Unsupported file type; use video, audio, images or TXT/SRT/VTT transcripts")
    directory = project_dir(project_id) / "sources"
    directory.mkdir(exist_ok=True)
    path = directory / (key + suffix)
    total = 0
    try:
        with path.open("wb") as out:
            while chunk := stream.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD:
                    raise ValueError("Upload exceeds 500 MB")
                out.write(chunk)
        ingest(path, Path(name).name, project_id, key)
        return next(a for a in db.project(project_id)["assets"] if a["id"] == key)
    except Exception:
        path.unlink(missing_ok=True)
        raise


@app.post("/api/projects/{project_id}/assets")
def upload(project_id: str, file: UploadFile = File(...)):
    return accept_file(project_id, file.filename or "upload.mp4", file.file)


@app.post("/api/projects/{project_id}/transcript")
def import_transcript(project_id: str, body: TranscriptCreate):
    import io
    name = Path(body.name).stem + ".txt"
    return accept_file(project_id, name, io.BytesIO(body.text.encode("utf-8")))


@app.post("/api/projects/{project_id}/reference-url")
def reference_url(project_id: str, body: URLImport):
    db.project(project_id)
    directory = project_dir(project_id) / "downloads"
    directory.mkdir(exist_ok=True)
    key = db.uid()
    target = directory / (key + ".media")
    fetch_direct(body.url, target)
    try:
        ingest(target, Path(urlsplit(body.url).path).name or "URL reference", project_id, key)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return next(a for a in db.project(project_id)["assets"] if a["id"] == key)


@app.get("/api/projects/{project_id}/assets/{asset_id}/file")
def media_file(project_id: str, asset_id: str):
    a = db.asset(asset_id, project_id)
    media_type = mimetypes.guess_type(a["name"])[0] or ("video/mp4" if a["kind"] == "video" else "application/octet-stream")
    return FileResponse(a["path"], media_type=media_type)


@app.get("/api/projects/{project_id}/assets/{asset_id}/thumbnail")
def thumbnail(project_id: str, asset_id: str):
    a = db.asset(asset_id, project_id)
    p = Path(a["path"]).parent / (asset_id + ".jpg")
    if not p.exists():
        raise HTTPException(404, "No thumbnail for this audio asset")
    return FileResponse(p)


@app.get("/api/projects/{project_id}/styles")
def styles(project_id: str):
    db.project(project_id)
    return list_styles(project_id)


@app.get("/api/projects/{project_id}/styles/{style_id}")
def style(project_id: str, style_id: str):
    return {"markdown": style_text(style_id, project_id)}


@app.put("/api/projects/{project_id}/styles/{style_id}")
def update_style(project_id: str, style_id: str, body: MarkdownSave):
    save_style(style_id, project_id, body.markdown)
    return {"saved": True}


@app.post("/api/projects/{project_id}/jobs")
def create_job(project_id: str, body: JobCreate):
    return jobs.submit(project_id, body)


@app.get("/api/projects/{project_id}/jobs")
def project_jobs(project_id: str):
    db.project(project_id)
    with db.connect() as c:
        keys = [r[0] for r in c.execute("SELECT id FROM jobs WHERE project_id=? ORDER BY created DESC LIMIT 50", (project_id,))]
    return [db.job(key) for key in keys]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    return db.job(job_id)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    return jobs.cancel(job_id)


@app.post("/api/jobs/{job_id}/approve")
def approve_job(job_id: str):
    j = db.job(job_id)
    if j["kind"] != "plan" or j["status"] != "completed":
        raise ValueError("Only a completed editing plan can be approved")
    timeline = Timeline.model_validate(j["result"]["timeline"])
    validate_timeline(timeline, j["project_id"], True)
    project = db.save_timeline(j["project_id"], j["payload"]["base_revision"], timeline)
    return {"project": project, "job": jobs.submit(j["project_id"], JobCreate(kind="preview"))}


@app.get("/api/jobs/{job_id}/output")
def job_output(job_id: str, download: bool = False):
    j = db.job(job_id)
    if j["status"] != "completed" or j["kind"] not in {"generate", "preview", "export"}:
        raise HTTPException(404, "No rendered output")
    path = project_dir(j["project_id"]) / "edit/jobs" / job_id / "output.mp4"
    return FileResponse(path, media_type="video/mp4", filename=f"ImaginePro-{j['kind']}.mp4" if download else None)


@app.get("/api/jobs/{job_id}/verification")
def job_verification(job_id: str):
    j = db.job(job_id)
    path = project_dir(j["project_id"]) / "edit/jobs" / job_id / "verification.jpg"
    if j["status"] != "completed" or not path.exists():
        raise HTTPException(404, "No verification sheet")
    return FileResponse(path)


if (ROOT / "frontend/out").is_dir():
    app.mount("/", StaticFiles(directory=ROOT / "frontend/out", html=True), name="editor")
