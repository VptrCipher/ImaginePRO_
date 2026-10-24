import json
import threading
import time
import sqlite3
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.main import app
from backend import db
from backend.models import Timeline, EditPlan, strict_json_schema
from backend.media import run, probe, validate_timeline
from backend.config import binary
from backend.rendering import render, make_captions
from backend.reference import public_target
from backend.agent import command, DISABLED_FEATURES

HEADERS = {"X-Editor-Client": "video-use"}


def test_database_connections_close_after_transaction():
    db.init()
    with db.connect() as connection:
        assert connection.execute("SELECT 1").fetchone()[0] == 1
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


@pytest.fixture
def client():
    with TestClient(app, headers=HEADERS) as c:
        yield c


@pytest.fixture(scope="session")
def source(tmp_path_factory):
    path = tmp_path_factory.mktemp("media") / "raw.mp4"
    run([binary("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=4", "-c:v", "libx264", "-pix_fmt", "yuv420p", path])
    return path


def import_source(client, source):
    p = client.post("/api/projects", json={"name": "Integration"}).json()
    with source.open("rb") as f:
        result = client.post(f"/api/projects/{p['id']}/assets", files={"file": ("raw.mp4", f, "video/mp4")})
    assert result.status_code == 200, result.text
    return p, result.json()


def test_manual_edit_persists_and_renders_real_mp4(client, source, tmp_path):
    p, a = import_source(client, source)
    timeline = Timeline.model_validate({"clips": [{"asset_id": a["id"], "start": 2, "end": 3}, {"asset_id": a["id"], "start": .2, "end": 1.2}], "grade": "warm_cinematic", "title": "REAL EDIT", "fade_out": True})
    saved = client.put(f"/api/projects/{p['id']}/timeline", json={"revision": 0, "timeline": timeline.model_dump()})
    assert saved.status_code == 200, saved.text
    reopened = client.get(f"/api/projects/{p['id']}").json()
    assert reopened["timeline"] == timeline.model_dump()
    assert reopened["revision"] == 1
    conflict = client.put(f"/api/projects/{p['id']}/timeline", json={"revision": 0, "timeline": timeline.model_dump()})
    assert conflict.status_code == 409
    report = render(p["id"], timeline, tmp_path, cancel=threading.Event())
    assert report["decoded"] and abs(report["actual_duration"] - 2) < .15
    assert (report["width"], report["height"]) == (1280, 720)
    assert (tmp_path / "output.mp4").stat().st_size > 10000
    assert source.read_bytes() != (tmp_path / "output.mp4").read_bytes()
    assert (tmp_path / "verification.jpg").exists()


def test_1080_portrait_export(client, source, tmp_path):
    p, a = import_source(client, source)
    timeline = Timeline.model_validate({"clips": [{"asset_id": a["id"], "start": 0, "end": .5, "zoom": 1.1}], "aspect": "portrait"})
    result = render(p["id"], timeline, tmp_path, preview=False)
    assert (result["width"], result["height"]) == (1080, 1920)
    assert result["video_encoding"] == "one segment encode + copy concat/remux"


def test_final_effects_use_lossless_intermediates(client, source, tmp_path):
    p,a=import_source(client,source)
    timeline=Timeline.model_validate({"clips":[{"asset_id":a["id"],"start":0,"end":.5}],"title":"QUALITY CHECK"})
    result=render(p["id"],timeline,tmp_path,preview=False)
    assert result["video_encoding"] == "lossless intermediates + one delivery encode"
    assert result["decoded"]


def test_paths_ranges_and_asset_scope_are_validated(client, source):
    p, a = import_source(client, source)
    other = client.post("/api/projects", json={"name": "Other"}).json()
    assert client.get(f"/api/projects/{other['id']}/assets/{a['id']}/file").status_code == 404
    t = Timeline.model_validate({"clips": [{"asset_id": a["id"], "start": 0, "end": 9}]})
    with pytest.raises(ValueError):
        validate_timeline(t, p["id"])
    with pytest.raises(ValidationError):
        Timeline.model_validate({"clips": [{"asset_id": "../../secret", "start": 0, "end": 1}]})
    with pytest.raises(ValidationError):
        Timeline.model_validate({"grade": "movie=/etc/passwd"})
    with pytest.raises(ValidationError):
        Timeline.model_validate({"clips": [{"asset_id": a["id"], "start": 1, "end": .2}]})


def test_caption_offsets_and_no_ass_injection(tmp_path):
    key = "a" * 32
    t = Timeline.model_validate({"clips": [{"asset_id": key, "start": 5, "end": 6}, {"asset_id": key, "start": 1, "end": 3}], "captions": "pop"})
    transcript = {key: {"words": [{"type": "word", "text": "Late", "start": 5.1, "end": 5.6}, {"type": "word", "text": r"{\pos(0,0)}early", "start": 1.2, "end": 2.5}]}}
    count = make_captions(t, transcript, 720, 1280, tmp_path / "test.ass")
    text = (tmp_path / "test.ass").read_text(encoding="utf-8")
    assert count == 2
    assert "0:00:00.10,0:00:00.60" in text
    assert "0:00:01.20,0:00:02.50" in text
    assert r"{\pos" not in text


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://127.0.0.1/a.mp4", "http://169.254.169.254/latest", "http://[::1]/x", "http://user:pass@example.com/x", "https://example.com:8443/x"])
def test_unsafe_reference_urls_rejected(url):
    with pytest.raises(ValueError):
        public_target(url)


def test_cross_origin_and_rebinding_rejected(client):
    assert client.post("/api/projects", json={"name": "No"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 403
    with TestClient(app) as no_header:
        assert no_header.post("/api/projects", json={"name": "No"}).status_code == 403


def test_skill_registry_preserves_upstream_and_no_generated_skills(client):
    p = client.post("/api/projects", json={"name": "Styles"}).json()
    items = client.get(f"/api/projects/{p['id']}/styles").json()
    base = next(s for s in items if s["name"] == "video-use")
    text = client.get(f"/api/projects/{p['id']}/styles/{base['id']}").json()["markdown"]
    assert "Hard Rules" in text
    assert client.put(f"/api/projects/{p['id']}/styles/{base['id']}", json={"markdown": "do not overwrite"}).status_code == 400


def test_schema_and_runtime_configuration_are_restricted(tmp_path):
    schema = strict_json_schema(EditPlan)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    cmd = command(tmp_path, tmp_path/"schema.json", tmp_path/"out.json")
    assert "--ignore-user-config" in cmd and "--ignore-rules" in cmd
    assert "read-only" in cmd
    assert "--dangerously-bypass-approvals-and-sandbox" not in cmd
    assert all(f"features.{x}=false" in cmd for x in DISABLED_FEATURES)


def test_real_queue_lifecycle_and_download(client, source):
    p, a = import_source(client, source)
    timeline = Timeline.model_validate({"clips":[{"asset_id":a["id"],"start":0,"end":.4}]})
    assert client.put(f"/api/projects/{p['id']}/timeline",json={"revision":0,"timeline":timeline.model_dump()}).status_code==200
    queued = client.post(f"/api/projects/{p['id']}/jobs",json={"kind":"preview"})
    assert queued.status_code==200,queued.text
    key=queued.json()["id"]
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        result=client.get(f"/api/jobs/{key}").json()
        if result["status"] in {"completed","failed","cancelled"}:
            break
        time.sleep(.2)
    assert result["status"]=="completed",result
    stream=client.get(f"/api/jobs/{key}/output",headers={"Range":"bytes=0-127"})
    assert stream.status_code==206 and len(stream.content)==128
    assert client.post(f"/api/jobs/{key}/approve").status_code==400


def test_audio_music_mixing_and_caption_composite(client, source, tmp_path):
    p,a=import_source(client,source)
    music=tmp_path/"music.wav"
    run([binary("ffmpeg"),"-v","error","-y","-f","lavfi","-i","sine=frequency=440:duration=1",music])
    with music.open("rb") as f:
        sound=client.post(f"/api/projects/{p['id']}/assets",files={"file":("music.wav",f,"audio/wav")}).json()
    timeline=Timeline.model_validate({"clips":[{"asset_id":a["id"],"start":0,"end":.5}],"music_asset_id":sound["id"],"music_volume":.1})
    outdir=tmp_path/"mix"
    result=render(p["id"],timeline,outdir)
    assert result["decoded"]
    _,stats=run([binary("ffmpeg"),"-hide_banner","-i",outdir/"output.mp4","-af","volumedetect","-vn","-f","null","-"])
    assert b"mean_volume: -inf" not in stats


def test_saved_reference_profile_reusable_across_owner_projects(client,tmp_path):
    first=client.post("/api/projects",json={"name":"Reference owner"}).json()
    second=client.post("/api/projects",json={"name":"New footage"}).json()
    style_id=db.uid()
    (tmp_path/"clean.md").write_text("# Reference Style Overview\nWarm highlights; content is target-specific.",encoding="utf-8")
    with db.connect() as c:
        c.execute("INSERT INTO styles VALUES(?,?,?,?,?)",(style_id,first["id"],"Saved reference",str(tmp_path),"{}"))
    styles=client.get(f"/api/projects/{second['id']}/styles").json()
    assert any(s["id"]==style_id for s in styles)
    profile=client.get(f"/api/projects/{second['id']}/styles/{style_id}").json()
    assert "Warm highlights" in profile["markdown"]
