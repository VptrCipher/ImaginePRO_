"""Eight stills before any full render; actual bundled Canvas engine, no mock frames."""
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.config import ROOT
from backend.models import MotionGraphic
from backend.framecraft_renderer import render_scene

workspace = ROOT / ".fixtures/framecraft"
workspace.mkdir(parents=True, exist_ok=True)
g = MotionGraphic(template="framecraft", text="Small spark. Big world.", detail="Paper, ink & possibility.", start=0, duration=4)
render_scene(g, 1080, 1920, workspace, stills=True)
paths = sorted((workspace / "stills").glob("frame-*.png"))
sheet = Image.new("RGB", (270*8, 502), "#172f3b")
d = ImageDraw.Draw(sheet)
checks = json.loads((workspace / "stills/checks.json").read_text())
for i, path in enumerate(paths):
    with Image.open(path) as im:
        im = im.convert("RGB").resize((270, 480))
        sheet.paste(im, (i*270, 0))
    d.text((i*270+8, 484), f"{checks['times'][i]:.2f}s", fill="white")
sheet.save(workspace / "lookdev.jpg")
print(json.dumps({"contact_sheet": str(workspace / "lookdev.jpg"), "checks": checks}, indent=2))
