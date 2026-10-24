import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import puppeteer from 'puppeteer-core';
import { masterTime } from './timeline.mjs';
import { makeScore } from './score.mjs';
import { makeCompositionScore } from './composition-score.mjs';

const root=path.dirname(fileURLToPath(import.meta.url));
const [configPath, output, mode='video']=process.argv.slice(2);
const config=JSON.parse(fs.readFileSync(configPath,'utf8'));
const composition=!!config.film;
if(!Number.isInteger(config.width)||!Number.isInteger(config.height)||config.width<100||config.height<100||config.width*config.height>2073600||!Number.isFinite(config.duration)||config.duration<(composition?.5:3)||config.duration>(composition?180:10)||(!composition&&(typeof config.text!=='string'||config.text.length>100||typeof config.detail!=='string'||config.detail.length>140)))throw Error('Invalid scene config');
const exe=[process.env.FRAMECRAFT_BROWSER_PATH,path.join(process.env.LOCALAPPDATA||'', 'Google/Chrome/Application/chrome.exe'),'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','/usr/bin/google-chrome','/usr/bin/chromium'].find(p=>p&&fs.existsSync(p));
if(!exe)throw Error('Framecraft needs installed Chrome or Edge. No browser is downloaded.');
const profile=fs.mkdtempSync(path.join(os.tmpdir(),'framecraft-'));
let browser,ff,ffError='',pageError,blocked=0;
const cleanup=async()=>{if(ff&&ff.exitCode===null)ff.kill();if(browser)await browser.close();fs.rmSync(profile,{recursive:true,force:true});};
const timer=setTimeout(()=>{console.error('Animation rendering timed out');cleanup().finally(()=>process.exit(1));},composition?Math.min(880000,config.duration*15000+60000):270000);
try{
  browser=await puppeteer.launch({executablePath:exe,headless:true,userDataDir:profile,protocolTimeout:60000,args:['--disable-background-networking','--disable-component-update','--no-first-run','--no-default-browser-check','--disable-sync']});
  const page=await browser.newPage();page.on('pageerror',e=>{pageError=e;});
  await page.setRequestInterception(true);page.on('request',r=>{blocked++;r.abort();});
  await page.setViewport({width:config.width,height:config.height,deviceScaleFactor:1});
  const html=fs.readFileSync(path.join(root,composition?'composition.html':'scene.html'),'utf8').replace('</script>',`window.masterClock=${masterTime.toString()};</script>`);
  await page.setContent(html,{waitUntil:'domcontentloaded'});
  // Only trusted bundled code is evaluated; user/model data travels as serialized arguments.
  await page.evaluate(c=>window.initScene(c,window.masterClock),config);
  await page.waitForFunction(()=>window.READY===true,{timeout:30000});
  const grab=async f=>{
    const data=await page.evaluate(f=>{window.render(f);return document.querySelector('canvas').toDataURL('image/png').split(',')[1]},f);
    if(pageError)throw pageError;return Buffer.from(data,'base64');
  };
  const score=composition?makeCompositionScore(config,path.join(path.dirname(output),'composition-score.wav')):makeScore(config,path.join(path.dirname(output),'framecraft-score.wav'));
  if(mode==='stills'){
    fs.mkdirSync(output,{recursive:true});
    const times=[0,.25,.75,1.35,2.05,2.48,2.95,3.8].map(t=>t/4*config.duration);
    for(const [i,t] of times.entries())fs.writeFileSync(path.join(output,`frame-${String(i).padStart(2,'0')}.png`),await grab(Math.floor(t*30)));
    const a=await grab(39),b=await grab(0),c=await grab(39);
    if(!a.equals(c))throw Error('Frame rendering is not deterministic');
    fs.writeFileSync(path.join(output,'checks.json'),JSON.stringify({deterministic:true,motion_changes:!a.equals(b),external_requests:blocked,score,times},null,2));
  }else{
    ff=spawn(process.env.FFMPEG_PATH||'ffmpeg',['-v','error','-nostdin','-y','-f','image2pipe','-framerate','30','-vcodec','png','-i','pipe:0','-an','-c:v','png','-pix_fmt','rgba',output],{windowsHide:true});
    ff.stderr.on('data',d=>{ffError=(ffError+d.toString()).slice(-3500)});
    const complete=new Promise((resolve,reject)=>{ff.on('error',reject);ff.on('close',code=>code===0?resolve():reject(Error(ffError||`FFmpeg exited ${code}`)))});
    // Attach immediately, since encoding failure can precede the next frame capture.
    complete.catch(()=>{});ff.stdin.on('error',()=>{});
    for(let f=0;f<Math.ceil(config.duration*30);f++){
      if(ff.exitCode!==null)throw Error(ffError||'Encoder stopped');
      if(!ff.stdin.write(await grab(f)))await Promise.race([once(ff.stdin,'drain'),complete.then(()=>{throw Error('Encoder closed')})]);
    }
    ff.stdin.end();await complete;
    fs.writeFileSync(path.join(path.dirname(output),composition?'composition-checks.json':'framecraft-checks.json'),JSON.stringify({frames:Math.ceil(config.duration*30),external_requests:blocked,score},null,2));
  }
}finally{clearTimeout(timer);await cleanup();}
