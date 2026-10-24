import json
from uuid import uuid4
import httpx
import pytest
from fastapi.testclient import TestClient
from backend import director
from backend.main import app


def test_director_enhances_via_agenticorg_without_exposing_key(monkeypatch):
    company,agent=str(uuid4()),str(uuid4())
    calls=[]
    def provider(request):
        calls.append(request)
        assert request.headers['Authorization']=='Bearer test-private-key'
        if request.url.path=='/api/v1/companies':return httpx.Response(200,json={'items':[{'id':company}]})
        if request.url.path=='/api/v1/agents':return httpx.Response(200,json={'items':[{'id':agent,'company_id':company,'agent_type':'imaginepro_director'}]})
        if request.url.path==f'/api/v1/agents/{agent}':return httpx.Response(200,json={'id':agent,'company_id':company,'agent_type':'imaginepro_director','authorized_tools':[],'connector_ids':[],'status':'active'})
        assert request.url.path=='/api/v1/chat/query'
        body=json.loads(request.content)
        assert body['company_id']==company and body['agent_id']==agent
        assert 'robot discovers a star' in body['query'] and 'portrait' in body['query']
        return httpx.Response(200,json={'answer':'A five-second paper cartoon. A curious robot discovers a star, raises it, then holds a proud closing pose.','agent':'ImaginePro Enhance Director','hitl_trigger':None})
    actual_client=httpx.Client
    monkeypatch.setattr(director.httpx,'Client',lambda **kwargs:actual_client(**kwargs,transport=httpx.MockTransport(provider)))
    monkeypatch.setattr(director,'agenticorg_key',lambda:'test-private-key')
    monkeypatch.setattr(director,'configuration',lambda:director.DirectorConfiguration())
    with TestClient(app,headers={'X-Editor-Client':'video-use'}) as client:
        p=client.post('/api/projects',json={'name':'Director enhancement'}).json()
        result=client.post(f"/api/projects/{p['id']}/enhance",json={'prompt':'robot discovers a star','aspect':'portrait'})
        assert result.status_code==200,result.text
        assert result.json()['provider']=='Pine Labs AgenticOrg'
        assert result.json()['prompt'].startswith('A five-second')
        assert 'test-private-key' not in result.text
        assert len(calls)==4
        assert client.get(f"/api/projects/{p['id']}").json()['revision']==0


def test_director_auth_failure_is_visible_and_does_not_change_project(monkeypatch):
    actual_client=httpx.Client
    transport=httpx.MockTransport(lambda request:httpx.Response(401,json={'detail':'private upstream diagnostic'}))
    monkeypatch.setattr(director.httpx,'Client',lambda **kwargs:actual_client(**kwargs,transport=transport))
    monkeypatch.setattr(director,'agenticorg_key',lambda:'test-private-key')
    monkeypatch.setattr(director,'configuration',lambda:director.DirectorConfiguration())
    with TestClient(app,headers={'X-Editor-Client':'video-use'}) as client:
        p=client.post('/api/projects',json={'name':'Director denied'}).json()
        result=client.post(f"/api/projects/{p['id']}/enhance",json={'prompt':'Keep my original idea'})
        assert result.status_code==401 and 'HTTP 401' in result.text
        assert 'test-private-key' not in result.text and 'private upstream' not in result.text
        assert client.get(f"/api/projects/{p['id']}").json()['timeline']==p['timeline']


def test_director_rejects_foreign_company_and_tool_enabled_agent():
    company,agent=str(uuid4()),str(uuid4())
    def provider(request):
        if request.url.path.endswith('/companies'):return httpx.Response(200,json={'items':[{'id':company}]})
        return httpx.Response(200,json={'company_id':company,'agent_type':'imaginepro_director','authorized_tools':['send_email'],'status':'active'})
    with httpx.Client(transport=httpx.MockTransport(provider),base_url=director.DEFAULT_URL) as client:
        with pytest.raises(director.DirectorError,match='not available'):
            director.resolve_agent(client,director.DirectorConfiguration(company_id=str(uuid4())))
        with pytest.raises(director.DirectorError,match='no tools'):
            director.resolve_agent(client,director.DirectorConfiguration(company_id=company,agent_id=agent))


@pytest.mark.parametrize('url',['http://agenticorg.ai','https://example.com','https://agenticorg.ai.evil.test','https://u:p@agenticorg.ai','https://agenticorg.ai/?key=secret'])
def test_director_credentials_stay_on_reviewed_provider_hosts(url):
    with pytest.raises(ValueError):director.DirectorConfiguration(base_url=url)


def test_director_configuration_never_returns_or_serializes_key(monkeypatch,tmp_path):
    saved=[]
    monkeypatch.setattr(director,'CONFIG',tmp_path/'director.json')
    monkeypatch.setattr(director,'agenticorg_key',lambda:'test-private-key')
    monkeypatch.setattr(director,'set_agenticorg_key',lambda key:saved.append(key))
    result=director.save_configuration(director.DirectorConfiguration(api_key='test-private-key'))
    assert saved==['test-private-key'] and result['key_configured']
    assert 'test-private-key' not in json.dumps(result)+director.CONFIG.read_text()
