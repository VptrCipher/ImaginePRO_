"""Isolated installed-browser media engine, with declarative input and a bundled scene.

No scripts from Markdown or model responses are executed. The fresh browser profile
has no signed-in sessions, and all page requests are blocked by the runner.
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
from .config import ROOT, binary, animation_browser
from .media import Cancelled


def render_scene(graphic, width, height, workspace, cancel=None, stills=False, composition=None):
    engine = ROOT / "backend/framecraft"
    if not (engine / "node_modules/puppeteer-core/package.json").exists():
        raise RuntimeError("Install Framecraft dependencies: npm ci --prefix backend/framecraft (Node 22.12+)")
    node = binary('node')
    config = {"width": width, "height": height, "duration": graphic.duration,
              "text": graphic.text, "detail": graphic.detail}
    if composition is not None:
        config["film"] = composition.model_dump()
    config_path = workspace / "framecraft.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    target = workspace / ("stills" if stills else "motion-graphics.mov")
    env = dict(os.environ, FFMPEG_PATH=binary("ffmpeg"))
    browser = animation_browser()
    if browser:
        env['FRAMECRAFT_BROWSER_PATH'] = browser
    with tempfile.TemporaryFile() as log:
        p = subprocess.Popen([node, str(engine / "render.mjs"), str(config_path), str(target), "stills" if stills else "video"],
                             stdout=log, stderr=log, env=env,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        started = time.monotonic()
        try:
            while p.poll() is None:
                if cancel and cancel.is_set():
                    raise Cancelled("Framecraft rendering cancelled")
                if time.monotonic() - started > (900 if composition is not None else 300):
                    raise TimeoutError("Animation rendering exceeded its time budget")
                time.sleep(.15)
            if p.returncode:
                log.seek(0)
                raise RuntimeError(log.read().decode(errors="replace")[-3500:])
        finally:
            if p.poll() is None:
                if os.name == "nt":
                    # Stop only this owned renderer and its browser/encoder descendants.
                    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    p.terminate()
                p.wait()
    return target, graphic.start, graphic.start + graphic.duration
