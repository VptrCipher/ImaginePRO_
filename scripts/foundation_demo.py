"""P0 checkpoint: synthetic raw video → genuine Codex decision → genuine MP4."""
import json
import sys
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import db
from backend.config import binary, project_dir
from backend.media import run, ingest, validate_timeline
from backend.agent import plan_edit
from backend.rendering import render

db.init()
project = db.create_project("Foundation · actual Codex edit")
p = project_dir(project["id"])
sources = p / "sources"
sources.mkdir()
key = db.uid()
raw = sources / f"{key}.mp4"
run([binary("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=8", "-c:v", "libx264", "-pix_fmt", "yuv420p", raw])
ingest(raw, "raw-test-footage.mp4", project["id"], key)
project = db.project(project["id"])
plan = plan_edit(project, "Use seconds 1 to 5 only, add a warm cinematic grade, a title saying FIRST CUT, and a fade out. No captions because there is no speech.", "", {}, p / "edit/agent", threading.Event())
validate_timeline(plan.timeline, project["id"], True)
db.save_timeline(project["id"], 0, plan.timeline)
verification = render(project["id"], plan.timeline, p / "edit/foundation", cancel=threading.Event(), progress=lambda pct, msg: print(f"{pct:.0f}% {msg}", flush=True))
result = {"project_id": project["id"], "plan": plan.model_dump(), "verification": verification, "output": str(p / "edit/foundation/output.mp4")}
(p / "edit/foundation/demo.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
