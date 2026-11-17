"""The local LLM for translate mode: Gemma 3, run by Sorph itself.

No Ollama, no Homebrew, nothing to start by hand. Two things are downloaded
once (install()):

* the llama.cpp runtime: prebuilt `llama-server` for this Mac's processor
  (MIT, about 30 MB unpacked), from the llama.cpp GitHub release pinned
  below and checked against its SHA-256. install.sh fetches it;
* the weights: Gemma 3 4B, 4-bit (2.5 GB, Google's Gemma terms), from
  llama.cpp's own Hugging Face organisation, pinned to a commit. They are
  fetched the first time translate mode is turned on (or by
  `install.sh --translate` / `--with-cleanup`, ahead of time), so an
  install that only dictates never downloads them.

The same server also runs the optional cleanup pass (Server.stream).

While translate mode is on, Sorph runs llama-server as a child process,
listening on 127.0.0.1 only, on a free port, behind a key made up for that
run. It is stopped when translate mode is turned off or Sorph goes away
(quit, crash or kill), and it lets go of the model's memory after SLEEP_IDLE_SEC without a request
(the next sentence then takes a few seconds longer).

Needs macOS 13.3 or later (what the prebuilt runtime is built for). Where
it is missing, translate mode uses M2M100 instead (see translate.py).
"""

import atexit
import hashlib
import json
import os
import platform
import secrets
import shutil
import socket
import subprocess
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

LLAMA_TAG = "b12470"
LLAMA_URL = ("https://github.com/ggml-org/llama.cpp/releases/download/"
             "{tag}/llama-{tag}-bin-macos-{arch}.tar.gz")
LLAMA_SHA256 = {
    "x64": "58e935bf5974a649929b15ff8ebdfa6dd11894fdb0486f5b8d52a13584849ee4",
    "arm64": "23e0c4f1705e01519f094a3d4ce3194cead4251f862137e996173b74b73d2404",
}
MIN_MACOS = (13, 3)

MODEL_REPO = "ggml-org/gemma-3-4b-it-GGUF"
MODEL_REVISION = "d0976223747697cb51e056d85c532013931fe52e"
MODEL_FILE = "gemma-3-4b-it-Q4_K_M.gguf"
MODEL_NAME = "gemma3:4b"       # for status lines
MODEL_GB = 2.5

CONTEXT = 2048                # tokens: a dictated sentence and its answer
SLEEP_IDLE_SEC = 900
START_TIMEOUT = 120           # cold start reads 2.5 GB from disk
REQUEST_TIMEOUT = 60

RUNTIME_ROOT = Path(
    os.environ.get("SORPH_LLAMA_DIR")
    or Path.home() / "Library" / "Application Support" / "LocalFlow"
    / "llama")
# written by `install.sh --no-translate`: this install does without Gemma,
# and neither an update nor turning translate mode on may fetch it
OPT_OUT = RUNTIME_ROOT.parent / "no-translate-model"

_install_lock = threading.Lock()


# ---------------------------------------------------------------- install

def arch() -> str:
    return "arm64" if platform.machine() == "arm64" else "x64"


def supported() -> bool:
    """Can the prebuilt runtime run on this macOS?"""
    try:
        version = tuple(int(p) for p in platform.mac_ver()[0].split(".")[:2])
    except ValueError:
        return False
    return len(version) == 2 and version >= MIN_MACOS


def server_path() -> Path:
    return RUNTIME_ROOT / LLAMA_TAG / "llama-server"


def model_path():
    """The weights file if it is on disk already, else None."""
    try:
        from huggingface_hub import hf_hub_download
        return hf_hub_download(MODEL_REPO, MODEL_FILE,
                               revision=MODEL_REVISION, local_files_only=True)
    except Exception:
        return None


def installed() -> bool:
    return (supported() and os.access(server_path(), os.X_OK)
            and model_path() is not None)


def available() -> bool:
    """Can this install use Gemma: on disk already, or fetched when it is
    first needed? False on a macOS too old for the runtime and on a
    --no-translate install."""
    return supported() and not OPT_OUT.exists()


def install_runtime(say=print) -> Path:
    """Download, verify and unpack llama-server. Idempotent."""
    target = server_path()
    if os.access(target, os.X_OK):
        return target
    url = LLAMA_URL.format(tag=LLAMA_TAG, arch=arch())
    say(f"downloading the llama.cpp runtime ({LLAMA_TAG}, {arch()})")
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=RUNTIME_ROOT) as tmp:
        archive = Path(tmp) / "llama.tar.gz"
        digest = hashlib.sha256()
        with urllib.request.urlopen(url, timeout=60) as resp, \
                open(archive, "wb") as out:
            for chunk in iter(lambda: resp.read(1 << 20), b""):
                digest.update(chunk)
                out.write(chunk)
        if digest.hexdigest() != LLAMA_SHA256[arch()]:
            raise RuntimeError(
                f"llama.cpp runtime failed its checksum ({url}); "
                f"nothing was installed")
        unpacked = Path(tmp) / "unpacked"
        with tarfile.open(archive) as tar:
            try:
                tar.extractall(unpacked, filter="data")
            except TypeError:       # Python before the extraction filters
                for member in tar.getmembers():
                    if (member.name.startswith(("/", "..")) or
                            "/../" in member.name or member.isdev()):
                        raise RuntimeError("unsafe path in runtime archive")
                tar.extractall(unpacked)
        found = list(unpacked.rglob("llama-server"))
        if not found:
            raise RuntimeError("llama-server missing from the runtime archive")
        final = RUNTIME_ROOT / LLAMA_TAG
        shutil.rmtree(final, ignore_errors=True)
        os.replace(found[0].parent, final)
    for old in RUNTIME_ROOT.iterdir():        # runtimes of older Sorphs
        if old.is_dir() and old.name != LLAMA_TAG:
            shutil.rmtree(old, ignore_errors=True)
    return target


def _progress_bar(on_progress):
    """A tqdm class that reports the downloaded share (0..1) to
    `on_progress` instead of drawing a bar."""
    from tqdm.auto import tqdm

    class Bar(tqdm):
        def __init__(self, *args, **kwargs):
            self._all = kwargs.get("total") or 0
            self._got = kwargs.get("initial") or 0
            kwargs["disable"] = True    # no bar in the service's log
            super().__init__(*args, **kwargs)

        def update(self, n=1):
            self._got += n or 0
            if self._all:
                try:
                    on_progress(min(1.0, self._got / self._all))
                except Exception:
                    pass            # a status line must not stop a download
            return super().update(n)

    return Bar


def install_model(say=print, on_progress=None) -> str:
    """Download the weights (resumes a broken download). Idempotent.
    `on_progress(share)` is called with 0..1 while it downloads."""
    path = model_path()
    if path:
        return path
    from huggingface_hub import hf_hub_download
    say(f"downloading the translation model {MODEL_NAME} "
        f"({MODEL_GB} GB, once)")
    if on_progress is not None:
        try:
            return hf_hub_download(MODEL_REPO, MODEL_FILE,
                                   revision=MODEL_REVISION,
                                   tqdm_class=_progress_bar(on_progress))
        except TypeError:           # a huggingface_hub without tqdm_class
            pass
    return hf_hub_download(MODEL_REPO, MODEL_FILE, revision=MODEL_REVISION)


def install(say=print, on_progress=None) -> bool:
    """Everything translate mode's LLM needs. False on a macOS that cannot
    run the runtime (M2M100 is used there). Safe from several threads: the
    second caller waits for the first one's download."""
    if not supported():
        say(f"macOS {platform.mac_ver()[0]} is older than "
            f"{MIN_MACOS[0]}.{MIN_MACOS[1]}: translate mode will use the "
            f"smaller M2M100 model")
        return False
    with _install_lock:
        install_runtime(say)
        install_model(say, on_progress)
    OPT_OUT.unlink(missing_ok=True)
    return True


# ---------------------------------------------------------------- server

# llama-server under a watchdog shell: it is killed when Sorph goes away
# for any reason (Quit from the menu ends the process without running
# Python's exit handlers; a crash or kill -9 runs nothing at all), so a
# 4 GB orphan can never be left behind.
_WATCHDOG = ('parent=$1; shift; "$@" & child=$!; '
             'trap \'kill "$child" 2>/dev/null\' TERM INT HUP; '
             'while kill -0 "$parent" 2>/dev/null '
             '&& kill -0 "$child" 2>/dev/null; do sleep 1; done; '
             'kill "$child" 2>/dev/null; wait "$child" 2>/dev/null')


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    """llama-server as a child of this process. start() and stop() are
    idempotent and safe from any thread."""

    def __init__(self, threads: int = 4, sleep_idle: int = SLEEP_IDLE_SEC):
        self.threads = threads
        self.sleep_idle = sleep_idle
        self._proc = None
        self._port = None
        self._key = None
        self._lock = threading.Lock()
        atexit.register(self.stop)

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> bool:
        """Run the server and wait until the model is loaded. False when
        it is not installed or does not come up."""
        with self._lock:
            if self.running:
                return True
            model = model_path()
            if not (model and supported()
                    and os.access(server_path(), os.X_OK)):
                return False
            self._port, self._key = _free_port(), secrets.token_hex(16)
            cmd = [str(server_path()), "-m", model,
                   "--host", "127.0.0.1", "--port", str(self._port),
                   "--api-key", self._key, "--alias", MODEL_NAME,
                   "-c", str(CONTEXT), "-np", "1", "-t", str(self.threads),
                   "--no-webui", "--no-mmproj", "--offline",
                   "--sleep-idle-seconds", str(self.sleep_idle)]
            try:
                self._proc = subprocess.Popen(
                    ["/bin/sh", "-c", _WATCHDOG, "sorph-llama",
                     str(os.getpid())] + cmd, stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError as exc:
                print(f"warning: could not start llama-server: {exc}",
                      flush=True)
                self._proc = None
                return False
            deadline = time.time() + START_TIMEOUT
            while time.time() < deadline:
                if self._proc.poll() is not None:
                    print(f"warning: llama-server exited with "
                          f"{self._proc.returncode}", flush=True)
                    self._proc = None
                    return False
                if self._healthy():
                    return True
                time.sleep(0.2)
            print("warning: llama-server did not come up in time",
                  flush=True)
            self._kill()
            return False

    def _healthy(self) -> bool:
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{self._port}/health", timeout=2) as r:
                return r.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def stop(self):
        with self._lock:
            self._kill()

    def _kill(self):
        proc, self._proc = self._proc, None
        if proc is None or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    def chat(self, system: str, user: str, max_tokens: int = 512):
        """The model's answer, or None (not running, error, timeout)."""
        if not self.start():
            return None
        payload = json.dumps({
            "model": MODEL_NAME,
            "temperature": 0,
            "max_tokens": max_tokens,
            "cache_prompt": True,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{self._port}/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self._key}"})
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
                return json.loads(r.read())["choices"][0]["message"]["content"]
        except (urllib.error.URLError, TimeoutError, OSError, ValueError,
                KeyError, IndexError, TypeError):
            return None

    def stream(self, system: str, user: str, on_partial=None,
               first_timeout: float = 4, total_timeout: float = 15,
               max_tokens: int = 512):
        """The model's answer, streamed: `on_partial(text_so_far)` fires
        per token. None when it does not answer in time. Never waits for a
        cold start: a server that is not up is started in the background
        for the next call (a dictation must not stall on a model load)."""
        if not self.running:
            threading.Thread(target=self.start, daemon=True).start()
            return None
        payload = json.dumps({
            "model": MODEL_NAME,
            "temperature": 0,
            "max_tokens": max_tokens,
            "cache_prompt": True,
            "stream": True,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{self._port}/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self._key}"})
        out = ""
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=first_timeout) as r:
                for line in r:
                    if time.time() - t0 > total_timeout:
                        return None
                    line = line.strip()
                    if not line.startswith(b"data:"):
                        continue
                    data = line[5:].strip()
                    if data == b"[DONE]":
                        break
                    choice = json.loads(data)["choices"][0]
                    piece = (choice.get("delta") or {}).get("content")
                    if piece:
                        out += piece
                        if on_partial is not None:
                            on_partial(out)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError,
                KeyError, IndexError, TypeError):
            return None
        return out
