import * as ort from 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.23.2/dist/ort.webgpu.min.mjs';
import { DemucsProcessor } from './vendor/demucs/processor.js';

const MODEL = 'https://huggingface.co/timcsy/demucs-web-onnx/resolve/92e33df61cfc9eb820272aaa62d2ef6dcf4d950d/htdemucs_embedded.onnx';
let processor;
const progress = (stage, percent = null) => postMessage({type:'progress',stage,percent});

async function modelBytes() {
  let cache;
  try { cache = await caches.open('unlayer-demucs-v1'); } catch {}
  const cached = await cache?.match(MODEL);
  if (cached) { progress('Reading cached model'); return cached.arrayBuffer(); }
  progress('Downloading model · about 172 MB on first use');
  const response = await fetch(MODEL,{signal:AbortSignal.timeout(600000)});
  if (!response.ok) throw Error(`Model download failed (${response.status}). Check your connection and retry.`);
  if (!response.body) return response.arrayBuffer();
  const reader = response.body.getReader(), chunks = [];
  const total = Number(response.headers.get('content-length'));
  let loaded = 0;
  while (true) {
    const {done,value} = await reader.read();
    if (done) break;
    chunks.push(value); loaded += value.length;
    progress(`Downloading model · ${(loaded/1048576).toFixed(1)} MB${total ? ` / ${(total/1048576).toFixed(1)} MB` : ''}`, total ? loaded/total*100 : null);
  }
  if (loaded !== 180534758) throw Error("Model download was incomplete. Check your connection and retry.");
  const bytes = new Uint8Array(loaded);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk,offset); offset += chunk.length; }
  // Cache failures (private browsing, storage quota) must not prevent inference.
  try { await cache?.put(MODEL,new Response(bytes,{headers:{'Content-Type':'application/octet-stream'}})); } catch {}
  return bytes.buffer;
}

self.onmessage = async ({data}) => {
  try {
    if (!processor) {
      ort.env.wasm.numThreads = 1; // GitHub Pages does not provide cross-origin isolation.
      ort.env.wasm.wasmPaths = 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.23.2/dist/';
      ort.env.logLevel = 'error';
      let gpu = false;
      try { gpu = Boolean(await navigator.gpu?.requestAdapter()); } catch {}
      postMessage({type:'engine',engine:gpu?'WebGPU':'WebAssembly CPU'});
      const candidate = new DemucsProcessor({ort,sessionOptions:{executionProviders:gpu?['webgpu','wasm']:['wasm'],enableCpuMemArena:false,enableMemPattern:false},
        onProgress:({progress:p,currentSegment,totalSegments})=>progress(`Separating · section ${currentSegment} of ${totalSegments}`,Math.min(99,p*100))});
      const bytes = await modelBytes();
      progress('Preparing AI model · this can take a minute');
      await candidate.loadModel(bytes);
      processor = candidate;
    }
    progress('Separating instrument parts',0);
    const result = await processor.separate(data.left,data.right);
    const names = ['vocals','drums','bass','other'];
    const stems = names.map(name=>({name,left:result[name].left,right:result[name].right}));
    for (const stem of stems) {
      if (stem.left.length!==data.left.length || stem.right.length!==data.right.length) throw Error('The model returned an incomplete recording.');
      for (const channel of [stem.left,stem.right]) for (const sample of channel) if (!Number.isFinite(sample)) throw Error('The model returned invalid audio. Please retry.');
    }
    postMessage({type:'complete',stems},stems.flatMap(s=>[s.left.buffer,s.right.buffer]));
  } catch (error) {
    processor = null;
    postMessage({type:'error',message:error.message || String(error)});
  }
};
