// The Sorph demo's dictation loop: a port of flow.py's Recorder and
// preview loop (hands-free "locked" mode) and overlay.py's VoiceMotion.
// Every constant below is the Mac app's.

import { ruleCleanup, endsSentence, join, stripRepeats } from './cleanup.js';
import { LiveTyper } from './typer.js';
import { modelForLanguage } from './languages.js';

export const SAMPLE_RATE = 16000;     // what Whisper expects
const PREVIEW_MIN_SEC = 0.8;          // don't preview until this much audio exists
const PREVIEW_STEP_SEC = 0.5;         // new audio needed before re-transcribing
const PREVIEW_WINDOW_SEC = 24;        // force a commit when an utterance gets this long
const ENDPOINT_SEC = 1.2;             // this much silence ends a sentence (locked mode)
const SOFT_GAP_SEC = 0.4;             // a long buffer is split at its last pause this long
const MIN_UTTERANCE_SEC = 2.0;        // shorter segments wait for more speech
const SILENCE_RMS = 0.01;             // frame RMS below this is silence
const FRAME = SAMPLE_RATE / 10;       // 100 ms analysis frames
const LEVEL_WINDOW = SAMPLE_RATE * 30 / 1000;   // live level spans the last 30 ms
const PREROLL_SEC = 0.3;              // audio kept before speech starts

const sleep = ms => new Promise(r => setTimeout(r, ms));

// ---------------------------------------------------------------- recorder

// The mic at its native rate, averaged down to 16 kHz in an audio worklet
// (a box filter over each output sample's span of input).
const TAP = `registerProcessor('tap', class extends AudioWorkletProcessor {
  constructor() { super(); this.r = sampleRate / ${SAMPLE_RATE}; this.t = 0; this.acc = 0; this.cnt = 0; this.out = []; }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) {
      this.acc += ch[i]; this.cnt++; this.t++;
      if (this.t >= this.r) { this.out.push(this.acc / this.cnt); this.acc = 0; this.cnt = 0; this.t -= this.r; }
    }
    if (this.out.length >= 512) { this.port.postMessage(Float32Array.from(this.out)); this.out = []; }
    return true;
  }
});`;

// The mic stays open between dictations so a press starts at once; audio is
// only kept (and the level only moves) between start() and stop().
export class Recorder {
  constructor() { this.chunks = []; this.level = 0; this.recording = false; this.tail = new Float32Array(LEVEL_WINDOW); }

  async open() {
    // the raw mic, as the Mac app hears it: no gain riding, no gating
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: {
      channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
    this.ctx = new AudioContext();
    const url = URL.createObjectURL(new Blob([TAP], { type: 'text/javascript' }));
    await this.ctx.audioWorklet.addModule(url);
    const src = this.ctx.createMediaStreamSource(this.stream);
    this.node = new AudioWorkletNode(this.ctx, 'tap');
    this.node.port.onmessage = ({ data }) => this._onAudio(data);
    src.connect(this.node);
    await this.ctx.resume();
  }

  _onAudio(chunk) {
    if (!this.recording) return;
    this.chunks.push(chunk);
    const t = new Float32Array(LEVEL_WINDOW);
    const keep = Math.max(0, LEVEL_WINDOW - chunk.length);
    t.set(this.tail.subarray(LEVEL_WINDOW - keep), 0);
    t.set(chunk.subarray(Math.max(0, chunk.length - LEVEL_WINDOW)), keep);
    this.tail = t;
    let s = 0; for (const x of t) s += x * x;
    this.level = Math.sqrt(s / LEVEL_WINDOW);
  }

  // Everything captured so far (recording continues).
  snapshot() {
    let n = 0; for (const c of this.chunks) n += c.length;
    const out = new Float32Array(n);
    let o = 0; for (const c of this.chunks) { out.set(c, o); o += c.length; }
    return out;
  }

  // Forget the first n samples (they are committed).
  drop(n) {
    const audio = this.snapshot();
    this.chunks = n < audio.length ? [audio.slice(n)] : [];
  }

  clear() { this.chunks = []; }

  start() { this.chunks = []; this.level = 0; this.tail.fill(0); this.recording = true; }

  stop() { this.recording = false; this.level = 0; return this.snapshot(); }

  close() {
    if (this.stream) this.stream.getTracks().forEach(t => t.stop());
    if (this.ctx) this.ctx.close();
    this.stream = this.ctx = null; this.level = 0; this.tail.fill(0);
  }
}

// ---------------------------------------------------------------- sphere motion

// Turns the live mic level into the energy sphere's motion: every syllable
// swells the ribbons, word gaps dip them, and when you stop talking they
// glide back to rest on a critically damped spring. Loudness is relative to
// your own voice, so a quiet speaker moves the sphere as much as a loud one.
export class VoiceMotion {
  static REST = 0.05; static REF_FLOOR = 0.006; static REF_DECAY_SEC = 12.0;
  static SYL_RISE = 0.035; static SYL_FALL = 0.09; static VOICED = 0.15;
  static EASE_W = 9.0; static PULSE_GAP = 0.12; static PULSE_SEC = 0.6;

  constructor(sensitivity = 82) { this.setSensitivity(sensitivity); this.reset(); }

  setSensitivity(dial) {
    const v = Math.min(100, Math.max(0, dial)) / 50;   // 0..2
    this.peak = 0.08 + 0.72 * v;        // level at a full syllable
    this.pulseGain = 0.20 + 0.80 * v;   // flash strength
    this.flowGain = 1.0 + 2.0 * v;      // how much the voice speeds the ribbons
  }

  reset() {
    this.t = 0; this.ref = 0.02; this.noise = 0.004; this.syl = 0; this.voiced = 0;
    this.level = VoiceMotion.REST; this.vel = 0; this.pulse = 0; this.lastOnset = -1;
  }

  // Advance by dt seconds; returns {level, pulse, speed}.
  step(rms, dt, listening = true) {
    const V = VoiceMotion;
    this.t += dt;
    let target;
    if (listening) {
      // the room: follows quiet frames down fast, creeps up slowly
      const k = rms < this.noise ? dt / 0.3 : dt / 8.0;
      this.noise = Math.min(0.02, this.noise + (rms - this.noise) * Math.min(1, k));
      // your voice: jumps to peaks, forgets over REF_DECAY_SEC
      if (rms > this.ref) this.ref += (rms - this.ref) * Math.min(1, dt / 0.05);
      else this.ref = Math.max(V.REF_FLOOR, this.ref * 0.5 ** (dt / V.REF_DECAY_SEC));
      const gate = 1.5 * this.noise;
      const v = Math.min(1, Math.max(0, (rms - gate) / Math.max(this.ref - gate, 1e-4)));
      // a syllable starts: a flash of light that grows with it
      if (v > 0.25 && v > this.syl * 1.3 + 0.1 && this.t - this.lastOnset > V.PULSE_GAP) this.lastOnset = this.t;
      if (this.t - this.lastOnset < V.PULSE_GAP) this.pulse = Math.max(this.pulse, this.pulseGain * 0.6 * v);
      const tau = v > this.syl ? V.SYL_RISE : V.SYL_FALL;
      this.syl += (v - this.syl) * (1 - Math.exp(-dt / tau));
      const on = v > V.VOICED ? 1 : 0;
      this.voiced += (on - this.voiced) * (1 - Math.exp(-dt / (on ? 0.08 : 0.35)));
      target = V.REST + (this.peak - V.REST) * (0.3 * this.voiced + 0.7 * this.syl);
    } else {
      // transcribing: a calm breath
      this.syl = this.voiced = 0;
      target = 0.08 + 0.03 * Math.sin(this.t * 1.5);
    }
    if (listening && (this.voiced > 0.5 || target > this.level)) {
      // speaking, or a word starting: follow every syllable at once
      const tau = target > this.level ? V.SYL_RISE : V.SYL_FALL;
      this.level += (target - this.level) * (1 - Math.exp(-dt / tau));
      this.vel = 0;
    } else {
      // a pause: velocity and position both glide to rest, no jolt
      const w = V.EASE_W;
      this.vel += (-w * w * (this.level - target) - 2 * w * this.vel) * dt;
      this.level += this.vel * dt;
    }
    this.pulse *= 0.02 ** (dt / V.PULSE_SEC);
    return { level: this.level, pulse: this.pulse, speed: 0.8 + this.flowGain * this.level };
  }
}

// ---------------------------------------------------------------- stage 1: STT

// Talks to worker.js. Models are named as in the app (base.en, small, ...)
// and loaded once each; a language never needs its own download.
export class Transcriber {
  constructor(onEvent) {
    this.worker = new Worker(new URL('./worker.js', import.meta.url), { type: 'module' });
    this.pending = new Map(); this.ready = new Set(); this.loading = new Map(); this.id = 0;
    this.worker.onmessage = ({ data }) => {
      const waiting = this.loading.get(data.name);
      if (data.type === 'ready') { this.ready.add(data.name); if (waiting) waiting.resolve(); }
      if ((data.type === 'text' || data.type === 'error') && this.pending.has(data.id)) {
        const { resolve, reject } = this.pending.get(data.id); this.pending.delete(data.id);
        data.type === 'text' ? resolve(data.text) : reject(new Error(data.message));
        return;
      }
      if (data.type === 'error' && waiting && !data.id) { this.loading.delete(data.name); waiting.reject(new Error(data.message)); }
      onEvent(data);
    };
  }

  // Resolves once `name` can decode; starts its download the first time.
  ensure(name) {
    if (!this.loading.has(name)) {
      let resolve, reject;
      const promise = new Promise((a, b) => { resolve = a; reject = b; });
      promise.catch(() => {});
      this.loading.set(name, { promise, resolve, reject });
      this.worker.postMessage({ type: 'load', name, repo: `onnx-community/whisper-${name}` });
    }
    return this.loading.get(name).promise;
  }

  // A window that is only a non-speech tag ("[BLANK_AUDIO]", "(music)") is
  // dropped; a segment that loops is cut at the first repeat.
  async transcribe(name, language, audio, opts = {}) {
    await this.ensure(name);
    // English-only models take no language; the multilingual ones are told
    // which one to expect, as faster-whisper is
    if (!name.endsWith('.en')) opts = { ...opts, language, task: 'transcribe' };
    const id = ++this.id;
    const text = await new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.worker.postMessage({ type: 'transcribe', id, name, audio, opts }, [audio.buffer]);
    });
    return stripRepeats(text.replace(/\s*[[(][^\])]*[\])]\s*/g, ' ').trim()).trim();
  }
}

// ---------------------------------------------------------------- app

function frameRms(audio) {
  const n = Math.floor(audio.length / FRAME), out = new Float32Array(n);
  for (let f = 0; f < n; f++) {
    let s = 0; for (let i = f * FRAME; i < (f + 1) * FRAME; i++) s += audio[i] * audio[i];
    out[f] = Math.sqrt(s / FRAME);
  }
  return out;
}
const speechFrames = rms => { const s = []; rms.forEach((r, i) => { if (r > SILENCE_RMS) s.push(i); }); return s; };

// Sample index where the first finished utterance ends: the start of the
// first silence gap of ENDPOINT_SEC after speech (plus half the gap, so the
// decoder sees the trailing pause). null if the utterance is still going.
function utteranceEnd(rms) {
  const speech = speechFrames(rms);
  if (!speech.length) return null;
  const gap = Math.trunc(ENDPOINT_SEC * SAMPLE_RATE / FRAME);
  for (let k = 1; k < speech.length; k++)
    if (speech[k] - speech[k - 1] > gap) return Math.trunc((speech[k - 1] + 1 + Math.floor(gap / 2)) * FRAME);
  if (rms.length - 1 - speech[speech.length - 1] >= gap) return Math.trunc((speech[speech.length - 1] + 1 + Math.floor(gap / 2)) * FRAME);
  return null;
}

// Sample index in the middle of the last silence gap of at least
// `minGapSec`, or null: where to split a long buffer without cutting a word.
function lastPause(rms, minGapSec = SOFT_GAP_SEC) {
  const speech = speechFrames(rms), gap = Math.trunc(minGapSec * SAMPLE_RATE / FRAME);
  for (let k = speech.length - 1; k > 0; k--) {
    const a = speech[k - 1], b = speech[k];
    if (b - a > gap) return Math.trunc((a + 1 + Math.floor((b - a) / 2)) * FRAME);
  }
  return null;
}

// One hands-free dictation. `ui.show(typed)` gets the current sentence as
// the typer holds it; `ui.settle()` marks it finished (it never changes again).
export class Dictation {
  constructor(recorder, transcriber, ui, language = 'en') {
    Object.assign(this, { recorder, transcriber, ui, language });
    this.locked = false;          // Option+A: hands-free, sentences commit on pauses
    this.st = { committed: '', seenN: 0, spokenN: 0, active: true, typer: new LiveTyper() };
    this.loop = this._previewLoop();
  }

  // the live preview runs base.en (or base); finished sentences use
  // small.en (or small) once it has loaded, as the Mac app does
  get previewModel() { return modelForLanguage('base.en', this.language); }
  get model() {
    const small = modelForLanguage('small.en', this.language);
    return this.transcriber.ready.has(small) ? small : this.previewModel;
  }

  // Switch language mid-dictation: the next decode uses it (and waits for
  // its model, the first time a multilingual one is needed).
  setLanguage(code) { this.language = code; }

  // Every ~0.5 s of new audio: transcribe the current utterance and show it.
  // Once an utterance ends it is cleaned up, committed, and its audio
  // dropped: the next decode is short and committed words never change.
  async _previewLoop() {
    const st = this.st, rec = this.recorder;
    while (st.active) {
      const audio = rec.snapshot(), n = audio.length;
      if (n - st.seenN < PREVIEW_STEP_SEC * SAMPLE_RATE) { await sleep(50); continue; }
      const rms = frameRms(audio), speech = speechFrames(rms);
      if (!speech.length) {
        // nothing but silence: keep a little pre-roll, drop the rest
        const keep = PREROLL_SEC * SAMPLE_RATE;
        if (n > keep) rec.drop(n - keep);
        st.seenN = Math.min(n, keep);
        continue;
      }
      // decode only up to shortly after the last speech: trailing silence
      // costs time and invites hallucinated repeats
      const lastSpeech = (speech[speech.length - 1] + 1) * FRAME + PREROLL_SEC * SAMPLE_RATE;
      if (n < PREVIEW_MIN_SEC * SAMPLE_RATE) { await sleep(50); continue; }
      // sentence commits: only while locked (a held dictation is decoded
      // whole on release, with full context), on a real pause, and never
      // for a scrap shorter than MIN_UTTERANCE_SEC
      let end = this.locked ? utteranceEnd(rms) : null;
      if (end !== null && end < MIN_UTTERANCE_SEC * SAMPLE_RATE) end = null;
      if (end === null && n > PREVIEW_WINDOW_SEC * SAMPLE_RATE) {
        const pause = lastPause(rms);
        end = pause && pause > MIN_UTTERANCE_SEC * SAMPLE_RATE ? pause : n;
      }
      if (end === null && lastSpeech <= st.spokenN) { st.seenN = n; continue; }   // no new speech
      let text;
      try {
        if (end !== null) text = await this.transcriber.transcribe(this.model, this.language, audio.slice(0, end));
        else {
          st.spokenN = lastSpeech;
          text = await this.transcriber.transcribe(this.previewModel, this.language, audio.slice(0, Math.min(n, lastSpeech)), { no_repeat_ngram_size: 3 });
        }
      } catch (err) {                       // never let preview kill dictation
        console.warn('preview failed', err);
        return;
      }
      if (!st.active) return;               // stopped mid-decode
      if (end !== null) { this._commit(text, end); continue; }
      st.seenN = n;
      if (!text) continue;                  // never wipe the line
      st.typer.update(text, true);
      this.ui.show(st.typer.typed);
    }
  }

  // Finish a sentence: clean it up (without closing it unless it is already
  // closed), correct the line word by word, and let it go.
  _commit(text, n) {
    const st = this.st;
    const clean = ruleCleanup(text, this.language, { close: false, capitalizeFirst: endsSentence(st.committed) });
    st.typer.update(clean, true);
    st.committed = join(st.committed, st.typer.typed);
    this.ui.show(st.typer.typed);
    if (st.typer.typed) this.ui.settle();
    st.typer = new LiveTyper();
    this.recorder.drop(n);
    st.seenN = 0; st.spokenN = 0;
  }

  // A tap too short to be speech: forget it, unless a sentence was
  // already committed.
  async cancel() {
    this.st.active = false;
    await this.loop;
    this.recorder.clear();
  }

  // Stop: wait for an in-flight decode, transcribe what is left with the
  // accurate model, show it raw, then the closing cleanup pass.
  async finish() {
    const st = this.st;
    st.active = false;
    await this.loop;
    const audio = this.recorder.snapshot();
    this.recorder.clear();
    if (!speechFrames(frameRms(audio)).length) { if (st.typer.typed) this.ui.settle(); return; }
    const tail = await this.transcriber.transcribe(this.model, this.language, audio);
    if (!tail) { if (st.typer.typed) this.ui.settle(); return; }
    st.typer.update(tail, true);
    this.ui.show(st.typer.typed);
    const text = ruleCleanup(tail, this.language, { capitalizeFirst: endsSentence(st.committed) });
    if (text !== tail) {
      await sleep(250);                     // let the raw text register
      st.typer.update(text, true);
      this.ui.show(st.typer.typed);
    }
    st.typer.update(text);                  // exact: capitals and commas land
    this.ui.show(st.typer.typed);
    st.committed = join(st.committed, st.typer.typed);
    this.ui.settle();
  }
}
