"""Start only the isolated online-demo worker, without opening a terminal."""
import os
import sys
import json
import logging
from pathlib import Path

root=Path(__file__).resolve().parents[1]
os.chdir(root);sys.path.insert(0,str(root))
from backend.local_secrets import _crypt
config=json.loads(_crypt((root/'storage/demo-deploy/secrets.dpapi').read_bytes(),decrypt=True))
os.environ['VIDEO_EDITOR_STORAGE']=str(root/'storage/cloud-demo')
os.environ['IMAGINEPRO_BRIDGE_SECRET']=config['bridge_secret']
os.environ['IMAGINEPRO_DEMO']='1'
# config was imported while reading the owner-bound credential store. Reset its
# storage target before importing the app/db/transcription modules.
from backend import config as backend_config
backend_config.STORAGE=Path(os.environ['VIDEO_EDITOR_STORAGE'])
backend_config.STORAGE.mkdir(parents=True,exist_ok=True)
from backend import local_secrets
local_secrets.STORAGE=backend_config.STORAGE
logs=root/'storage/demo-deploy'
sys.stdin=open(os.devnull,'r');sys.stdout=open(logs/'worker.log','a',encoding='utf-8',buffering=1);sys.stderr=sys.stdout
logging.basicConfig(stream=sys.stdout,level=logging.INFO)
import uvicorn
uvicorn.run('cloud.gateway:app',host='127.0.0.1',port=8767,access_log=False,log_config=None)
