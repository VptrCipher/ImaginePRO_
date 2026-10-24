import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from . import db
from .config import project_dir
from .models import Timeline
from .media import Cancelled, validate_timeline
from .agent import plan_edit
from .transcription import transcribe
from .styles import style_text
from .rendering import render
from .reference import analyze

executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="video-worker")
signals = {}
lock = threading.Lock()


def submit(project_id, request):
    project = db.project(project_id)
    if request.kind in {"preview", "export"}:
        validate_timeline(Timeline.model_validate(project["timeline"]), project_id, True)
    if request.kind == "plan" and not any(a["kind"] == "video" for a in project["assets"]):
        raise ValueError("Import video before requesting an edit plan")
    if request.kind == "generate" and not request.prompt.strip():
        raise ValueError("Describe the video you want to generate")
    for asset_id in request.input_asset_ids:
        db.asset(asset_id, project_id)
    if request.style_id:
        style_text(request.style_id, project_id)
    key = db.uid()
    payload = request.model_dump() | {"base_revision": project["revision"], "project_snapshot": project}
    with lock, db.connect() as c:
        pending = c.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
        if pending >= 8:
            raise ValueError("Queue is full; wait for a job to finish")
        c.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)", (key, project_id, request.kind, "queued", 0, "Waiting for worker", json.dumps(payload), None, None, time.time()))
        signals[key] = threading.Event()
    executor.submit(work, key)
    return db.job(key)


def cancel(key):
    j = db.job(key)
    if j["status"] in {"queued", "running"}:
        with lock:
            if key in signals:
                signals[key].set()
        db.update_job(key, message="Cancellation requested")
    return db.job(key)


def work(key):
    event = signals[key]
    j = db.job(key)
    payload = j["payload"]
    workspace = project_dir(j["project_id"]) / "edit" / "jobs" / key
    workspace.mkdir(parents=True, exist_ok=True)
    def progress(value, message):
        if event.is_set():
            raise Cancelled("Cancelled by user")
        db.update_job(key, progress=value, message=message)
    try:
        progress(1, "Starting job")
        db.update_job(key, status="running")
        if j["kind"] == "generate":
            from .generation import generate
            result = generate(j["project_id"], payload, workspace, event, progress)
            result |= {"output_url":f"/api/jobs/{key}/output", "verification_url":f"/api/jobs/{key}/verification"}
            db.update_job(key,status="completed",progress=100,message="Your video is ready",result=result)
            return
        elif j["kind"] == "plan":
            project = payload["project_snapshot"]
            transcripts = {}
            for a in project["assets"]:
                if a["kind"] == "video":
                    full = db.asset(a["id"], j["project_id"])
                    transcripts[a["id"]] = transcribe(full, event, lambda m: progress(15, m))
            progress(40, "Codex is planning edits from the transcript and selected style")
            style = style_text(payload.get("style_id"), j["project_id"])
            plan = plan_edit(project, payload["prompt"], style, transcripts, workspace / "agent", event)
            validate_timeline(plan.timeline, j["project_id"], True)
            result = plan.model_dump() | {"base_revision": payload["base_revision"]}
        elif j["kind"] == "reference":
            result = analyze(j["project_id"], payload["reference_asset_ids"], workspace, event, progress)
        else:
            timeline = Timeline.model_validate(payload["project_snapshot"]["timeline"])
            result = render(j["project_id"], timeline, workspace, preview=j["kind"] == "preview", cancel=event, progress=progress)
            result |= {"revision": payload["base_revision"], "output_url": f"/api/jobs/{key}/output", "verification_url": f"/api/jobs/{key}/verification"}
        progress(100, "Plan ready for approval" if j["kind"] == "plan" else "Completed")
        db.update_job(key, status="completed", result=result)
    except Cancelled:
        db.update_job(key, status="cancelled", message="Cancelled")
    except Exception as e:
        db.update_job(key, status="failed", error=str(e)[:3500], message="Job failed; your source files are preserved")
    finally:
        with lock:
            signals.pop(key, None)
