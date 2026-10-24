import {createHmac, timingSafeEqual} from 'node:crypto';
const cookieName='imaginepro_demo';
const json=(status,value,headers={})=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store',...headers}});
const sign=(secret,value)=>createHmac('sha256',secret).update(value).digest('hex');
function equal(a,b){const x=Buffer.from(a),y=Buffer.from(b);return x.length===y.length&&timingSafeEqual(x,y)}
function authenticated(request,secret){const value=(request.headers.get('cookie')||'').split(';').map(s=>s.trim()).find(s=>s.startsWith(cookieName+'='))?.slice(cookieName.length+1)||'';const[expiry,signature]=value.split('.');return Number(expiry)>Date.now()/1000&&equal(signature||'',sign(secret,'session:'+expiry))}
export default {
 async fetch(request){
  const secret=process.env.IMAGINEPRO_BRIDGE_SECRET,base=process.env.IMAGINEPRO_BACKEND_URL,password=process.env.IMAGINEPRO_DEMO_PASSWORD;
  if(!secret||!base||!password)return json(503,{detail:'The demo connection is not configured.'});
  const url=new URL(request.url);const route=url.searchParams.get('__path')||'';url.searchParams.delete('__path');
  if(route==='demo/login'&&request.method==='POST'){
   let input;try{input=await request.json()}catch{return json(400,{detail:'Enter your demo passcode.'})}
   if(!equal(String(input.password||''),password))return json(401,{detail:'Incorrect demo passcode.'});
   const expiry=Math.floor(Date.now()/1000)+43200;return json(200,{ok:true},{'Set-Cookie':`${cookieName}=${expiry}.${sign(secret,'session:'+expiry)}; Max-Age=43200; Path=/; HttpOnly; Secure; SameSite=Lax`});
  }
  if(!authenticated(request,secret))return json(401,{detail:'Sign in to ImaginePro.',login:true});
  if(!route||route.includes('..')||route.includes('\\')||route.startsWith('/'))return json(400,{detail:'Invalid API path'});
  const target=new URL('/api/'+route,base);target.search=url.search;
  const media=/^(?:projects\/[a-f0-9]{32}\/assets\/[a-f0-9]{32}\/(?:file|thumbnail)|jobs\/[a-f0-9]{32}\/(?:output|verification))$/;
  if(['GET','HEAD'].includes(request.method)&&media.test(route)){
   const expiry=Math.floor(Date.now()/1000)+3600;const query=target.searchParams.toString();target.searchParams.set('bridge_exp',String(expiry));target.searchParams.set('bridge_sig',sign(secret,`GET\n${target.pathname}\n${query}\n${expiry}`));return new Response(null,{status:307,headers:{Location:target.href,'Cache-Control':'private, no-store'}});
  }
  const headers=new Headers({'X-ImaginePro-Bridge':secret,'X-Editor-Client':'video-use'});
  if(request.headers.get('content-type'))headers.set('Content-Type',request.headers.get('content-type'));
  let body;if(!['GET','HEAD'].includes(request.method)){body=await request.arrayBuffer();if(body.byteLength>3*1024*1024)return json(413,{detail:'Use chunked media import for large files.'});}
  try{
   const response=await fetch(target,{method:request.method,headers,body,redirect:'manual',signal:AbortSignal.timeout(115000)});
   const safe=new Headers({'Cache-Control':'private, no-store','Content-Type':response.headers.get('content-type')||'application/json'});
   return new Response(response.body,{status:response.status,headers:safe});
  }catch{return json(503,{detail:'The rendering PC is offline. Keep the ImaginePro demo connection running and try again.'});}
 }
};
