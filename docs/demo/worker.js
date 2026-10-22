// Speech-to-text for the Sorph demo: Whisper in the browser (WebGPU, or
// WebAssembly where WebGPU is missing). Plays the part of flow.py's
// Transcriber: greedy, temperature 0, no cross-segment context.

import { pipeline, env } from 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.3.1/dist/transformers.min.js';

env.allowLocalModels = false;

const pipes = {};
let queue = Promise.resolve();      // one decode at a time, like the app's switch lock

async function device() {
  try {
    const adapter = navigator.gpu && await navigator.gpu.requestAdapter();
    if (adapter) return { device: 'webgpu' };
  } catch (_) { /* fall through */ }
  return { device: 'wasm' };
}

async function load({ name, repo }) {
  const d = await device();
  // the Mac app runs int8 on the CPU; on the GPU a 4-bit decoder is the
  // fast path, and the encoder keeps full precision (an fp16 encoder
  // decodes every utterance as "you")
  const dtype = d.device === 'webgpu'
    ? { encoder_model: 'fp32', decoder_model_merged: 'q4' }
    : { encoder_model: 'q8', decoder_model_merged: 'q8' };
  const files = {};
  pipes[name] = await pipeline('automatic-speech-recognition', repo, {
    device: d.device, dtype,
    progress_callback: p => {
      if (p.status !== 'progress' || !p.total) return;
      files[p.file] = [p.loaded, p.total];
      let loaded = 0, total = 0;
      for (const [l, t] of Object.values(files)) { loaded += l; total += t; }
      postMessage({ type: 'progress', name, loaded, total });
    },
  });
  // the first GPU decode compiles its shaders: pay that now, not mid-sentence
  await serial(() => pipes[name](new Float32Array(16000)));
  postMessage({ type: 'ready', name, device: d.device });
}

function serial(job) {
  const run = queue.then(job);
  queue = run.catch(() => {});
  return run;
}

async function transcribe({ id, name, audio, opts }) {
  const out = await serial(() => pipes[name](audio, opts || {}));
  postMessage({ type: 'text', id, text: out.text || '' });
}

// downloads run side by side; decodes take turns
onmessage = ({ data }) => {
  (data.type === 'load' ? load(data) : transcribe(data))
    .catch(err => postMessage({ type: 'error', id: data.id, name: data.name, message: String(err && err.message || err) }));
};
