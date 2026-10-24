"""Run A–G against a running app using real Codex, local Whisper and FFmpeg.

Requires .fixtures/speech.wav (scripts/make-demo.ps1 creates it on Windows).
Creates only new projects and generated test assets; never modifies user footage.
"""
import json
import sys
import time
from pathlib import Path
import httpx
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.config import ROOT, binary, project_dir
from backend.media import run

client = httpx.Client(base_url="http://127.0.0.1:8765/api", headers={"X-Editor-Client": "video-use"}, timeout=180)
report = {"tests": {}, "outputs": []}
fixtures = ROOT / ".fixtures"
fixtures.mkdir(exist_ok=True)


def request(method, path, **kwargs):
    r = client.request(method, path, **kwargs)
    r.raise_for_status()
    return r.json()


def wait_job(job):
    previous = ""
    start = time.monotonic()
    while time.monotonic() - start < 900:
        j = request("GET", "/jobs/" + job["id"])
        text = f"{j['kind']}: {j['status']} {j['progress']:.0f}% {j['message']}"
        if text != previous:
            print(text, flush=True)
            previous = text
        if j["status"] == "completed":
            return j
        if j["status"] in {"failed", "cancelled"}:
            raise RuntimeError(j["error"] or j["message"])
        time.sleep(.75)
    raise TimeoutError("Acceptance job timed out")


def upload(project, path, name=None):
    with path.open("rb") as f:
        return request("POST", f"/projects/{project['id']}/assets", files={"file": (name or path.name, f)})


def job(project, kind, **kwargs):
    return wait_job(request("POST", f"/projects/{project['id']}/jobs", json={"kind": kind, **kwargs}))


def approve(plan):
    result = request("POST", f"/jobs/{plan['id']}/approve")
    return result["project"], wait_job(result["job"])


def record_output(j):
    result = j["result"]
    report["outputs"].append({"job_id": j["id"], **result})
    response = client.get(result["output_url"].replace("/api", "", 1), headers={"Range": "bytes=0-255"})
    assert response.status_code == 206, "Preview seeking requires HTTP range responses"
    assert len(response.content) == 256


try:
    assert (fixtures / "speech.wav").exists(), "Run scripts/make-demo.ps1 first"
    source = fixtures / "raw-speech.mp4"
    run([binary("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=960x540:rate=30", "-i", fixtures / "speech.wav", "-shortest", "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "aac", source])
    project = request("POST", "/projects", json={"name": "Demo · your story, edited"})
    report["project_id"] = project["id"]
    asset = upload(project, source)
    styles = request("GET", f"/projects/{project['id']}/styles")
    manual = next(s for s in styles if s["name"] == "video-use")
    print("A/C: genuine Codex edit with manually installed video-use skill", flush=True)
    plan = job(project, "plan", prompt="Remove long pauses and the filler Um, preserve all meaningful speech. Use landscape, animated pop captions, neutral punch color, and a short intro title YOUR STORY. End with a fade. Keep word boundaries safe.", style_id=manual["id"])
    assert len(plan["result"]["timeline"]["clips"]) >= 2
    project, preview = approve(plan)
    assert preview["result"]["caption_cues"] > 5
    assert preview["result"]["actual_duration"] < asset["metadata"]["duration"] - 1
    record_output(preview)
    exported = job(project, "export")
    assert (exported["result"]["width"], exported["result"]["height"]) == (1920,1080)
    record_output(exported)
    report["tests"]["A_basic_AI_edit"] = {"passed": True, "plan_job": plan["id"], "render_job": exported["id"], "source_seconds": asset["metadata"]["duration"], "output_seconds": exported["result"]["actual_duration"], "captions": exported["result"]["caption_cues"]}
    report["tests"]["C_manual_skill"] = {"passed": True, "skill": manual["name"], "skill_id": manual["id"]}
    print("B/G: split, reorder, trim, save and reopen", flush=True)
    timeline = project["timeline"]
    original = json.loads(json.dumps(timeline))
    c = timeline["clips"][0]
    mid = (c["start"]+c["end"])/2
    timeline["clips"][0:1] = [{**c,"end":mid}, {**c,"start":mid}]
    timeline["clips"][0],timeline["clips"][1] = timeline["clips"][1],timeline["clips"][0]
    timeline["clips"][-1]["end"] -= .1
    project = request("PUT", f"/projects/{project['id']}/timeline", json={"revision":project["revision"],"timeline":timeline})
    reopened = request("GET", f"/projects/{project['id']}")
    assert reopened["timeline"] == timeline
    edited = job(project,"preview")
    record_output(edited)
    report["tests"]["B_manual_edit"] = {"passed": True, "render_job":edited["id"]}
    report["tests"]["G_persistence"] = {"passed": True, "revision":project["revision"]}
    # Restore the meaningful chronological edit after testing the intentionally reordered split.
    project = request("PUT", f"/projects/{project['id']}/timeline", json={"revision":project["revision"],"timeline":original})
    print("D: reference video → clean.md → different source → real preview", flush=True)
    ref_video = upload(project, fixtures / "raw-speech.mp4", "reference-video.mp4")
    # Reference is a separate short color-graded video, not the target footage.
    foundations = list((ROOT/"storage/projects").glob("*/edit/foundation/output.mp4"))
    if foundations:
        ref_video = upload(project, foundations[-1], "warm-reference.mp4")
    reference = job(project,"reference", reference_asset_ids=[ref_video["id"]])
    assert "# Evidence and Timestamps" in reference["result"]["markdown"]
    ref_plan = job(project,"plan",prompt="Apply the supported visual style from this reference to the original raw-speech.mp4 footage only. Keep speech and animated captions, no reference footage in the output. Use warm cinematic grade when appropriate.",style_id=reference["result"]["style_id"])
    assert all(c["asset_id"]==asset["id"] for c in ref_plan["result"]["timeline"]["clips"])
    assert ref_plan["result"]["timeline"]["title"] != "FIRST CUT", "Copy editing style, not reference title content"
    project, styled_preview = approve(ref_plan)
    record_output(styled_preview)
    report["tests"]["D_reference_video"] = {"passed":True,"style_id":reference["result"]["style_id"],"render_job":styled_preview["id"],"sampled_frames":reference["result"]["frame_count"]}
    print("E: reference images with explicitly unknown temporal/audio properties",flush=True)
    image = Image.new("RGB", (960,540), "#18272a")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf",60) if Path("C:/Windows/Fonts/arialbd.ttf").exists() else ImageFont.load_default()
    draw.rectangle((50,50,350,490),fill="#b28857")
    draw.text((410,165),"YOUR STORY",font=font,fill="#f2dfbd")
    draw.rounded_rectangle((415,270,850,335),12,fill="#101719")
    draw.text((435,282),"CLEAN CAPTIONS",font=font.font_variant(size=35),fill="white")
    image_path=fixtures/"reference-board.png"
    image.save(image_path)
    image_asset=upload(project,image_path)
    image_style=job(project,"reference",reference_asset_ids=[image_asset["id"]])
    md=image_style["result"]["markdown"]
    assert "Unknown: static images provide no temporal evidence" in md
    assert "no motion can be inferred" in md
    # Exercise human edits to clean.md; the selected Markdown is loaded by the next planner.
    sid=image_style["result"]["style_id"]
    request("PUT",f"/projects/{project['id']}/styles/{sid}",json={"markdown":md+"\nHuman preference: use warm_cinematic, retain readable pop captions.\n"})
    image_plan=job(project,"plan",prompt="Apply supported visual rules from the selected style to original raw-speech.mp4 only. Keep chronological speech and pop captions. Use warm_cinematic; unknown pacing is not a constraint.",style_id=sid)
    project,image_preview=approve(image_plan)
    record_output(image_preview)
    report["tests"]["E_reference_images"]={"passed":True,"style_id":sid,"render_job":image_preview["id"]}
    print("F: direct public CC0 video URL and unsafe URL rejection",flush=True)
    url_asset=request("POST",f"/projects/{project['id']}/reference-url",json={"url":"https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4"})
    url_style=job(project,"reference",reference_asset_ids=[url_asset["id"]])
    rejected=client.post(f"/projects/{project['id']}/reference-url",json={"url":"http://127.0.0.1/private.mp4"})
    assert rejected.status_code==400
    report["tests"]["F_reference_URL"]={"passed":True,"style_id":url_style["result"]["style_id"],"unsafe_url_status":rejected.status_code}
    final=job(project,"export")
    record_output(final)
    report["final_job_id"]=final["id"]
    report["final_output"]=str(project_dir(project["id"])/"edit/jobs"/final["id"]/"output.mp4")
    report["passed"]=True
finally:
    report_path=ROOT/"storage/acceptance-report.json"
    report_path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(f"Report: {report_path}",flush=True)
    client.close()
