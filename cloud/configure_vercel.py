"""Configure only this demo project using the CLI's authenticated session."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.config import binary
from backend.local_secrets import _crypt

TEAM='team_2ooS5cJ2DIu0XGqE7LudXCrY'
PROJECT='imaginepro-demo'
DEPLOY=ROOT/'storage/demo-deploy'
CLI=ROOT/'.tools/vercel/node_modules/vercel/dist/index.js'
BASE=[binary('node'),str(CLI)]
ENV=dict(os.environ,VERCEL_TELEMETRY_DISABLED='1',NO_COLOR='1')


def run(args,secret=None):
    result=subprocess.run(BASE+args,cwd=ROOT,env=ENV,input=secret,capture_output=True,text=True,timeout=90,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:
        output=result.stdout+result.stderr
        if secret:output=output.replace(secret,'[redacted]')
        raise RuntimeError(output)
    return result.stdout


def configure():
    # The explicit team ID prevents a different CLI default from receiving data.
    response=run(['api',f'/v9/projects/{PROJECT}?teamId={TEAM}','--method','GET'])
    project=json.loads(response[response.index('{'):])
    assert project['accountId']==TEAM and project['name']==PROJECT
    (DEPLOY/'vercel-project.json').write_text(json.dumps({'projectId':project['id'],'orgId':TEAM,'projectName':PROJECT}),encoding='utf-8')
    package=DEPLOY/'package'
    (package/'.vercel').mkdir(exist_ok=True)
    (package/'.vercel/project.json').write_text(json.dumps({'projectId':project['id'],'orgId':TEAM,'projectName':PROJECT}),encoding='utf-8')
    config=json.loads(_crypt((DEPLOY/'secrets.dpapi').read_bytes(),decrypt=True))
    connection=json.loads((DEPLOY/'connection.json').read_text())
    values={'IMAGINEPRO_BRIDGE_SECRET':config['bridge_secret'],'IMAGINEPRO_BACKEND_URL':connection['backend_url'],'IMAGINEPRO_DEMO_PASSWORD':config['demo_password']}
    for key,value in values.items():
        run(['env','add',key,'--environment','production,preview','--project',project['id'],'--scope',TEAM,'--sensitive','--force','--yes'],secret=value)
        print(f'{key}: configured securely',flush=True)
    print(json.dumps({'project':PROJECT,'id':project['id'],'team':TEAM}),flush=True)


if __name__=='__main__':configure()
