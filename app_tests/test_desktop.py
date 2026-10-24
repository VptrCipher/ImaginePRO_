import hashlib
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend import config
from backend.main import app


@pytest.mark.skipif(os.name!='nt',reason='Windows desktop executable discovery')
def test_codex_remains_available_without_a_developer_shell_path(monkeypatch,tmp_path):
    monkeypatch.delenv('CODEX_PATH',raising=False)
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path))
    monkeypatch.setattr(config.shutil,'which',lambda name:None)
    installed=tmp_path/'OpenAI/Codex/bin/current-installation/codex.exe'
    installed.parent.mkdir(parents=True)
    installed.write_bytes(b'installed executable')
    assert config.binary('codex')==str(installed)


@pytest.mark.skipif(os.name!='nt',reason='Windows desktop executable discovery')
def test_node_remains_available_without_a_developer_shell_path(monkeypatch,tmp_path):
    monkeypatch.delenv('NODE_BINARY_PATH',raising=False)
    monkeypatch.setenv('ProgramFiles',str(tmp_path))
    monkeypatch.setattr(config.shutil,'which',lambda name:None)
    installed=tmp_path/'nodejs/node.exe'
    installed.parent.mkdir()
    installed.write_bytes(b'installed executable')
    assert config.binary('node')==str(installed)


def test_explicit_animation_browser_is_checked_before_startup(monkeypatch,tmp_path):
    path=tmp_path/'browser.exe'
    monkeypatch.setenv('FRAMECRAFT_BROWSER_PATH',str(path))
    assert config.animation_browser() is None
    path.write_bytes(b'installed browser')
    assert config.animation_browser()==str(path)


def test_launcher_can_identify_this_installation_without_touching_projects():
    with TestClient(app,headers={'X-Editor-Client':'video-use'}) as client:
        project=client.post('/api/projects',json={'name':'Preserved during startup check'}).json()
        response=client.get('/api/health')
        assert response.status_code==200
        status=response.json()
        assert status['application']=='ImaginePro'
        assert status['installation_id']==hashlib.sha256(str(config.ROOT).casefold().encode()).hexdigest()[:20]
        assert status['tools']['frontend'] and 'animation_browser' in status['tools']
        assert client.get('/api/projects/'+project['id']).json()==project
