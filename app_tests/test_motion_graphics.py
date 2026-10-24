import threading
from pathlib import Path
import numpy as np
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from backend.main import app
from backend.models import MotionGraphic, Timeline
from backend.motion_graphics import frame, render_overlay
from backend.media import run, probe, validate_timeline, Cancelled
from backend.rendering import render
from backend.config import binary


def graphic(**changes):
    return MotionGraphic.model_validate({"template":"kinetic_title","text":"Your story.","detail":"A little more possibility.","start":0,"duration":2,"position":"center","palette":"cream",**changes})


@pytest.mark.parametrize("template",["kinetic_title","callout","lower_third"])
def test_animated_layer_changes_over_time_and_stays_transparent_outside_card(template):
    g=graphic(template=template)
    early=np.array(frame([g],640,360,.06))
    middle=np.array(frame([g],640,360,.8))
    later=np.array(frame([g],640,360,1.2))
    assert early[:,:,3].sum()<middle[:,:,3].sum()
    assert not np.array_equal(middle,later),"The rotating accent/progress line must actually animate"
    assert middle[0,0,3]==0 and middle[:,:,3].max()>240
    assert np.array(frame([g],640,360,2.1))[:,:,3].sum()==0


def test_no_animation_code_or_unsupported_template_is_accepted():
    with pytest.raises(ValidationError):
        graphic(template="python:open('/etc/passwd')")
    with pytest.raises(ValidationError):
        graphic(palette="movie=/etc/passwd")
    with pytest.raises(ValidationError):
        graphic(duration=100)


def test_overlay_cancel_is_respected(tmp_path):
    cancelled=threading.Event()
    cancelled.set()
    with pytest.raises(Cancelled):
        render_overlay([graphic()],320,180,tmp_path,cancelled)


def test_talking_head_style_overlay_composites_over_real_video(tmp_path):
    headers={"X-Editor-Client":"video-use"}
    source=tmp_path/"source.mp4"
    run([binary("ffmpeg"),"-v","error","-y","-f","lavfi","-i","testsrc2=size=640x360:rate=30:duration=2","-c:v","libx264","-pix_fmt","yuv420p",source])
    with TestClient(app,headers=headers) as client:
        p=client.post("/api/projects",json={"name":"Overlay integration"}).json()
        with source.open("rb") as f:
            a=client.post(f"/api/projects/{p['id']}/assets",files={"file":("source.mp4",f,"video/mp4")}).json()
        timeline=Timeline.model_validate({"clips":[{"asset_id":a["id"],"start":0,"end":2}],"motion_graphics":[graphic(template="lower_third",text="A speaker",detail="Supplied label",position="lower_left",duration=1.5,start=.25).model_dump()]})
        assert validate_timeline(timeline,p["id"])==2
        out=tmp_path/"render"
        result=render(p["id"],timeline,out,preview=True)
        assert result["decoded"] and result["motion_graphics"]==1
        overlay=probe(out/"motion-graphics.mov")
        assert overlay["codec"]=="png", "Alpha intermediate must remain lossless"
        # Source is not covered by a fullscreen opaque layer: upper frame stays transparent.
        image=np.array(frame(timeline.motion_graphics,1280,720,1.0))
        assert image[:300,:,3].sum()==0
        assert image[440:550,100:400,3].sum()>0
        too_long=timeline.model_copy(deep=True)
        too_long.motion_graphics[0].duration=3
        with pytest.raises(ValueError,match="Animation windows"):
            validate_timeline(too_long,p["id"])
