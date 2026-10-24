"""Real Codex plan → approval → Canvas preview → 1080p export using the default MD."""
import json
import shutil
import sys
import time
from pathlib import Path
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.config import ROOT, binary, project_dir
from backend.media import run

fixtures=ROOT/".fixtures/framecraft"
fixtures.mkdir(parents=True,exist_ok=True)
source=fixtures/"blank-source.mp4"
run([binary("ffmpeg"),"-v","error","-y","-f","lavfi","-i","color=c=0xf3eddf:s=540x960:r=30:d=4",
     "-an","-c:v","libx264","-pix_fmt","yuv420p",source])
client=httpx.Client(base_url="http://127.0.0.1:8765/api",headers={"X-Editor-Client":"video-use"},timeout=120)


def req(method,path,**kwargs):
    r=client.request(method,path,**kwargs);r.raise_for_status();return r.json()


def wait(job):
    previous=""
    for _ in range(600):
        job=req("GET",f"/jobs/{job['id']}")
        message=f"{job['kind']}: {job['status']} {job['progress']:.0f}% {job['message']}"
        if message!=previous:print(message,flush=True);previous=message
        if job["status"]=="completed":return job
        if job["status"] in {"failed","cancelled"}:raise RuntimeError(job["error"] or job["message"])
        time.sleep(.7)
    raise TimeoutError("Framecraft demo timed out")


project=req("POST","/projects",json={"name":"Framecraft · small spark, big world · 4s"})
styles=req("GET",f"/projects/{project['id']}/styles")
assert next(s for s in styles if s["id"]=="builtin_framecraft")["default"]
markdown=req("GET",f"/projects/{project['id']}/styles/builtin_framecraft")["markdown"]
assert markdown==(ROOT/"templates/framecraft/Framecraft.md").read_text(encoding="utf-8")
with source.open("rb") as f:
    asset=req("POST",f"/projects/{project['id']}/assets",files={"file":(source.name,f,"video/mp4")})
prompt="""Make an EXACTLY 4-second standalone Framecraft animation from the uploaded blank-source.mp4.
Use the full source range 0..4 at zoom 1 and grade none, portrait 1080x1920. The blank footage is just a
canvas carrier. Use exactly ONE supported framecraft motion_graphic spanning output 0..4 seconds,
cream palette, centered. Closing text EXACTLY 'Small spark. Big world.'; detail EXACTLY 'Paper, ink & possibility.'
Use the bundled handmade risograph bloom/universe scene and automatic picture-synced synthesized score.
No captions (there is no speech), no legacy title, no final fade, no imported music. One continuous shot.
The template's opening dot, drawn orbits, staggered print layers, breath and final poster demonstrate its style.
Hold the closing poster for the last full second. Do not copy the MD's example subjects or pretend to make
custom character animation. This is the curated Framecraft scene, rendered by the trusted Canvas engine.
"""
plan=wait(req("POST",f"/projects/{project['id']}/jobs",json={"kind":"plan","prompt":prompt,"style_id":"builtin_framecraft"}))
t=plan["result"]["timeline"]
assert abs(sum(c["end"]-c["start"] for c in t["clips"])-4)<.01,t
assert len(t["motion_graphics"])==1 and t["motion_graphics"][0]["template"]=="framecraft",t
assert t["motion_graphics"][0]["start"]==0 and t["motion_graphics"][0]["duration"]==4,t
assert t["captions"]=="none" and t["aspect"]=="portrait" and not t["title"] and not t["fade_out"],t
approved=req("POST",f"/jobs/{plan['id']}/approve")
preview=wait(approved["job"])
export=wait(req("POST",f"/projects/{project['id']}/jobs",json={"kind":"export"}))
assert export["result"]["decoded"] and export["result"]["framecraft_score"]
assert abs(export["result"]["actual_duration"]-4)<.05
assert (export["result"]["width"],export["result"]["height"])==(1080,1920)
work=project_dir(project["id"])/"edit/jobs"/export["id"]
outputs=ROOT/"storage/exports";outputs.mkdir(exist_ok=True)
deliverable=outputs/f"framecraft-showcase-4s-{export['id'][:8]}.mp4"
shutil.copy2(work/"output.mp4",deliverable)
download=Path.home()/"Downloads"/deliverable.name
shutil.copy2(deliverable,download)
run([binary("ffmpeg"),"-v","error","-y","-ss","3.5","-i",deliverable,"-frames:v","1",deliverable.with_suffix(".jpg")])
run([binary("ffmpeg"),"-v","error","-y","-i",deliverable,"-vf","fps=3,scale=216:-2,tile=6x2","-frames:v","1",outputs/"framecraft-motion-strip.jpg"])
_,audio_log=run([binary("ffmpeg"),"-hide_banner","-nostats","-i",deliverable,"-af","loudnorm=I=-14:TP=-1:LRA=11:print_format=json","-f","null","-"])
log=audio_log.decode(errors="replace");audio=json.loads(log[log.rfind('{'):log.rfind('}')+1])
report={"project_id":project["id"],"plan_job":plan["id"],"preview_job":preview["id"],"export_job":export["id"],
        "template_id":"builtin_framecraft","plan":plan["result"],"verification":export["result"],
        "engine_checks":json.loads((work/"framecraft-checks.json").read_text()),"audio_measurement":audio,
        "output":str(deliverable),"downloads_copy":str(download),"motion_strip":str(outputs/"framecraft-motion-strip.jpg"),
        "audio_review":"Synthesized score checked numerically; not listened to.",
        "scope":"Curated Canvas scene, not unrestricted code execution or arbitrary character animation."}
(ROOT/"storage/framecraft-test-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report,indent=2),flush=True)
