import fs from 'node:fs';
import { EVENTS, BREATH, masterTime } from './timeline.mjs';

export function makeScore(config, target) {
  const sr=48000,n=Math.ceil(config.duration*sr),L=new Float64Array(n),R=new Float64Array(n);
  let seed=11129;const noise=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/2147483648-1};
  const actual=t=>t<3?t/3*(config.duration-1):config.duration-1+t-3;
  function sound(at,duration,hz,kind,pan=0){
    let start=Math.round(actual(at)*sr),end=Math.min(n,start+Math.round(duration*sr)),filter=0;
    for(let i=start;i<end;i++){
      let t=(i-start)/sr,a=0;
      if(kind==='pluck') a=(Math.sin(2*Math.PI*hz*t)+.38*Math.sin(2*Math.PI*hz*2.002*t)+.19*Math.sin(2*Math.PI*hz*3.01*t))*Math.exp(-7*t)*Math.min(1,t/.003)*.19;
      if(kind==='bell') a=(Math.sin(2*Math.PI*hz*t)+.3*Math.sin(2*Math.PI*hz*2.76*t)+.12*Math.sin(2*Math.PI*hz*5.41*t))*Math.exp(-3.3*t)*Math.min(1,t/.004)*.12;
      if(kind==='whoosh') {filter+=.09*(noise()-filter);a=filter*Math.sin(Math.PI*t/duration)**2*.32;}
      if(kind==='impact') a=(Math.sin(2*Math.PI*(62*t+10*(1-Math.exp(-20*t))))*Math.exp(-13*t)+noise()*.16*Math.exp(-24*t))*.3;
      const left=Math.sqrt((1-pan)/2),right=Math.sqrt((1+pan)/2);L[i]+=a*left;R[i]+=a*right;
    }
  }
  for(const e of EVENTS){
    const kind=['draw','riser'].includes(e.kind)?'whoosh':e.kind==='orbit'?'bell':'pluck';
    sound(e.at,kind==='whoosh'?.32:.9,e.hz,kind,e.pan);
    if(e.kind==='bloom'){sound(e.at,.5,60,'impact');[220,330,440,550,660].forEach((h,j)=>sound(e.at+j*.023,1.25,h,'bell',(j-2)*.17));}
  }
  // Quiet detuned chord, with a real breath in the same master clock as the picture.
  for(let i=0;i<n;i++){
    let t=i/sr,m=masterTime(t,config.duration),env=Math.min(1,t/.7)*Math.min(1,(config.duration-t)/.25);
    let pad=[110,165,220].reduce((s,h)=>s+Math.sin(2*Math.PI*h*t)+.35*Math.sin(2*Math.PI*h*1.003*t),0)*.015*env;
    L[i]+=pad;R[i]+=pad*.97;
    let breath=m>BREATH[0]&&m<BREATH[1]?.04:1;
    let fade=Math.min(1,t/.015,(config.duration-t)/.08);
    L[i]=Math.tanh(L[i]*1.3)*breath*fade;R[i]=Math.tanh(R[i]*1.3)*breath*fade;
  }
  // Small stereo delay/reverb taps; do not fill the intentional breath.
  for(let i=n-1;i>=0;i--){let m=masterTime(i/sr,config.duration);if(m>BREATH[0]&&m<BREATH[1])continue;
    for(const [delay,gain] of [[.071,.12],[.109,.08],[.173,.045]]){let j=i-Math.round(sr*delay);if(j>=0){L[i]+=R[j]*gain;R[i]+=L[j]*gain;}}
  }
  let peak=0,energy=0;for(let i=0;i<n;i++){if(!Number.isFinite(L[i])||!Number.isFinite(R[i]))throw Error('Non-finite score sample');peak=Math.max(peak,Math.abs(L[i]),Math.abs(R[i]));energy+=L[i]**2+R[i]**2;}
  if(peak<.001||energy<.001)throw Error('Score is silent');
  let gain=.74/peak,buf=Buffer.alloc(44+n*4);buf.write('RIFF');buf.writeUInt32LE(36+n*4,4);buf.write('WAVEfmt ',8);buf.writeUInt32LE(16,16);buf.writeUInt16LE(1,20);buf.writeUInt16LE(2,22);buf.writeUInt32LE(sr,24);buf.writeUInt32LE(sr*4,28);buf.writeUInt16LE(4,32);buf.writeUInt16LE(16,34);buf.write('data',36);buf.writeUInt32LE(n*4,40);
  for(let i=0;i<n;i++){buf.writeInt16LE(Math.round(Math.max(-1,Math.min(1,L[i]*gain))*32767),44+i*4);buf.writeInt16LE(Math.round(Math.max(-1,Math.min(1,R[i]*gain))*32767),46+i*4);}
  fs.writeFileSync(target,buf);
  return {sample_rate:sr,channels:2,duration:config.duration,peak:.74,rms:Math.sqrt(energy/(n*2))*gain,events:EVENTS};
}
