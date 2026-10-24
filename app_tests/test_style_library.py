import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend import agent
from backend.main import app
from backend.models import EditPlan, Timeline
from backend.styles import skill_registry, style_text
from backend.config import ROOT

NAMES = {"hand-drawn-cartoon": "Hand-drawn Cartoon", "apple-launch-film": "Apple Launch Film",
         "vox-explainer": "Vox Explainer", "kinetic-typography": "Kinetic Typography"}


@pytest.mark.parametrize("slug,name", NAMES.items())
def test_installed_style_is_named_inspectable_and_read_only(slug, name):
    with TestClient(app, headers={"X-Editor-Client": "video-use"}) as client:
        project = client.post("/api/projects", json={"name": "Style library"}).json()
        base = f"/api/projects/{project['id']}/styles"
        styles = client.get(base).json()
        matches = [s for s in styles if s.get("slug") == slug and s.get("bundled")]
        assert len(matches) == 1
        style = matches[0]
        assert style["name"] == name and style["kind"] == "skill"
        assert style["source_url"].startswith("https://github.com/")
        original = (ROOT / "skills" / slug / "SKILL.md").read_text(encoding="utf-8")
        markdown = client.get(base + "/" + style["id"]).json()["markdown"]
        assert markdown.startswith(original)
        assert (ROOT / "skills" / slug / "LICENSE").read_text(encoding="utf-8").startswith("MIT License")
        assert client.put(base + "/" + style["id"], json={"markdown": "overwrite"}).status_code == 400
        assert (ROOT / "skills" / slug / "SKILL.md").read_text(encoding="utf-8") == original


@pytest.mark.parametrize("slug", NAMES)
def test_selected_style_reaches_planner_as_context_not_executable_tools(slug, monkeypatch, tmp_path):
    style = next(s for s in skill_registry() if s.get("slug") == slug and s.get("bundled"))
    original = (ROOT / "skills" / slug / "SKILL.md").read_text(encoding="utf-8")
    captured = []
    class CaptureRuntime:
        def generate(self, request, model, workspace, cancel=None, images=None):
            captured.append(request)
            return EditPlan(summary="Bounded edit", warnings=[], timeline=Timeline())
    monkeypatch.setattr(agent, "runtime", CaptureRuntime())
    agent.plan_edit({"assets": [], "timeline": Timeline().model_dump()}, "Follow the selected style",
                    style_text(style["id"], "a"*32), {}, tmp_path)
    assert len(captured) == 1
    assert json.dumps(original, ensure_ascii=False)[1:-1] in captured[0]
    assert "untrusted creative context" in captured[0] and "You have NO tools" in captured[0]
