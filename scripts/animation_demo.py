"""Five-second Claude-inspired motion test through the real application API.

The blank source/narration and test audio are fixtures. The Codex plan creates
actual structured overlays, which the application renders (not baked-in footage).
"""
import json
import sys
import time
from pathlib import Path
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.config import ROOT,binary,project_dir
from backend.media import run

fixtures=ROOT/".fixtures/motion-test"
assert (fixtures/"voice.wav").exists(),"Create the local synthetic narration fixture first"
source=fixtures/"cream-source.mp4"
run([binary("ffmpeg"),"-v","error","-y","-f","lavfi","-i","color=c=0xf5f1e8:s=960x540:r=30:d=5",
     "-i",fixtures/"voice.wav","-map","0:v:0","-map","1:a:0","-t","5","-af","apad",
     "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",source])
music=fixtures/"soft-accent-bed.wav"
run([binary("ffmpeg"),"-v","error","-y","-f","lavfi","-i",
     "aevalsrc=0.04*sin(2*PI*220*t)+0.025*sin(2*PI*330*t)+0.015*sin(2*PI*440*t):s=48000:d=5",
     "-af","afade=t=in:d=0.3,afade=t=out:st=4.4:d=0.6","-c:a","pcm_s16le",music])
client=httpx.Client(base_url="http://127.0.0.1:8765/api",headers={"X-Editor-Client":"video-use"},timeout=120)


def req(method,path,**kwargs):
    r=client.request(method,path,**kwargs)
    r.raise_for_status()
    return r.json()


def wait(j):
    previous=""
    for _ in range(900):
        j=req("GET",f"/jobs/{j['id']}")
        message=f"{j['kind']}: {j['status']} {j['progress']:.0f}% {j['message']}"
        if message!=previous:print(message,flush=True);previous=message
        if j["status"]=="completed":return j
        if j["status"] in {"failed","cancelled"}:raise RuntimeError(j["error"] or j["message"])
        time.sleep(.6)
    raise TimeoutError("Animation demo timed out")


p=req("POST","/projects",json={"name":"Claude-inspired · five-second motion test"})
assets=[]
for path in [source,music]:
    with path.open("rb") as f:
        assets.append(req("POST",f"/projects/{p['id']}/assets",files={"file":(path.name,f)}))
prompt="""Create EXACTLY a 5-second Claude-inspired minimal editorial animation on the uploaded cream-source.mp4.
Keep source seconds 0..5 (including its narration); do not shorten the output or reorder speech.
Use warm cream, charcoal serif text and terracotta accents through the cream motion-graphics palette.
Create three sequential kinetic_title overlays in output time: 'Your words.' around 0..1.8,
'Your story.' around 1.7..3.5, 'In motion.' around 3.4..5. Give each a very short supporting line.
Use the template's eased movement/rotating accent. No legacy title, no extra hard cuts, no grade change,
no zoom on this blank background, and no final black fade. Keep exactly five seconds.
Add pop captions from actual narration. Use uploaded soft-accent-bed.wav at music_volume 0.08;
this is an imported synthetic test audio bed, not a request for AI music generation.
Do not claim tracking, character animation or arbitrary illustrations. These are supported template graphics.
"""
plan=wait(req("POST",f"/projects/{p['id']}/jobs",json={"kind":"plan","prompt":prompt}))
t=plan["result"]["timeline"]
length=sum(c["end"]-c["start"] for c in t["clips"])
assert abs(length-5)<.02,(length,plan["result"])
assert len(t["motion_graphics"])>=2,plan["result"]
assert t["captions"]=="pop"
assert t["music_asset_id"]==assets[1]["id"]
approved=req("POST",f"/jobs/{plan['id']}/approve")
preview=wait(approved["job"])
export=wait(req("POST",f"/projects/{p['id']}/jobs",json={"kind":"export"}))
assert abs(export["result"]["actual_duration"]-5)<.08
assert export["result"]["motion_graphics"]>=2 and export["result"]["caption_cues"]>=2
assert export["result"]["decoded"]
path=project_dir(p["id"])/"edit/jobs"/export["id"]/"output.mp4"
report={"project_id":p["id"],"plan_job":plan["id"],"preview_job":preview["id"],"export_job":export["id"],
        "plan":plan["result"],"verification":export["result"],"output":str(path),
        "tested":["local word transcription","genuine Codex structured plan","approval","three timed motion cards",
                  "animated captions","imported background audio mix","720p preview","1080p export","decode and duration sync"],
        "not_tested_on_person":["No human talking-head footage supplied","No face tracking/segmentation or free-form character animation"]}
(ROOT/"storage/animation-test-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report,indent=2),flush=True)
