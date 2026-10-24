"""Windowless server entry point. Projects and credentials keep their existing paths."""
import datetime
import json
import logging
import os
from pathlib import Path
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0,str(ROOT))
storage=Path(os.environ.get('VIDEO_EDITOR_STORAGE',ROOT/'storage')).resolve()
logs=storage/'logs'
logs.mkdir(parents=True,exist_ok=True)
sys.stdin=open(os.devnull,'r')
sys.stdout=open(logs/'server.log','a',encoding='utf-8',buffering=1)
sys.stderr=sys.stdout
logging.basicConfig(stream=sys.stdout,level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s: %(message)s')

try:
    # Native media work never inherits a developer shell's arbitrary import path.
    print('\nImaginePro starting '+datetime.datetime.now(datetime.timezone.utc).isoformat(),flush=True)
    state=storage/'desktop'
    state.mkdir(exist_ok=True)
    (state/'server.json').write_text(json.dumps({'pid':os.getpid(),'root':str(ROOT),
        'started':datetime.datetime.now(datetime.timezone.utc).isoformat()}),encoding='utf-8')
    from backend.config import binary,animation_browser
    for name in ['codex','node','ffmpeg','ffprobe']:
        binary(name)
    import uvicorn
    uvicorn.run('backend.main:app',host='127.0.0.1',port=8765,access_log=False,log_config=None)
except BaseException:
    traceback.print_exc()
    raise
