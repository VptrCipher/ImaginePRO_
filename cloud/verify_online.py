"""Exercise large media import through the public editor without logging secrets."""
import hashlib
import io
import json
import os
import sys
from pathlib import Path
import httpx
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.local_secrets import _crypt

DEPLOY=ROOT/'storage/demo-deploy'
URL='https://imaginepro-demo.vercel.app'


def verify():
    config=json.loads(_crypt((DEPLOY/'secrets.dpapi').read_bytes(),decrypt=True))
    with httpx.Client(base_url=URL,timeout=120,follow_redirects=True) as client:
        assert client.get('/api/health').status_code==401
        login=client.post('/api/demo/login',json={'password':config['demo_password']})
        login.raise_for_status()
        assert client.get('/api/runtime').json()['authenticated_with_chatgpt']
        project=client.post('/api/projects',json={'name':'Deployment verification'}).json()
        stream=io.BytesIO()
        Image.frombytes('RGB',(1400,1400),os.urandom(1400*1400*3)).save(stream,format='PNG')
        data=stream.getvalue()
        assert len(data)>4.5*1024*1024
        created=client.post('/api/bridge/uploads',json={'project_id':project['id'],'name':'Large import verification.png','size':len(data)})
        created.raise_for_status()
        upload=created.json()
        for offset in range(0,len(data),upload['chunk_size']):
            response=client.patch('/api/bridge/uploads/'+upload['id'],params={'offset':offset},content=data[offset:offset+upload['chunk_size']],headers={'Content-Type':'application/octet-stream'})
            response.raise_for_status()
            print(f'Uploaded {response.json()["received"]}/{len(data)} bytes',flush=True)
        response=client.post('/api/bridge/uploads/'+upload['id']+'/finish')
        response.raise_for_status()
        asset=response.json()
        media=client.get(asset['url'])
        media.raise_for_status()
        assert hashlib.sha256(media.content).digest()==hashlib.sha256(data).digest()
        ranged=client.get(asset['url'],headers={'Range':'bytes=0-127'})
        assert ranged.status_code==206 and ranged.content==data[:128]
        result={'url':URL,'project_id':project['id'],'upload_bytes':len(data),'byte_identical_download':True,'range_status':ranged.status_code,'codex_authenticated':True}
        (DEPLOY/'online-import-verification.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result),flush=True)
    access=Path.home()/'Downloads/ImaginePro-Online-Demo.txt'
    access.write_text(f'ImaginePro online demo\n\nOpen: {URL}\nDemo passcode: {config["demo_password"]}\n\nKeep this PC on, connected to the internet, and awake during the demo.\nThe Vercel editor uses the isolated Codex-connected worker on this PC.\nThe desktop app and existing projects are separate.\n\nThe demo tunnel is temporary; restarting the connection may require republishing its URL.\n',encoding='utf-8')
    print(json.dumps({'access_file':str(access)}),flush=True)


if __name__=='__main__':verify()
