"""Run the real import → style/prompt → generated timeline flow on speech footage."""
import json
import sys
import time
from pathlib import Path
import httpx

root=Path(__file__).resolve().parents[1]
client=httpx.Client(base_url='http://127.0.0.1:8765/api',headers={'X-Editor-Client':'video-use'},timeout=120)
def request(method,path,**kwargs):
    response=client.request(method,path,**kwargs)
    response.raise_for_status()
    return response.json()

project=request('POST','/projects',json={'name':'ImaginePro · footage with animated callouts'})
source=root/'.fixtures/raw-speech.mp4'
with source.open('rb') as stream:
    asset=request('POST',f"/projects/{project['id']}/assets",files={'file':(source.name,stream,'video/mp4')})
styles=request('GET',f"/projects/{project['id']}/styles")
style=next(s for s in styles if s.get('slug')=='vox-explainer' and s.get('bundled'))
job=request('POST',f"/projects/{project['id']}/jobs",json={'kind':'generate','aspect':'landscape','input_asset_ids':[asset['id']],
    'style_id':style['id'],'prompt':'Create a 4-second opening from this footage. Preserve the original picture and speech. Add two compact animated editorial callouts illustrating words actually spoken, use the selected Vox style and readable pop captions. Keep most of the source picture visible.'})
print(json.dumps({'project_id':project['id'],'job_id':job['id']},indent=2),flush=True)
last=''
deadline=time.monotonic()+1000
while time.monotonic()<deadline:
    job=request('GET',f"/jobs/{job['id']}")
    status=f"{job['status']} {job['progress']:.0f}% {job['message']}"
    if status!=last:print(status,flush=True);last=status
    if job['status'] in {'completed','failed','cancelled'}:break
    time.sleep(1)
assert job['status']=='completed',job.get('error') or job
updated=request('GET',f"/projects/{project['id']}")
assert updated['timeline']['clips'][0]['asset_id']==job['result']['asset_id']
assert job['result']['decoded'] and job['result']['footage_edited'] and job['result']['caption_cues']>0
assert (job['result']['width'],job['result']['height'])==(1920,1080)
report={'project_id':project['id'],'job_id':job['id'],'result':job['result'],'timeline':updated['timeline']}
(root/'storage/footage-generation-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2),flush=True)
