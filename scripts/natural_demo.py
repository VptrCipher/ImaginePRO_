"""Polished acceptance follow-up: permitted natural footage + speech + saved reference.

Uses the public CC0 MDN flower clip already imported by acceptance_demo.py.
Verifies cross-project style reuse and preservation of the target title.
"""
import json
import sys
import time
from pathlib import Path
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import db
from backend.config import ROOT,binary,project_dir
from backend.media import run,probe

report_path=ROOT/"storage/acceptance-report.json"
report=json.loads(report_path.read_text(encoding="utf-8"))
with db.connect() as c:
    row=c.execute("SELECT path FROM assets WHERE project_id=? AND name='flower.mp4'",(report["project_id"],)).fetchone()
assert row,"Run acceptance_demo.py first to retrieve the permitted CC0 source"
raw=ROOT/".fixtures/natural-footage.mp4"
speech=ROOT/".fixtures/speech.wav"
run([binary("ffmpeg"),"-v","error","-y","-stream_loop","-1","-i",row["path"],"-i",speech,"-map","0:v:0","-map","1:a:0","-t",str(probe(speech)["duration"]),"-c:v","libx264","-preset","fast","-pix_fmt","yuv420p","-c:a","aac",raw])
client=httpx.Client(base_url="http://127.0.0.1:8765/api",headers={"X-Editor-Client":"video-use"},timeout=120)
def req(method,path,**kw):
    response=client.request(method,path,**kw)
    response.raise_for_status()
    return response.json()
def wait(j):
    previous=""
    for _ in range(1200):
        j=req("GET",f"/jobs/{j['id']}")
        msg=f"{j['kind']}: {j['status']} {j['progress']:.0f}% {j['message']}"
        if previous!=msg: print(msg,flush=True);previous=msg
        if j["status"]=="completed":return j
        if j["status"] in {"failed","cancelled"}:raise RuntimeError(j["error"])
        time.sleep(.6)
    raise TimeoutError("Demo job timed out")
p=req("POST","/projects",json={"name":"Spring story · creator demo"})
with raw.open("rb") as f:a=req("POST",f"/projects/{p['id']}/assets",files={"file":("spring-footage.mp4",f,"video/mp4")})
style_id=report["tests"]["D_reference_video"]["style_id"]
assert any(s["id"]==style_id for s in req("GET",f"/projects/{p['id']}/styles"))
timeline=p["timeline"]
timeline["title"]="SPRING STORY"
p=req("PUT",f"/projects/{p['id']}/timeline",json={"revision":0,"timeline":timeline})
j=wait(req("POST",f"/projects/{p['id']}/jobs",json={"kind":"plan","style_id":style_id,"prompt":"Edit the speech into a concise, warm landscape video. Remove long pauses and filler words, keep the meaningful sentences in order, use animated captions and a final fade. Adapt the reference's visual editing approach, retaining this project's existing title."}))
assert j["result"]["timeline"]["title"]=="SPRING STORY",j["result"]
assert j["result"]["timeline"]["captions"]=="pop"
approved=req("POST",f"/jobs/{j['id']}/approve")
preview=wait(approved["job"])
final=wait(req("POST",f"/projects/{p['id']}/jobs",json={"kind":"export"}))
assert final["result"]["decoded"] and final["result"]["caption_cues"]>5
assert final["result"]["actual_duration"]<probe(raw)["duration"]-1
report["tests"]["H_natural_footage_and_style_content_preservation"]={"passed":True,"project_id":p["id"],"plan_job":j["id"],"render_job":final["id"],"title":"SPRING STORY","cross_project_style_reuse":True,"source_attribution":"MDN CC0 flower.mp4; synthetic Windows speech fixture"}
report["final_demo_project_id"]=p["id"]
report["final_job_id"]=final["id"]
report["final_output"]=str(project_dir(p["id"])/"edit/jobs"/final["id"]/"output.mp4")
report["outputs"].append({"job_id":final["id"],**final["result"]})
report_path.write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({"project_id":p["id"],"output":report["final_output"],"verification":final["result"]},indent=2),flush=True)
