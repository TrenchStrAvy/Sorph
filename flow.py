#!/usr/bin/env python3
"""Sorph — free, private dictation for macOS.

Hold Right-Option → speak → release. Your words are transcribed locally
with faster-whisper, optionally cleaned up by a local language model, and
pasted into whatever app has focus. In translate mode (menu bar → Translate)
you speak one language and the text is written in another.

Pipeline:  hotkey → mic capture → faster-whisper (Stage 1)
           → cleanup (Stage 2: rules, or Sorph's own Gemma) → clipboard + Cmd+V

While the key is held, a preview loop re-transcribes the audio so far about
once a second and types the words straight into the field you are dictating
into, correcting them in place as later audio refines them; after release
the cleanup pass corrects the text the same way. (--preview card shows the
words in the overlay instead and pastes at the end; --preview off waits.)
"""

import argparse
import atexit
import concurrent.futures
import os
import queue
import socket
import subprocess
import sys
import threading
import time

import numpy as np
from pynput import keyboard
from pynput.keyboard import Controller, Key

import cleanup
import dictionary
import ducking
import gemma
import languages
import mics
import muxpane
import settings
import speech
import tone
import translate

try:
    import typer
except Exception as _exc:  # Quartz missing → no inline typing
    typer = None
    print(f"warning: inline typing unavailable ({_exc})")

# ---------------------------------------------------------------- config

SAMPLE_RATE = 16_000          # what Whisper expects
CHANNELS = 1
HOTKEY = Key.alt_r            # Right-Option: hold to record
# while holding the hotkey, letters (Q/W/E/R/T, user-assignable in the
# menu bar) switch the dictation language; the keystroke is swallowed.
# Read from settings on every press so menu changes apply immediately.
MIN_RECORDING_SEC = 0.4       # ignore accidental taps

DEFAULT_MODEL = "small.en"    # good speed/accuracy balance on CPU
PREVIEW_MODEL = "base"        # fast model for the live preview only; every
                              # committed or final sentence uses DEFAULT_MODEL.
                              # Multilingual: one preview model for every
                              # language (its text is replaced anyway)
OLLAMA_MODEL = "gemma3:4b"    # only opt-in; smaller models rewrite sentences
CLEANUP_IDLE_SEC = 3600       # with the cleanup pass on, Gemma stays in
                              # memory this long between dictations
CPU_THREADS = max(1, (os.cpu_count() or 8) // 2)   # physical cores (i9: 8)

LOCK_KEYCODE = 0              # A: tap while holding Right-Option to lock on
PREVIEW_MIN_SEC = 0.8         # don't preview until this much audio exists
PREVIEW_STEP_SEC = 0.5        # new audio needed before re-transcribing
PREVIEW_WINDOW_SEC = 24       # force a commit when an utterance gets this long
ENDPOINT_SEC = 1.2            # this much silence ends a sentence (locked mode)
SOFT_GAP_SEC = 0.4            # a long buffer is split at its last pause this long
MIN_UTTERANCE_SEC = 2.0       # shorter segments wait for more speech: Whisper
                              # needs context, and each decode has a fixed cost
SILENCE_RMS = 0.01            # frame RMS below this is silence
FRAME = SAMPLE_RATE // 10     # 100 ms analysis frames
LEVEL_WINDOW = SAMPLE_RATE * 30 // 1000   # live level spans the last 30 ms:
                              # mic callbacks can be ~4 ms, too short to
                              # read a steady loudness from
PREROLL_SEC = 0.3             # audio kept before speech starts
SHOW_CORRECTIONS_SEC = 0.7    # how long the diff stays visible before paste
GATE_RATIO = 0.25             # sound under this share of your usual voice
                              # level is background until the decoder is
                              # sure it is speech
TOKENS_PER_SEC = 8            # decode budget: about twice fast speech


def frame_rms(audio) -> np.ndarray:
    """Loudness of each 100 ms frame."""
    n = len(audio) // FRAME
    if n == 0:
        return np.zeros(0)
    frames = audio[: n * FRAME].reshape(n, FRAME)
    return np.sqrt((frames ** 2).mean(axis=1))


def voice_gate(level) -> float:
    """Frame RMS from which sound counts as the user's own voice, given
    their learned voice level (None: not learned yet)."""
    return max(SILENCE_RMS, GATE_RATIO * level) if level else SILENCE_RMS


def learn_level(old, audio):
    """Voice level after hearing `audio`: the loudness of its louder
    speech frames. Rises at once, falls slowly, so one quiet or
    background-only take does not lower the gate. None: nothing to learn."""
    rms = frame_rms(audio)
    loud = rms[rms > SILENCE_RMS]
    if len(loud) < 5:
        return None
    heard = float(np.percentile(loud, 90))
    if old is None or heard >= old:
        return heard
    return old + 0.1 * (heard - old)


# ---------------------------------------------------------------- recorder

class Recorder:
    """Captures mic audio between start() and stop()."""

    def __init__(self):
        self._chunks = []
        self._lock = threading.Lock()
        self._stream = None
        self._held = False      # stream kept open after stop(hold=True)
        self.level = 0.0        # live mic RMS, read by the overlay
        self._tail = np.zeros(LEVEL_WINDOW, dtype=np.float32)

    def _on_audio(self, data, *_):
        if self._held:
            return              # open for show only: nothing is kept
        chunk = np.asarray(data, dtype=np.float32).reshape(-1).copy()
        with self._lock:
            self._chunks.append(chunk)
        self._tail = np.concatenate((self._tail, chunk))[-LEVEL_WINDOW:]
        self.level = float(np.sqrt((self._tail ** 2).mean()))

    def snapshot(self) -> np.ndarray:
        """Everything captured so far (recording continues)."""
        with self._lock:
            chunks = list(self._chunks)
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks)

    def drop(self, n: int):
        """Forget the first n samples (they are committed)."""
        with self._lock:
            if not self._chunks:
                return
            audio = np.concatenate(self._chunks)
            self._chunks = [audio[n:]] if n < len(audio) else []

    def start(self):
        self.release()
        with self._lock:
            self._chunks = []
        self.level = 0.0
        self._tail[:] = 0.0
        self._stream = mics.open_stream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            callback=self._on_audio,
        )

    def stop(self, hold: bool = False) -> np.ndarray:
        """End the recording and return it. With `hold` the microphone
        stays open (and unheard) until release(): Muxpane sends a dictated
        reply once Sorph's microphone has closed and the text has stopped
        changing, and a translation is not written yet at that point."""
        if hold and self._stream is not None:
            self._held = True
            self.level = 0.0
        else:
            mics.close_stream(self._stream)
            self._stream = None
        return self.snapshot()

    def release(self):
        """Close a microphone kept open by stop(hold=True). A recording
        that has started since is left alone."""
        if self._held:
            self._held = False
            mics.close_stream(self._stream)
            self._stream = None


# ---------------------------------------------------------------- stage 1: STT

class Transcriber:
    """faster-whisper wrapper that follows the configured language.

    `base_model` is what the user asked for (e.g. small.en). English-only
    models can't decode German/French, so switching language may swap in
    the multilingual sibling (small). Loaded models are cached so flipping
    back and forth is instant after the first load.
    """

    def __init__(self, base_model: str, language: str = "en", **decode):
        self.base_model = base_model
        self.language = language
        self.decode = decode            # extra transcribe() options
        self._models = {}
        self._lock = threading.Lock()
        self._switch = threading.RLock()
        self.model_name = settings.model_for_language(base_model, language)
        self.model = self._load(self.model_name)

    def _load(self, name: str):
        with self._lock:
            if name not in self._models:
                from faster_whisper import WhisperModel
                print(f"Loading {name} (first run downloads the model)...",
                      flush=True)
                t0 = time.time()
                self._models[name] = WhisperModel(
                    speech.path(name), device="cpu", compute_type="int8",
                    cpu_threads=CPU_THREADS)
                print(f"Model ready in {time.time() - t0:.1f}s", flush=True)
            return self._models[name]

    def set_language(self, language: str):
        """Switch dictation language, loading a different model if needed.
        Holds the switch lock so a transcription started during the swap
        waits for the right model instead of decoding with the old one."""
        with self._switch:
            name = settings.model_for_language(self.base_model, language)
            if name != self.model_name:
                self.model = self._load(name)
                self.model_name = name
            self.language = language

    def transcribe(self, audio: np.ndarray, gate=None,
                   task: str = "transcribe") -> str:
        """Text of `audio` (samples, or a file path). `gate` is the voice
        gate (see voice_gate): segments whose audio never reaches it are
        only kept when the decoder is confident they are speech.
        `task="translate"` makes Whisper write English whatever the
        spoken language is."""
        with self._switch:
            model, language = self.model, self.language
        options = dict(self.decode)
        entries = settings.get_dictionary()
        hotwords = dictionary.hotwords(entries)
        if hotwords:
            options["hotwords"] = hotwords
        rms = seconds = None
        if isinstance(audio, np.ndarray):
            seconds = len(audio) / SAMPLE_RATE
            if gate is not None:
                rms = frame_rms(audio)
            if seconds <= 30:
                # a decoder that runs away on noise stops early instead of
                # writing (and timing) hundreds of invented tokens
                options["max_new_tokens"] = int(seconds * TOKENS_PER_SEC) + 16
        segments, _ = model.transcribe(
            audio,
            vad_filter=True,          # trim silence before decoding
            vad_parameters={"min_silence_duration_ms": 300},
            beam_size=1,              # greedy: fastest, fine for dictation
            temperature=0.0,          # single pass: the default fallback
                                      # ladder re-decodes up to 6× when a
                                      # chunk is cut mid-word (7 s stalls)
            condition_on_previous_text=False,  # no cross-segment context
            language=language,
            task=task,
            **options,
        )
        # Segments the decoder made up are dropped (see
        # cleanup.plausible_segment); a loop ("the the the"), inside one
        # segment or spread over several, is cut at the first repeat.
        keep = []
        for s in segments:
            voiced = True
            if rms is not None:
                a = max(0, int(s.start * SAMPLE_RATE / FRAME))
                b = int(np.ceil(s.end * SAMPLE_RATE / FRAME))
                voiced = bool(np.any(rms[a:max(b, a + 1)] > gate))
            if cleanup.plausible_segment(s.avg_logprob, s.no_speech_prob,
                                         s.compression_ratio, voiced):
                keep.append(cleanup.strip_repeats(s.text.strip()))
        text = cleanup.strip_repeats(" ".join(t for t in keep if t).strip())
        if seconds is not None and not cleanup.plausible_length(text, seconds):
            return ""
        return dictionary.apply(text, entries)


# ---------------------------------------------------------------- stage 2: cleanup

def ollama_warmup():
    """Load the cleanup model into RAM in the background so the first real
    dictation doesn't pay the multi-second cold start."""
    def _warm():
        if cleanup.ollama_warmup(OLLAMA_MODEL):
            print(f"({OLLAMA_MODEL} warmed up)")
        else:
            print(f"warning: Ollama not reachable at {cleanup.OLLAMA_URL} — "
                  f"cleanup will fall back to rules only")
    threading.Thread(target=_warm, daemon=True).start()


def translation_llm(use_ollama: bool = False, keep_loaded: bool = False):
    """(gemma.Server or None, llm callable or None) for translate mode:
    Sorph's own Gemma where this install can have it (its weights are
    fetched when first needed), else the Ollama model of an --ollama
    install, else nothing (M2M100 translates). `keep_loaded`: the cleanup
    pass uses the server too, so it holds on to the model for longer."""
    if gemma.available():
        server = gemma.Server(
            CPU_THREADS, CLEANUP_IDLE_SEC if keep_loaded
            else gemma.SLEEP_IDLE_SEC)
        return server, server.chat
    if use_ollama:
        return None, translate.ollama_chat(OLLAMA_MODEL)
    return None, None


# ---------------------------------------------------------------- injection

_kbd = Controller()

try:
    import focus
except Exception as _exc:  # pyobjc missing → old behaviour (paste wherever)
    focus = None
    print(f"warning: focus tracking unavailable ({_exc})")


def inject_text(text: str, target=None):
    """Paste text into the app that had focus when dictation started
    (falls back to whatever is focused now): clipboard → Cmd+V → restore."""
    if focus is not None and target is not None:
        if not focus.restore(target):
            print(f"  (could not refocus {target.app_name}; "
                  f"pasting into the current app)")
    old = subprocess.run(["pbpaste"], capture_output=True).stdout
    subprocess.run(["pbcopy"], input=text.encode())
    time.sleep(0.05)
    with _kbd.pressed(Key.cmd):
        _kbd.press("v")
        _kbd.release("v")
    time.sleep(0.3)  # let the paste land before restoring
    subprocess.run(["pbcopy"], input=old)


# ---------------------------------------------------------------- app

class FlowApp:
    def __init__(self, model_name: str, use_ollama: bool, overlay=None,
                 language: str = "en", progress=None,
                 preview: str = "inline", use_cleanup: bool = False):
        report = progress or (lambda caption, frac: None)
        self.menubar = None
        self.window = None          # Sorph's window, when the UI is up
        self.gemma, llm = translation_llm(use_ollama, use_cleanup)
        # the cleanup pass: Sorph's own Gemma (--cleanup), or an Ollama
        # (--ollama, installs made before Sorph ran Gemma itself)
        self.use_cleanup = use_cleanup and self.gemma is not None
        if use_cleanup and not self.use_cleanup:
            print("warning: the cleanup model cannot run on this install"
                  + ("; using Ollama" if use_ollama else "; rules only"),
                  flush=True)
        use_ollama = use_ollama and not self.use_cleanup
        if self.use_cleanup:
            report("warming up cleanup model", 0.2)
            threading.Thread(target=self._warm_cleanup, daemon=True).start()
        elif use_ollama:
            report("warming up cleanup model", 0.2)
            ollama_warmup()
        if preview == "inline" and typer is None:
            preview = "card"
        self.preview = preview          # inline | card | off
        self.typer = typer.LiveTyper() if typer is not None else None
        # every recording gets its own LiveTyper (a quick second press must
        # not reset the state of a dictation still being finalized), and
        # all keystrokes go through one lock so two jobs never interleave
        self._type_lock = threading.Lock()
        self.language = language
        report(f"loading speech model "
               f"({settings.model_for_language(model_name, language)})", 0.3)
        self.transcriber = Transcriber(model_name, language)
        report("loading preview model", 0.7)
        # the preview decodes audio cut mid-word all the time, which makes
        # small models loop; forbid repeated trigrams at the decoder
        self.previewer = Transcriber(PREVIEW_MODEL, language,
                                     no_repeat_ngram_size=3)
        self.use_ollama = use_ollama
        self.translate_to = settings.get_translate_to()
        self.llm = llm is not None      # a local LLM translates
        self.translator = translate.Translator(CPU_THREADS, llm)
        # sentences of a locked dictation are translated here while the
        # next one is spoken, so the end of the dictation has little left
        self._translations = concurrent.futures.ThreadPoolExecutor(
            1, thread_name_prefix="translate")
        if (self._route() == "llm" and self.gemma is not None
                and not gemma.installed()):
            self._prepare_translation()     # 2.5 GB: not behind the splash
        elif self._route() in ("m2m", "llm"):
            report("loading translation model", 0.8)
            self._load_translator()
        report("almost there", 0.9)
        self.recorder = Recorder()
        self.ducker = ducking.Ducker()
        self.ducker.recover()
        self.overlay = overlay
        self.recording = False
        self.locked = False
        self._hotkey_down = False
        self.record_started = 0.0
        self.target = None          # where the text should land
        self.muxpane_target = None  # a Muxpane agent this dictation is for
        self._preview_thread = None
        self._preview_state = {}    # filled by the preview loop
        self.worker = queue.Queue()
        threading.Thread(target=self._process_loop, daemon=True).start()
        # Muxpane: this Sorph takes the hand-off (reads its answer target,
        # gives the text back) instead of typing into Muxpane's reply field.
        # A file left by a quit that skips atexit names a dead pid: ignored.
        if muxpane.announce():
            atexit.register(muxpane.withdraw)

    def status_text(self) -> str:
        mode = " · locked" if self.locked else ""
        to = (f" · → {translate.english_name(self.translate_to)}"
              if self._route() else "")
        return (f"model {self.transcriber.model_name} · cleanup "
                f"{self._cleanup_name()}{to}{mode}")

    def _cleanup_name(self) -> str:
        if getattr(self, "use_cleanup", False):
            return gemma.MODEL_NAME
        return OLLAMA_MODEL if self.use_ollama else "rules"

    def _notify(self, text: str):
        """A status line for the menu and Sorph's window (downloads)."""
        print(text, flush=True)
        if self.menubar:
            self.menubar.set_status(text)
        self._tell(text)

    # -- Sorph's own Gemma (translate mode, cleanup pass)

    def _fetch_gemma(self) -> bool:
        """Download Gemma (once), with the progress in the status line."""
        what = f"downloading language model ({gemma.MODEL_GB} GB, once)…"
        seen = [-1]

        def progress(share):
            pct = int(share * 100)
            if pct != seen[0]:
                seen[0] = pct
                text = f"{what} {pct}%"
                if self.menubar:
                    self.menubar.set_status(text)
                self._tell(text)
        try:
            self._notify(what)
            return gemma.install(lambda m: print(m, flush=True), progress)
        except Exception as exc:
            print(f"warning: could not download {gemma.MODEL_NAME}: {exc}",
                  flush=True)
            return False

    def _warm_cleanup(self):
        """Have the cleanup model in memory before the first dictation."""
        if not gemma.installed() and not self._fetch_gemma():
            self._notify("cleanup model unavailable; rules only")
            return
        if self.gemma.start():
            # one tiny request: the instructions are read (and cached) now,
            # not while the first dictation waits for its first token
            self.gemma.chat(cleanup.SYSTEM_PROMPT.format(
                language=languages.english_name(self.language)), "ok",
                max_tokens=1)
            print(f"({gemma.MODEL_NAME} warmed up)", flush=True)
        else:
            print("warning: the cleanup model did not start; rules only",
                  flush=True)
        if self.menubar:
            self.menubar.set_status(self.status_text())
        self._tell("ready")

    def _tell(self, state: str):
        """Status line of Sorph's window, if there is one."""
        window = getattr(self, "window", None)
        if window is not None:
            window.set_state(state)

    # -- translate mode

    def _route(self):
        """How dictation is translated right now ("llm", "m2m",
        "whisper"), or None: translate mode is off or cannot do this pair."""
        if not self.translate_to:
            return None
        return translate.route(self.transcriber.language, self.translate_to,
                               self.llm)

    def _load_translator(self) -> bool:
        """Bring up what the current pair translates with: Sorph's own
        Gemma, or M2M100 (an Ollama needs nothing from here)."""
        route = self._route()
        if route == "llm":
            if self.gemma is None:
                return True
            if not gemma.installed() and not self._fetch_gemma():
                return False
            if self.gemma.start():
                return True
            print("warning: the translation model did not start",
                  flush=True)
            return False
        if route != "m2m":
            return True
        try:
            self.translator.load()
            return True
        except Exception as exc:
            print(f"warning: translation model unavailable: {exc}",
                  flush=True)
            return False

    def _translator_ready(self) -> bool:
        route = self._route()
        if route == "llm":
            return self.gemma is None or self.gemma.running
        return route != "m2m" or self.translator.ready

    def set_translate(self, code):
        """Translate dictation into `code` (None: off); from the menu."""
        settings.set_translate_to(code)
        self.translate_to = code
        if self.menubar:
            self.menubar.set_translate(code)
        if self.window:
            self.window.refresh()
        self._prepare_translation()

    def toggle_translate(self):
        """Dictate ↔ Translate, from the menu bar: off if it is on, else
        on into the language last translated into (or the first of the
        user's languages this one can be translated into)."""
        if self._route():
            self.set_translate(None)
            return
        spoken = self.transcriber.language
        for code in ([settings.get_last_target()] + settings.get_languages()
                     + ["en", "es", "fr", "de"]):
            if code and translate.route(spoken, code, self.llm):
                self.set_translate(code)
                return

    def _prepare_translation(self):
        """Fetch and load what the current pair needs, off the caller's
        thread; the menu's status line says so while it runs."""
        def _prepare():
            if not self.translate_to:
                if self.gemma is not None and not self.use_cleanup:
                    self.gemma.stop()   # translate off: give the memory back
            elif not self._translator_ready():
                if self.menubar:
                    self.menubar.set_status(
                        "loading translation model…"
                        if self.llm or translate.Translator.cached()
                        else "downloading translation model (490 MB)…")
                if not self._load_translator():
                    self._notify("translation model unavailable "
                                 "(no connection?)")
                    return
                self._tell("ready")
            if self.menubar:
                self.menubar.set_status(self.status_text())
        threading.Thread(target=_prepare, daemon=True).start()

    def _translate(self, text: str, route) -> str:
        """`text` in the target language; the text as spoken when the
        translation fails (better than losing the dictation)."""
        if not text or route in (None, "whisper"):
            return text
        try:
            return self.translator.translate(
                text, self.transcriber.language, self.translate_to,
                use_llm=route == "llm")
        except Exception as exc:
            print(f"warning: translation failed, writing the original: "
                  f"{exc}", flush=True)
            return text

    def _task(self, st) -> str:
        """Whisper task for a final decode of this recording."""
        return ("translate" if st.get("translating")
                and self._route() == "whisper" else "transcribe")

    # -- language (called from the menu bar, on the main thread)

    def set_language(self, code: str):
        """Switch language; safe from the hotkey thread or the menu."""
        if code == self.language:
            return
        settings.set_language(code)
        self.language = code
        if self.overlay:
            self.overlay.set_note(self._note(languages.native_name(code)))
        if self.menubar:
            self.menubar.set_language(code)
            self.menubar.set_status("loading model…")
        if self.window:
            self.window.refresh()

        def _switch():
            try:
                self.transcriber.set_language(code)
                self.previewer.set_language(code)
                print(f"\nlanguage → {languages.label(code)} "
                      f"({self.transcriber.model_name})", flush=True)
            except Exception as exc:
                print(f"warning: could not switch language: {exc}",
                      flush=True)
            if self.menubar:
                self.menubar.set_status(self.status_text())
            self._prepare_translation()     # the new pair may need the model
        threading.Thread(target=_switch, daemon=True).start()

    def _note(self, text=""):
        if not text and self._route():
            text = (f"{languages.native_name(self.transcriber.language)} → "
                    f"{translate.native_name(self.translate_to)}")
        # dictating to a Muxpane agent: the caption says which one
        target = getattr(self, "muxpane_target", None)
        if target:
            text = (text + "  " if text else "") + muxpane.caption(target)
        return ("🔒 " + text).strip() if self.locked else text

    # -- hotkey handlers (must return fast; heavy work goes to the worker)

    def on_press(self, key, injected=False):
        if injected:            # our own typing (typer.py), not the user
            return
        if (key == Key.enter and self.menubar is not None
                and getattr(self.menubar, "moving", False)):
            self.menubar.finish_move()      # Enter = "Done moving"
            return
        vk = getattr(key, "vk", None)
        if self._hotkey_down and self.recording and vk is not None:
            if vk == LOCK_KEYCODE:
                self._toggle_lock()
                return
            code = settings.quick_keys_by_keycode().get(vk)
            if code:
                self.set_language(code)
                return
        if key == HOTKEY:
            self._hotkey_down = True
            if not self.recording:
                self._start_recording()

    def on_release(self, key, injected=False):
        if injected:
            return
        if key == HOTKEY:
            self._hotkey_down = False
            if self.recording and not self.locked:
                self._stop_recording()

    def _start_recording(self):
        self.recording = True
        self.record_started = time.time()
        self.ducker.duck()            # music down before the mic opens
        self.target = focus.capture() if focus is not None else None
        # Muxpane offers to send this answer to one of its agents: the
        # words go there (through Muxpane), not into the focused field
        self.muxpane_target = muxpane.read_target()
        # nowhere for the words to land: a text-less spot (Finder, the
        # Desktop, a button) that would leave them on the clipboard. Not
        # for Muxpane (its agent takes them) nor for an app that hides its
        # focus from Accessibility (target None: pasted as always).
        no_field = (self.muxpane_target is None and self.target is not None
                    and not self.target.editable)
        self.recorder.start()
        if self.overlay:
            self.overlay.set_muxpane(self.muxpane_target is not None)
            self.overlay.set_note(self._note())
            self.overlay.show_recording()
        if self.typer is not None:
            self.typer = typer.LiveTyper()
        # inline typing only into a confirmed text input: keystrokes sent to
        # Finder or the Desktop select files and open them in Quick Look.
        # Anywhere else this dictation previews in the card instead.
        preview = self.preview
        if preview == "inline" and not (self.target is not None
                                        and self.target.editable):
            preview = "card"
        if self.muxpane_target is not None:
            preview = "card"          # never typed into the field in front"
        elif no_field:
            # no words over the orb; the preview only listens, and the
            # first words heard sound the alert (holding the key for a
            # quick key, without speaking, stays silent)
            preview = "listen"
        # translate mode: the words are written as spoken, exactly like a
        # plain dictation, and swapped for the translation at the end
        self._preview_state = {"text": "", "committed": "",
                               "translating": self._route() is not None,
                               "parts": [],
                               "gate": voice_gate(settings.get_voice_level(
                                   settings.get_mic())),
                               "seen_n": 0, "target": self.target,
                               "muxpane": self.muxpane_target,
                               "typer": self.typer, "active": True,
                               "preview": preview, "no_field": no_field}
        if preview != "off":
            self._preview_thread = threading.Thread(
                target=self._preview_loop, daemon=True)
            self._preview_thread.start()
        self._tell("listening…")
        print("● recording... (release to transcribe)", flush=True)

    def _stop_recording(self):
        self.recording = False
        self.locked = False
        self._preview_state["active"] = False   # this job's loop must end
        self.ducker.restore()
        try:
            audio = self.recorder.stop(
                hold=bool(self._preview_state.get("translating")))
        except Exception as exc:     # never leave the app stuck recording
            print(f"warning: recorder failed: {exc}", flush=True)
            if self.overlay:
                self.overlay.hide()
            return
        st = self._preview_state
        if (time.time() - self.record_started < MIN_RECORDING_SEC
                and not st.get("committed")):
            if self.overlay:
                self.overlay.hide()
            self.recorder.release()
            print("  (too short, ignored)")
            return
        if self.overlay and not st.get("orb_off"):
            self.overlay.show_transcribing()
        self.worker.put((audio, self.target, self._preview_thread, st))

    def _toggle_lock(self):
        """Option+A: keep dictating after Right-Option is released; press
        again to finish."""
        if self.locked:
            print("🔓 unlocked", flush=True)
            self._stop_recording()
            if self.menubar:
                self.menubar.set_status(self.status_text())
            return
        self.locked = True
        print("🔒 locked: dictation stays on until Option+A again",
              flush=True)
        if self.overlay:
            self.overlay.set_note(self._note())
        if self.menubar:
            self.menubar.set_status(self.status_text())

    # -- live preview (runs while recording)

    _frame_rms = staticmethod(frame_rms)

    @staticmethod
    def _utterance_end(rms):
        """Sample index where the first finished utterance ends: the start
        of the first silence gap of ENDPOINT_SEC after speech (plus half
        the gap, so the decoder sees the trailing pause). None if the
        utterance is still going."""
        speech = np.flatnonzero(rms > SILENCE_RMS)
        if len(speech) == 0:
            return None
        gap = int(ENDPOINT_SEC * SAMPLE_RATE / FRAME)
        for a, b in zip(speech[:-1], speech[1:]):
            if b - a > gap:
                return int((a + 1 + gap // 2) * FRAME)
        if len(rms) - 1 - speech[-1] >= gap:
            return int((speech[-1] + 1 + gap // 2) * FRAME)
        return None

    @staticmethod
    def _last_pause(rms, min_gap_sec=SOFT_GAP_SEC):
        """Sample index in the middle of the last silence gap of at least
        `min_gap_sec`, or None: where to split a long buffer without
        cutting a word."""
        speech = np.flatnonzero(rms > SILENCE_RMS)
        gap = int(min_gap_sec * SAMPLE_RATE / FRAME)
        for a, b in zip(speech[-2::-1], speech[::-1]):   # newest first
            if b - a > gap:
                return int((a + 1 + (b - a) // 2) * FRAME)
        return None

    def _preview_loop(self):
        """Every ~0.5 s of new audio: transcribe the current utterance and
        show it. Once an utterance ends (ENDPOINT_SEC of silence anywhere
        in the buffer, so a slow decode can't miss a pause) it is cleaned
        up, committed, and its audio dropped: the next decode is short and
        committed words are never corrected again."""
        st = self._preview_state
        # `st["active"]`, not `self.recording`: a quick new press flips the
        # shared flag back on, and this loop must not outlive its own job
        while st["active"]:
            audio = self.recorder.snapshot()
            n = len(audio)
            if n - st["seen_n"] < PREVIEW_STEP_SEC * SAMPLE_RATE:
                time.sleep(0.05)
                continue
            rms = self._frame_rms(audio)
            speech = np.flatnonzero(rms > SILENCE_RMS)
            if len(speech) == 0:
                # nothing but silence: keep a little pre-roll, drop the rest
                keep = int(PREROLL_SEC * SAMPLE_RATE)
                if n > keep:
                    self.recorder.drop(n - keep)
                st["seen_n"] = min(n, keep)
                continue
            # decode only up to shortly after the last speech: trailing
            # silence costs time and invites hallucinated repeats
            last_speech = int((speech[-1] + 1) * FRAME
                              + PREROLL_SEC * SAMPLE_RATE)
            if n < PREVIEW_MIN_SEC * SAMPLE_RATE:
                time.sleep(0.05)
                continue
            # sentence commits: only while locked (a held dictation is
            # decoded whole on release, with full context), on a real pause,
            # and never for a scrap shorter than MIN_UTTERANCE_SEC
            end = self._utterance_end(rms) if self.locked else None
            if end is not None and end < MIN_UTTERANCE_SEC * SAMPLE_RATE:
                end = None
            if end is None and n > PREVIEW_WINDOW_SEC * SAMPLE_RATE:
                pause = self._last_pause(rms)
                end = pause if pause and pause > MIN_UTTERANCE_SEC * SAMPLE_RATE else n
            if end is None and last_speech <= st.get("spoken_n", 0):
                st["seen_n"] = n            # no new speech: nothing to do
                continue
            gate = st.get("gate")
            try:
                if end is not None:
                    text = self.transcriber.transcribe(audio[:end], gate,
                                                       self._task(st))
                else:
                    st["spoken_n"] = last_speech
                    # start the preview where the user's voice starts:
                    # background sound before it reads as invented words
                    voiced = np.flatnonzero(rms > (gate or SILENCE_RMS))
                    start = (max(0, int(voiced[0] * FRAME
                                        - PREROLL_SEC * SAMPLE_RATE))
                             if len(voiced) else 0)
                    text = self.previewer.transcribe(
                        audio[start:min(n, last_speech)], gate)
            except Exception as exc:       # never let preview kill dictation
                print(f"warning: preview failed: {exc}", flush=True)
                return
            if not st["active"]:
                return                          # released mid-decode
            if end is not None:
                self._commit(st, text, end)     # then loop at once: the
                continue                        # rest may hold more speech
            st["seen_n"] = n
            if not text:
                continue                        # never wipe the field
            st["text"] = cleanup.join(st["committed"], text)
            self._show(st["text"], st.get("target"), soft=True, st=st)

    def _commit(self, st, text, n):
        """Finish a sentence: clean it up (without closing it unless it is
        already closed), correct the field, and lock it. Inline, the
        correction is word-based so a comma the preview model chose
        differently is left alone instead of retyping the sentence; the
        committed record is then whatever the field actually reads."""
        route = self._route() if st.get("translating") else None
        language = "en" if route == "whisper" else self.transcriber.language
        if settings.is_self_corrections():
            text = cleanup.self_correct(text, language)
        clean = cleanup.rule_cleanup(
            text, language, close=False,
            capitalize_first=cleanup.ends_sentence(st["committed"]))
        st["committed"] = cleanup.join(st["committed"], clean)
        st["text"] = st["committed"]
        if st.get("translating") and clean:
            # translated in the background while the next sentence is
            # spoken; written when the dictation ends
            st["parts"].append(self._translations.submit(
                self._translate, clean, route))
        ty = st.get("typer")
        inline = st["preview"] == "inline" and ty
        if inline and self._show_allowed(st.get("target")):
            with self._type_lock:
                ty.update(st["text"], soft=True)
                ty.commit()
                st["committed"] = st["text"] = ty.typed
        elif not inline:
            self._show(st["text"], st.get("target"), st=st)
        self.recorder.drop(n)
        st["seen_n"] = 0
        st["spoken_n"] = 0
        if clean:
            print(f"  ✓ {clean}", flush=True)

    def _show_allowed(self, target) -> bool:
        if focus is None or target is None:
            return True
        return focus._focused_element() == target.element

    def _show(self, text, target, words=None, soft=False, st=None):
        """Put `text` where the user can see it: typed into the target
        field (inline) or in the overlay card. Inline typing is skipped
        while focus is away from the target and catches up when it is
        back; the final pass restores focus."""
        st = st or {}
        if (st.get("no_field") and st.get("active")
                and not st.get("alerted")):
            st["alerted"] = True        # once per dictation
            # unless a field was clicked meanwhile: then the words land
            if focus is None or not focus.focused_is_text_input():
                play_alert()
                st["orb_off"] = True    # the sound said it: no orb, no
                if self.overlay:        # "transcribing" for this one
                    self.overlay.hide()
        preview = st.get("preview", self.preview)
        ty = st.get("typer", self.typer)
        if preview == "inline" and ty:
            if self._show_allowed(target):
                with self._type_lock:
                    ty.update(text, soft=soft)
        elif self.overlay and preview == "card":
            if words is not None:
                self.overlay.set_words(words)
            else:
                self.overlay.set_text(text)

    # -- background pipeline

    def _final_tail(self, audio, preview_thread, st,
                    task: str = "transcribe") -> str:
        """Accurate transcript of the audio not yet committed (waits for an
        in-flight preview decode first; those are short with base)."""
        if preview_thread is not None:
            preview_thread.join()
        rms = self._frame_rms(audio)
        if not np.any(rms > SILENCE_RMS):
            return ""
        return self.transcriber.transcribe(audio, st.get("gate"), task)

    def _process_translated(self, audio, target, preview_thread, st):
        """End of a dictation in translate mode: the field (or the card)
        reads what was said; translate it and put the translation in its
        place."""
        held = False
        try:
            t0 = time.time()
            route = self._route()
            committed = st.get("committed", "")
            tail = self._final_tail(audio, preview_thread, st,
                                    self._task(st))
            raw = cleanup.join(committed, tail)
            if not raw:
                print("  (heard nothing)")
                return
            self._tell("translating…")
            stt_ms = (time.time() - t0) * 1000
            if tail:
                self._learn_voice(audio)
            ty = st.get("typer")
            inline = st["preview"] == "inline" and ty
            if inline and focus is not None and target is not None:
                if not focus.restore(target):
                    print(f"  (could not refocus {target.app_name}; "
                          f"typing into the current app)")
            if inline:
                self._type_lock.acquire()   # released in `finally`
                held = True
                ty.update(raw, soft=True)   # everything said, as spoken
            else:
                self._show(raw, None, soft=True, st=st)
            if self.overlay and not st.get("orb_off"):
                self.overlay.show_cleaning()

            t1 = time.time()
            language = ("en" if route == "whisper"
                        else self.transcriber.language)
            style = (tone.PLAIN if st.get("muxpane") and settings.is_tone()
                     else tone.style_for(target) if settings.is_tone()
                     else tone.STANDARD)   # an agent's prompt: as in a terminal
            if settings.is_self_corrections():
                tail = cleanup.self_correct(tail, language)
            tail = cleanup.rule_cleanup(
                tail, language, close=tone.closes(style),
                capitalize_first=cleanup.ends_sentence(committed))
            text = ""
            for part in ([f.result() for f in st.get("parts", [])]
                         + [self._translate(tail, route)]):
                text = translate.join(text, part, self.translate_to)
            text = tone.apply(text, style)
            print(f"  said: {cleanup.join(committed, tail)}")
            print(f"→ {text}   [stt {stt_ms:.0f}ms, translate "
                  f"{(time.time() - t1) * 1000:.0f}ms]", flush=True)
            if st.get("muxpane"):
                self._to_muxpane(st["muxpane"], text)
            elif inline:
                ty.replace(text)
            elif (focus is not None and target is not None
                  and not target.editable
                  and not focus.focused_is_text_input()):
                subprocess.run(["pbcopy"], input=text.encode())
                print("  (no text field focused; copied to clipboard)",
                      flush=True)
            else:
                if target is not None and not target.editable:
                    target = None   # paste where the user is now
                inject_text(text, target)
        finally:
            if held:
                self._type_lock.release()
            self.recorder.release()     # the microphone held for Muxpane

    @staticmethod
    def _to_muxpane(target, text):
        if muxpane.deliver(target, text):
            print(f"  → muxpane: {target['name']} {target['pane']}", flush=True)
        elif text.strip():
            # Muxpane went away meanwhile: keep the words for the user
            subprocess.run(["pbcopy"], input=text.encode())
            print("  (muxpane unreachable; copied to clipboard)", flush=True)

    @staticmethod
    def _learn_voice(audio):
        """Remember how loud the user speaks into this mic, for the gate."""
        mic = settings.get_mic()
        old = settings.get_voice_level(mic)
        new = learn_level(old, audio)
        if new is not None and (old is None or abs(new - old) > 0.002):
            settings.set_voice_level(mic, new)

    def _process_loop(self):
        while True:
            audio, target, preview_thread, st = self.worker.get()
            held = False
            try:
                if st.get("translating"):
                    self._process_translated(audio, target, preview_thread,
                                             st)
                    continue
                t0 = time.time()
                committed = st.get("committed", "")
                tail = self._final_tail(audio, preview_thread, st)
                raw = cleanup.join(committed, tail)
                if not raw:
                    print("  (heard nothing)")
                    continue
                self._tell("cleaning up…")
                stt_ms = (time.time() - t0) * 1000
                if tail:
                    self._learn_voice(audio)
                ty = st.get("typer")
                inline = st["preview"] == "inline" and ty
                if inline and focus is not None and target is not None:
                    if not focus.restore(target):
                        print(f"  (could not refocus {target.app_name}; "
                              f"typing into the current app)")
                if inline:
                    self._type_lock.acquire()   # released in `finally`
                    held = True
                    ty.update(raw, soft=True)
                else:
                    self._show(raw, None, soft=True, st=st)
                if self.overlay and not st.get("orb_off"):
                    self.overlay.show_cleaning()

                t1 = time.time()
                language = self.transcriber.language
                style = (tone.PLAIN if st.get("muxpane") and settings.is_tone()
                         else tone.style_for(target) if settings.is_tone()
                         else tone.STANDARD)   # an agent's prompt: as in a terminal
                close = tone.closes(style)
                if settings.is_self_corrections():
                    tail = cleanup.self_correct(tail, language)
                text = cleanup.join(committed, cleanup.rule_cleanup(
                    tail, language, close=close,
                    capitalize_first=cleanup.ends_sentence(committed)))
                text = cleanup.rule_cleanup(text, language, close=close,
                                            capitalize_first=False)
                if self.use_cleanup:
                    text = cleanup.llm_cleanup(
                        text, language, self.gemma.stream,
                        self._show_partial(raw, st))
                    text = cleanup.rule_cleanup(text, language, close=close)
                elif self.use_ollama:
                    text = cleanup.ollama_cleanup(
                        text, language, OLLAMA_MODEL,
                        on_partial=self._show_partial(raw, st))
                    text = cleanup.rule_cleanup(text, language, close=close)
                text = tone.apply(text, style)
                clean_ms = (time.time() - t1) * 1000

                if text != raw:
                    print(f"  raw: {raw}")
                    if inline:
                        time.sleep(0.25)      # let the raw text register
                        ty.update(text, soft=True)
                    elif self.overlay and st["preview"] == "card":
                        self.overlay.set_words(cleanup.word_diff(raw, text))
                        time.sleep(SHOW_CORRECTIONS_SEC)
                print(f"→ {text}   [stt {stt_ms:.0f}ms, cleanup "
                      f"{clean_ms:.0f}ms]", flush=True)
                if st.get("muxpane"):
                    self._to_muxpane(st["muxpane"], text)
                elif inline:
                    ty.update(text)     # exact: capitals and commas land
                elif (target is not None and not target.editable
                      and not focus.focused_is_text_input()):
                    # started outside a text field and still no field in
                    # focus: Cmd+V would land in Finder; keep it for the user
                    subprocess.run(["pbcopy"], input=text.encode())
                    print("  (no text field focused; copied to clipboard)",
                          flush=True)
                else:
                    if target is not None and not target.editable:
                        target = None   # paste where the user is now
                    inject_text(text, target)
            finally:
                if held:
                    self._type_lock.release()
                if self.overlay:
                    self.overlay.hide()
                self._tell("ready")

    def _show_partial(self, raw, st):
        """While the LLM streams, paint its output over the raw text in the
        card: the cleaned prefix bright, the not-yet-reached remainder dim.
        Inline there is nothing to paint (and the type lock is held)."""
        if st["preview"] != "card":
            return None
        raw_words = raw.split()

        def _on_partial(partial):
            done = partial.split()
            rest = raw_words[len(done):]
            self._show(" ".join(done + rest), None, st=st,
                       words=[(w, "same") for w in done]
                       + [(w, "dim") for w in rest])
        return _on_partial

    def start_listener(self):
        print(f"Hold Right-Option to dictate, tap A while holding to lock "
              f"it on. Cleanup: "
              f"{self._cleanup_name()}. "
              f"Language: {languages.label(self.language)}. Ctrl+C to quit.",
              flush=True)
        self.listener = keyboard.Listener(on_press=self.on_press,
                                          on_release=self.on_release,
                                          darwin_intercept=self._intercept)
        self.listener.start()
        return self.listener

    def _intercept(self, event_type, event):
        """Swallow Q/W/E (language) and A (lock) while the hotkey is held so
        Option+Q doesn't also type 'œ' into the target app, and Enter while
        the sphere is being moved. Everything else passes, including Option
        combos while dictation is locked."""
        if self.menubar is not None and getattr(self.menubar, "moving", False):
            try:
                from Quartz import (CGEventGetIntegerValueField,
                                    kCGKeyboardEventKeycode)
                if CGEventGetIntegerValueField(
                        event, kCGKeyboardEventKeycode) == 36:   # Return
                    return None
            except Exception:
                pass
        if self._hotkey_down and self.recording:
            try:
                from Quartz import (CGEventGetIntegerValueField,
                                    kCGEventSourceUserData,
                                    kCGKeyboardEventKeycode)
                if (typer is not None and CGEventGetIntegerValueField(
                        event, kCGEventSourceUserData) == typer.TAG):
                    return event        # our own typing: pass it through
                vk = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
                if vk == LOCK_KEYCODE or vk in settings.quick_keys_by_keycode():
                    return None
            except Exception:
                pass
        return event

    def run(self):
        """Terminal-only mode (--no-pill): block on the hotkey listener."""
        self.start_listener().join()


ALERT_SOUND = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "assets", "no-field.wav")


def play_alert():
    """The short "this won't land" sound, without waiting for it."""
    try:
        subprocess.Popen(["afplay", ALERT_SOUND],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def acquire_single_instance_lock():
    """Bind a localhost port as a cross-process mutex. Returns the socket
    (keep it alive!) or None if another Sorph is already running."""
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", 47611))
        lock.listen(1)
        return lock
    except OSError:
        return None


def main():
    global OLLAMA_MODEL
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help="faster-whisper model (tiny.en/small.en/medium.en)")
    parser.add_argument("--cleanup", action="store_true",
                        help=f"also clean up transcripts with Sorph's own "
                             f"{gemma.MODEL_NAME} ({gemma.MODEL_GB} GB, "
                             f"downloaded once); rules-only otherwise")
    parser.add_argument("--ollama", action="store_true",
                        help=f"the cleanup pass through an Ollama model "
                             f"(default {OLLAMA_MODEL}) instead")
    parser.add_argument("--ollama-model", metavar="NAME",
                        help="Ollama model for --ollama")
    parser.add_argument("--preview", choices=["inline", "card", "off"],
                        default="inline",
                        help="while recording: type words into the field "
                             "(inline, default), show them in the overlay "
                             "(card), or wait for release (off)")
    parser.add_argument("--transcribe", metavar="WAV",
                        help="transcribe an audio file and exit (pipeline test)")
    parser.add_argument("--no-pill", action="store_true",
                        help="disable the floating recording indicator")
    parser.add_argument("--language", metavar="CODE",
                        help="dictation language code, e.g. de (default: "
                             "last choice from the menu bar, else en)")
    parser.add_argument("--position", choices=settings.POSITIONS,
                        help="where the sphere sits (saved, also in the "
                             "menu bar): bottom-left, bottom-center, "
                             "bottom-right, top-left, top-right")
    parser.add_argument("--translate-to", metavar="CODE",
                        help="translate mode: write dictation in this "
                             "language, e.g. ar (saved, also in the menu "
                             "bar); \"off\" turns it off")
    parser.add_argument("--list-languages", action="store_true",
                        help="print every supported language code and exit")
    parser.add_argument("--add-language", metavar="CODE", action="append",
                        help="add a language to the menu bar (repeatable)")
    parser.add_argument("--quick-key", metavar="LETTER=CODE", action="append",
                        help="assign a quick key, e.g. r=es (Q/W/E/R/T)")
    parser.add_argument("--add-word", metavar="ENTRY", action="append",
                        help="add to the personal dictionary: a word "
                             "(\"Ollama\") or a fix for a mishearing "
                             "(\"terror form = Terraform\"); repeatable")
    parser.add_argument("--remove-word", metavar="ENTRY", action="append",
                        help="remove a dictionary entry")
    parser.add_argument("--list-words", action="store_true",
                        help="print the personal dictionary and exit")
    args = parser.parse_args()
    if args.ollama_model:
        OLLAMA_MODEL = args.ollama_model
    if args.position:
        settings.set_position(args.position)

    if args.list_languages:
        enabled = set(settings.get_languages())
        for code in languages.sorted_codes():
            mark = "*" if code in enabled else " "
            print(f"{mark} {code:4} {languages.english_name(code):22} "
                  f"{languages.native_name(code)}")
        print("\n* = shown in the menu bar")
        print("\nTranslate mode can also write (--translate-to):")
        for code in sorted(translate.EXTRA_TARGETS,
                           key=translate.english_name):
            print(f"  {code:4} {translate.english_name(code):22} "
                  f"{translate.native_name(code)}")
        return
    if args.add_word or args.remove_word or args.list_words:
        for entry in args.add_word or []:
            settings.add_dictionary(entry)
        for entry in args.remove_word or []:
            settings.remove_dictionary(entry)
        for entry in settings.get_dictionary():
            print(entry)
        return
    if args.add_language or args.quick_key:
        for code in args.add_language or []:
            settings.add_language(code)
            print(f"added {languages.label(code)}")
        for spec in args.quick_key or []:
            slot, _, code = spec.partition("=")
            settings.add_language(code)
            settings.set_quick_key(slot.lower(), code)
            print(f"quick key {slot.upper()} → {languages.label(code)}")
        print("restart Sorph (or reopen the menu) to see the change")
        return

    language = args.language or settings.get_language()
    if language not in languages.CATALOG:
        parser.error(f"unknown language code {language!r}; "
                     f"see --list-languages")
    if args.translate_to:
        to = None if args.translate_to == "off" else args.translate_to
        if to and not translate.known(to):
            parser.error(f"unknown language code {to!r}; "
                         f"see --list-languages")
        settings.set_translate_to(to)

    if args.transcribe:
        transcriber = Transcriber(args.model, language)
        to = settings.get_translate_to()
        server, llm = translation_llm(args.ollama)
        route = translate.route(language, to, llm is not None)
        own = server is not None and (route == "llm" or args.cleanup)
        if own and not gemma.installed():
            gemma.install()                 # first use: fetch the weights
        if own:
            t2 = time.time()
            server.start()
            print(f"[{gemma.MODEL_NAME} loaded in {time.time() - t2:.1f}s]")
        t0 = time.time()
        text = transcriber.transcribe(
            args.transcribe,
            task="translate" if route == "whisper" else "transcribe")
        print(f"[{(time.time() - t0) * 1000:.0f}ms] {text}")
        t1 = time.time()
        written = "en" if route == "whisper" else language
        if settings.is_self_corrections():
            text = cleanup.self_correct(text, written)
        cleaned = cleanup.rule_cleanup(text, written)
        if own and args.cleanup and not route:
            cleaned = cleanup.llm_cleanup(cleaned, language, server.stream)
            cleaned = cleanup.rule_cleanup(cleaned, language)
        elif args.ollama and not route:
            cleaned = cleanup.ollama_cleanup(cleaned, language, OLLAMA_MODEL)
            cleaned = cleanup.rule_cleanup(cleaned, language)
        print(f"[cleanup {(time.time() - t1) * 1000:.0f}ms] {cleaned}")
        if route in ("m2m", "llm"):
            t2 = time.time()
            translator = translate.Translator(CPU_THREADS, llm)
            out = translator.translate(cleaned, language, to,
                                       use_llm=route == "llm")
            print(f"[translate → {translate.english_name(to)} "
                  f"{(time.time() - t2) * 1000:.0f}ms] {out}")
        elif to and to != language and not route:
            print(f"(no translation from {languages.english_name(language)} "
                  f"to {translate.english_name(to)})")
        if server is not None:
            server.stop()
        return

    lock = acquire_single_instance_lock()
    if lock is None:
        print("another Sorph instance is already running — exiting")
        return

    try:
        if args.no_pill:
            raise RuntimeError("--no-pill")
        run_with_ui(args, language, lock)
    except KeyboardInterrupt:
        print("\nbye")
    except Exception as exc:  # UI is cosmetic — never block dictation
        if not args.no_pill:
            print(f"warning: overlay unavailable ({exc}); "
                  f"terminal feedback only")
        app = FlowApp(args.model, args.ollama, language=language,
                      preview=args.preview, use_cleanup=args.cleanup)
        app._lock = lock
        try:
            app.run()
        except KeyboardInterrupt:
            print("\nbye")


def run_with_ui(args, language, lock):
    """Cocoa mode: splash while loading, then menu bar + pill + hotkey.

    The event loop must own the main thread, so the (slow) model load runs
    on a worker and hands the finished FlowApp back via callAfter.
    """
    from PyObjCTools import AppHelper
    from overlay import create_overlay
    from menubar import create_menubar
    from splash import create_splash

    overlay = create_overlay(lambda: 0.0)   # also sets up NSApplication
    # the dashboard is the startup screen and then Sorph's window; without
    # it (no WebKit, page not built) the plain splash card stands in
    try:
        from dashboard import create_dashboard
        dashboard = create_dashboard()
    except Exception as exc:
        print(f"warning: dashboard unavailable ({exc})", flush=True)
        dashboard = None
    splash = dashboard or create_splash()
    splash.show()
    state = {}

    def _ready(app):
        app._lock = lock
        app.overlay = overlay
        overlay.level_source = lambda: app.recorder.level
        app.menubar = create_menubar(
            app.status_text(), app.language, app.set_language,
            on_position=overlay.set_position, on_move=overlay.move_mode,
            translate_to=app.translate_to, on_translate=app.set_translate,
            llm=app.llm,
            on_open=dashboard.open if dashboard else None,
            on_toggle=app.toggle_translate,
            on_settings=dashboard.open_settings if dashboard else None)
        if dashboard:
            dashboard.bind(dict(
                language=lambda: app.language,
                translate_to=lambda: app.translate_to, llm=app.llm,
                on_language=app.set_language,
                on_translate=app.set_translate,
                on_position=overlay.set_position,
                on_changed=app.menubar.refresh,
                moving=lambda: bool(app.menubar.moving),
                on_move=lambda: app.menubar.toggleMove_(None)))
            app.menubar.on_moved = dashboard.refresh
            app.window = dashboard
        app.start_listener()
        splash.finish()

    def _failed(exc):
        splash.finish(f"failed to start: {exc}")
        print(f"fatal: {exc}", flush=True)
        AppHelper.callLater(3.0, AppHelper.stopEventLoop)
        state["error"] = exc

    def _load():
        try:
            app = FlowApp(args.model, args.ollama, language=language,
                          progress=splash.set_stage,
                          preview=args.preview, use_cleanup=args.cleanup)
        except Exception as exc:
            AppHelper.callAfter(_failed, exc)
            return
        AppHelper.callAfter(_ready, app)

    threading.Thread(target=_load, daemon=True).start()
    AppHelper.runEventLoop(installInterrupt=True)
    if "error" in state:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
