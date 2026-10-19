const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const code=fs.readFileSync('dist/app.js','utf8').split("$('#play').onclick=")[0];
class AudioContext {createBuffer(channels,length,sampleRate){const data=Array.from({length:channels},()=>new Float32Array(length));return {length,sampleRate,copyToChannel:(a,c)=>data[c].set(a),getChannelData:c=>data[c]};}}
const scope={AudioContext,Float32Array,ArrayBuffer,DataView,Blob,console};vm.createContext(scope);vm.runInContext(code,scope);
const stems=vm.runInContext('makeDemo()',scope);assert.equal(stems.length,4);
for(const stem of stems){const a=stem.getChannelData(0);assert.equal(a.length,22050*12);let energy=0;for(const value of a){assert(Number.isFinite(value));assert(Math.abs(value)<=1);energy+=value*value;}assert(energy/a.length>0.00001);}
(async()=>{const blob=vm.runInContext('wav([new Float32Array([0, .5, -1])],22050)',scope),buffer=Buffer.from(await blob.arrayBuffer());assert.equal(buffer.subarray(0,4).toString(),'RIFF');assert.equal(buffer.length,50);assert.equal(buffer.readUInt32LE(24),22050);assert.equal(buffer.readInt16LE(48),-32767);console.log('Four finite, non-silent stems and PCM WAV encoding verified.');})().catch(e=>{console.error(e);process.exitCode=1;});
