import json
import time
from pathlib import Path
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend import agent, db
from backend.composition import Film, Scene, Element
from backend.main import app
from backend.config import ROOT
from backend.config import binary, project_dir
from backend.media import run


def film():
    return Film(summary="A fresh illustrated test", scenes=[Scene(duration=3, background="#f3eddf",texture="paper",transition="cut",elements=[
        Element(id="disc",kind="ellipse",x=540,y=800,width=600,height=600,fill="#3996a4",end=3,entrance="pop"),
        Element(id="heading",kind="text",x=90,y=300,width=900,height=180,text="Ideas in motion",font_size=92,fill="#172f3b",align="center",end=3),
        Element(id="closing",kind="text",x=90,y=1300,width=900,height=150,text="A new beginning.",font_size=70,fill="#172f3b",start=1.5,end=3)])])


def test_scene_data_rejects_executable_content_and_cyclic_groups():
    with pytest.raises(ValidationError):
        Element(id="bad",kind="path",x=0,y=0,end=3,path='<script>alert(1)</script>')
    with pytest.raises(ValidationError):
        Element(id="bad",kind="rect",x=0,y=0,end=3,fill='url(https://example.com/x)')
    with pytest.raises(ValidationError,match="cyclic"):
        Scene(duration=3,background="#ffffff",elements=[Element(id="loop",parent="loop",kind="group",x=0,y=0,end=3)])
    with pytest.raises(ValidationError,match="timing"):
        Scene(duration=3,background="#ffffff",elements=[Element(id="late",kind="rect",x=0,y=0,end=4)])


def test_transcript_upload_supports_text_and_subtitle_formats():
    with TestClient(app,headers={"X-Editor-Client":"video-use"}) as client:
        p=client.post('/api/projects',json={"name":"Transcript imports"}).json()
        result=client.post(f"/api/projects/{p['id']}/transcript",json={"text":"Ideas become stories."})
        assert result.status_code==200
        assert result.json()["kind"]=="text" and result.json()["metadata"]["word_count"]==3
        srt=b'1\n00:00:00,000 --> 00:00:02,000\nHello, world.\n'
        result=client.post(f"/api/projects/{p['id']}/assets",files={"file":("script.srt",srt,"text/plain")})
        assert result.status_code==200 and result.json()["metadata"]["text"]=='Hello, world.'


def test_generate_queue_renders_and_places_result_on_timeline_without_approval(monkeypatch):
    if not (ROOT/'backend/framecraft/node_modules/puppeteer-core/package.json').exists():
        pytest.skip('Install Canvas rendering dependencies')
    captured=[]
    class TestRuntime:
        def generate(self,prompt,model,workspace,cancel=None,images=None):
            captured.append(prompt)
            assert model is Film
            return film()
    monkeypatch.setattr(agent,'runtime',TestRuntime())
    with TestClient(app,headers={"X-Editor-Client":"video-use"}) as client:
        p=client.post('/api/projects',json={"name":"Direct generation"}).json()
        # No dummy video is required. The request goes straight into generation.
        job=client.post(f"/api/projects/{p['id']}/jobs",json={"kind":"generate","prompt":"Make a 3-second original illustrated idea video","aspect":"portrait"}).json()
        deadline=time.monotonic()+150
        while time.monotonic()<deadline:
            job=client.get(f"/api/jobs/{job['id']}").json()
            if job['status'] in {'completed','failed','cancelled'}:break
            time.sleep(.4)
        assert job['status']=='completed',job.get('error')
        assert len(captured)==1 and '3-second original illustrated' in captured[0]
        assert job['result']['decoded'] and job['result']['revision']==1
        updated=client.get(f"/api/projects/{p['id']}").json()
        assert len(updated['timeline']['clips'])==1
        generated=next(a for a in updated['assets'] if a['id']==updated['timeline']['clips'][0]['asset_id'])
        assert generated['kind']=='video' and generated['metadata']['generated']
        assert updated['timeline']['clips'][0]['end']==3
        # Centered text belongs inside its top-left bounding box. Regression:
        # drawing at x=0 with center alignment clipped the left half of headings.
        workspace=project_dir(p['id'])/'edit/jobs'/job['id']
        still=workspace/'heading-check.png'
        run([binary('ffmpeg'),'-v','error','-y','-ss','1','-i',workspace/'output.mp4','-frames:v','1',still])
        image=Image.open(still).convert('RGB')
        ink=[x for y in range(300,480) for x in range(1080) if max(image.getpixel((x,y)))<100]
        assert ink and min(ink)>90 and max(ink)>750 and max(ink)<990
        output=client.get(f"/api/jobs/{job['id']}/output",headers={'Range':'bytes=0-127'})
        assert output.status_code==206 and len(output.content)==128


@pytest.mark.parametrize('cancelled',[False,True])
def test_unfinished_generation_preserves_saved_timeline(monkeypatch,cancelled):
    from backend import generation
    from backend.media import Cancelled
    def stop(*args,**kwargs):
        raise Cancelled('Stopped') if cancelled else RuntimeError('Scene validation failed')
    monkeypatch.setattr(generation,'generate',stop)
    with TestClient(app,headers={'X-Editor-Client':'video-use'}) as client:
        p=client.post('/api/projects',json={'name':'Generation recovery'}).json()
        job=client.post(f"/api/projects/{p['id']}/jobs",json={'kind':'generate','prompt':'Create a short film'}).json()
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            job=client.get(f"/api/jobs/{job['id']}").json()
            if job['status'] in {'failed','cancelled'}:break
            time.sleep(.05)
        assert job['status']==('cancelled' if cancelled else 'failed')
        updated=client.get(f"/api/projects/{p['id']}").json()
        assert updated['timeline']==p['timeline'] and updated['revision']==p['revision']
