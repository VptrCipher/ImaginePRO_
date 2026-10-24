import test from 'node:test';
import assert from 'node:assert/strict';
import {createHmac} from 'node:crypto';
import bridge from './api/bridge.mjs';

const secret='test-bridge-secret-'.repeat(4);
process.env.IMAGINEPRO_BRIDGE_SECRET=secret;
process.env.IMAGINEPRO_BACKEND_URL='https://renderer.example.test';
process.env.IMAGINEPRO_DEMO_PASSWORD='test-demo-passcode';
const request=(path,options={})=>new Request('https://editor.example.test/api/bridge?__path='+path,options);
let cookie;
test('login and protected API session',async()=>{
  assert.equal((await bridge.fetch(request('projects'))).status,401);
  assert.equal((await bridge.fetch(request('demo/login',{method:'POST',body:JSON.stringify({password:'wrong'})}))).status,401);
  const login=await bridge.fetch(request('demo/login',{method:'POST',body:JSON.stringify({password:'test-demo-passcode'})}));
  assert.equal(login.status,200);
  assert.match(login.headers.get('set-cookie'),/HttpOnly; Secure; SameSite=Lax/);
  cookie=login.headers.get('set-cookie').split(';')[0];
  assert.deepEqual(await login.json(),{ok:true});
});
test('media redirect has a path-specific signature without a bridge credential',async()=>{
  const path='projects/'+'a'.repeat(32)+'/assets/'+'b'.repeat(32)+'/file';
  const result=await bridge.fetch(request(path,{headers:{cookie}}));
  assert.equal(result.status,307);
  const target=new URL(result.headers.get('location'));
  assert.equal(target.hostname,'renderer.example.test');
  const expiry=target.searchParams.get('bridge_exp');
  assert.equal(target.searchParams.get('bridge_sig'),createHmac('sha256',secret).update(`GET\n/api/${path}\n\n${expiry}`).digest('hex'));
  assert.equal(target.href.includes(secret),false);
});
test('chunk upload forwards bytes and only server authentication',async()=>{
  const original=globalThis.fetch;
  globalThis.fetch=async(url,options)=>{
    assert.equal(String(url),'https://renderer.example.test/api/bridge/uploads/'+'a'.repeat(32)+'?offset=0');
    assert.equal(options.headers.get('X-ImaginePro-Bridge'),secret);
    assert.equal(options.headers.has('cookie'),false);
    assert.equal(options.body.byteLength,2*1024*1024);
    return new Response('{"received":2097152}',{status:200,headers:{'content-type':'application/json'}});
  };
  try{
    const response=await bridge.fetch(request('bridge/uploads/'+'a'.repeat(32)+'&offset=0',{method:'PATCH',headers:{cookie,'Content-Type':'application/octet-stream'},body:new Uint8Array(2*1024*1024)}));
    assert.equal(response.status,200);
    assert.equal((await response.json()).received,2097152);
  }finally{globalThis.fetch=original;}
});
test('offline renderer returns an actionable error',async()=>{
  const original=globalThis.fetch;
  globalThis.fetch=async()=>{throw new Error('offline')};
  try{assert.equal((await bridge.fetch(request('health',{headers:{cookie}}))).status,503)}finally{globalThis.fetch=original}
});
