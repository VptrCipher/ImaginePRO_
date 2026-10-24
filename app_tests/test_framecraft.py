import json
import threading
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.main import app
from backend.models import MotionGraphic, Timeline
from backend.framecraft_renderer import render_scene
from backend.media import Cancelled
from backend.config import ROOT


def scene():
    return MotionGraphic(template="framecraft", text="Small spark. Big world.", start=0, duration=4)


def test_default_template_is_available_in_new_projects_and_read_only():
    with TestClient(app, headers={"X-Editor-Client": "video-use"}) as client:
        p = client.post("/api/projects", json={"name": "Default template"}).json()
        base = f"/api/projects/{p['id']}/styles"
        templates = client.get(base).json()
        template = next(s for s in templates if s["id"] == "builtin_framecraft")
        assert template["kind"] == "template" and template["default"]
        assert template["name"] == "Framecraft"
        markdown = client.get(base + "/builtin_framecraft").json()["markdown"]
        original = (ROOT / "templates/framecraft/Framecraft.md").read_text(encoding="utf-8")
        assert markdown == original
        assert "# Motion Studio by Buck" in markdown
        assert client.put(base + "/builtin_framecraft", json={"markdown": "overwrite"}).status_code == 400
        assert client.get(base + "/builtin_framecraft").json()["markdown"] == original


def test_scene_requires_enough_time_and_cannot_be_mixed_with_cards():
    with pytest.raises(ValidationError, match="at least 3 seconds"):
        MotionGraphic(template="framecraft", text="Too short", start=0, duration=2)
    card = MotionGraphic(template="callout", text="Card", start=0, duration=1)
    with pytest.raises(ValidationError, match="one Framecraft"):
        Timeline(motion_graphics=[scene(), card])


def test_real_canvas_is_deterministic_and_treats_markup_as_data(tmp_path):
    if not (ROOT / "backend/framecraft/node_modules/puppeteer-core/package.json").exists():
        pytest.skip("Install Framecraft dependencies with npm ci --prefix backend/framecraft")
    graphic = MotionGraphic(template="framecraft", text='</script><img src="https://example.com/x">', start=0, duration=3)
    render_scene(graphic, 360, 640, tmp_path, stills=True)
    checks = json.loads((tmp_path / "stills/checks.json").read_text())
    assert checks["deterministic"] and checks["motion_changes"]
    assert checks["external_requests"] == 0
    assert len(list((tmp_path / "stills").glob("frame-*.png"))) == 8
    assert checks["score"]["sample_rate"] == 48000 and checks["score"]["rms"] > .01
    assert (tmp_path / "framecraft-score.wav").stat().st_size == 44 + 3*48000*4


def test_canvas_cancellation_stops_owned_renderer(tmp_path):
    if not (ROOT / "backend/framecraft/node_modules/puppeteer-core/package.json").exists():
        pytest.skip("Framecraft dependencies not installed")
    event = threading.Event(); event.set()
    with pytest.raises(Cancelled):
        render_scene(scene(), 360, 640, tmp_path, event)
