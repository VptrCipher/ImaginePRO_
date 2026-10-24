import importlib
import time

from fastapi.testclient import TestClient


def gateway(monkeypatch):
    monkeypatch.setenv('IMAGINEPRO_BRIDGE_SECRET','test-private-bridge-key-'*3)
    module=importlib.import_module('cloud.gateway')
    return module


def test_gateway_rejects_anonymous_and_private_paths(monkeypatch):
    g=gateway(monkeypatch)
    with TestClient(g.app) as client:
        assert client.get('/api/health').status_code==403
        assert client.get('/docs').status_code==404
        assert client.get('/').status_code==404
        response=client.get('/api/health',headers={'X-ImaginePro-Bridge':g.SECRET,'Host':'demo.trycloudflare.com'})
        assert response.status_code==200
        assert response.headers['cache-control']=='private, no-store'


def test_chunk_upload_checks_offsets_and_assembles_transcript(monkeypatch):
    g=gateway(monkeypatch)
    headers={'X-ImaginePro-Bridge':g.SECRET,'Host':'demo.trycloudflare.com'}
    with TestClient(g.app,headers=headers) as client:
        project=client.post('/api/projects',json={'name':'Bridge test'}).json()
        payload=b'A small transcript for the online demo.'
        started=client.post('/api/bridge/uploads',json={'project_id':project['id'],'name':'script.txt','size':len(payload)})
        assert started.status_code==200
        path='/api/bridge/uploads/'+started.json()['id']
        assert client.patch(path+'?offset=1',content=payload[:10]).status_code==409
        assert client.patch(path+'?offset=0',content=payload[:10]).json()['received']==10
        assert client.post(path+'/finish').status_code==409
        assert client.patch(path+'?offset=10',content=payload[10:]).status_code==200
        result=client.post(path+'/finish')
        assert result.status_code==200,result.text
        asset=result.json()
        assert client.get(asset['url']).content==payload
        assert client.post(path+'/finish').status_code==404
        # A link grants one particular read only, never project/API access.
        expiry=int(time.time())+300
        signed={'bridge_exp':expiry,'bridge_sig':g.signature(asset['url'],'',expiry)}
        anonymous=TestClient(g.app)
        assert anonymous.get(asset['url'],params=signed).status_code==200
        assert anonymous.get('/api/projects',params=signed).status_code==403
        assert anonymous.get(asset['url'],params={**signed,'bridge_exp':expiry+1}).status_code==403
        assert anonymous.post(asset['url'],params=signed).status_code==403
