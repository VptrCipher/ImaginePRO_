import fs from 'node:fs';
import path from 'node:path';
import { makeScore } from './score.mjs';
export function makeCompositionScore(config,target){
 const sr=48000,n=Math.ceil(config.duration*sr),data=Buffer.alloc(n*4);let offset=0;
 for(let i=0;i<config.film.scenes.length;i++){
   const duration=config.film.scenes[i].duration,file=path.join(path.dirname(target),`score-scene-${i}.wav`);
   makeScore({duration:Math.max(1.05,duration)},file);const wav=fs.readFileSync(file).subarray(44);
   const count=Math.min(wav.length,Math.round(duration*sr)*4,data.length-offset);wav.copy(data,offset,0,count);offset+=count;
 }
 const header=Buffer.alloc(44);header.write('RIFF');header.writeUInt32LE(36+data.length,4);header.write('WAVEfmt ',8);header.writeUInt32LE(16,16);header.writeUInt16LE(1,20);header.writeUInt16LE(2,22);header.writeUInt32LE(sr,24);header.writeUInt32LE(sr*4,28);header.writeUInt16LE(4,32);header.writeUInt16LE(16,34);header.write('data',36);header.writeUInt32LE(data.length,40);
 fs.writeFileSync(target,Buffer.concat([header,data]));return{duration:config.duration,sample_rate:sr,channels:2,scene_cues:config.film.scenes.length};
}
