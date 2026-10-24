"""Build a minimal deployable package. Never include the worker's data/secrets."""
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'storage/demo-deploy/package'


def build():
    PACKAGE.mkdir(parents=True,exist_ok=True)
    # Next output names change between builds; clear only this checked staging root.
    public=PACKAGE/'public'
    assert public.resolve().is_relative_to((ROOT/'storage/demo-deploy').resolve())
    if public.exists():shutil.rmtree(public)
    shutil.copytree(ROOT/'frontend/out',public)
    shutil.copyfile(ROOT/'cloud/login.html',public/'login.html')
    (PACKAGE/'api').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'cloud/api/bridge.mjs',PACKAGE/'api/bridge.mjs')
    shutil.copyfile(ROOT/'cloud/vercel.json',PACKAGE/'vercel.json')
    (PACKAGE/'package.json').write_text(json.dumps({'name':'imaginepro-demo','private':True,'type':'module','engines':{'node':'24.x'}}),encoding='utf-8')
    files=[{'file':p.relative_to(PACKAGE).as_posix(),'bytes':p.stat().st_size} for p in PACKAGE.rglob('*') if p.is_file() and '.vercel' not in p.parts]
    print(json.dumps({'path':str(PACKAGE),'files':len(files),'bytes':sum(p['bytes'] for p in files)}))


if __name__=='__main__':build()
