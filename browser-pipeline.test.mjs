import assert from 'node:assert/strict';
import { DemucsProcessor } from './dist/vendor/demucs/processor.js';
import { CONSTANTS } from './dist/vendor/demucs/constants.js';

// Exercise actual FFT, chunk stitching, endpoint weights and tensor cleanup.
// Deterministic model output isolates pipeline bugs from model quality.
for (const length of [441, CONSTANTS.TRAINING_SAMPLES + 37]) {
  let created=0,disposed=0,runs=0;
  const progress=[];
  class Tensor {
    constructor(type,data,dims){this.data=data;this.dims=dims;created++;}
    dispose(){disposed++;}
  }
  const processor=new DemucsProcessor({ort:{Tensor},onProgress:p=>progress.push(p)});
  processor.session={inputNames:['waveform','spectrogram'],outputNames:['audio'],run:async()=>{
    runs++;
    return {audio:new Tensor('float32',new Float32Array(8*CONSTANTS.TRAINING_SAMPLES).fill(.125),[1,4,2,CONSTANTS.TRAINING_SAMPLES])};
  }};
  const result=await processor.separate(new Float32Array(length),new Float32Array(length));
  assert.equal(Object.keys(result).length,4);
  for(const stem of Object.values(result)) for(const channel of [stem.left,stem.right]) {
    assert.equal(channel.length,length);
    for(const value of channel) assert(Math.abs(value-.125)<1e-6,'Every sample, including endpoints and seams, must survive overlap-add');
  }
  assert.equal(created,disposed,'Tensors must be released between chunks');
  assert.equal(progress.length,runs);
  assert.equal(progress.at(-1).progress,1);
  assert(progress.every(p=>p.progress>0&&p.progress<=1));
  assert(progress.every(p=>p.totalSegments===runs));
}
console.log('PASS: short/full chunks retain every sample, progress is bounded, and tensors are disposed.');
