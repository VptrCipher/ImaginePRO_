"""Reconnect the isolated demo worker, publish a changed tunnel, then open it."""
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import webbrowser
import httpx

ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'cloud'))
from configure_vercel import BASE, TEAM, PROJECT, ENV, configure, run
from backend.local_secrets import _crypt

DEPLOY=ROOT/'storage/demo-deploy'
URL='https://imaginepro-demo.vercel.app'
FLAGS=getattr(subprocess,'CREATE_NO_WINDOW',0)


def connected(url,secret):
    try:
        response=httpx.get(url+'/api/health',headers={'X-ImaginePro-Bridge':secret},timeout=12)
        return response.status_code==200 and response.json().get('application')=='ImaginePro'
    except (httpx.HTTPError,ValueError):return False


def start():
    DEPLOY.mkdir(parents=True,exist_ok=True)
    # Avoid two clicks publishing competing temporary tunnel addresses.
    import msvcrt
    lock=(DEPLOY/'start.lock').open('a+b')
    lock.seek(0)
    if lock.read(1)==b'':lock.write(b'0');lock.flush()
    lock.seek(0)
    try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:return
    config=json.loads(_crypt((DEPLOY/'secrets.dpapi').read_bytes(),decrypt=True))
    secret=config['bridge_secret']
    if not connected('http://127.0.0.1:8767',secret):
        subprocess.Popen([str(ROOT/'.venv/Scripts/pythonw.exe'),str(ROOT/'cloud/run_worker.pyw')],cwd=ROOT,creationflags=FLAGS)
        for _ in range(30):
            if connected('http://127.0.0.1:8767',secret):break
            time.sleep(1)
        else:raise RuntimeError('The isolated ImaginePro demo worker could not start.')
    connection_file=DEPLOY/'connection.json'
    connection=json.loads(connection_file.read_text()) if connection_file.is_file() else {}
    if not connection.get('backend_url') or not connected(connection['backend_url'],secret):
        stamp=str(int(time.time()))
        log=DEPLOY/f'tunnel-{stamp}.log'
        with log.open('wb') as output:
            subprocess.Popen([str(ROOT/'.tools/cloudflared.exe'),'tunnel','--url','http://127.0.0.1:8767','--protocol','http2','--no-autoupdate'],cwd=ROOT,stdout=output,stderr=output,creationflags=FLAGS)
        address=None
        for _ in range(60):
            found=re.findall(r'https://[a-z0-9-]+[.]trycloudflare[.]com',log.read_text(encoding='utf-8',errors='replace'))
            if found and connected(found[-1],secret):address=found[-1];break
            time.sleep(1)
        if not address:raise RuntimeError('The online demo tunnel could not connect. Check the internet connection.')
        connection={'backend_url':address}
        connection_file.write_text(json.dumps(connection),encoding='utf-8')
        configure()
        response=subprocess.run(BASE+['deploy','--prod','--yes','--no-wait','--json','--project',PROJECT,'--scope',TEAM,'--regions','bom1'],cwd=DEPLOY/'package',env=ENV,capture_output=True,text=True,timeout=120,creationflags=FLAGS)
        if response.returncode:raise RuntimeError(response.stderr)
        deployed=json.loads(response.stdout[response.stdout.index('{'):])['deployment']
        for _ in range(90):
            state=json.loads(run(['api',f'/v13/deployments/{deployed["id"]}?teamId={TEAM}','--method','GET']))
            if state['readyState']=='READY':break
            if state['readyState'] in {'ERROR','CANCELED'}:raise RuntimeError('Vercel could not publish the updated connection.')
            time.sleep(3)
        else:raise RuntimeError('Vercel is still building. Check the project dashboard before the demo.')
        connection.update({'deployment_id':deployed['id'],'editor_url':URL})
        connection_file.write_text(json.dumps(connection),encoding='utf-8')
    print('ImaginePro demo connection is running.',flush=True)
    if '--no-open' not in sys.argv:webbrowser.open(URL)
    lock.close()


if __name__=='__main__':
    stream=(DEPLOY/'launcher.log').open('a',encoding='utf-8',buffering=1)
    sys.stdout=stream;sys.stderr=stream
    try:start()
    except Exception as error:
        logging.exception('Demo connection failed')
        if '--no-open' in sys.argv:raise SystemExit(1)
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,'ImaginePro could not reconnect. Check your internet and Vercel sign-in.\n\nDetails: '+str(DEPLOY/'launcher.log'),'ImaginePro online demo',0x10)
