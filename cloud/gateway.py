"""Authenticated demo gateway around an isolated ImaginePro worker on this PC."""
import hashlib
import hmac
import json
import os
import re
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import parse_qsl, urlencode
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from backend import main, db
from backend.config import STORAGE, MAX_UPLOAD

SECRET=os.environ.get('IMAGINEPRO_BRIDGE_SECRET','')
if len(SECRET)<32:raise RuntimeError('A private demo bridge secret is required')
UPLOADS=STORAGE/'incoming'
UPLOADS.mkdir(parents=True,exist_ok=True)
LOCK=threading.Lock()
ID=r'[a-f0-9]{32}'
READ=re.compile(rf'^/api/(?:projects/{ID}/assets/{ID}/(?:file|thumbnail)|jobs/{ID}/(?:output|verification))$')
ALLOWED=re.compile(rf'^/api/(?:health|runtime|director/config|projects(?:/{ID}(?:/(?:timeline|assets(?:/{ID}/(?:file|thumbnail))?|transcript|reference-url|styles(?:/[^/]+)?|jobs|enhance))?)?|jobs/{ID}(?:/(?:cancel|approve|output|verification))?|bridge/uploads(?:/{ID}(?:/finish)?)?)$')


def signature(path,query,expires):
    return hmac.new(SECRET.encode(),f'GET\n{path}\n{query}\n{expires}'.encode(),hashlib.sha256).hexdigest()


@asynccontextmanager
async def lifespan(app):
    async with main.lifespan(main.app):yield


worker=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)


class UploadStart(BaseModel):
    project_id:str=Field(pattern=r'^[a-f0-9]{32}$')
    name:str=Field(min_length=1,max_length=200)
    size:int=Field(gt=0,le=MAX_UPLOAD)


@worker.exception_handler(ValueError)
async def invalid(request,error):
    return JSONResponse({'detail':str(error)},status_code=400)


@worker.exception_handler(KeyError)
async def missing(request,error):
    return JSONResponse({'detail':str(error)},status_code=404)


@worker.post('/api/bridge/uploads')
def upload_start(body:UploadStart):
    db.project(body.project_id)
    key=db.uid()
    name=Path(body.name).name
    if Path(name).suffix.lower() not in {'.mp4','.mov','.mkv','.webm','.m4v','.avi','.wav','.mp3','.m4a','.aac','.ogg','.flac','.png','.jpg','.jpeg','.webp','.txt','.srt','.vtt'}:
        raise HTTPException(400,'Unsupported media type')
    (UPLOADS/(key+'.json')).write_text(json.dumps(dict(project_id=body.project_id,name=name,size=body.size)),encoding='utf-8')
    (UPLOADS/(key+'.part')).touch()
    return {'id':key,'chunk_size':2*1024*1024}


def upload_paths(key):
    if not re.fullmatch(ID,key):raise HTTPException(404,'Upload not found')
    meta=UPLOADS/(key+'.json');part=UPLOADS/(key+'.part')
    if not meta.is_file() or not part.is_file():raise HTTPException(404,'Upload not found')
    return meta,part,json.loads(meta.read_text(encoding='utf-8'))


@worker.patch('/api/bridge/uploads/{key}')
async def upload_chunk(key:str,request:Request,offset:int=0):
    content=bytearray()
    async for block in request.stream():
        content.extend(block)
        if len(content)>2*1024*1024:raise HTTPException(413,'Upload chunk is too large')
    with LOCK:
        meta,part,data=upload_paths(key)
        if offset!=part.stat().st_size:raise HTTPException(409,'Upload position changed; retry the import')
        if offset+len(content)>data['size']:raise HTTPException(413,'Upload exceeds its declared size')
        with part.open('ab') as stream:stream.write(content)
    return {'received':offset+len(content)}


@worker.post('/api/bridge/uploads/{key}/finish')
async def upload_finish(key:str):
    meta,part,data=upload_paths(key)
    if part.stat().st_size!=data['size']:raise HTTPException(409,'Upload is incomplete')
    def ingest():
        with part.open('rb') as stream:return main.accept_file(data['project_id'],data['name'],stream)
    result=await run_in_threadpool(ingest)
    part.unlink();meta.unlink()
    return result


worker.mount('/',main.app)


class AuthenticatedGateway:
    def __init__(self,application):self.application=application
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.application(scope,receive,send)
        path=scope.get('path','')
        if not ALLOWED.fullmatch(path):return await JSONResponse({'detail':'Not found'},status_code=404)(scope,receive,send)
        headers=dict(scope['headers'])
        authorized=hmac.compare_digest(headers.get(b'x-imaginepro-bridge',b'').decode(),SECRET)
        params=parse_qsl(scope.get('query_string',b'').decode(),keep_blank_values=True)
        clean=[(k,v) for k,v in params if k not in {'bridge_exp','bridge_sig'}]
        original=urlencode(clean)
        if not authorized and scope['method'] in {'GET','HEAD'} and READ.fullmatch(path):
            values=dict(params)
            try:
                expiry=int(values.get('bridge_exp','0'))
                authorized=(time.time()<expiry<=time.time()+3700 and hmac.compare_digest(values.get('bridge_sig',''),signature(path,original,expiry)))
            except (ValueError,TypeError):authorized=False
        if not authorized:return await JSONResponse({'detail':'Demo bridge authentication required'},status_code=403)(scope,receive,send)
        # The original application remains loopback-only and unchanged.
        clean_headers=[(k,v) for k,v in scope['headers'] if k not in {b'host',b'origin',b'authorization',b'cookie',b'x-imaginepro-bridge',b'x-editor-client'}]
        clean_headers.extend([(b'host',b'127.0.0.1'),(b'x-editor-client',b'video-use')])
        scope=dict(scope,headers=clean_headers,query_string=original.encode())
        async def private(message):
            if message['type']=='http.response.start':
                message=dict(message,headers=[(k,v) for k,v in message.get('headers',[]) if k!=b'cache-control']+[(b'cache-control',b'private, no-store')])
            await send(message)
        await self.application(scope,receive,private)


app=AuthenticatedGateway(worker)
