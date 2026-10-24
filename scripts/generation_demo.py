"""Exercise the same one-submit flow exposed by the browser, using real Codex."""
import json
import sys
import time
from pathlib import Path
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.config import ROOT

client=httpx.Client(base_url='http://127.0.0.1:8765/api',headers={'X-Editor-Client':'video-use'},timeout=120)
def req(method,path,**kwargs):
    r=client.request(method,path,**kwargs);r.raise_for_status();return r.json()
def wait(job):
    last=''
    for _ in range(1200):
        job=req('GET',f"/jobs/{job['id']}")
        message=f"{job['status']} {job['progress']:.0f}% {job['message']}"
        if message!=last: print(message,flush=True);last=message
        if job['status']=='completed':return job
        if job['status'] in {'failed','cancelled'}:raise RuntimeError(job.get('error') or job['status'])
        time.sleep(.7)
    raise TimeoutError('Generation timed out')

p=req('POST','/projects',json={'name':'ImaginePro · transcript to cartoon · live demo'})
styles=req('GET',f"/projects/{p['id']}/styles")
style=next(s for s in styles if s.get('slug')=='hand-drawn-cartoon' and s.get('bundled'))
a=req('POST',f"/projects/{p['id']}/transcript",json={'text':'A little spark can change everything.'})
job=req('POST',f"/projects/{p['id']}/jobs",json={'kind':'generate','aspect':'portrait','input_asset_ids':[a['id']],
    'style_id':style['id'],'prompt':"Make a 5-second hand-drawn cartoon: a little round robot discovers a tiny star, lifts it overhead with a proud smile, and ends with 'Small sparks. Big ideas.' Warm paper, playful acting, keep the narration."})
print(json.dumps({'project_id':p['id'],'job_id':job['id']},indent=2),flush=True)
job=wait(job)
project=req('GET',f"/projects/{p['id']}")
assert project['timeline']['clips'][0]['asset_id']==job['result']['asset_id']
assert job['result']['decoded'] and job['result']['narration']
assert (job['result']['width'],job['result']['height'])==(1080,1920)
assert not any(j['kind']=='plan' for j in req('GET',f"/projects/{p['id']}/jobs"))
report={'project_id':p['id'],'job_id':job['id'],'result':job['result'],'timeline':project['timeline'],
        'workflow':'Import transcript → choose Hand-drawn Cartoon and prompt → one generate request → narrated original animation on timeline'}
(ROOT/'storage/direct-generation-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2),flush=True)
