"""Translate mode for Sorph: speak one language, write another.

The transcript Whisper produces is translated on this Mac before it is
written. Three ways to get there, picked per language pair by route():

* llm      the default: Gemma 3, run by Sorph itself (gemma.py; installed
           by install.sh). Every pair, natural sentences, 2 to 3 s each on
           an Intel i9. Without it, an Ollama started with --ollama does
           the same job.
* m2m      without an LLM, and as the fallback when it does not answer:
           M2M100 (Meta, MIT), run with CTranslate2, the engine
           faster-whisper already uses. One 490 MB model covers every pair
           among 100 languages; it gets the meaning across but drops and
           garbles more. Pairs without English go through English (French
           → English → Arabic): measured on the 418M model, that reads
           better than the direct pair, for about twice the time (0.6 to
           1.1 s a sentence).
* whisper  without an LLM, Whisper's own translate task covers the spoken
           languages M2M100 does not know (Telugu, Basque, Maltese, …)
           when the target is English.

M2M100 is downloaded on first use into ~/.cache/huggingface, and read
from there without touching the network afterwards.
"""

import json
import os
import re
import threading
import urllib.error
import urllib.request

import languages

# A CTranslate2 int8 conversion of facebook/m2m100_418M, pinned to a commit
# so the files can never change under an installed Sorph. (The 1.2B
# conversion was measured too: slower, and worse into Arabic.)
M2M_REPO = "jncraton/m2m100_418M-ct2-int8"
M2M_REVISION = "7c1b2620a4e58dacecbd8bf89cfd6da7eb9eb7b0"
M2M_FILES = ["model.bin", "config.json", "shared_vocabulary.json",
             "sentencepiece.bpe.model"]

M2M_CODES = frozenset(
    "af am ar ast az ba be bg bn br bs ca ceb cs cy da de el en es et fa ff "
    "fi fr fy ga gd gl gu ha he hi hr ht hu hy id ig ilo is it ja jv ka kk "
    "km kn ko lb lg ln lo lt lv mg mk ml mn mr ms my ne nl no ns oc or pa pl "
    "ps pt ro ru sd si sk sl so sq sr ss su sv sw ta th tl tn tr uk ur uz vi "
    "wo xh yi yo zh zu".split())

# Sorph (Whisper) code → M2M100 code, where they differ
_TO_M2M = {"jw": "jv"}

# Languages M2M100 writes but Whisper cannot hear: targets only.
# code → (native name, English name)
EXTRA_TARGETS = {
    "ast": ("Asturianu", "Asturian"),
    "ceb": ("Cebuano", "Cebuano"),
    "ff": ("Fulfulde", "Fulah"),
    "fy": ("Frysk", "Western Frisian"),
    "ga": ("Gaeilge", "Irish"),
    "gd": ("Gàidhlig", "Scottish Gaelic"),
    "ig": ("Igbo", "Igbo"),
    "ilo": ("Ilokano", "Iloko"),
    "lg": ("Luganda", "Ganda"),
    "ns": ("Sesotho sa Leboa", "Northern Sotho"),
    "or": ("ଓଡ଼ିଆ", "Odia"),
    "ss": ("SiSwati", "Swati"),
    "tn": ("Setswana", "Tswana"),
    "wo": ("Wolof", "Wolof"),
    "xh": ("isiXhosa", "Xhosa"),
    "zu": ("isiZulu", "Zulu"),
}

NO_SPACE = frozenset({"zh", "ja", "th", "lo", "km", "my"})  # written unspaced

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_TIMEOUT = 60
MAX_PIECES = 160              # longer "sentences" are split before decoding

_SENTENCES = re.compile(r"(?<=[.!?…؟])\s+|(?<=[。！？])")


# ---------------------------------------------------------------- catalog

def _names(code: str):
    return EXTRA_TARGETS.get(code) or languages.CATALOG.get(code, (code, code))


def native_name(code: str) -> str:
    return _names(code)[0]


def english_name(code: str) -> str:
    return _names(code)[1]


def label(code: str) -> str:
    native, english = _names(code)
    return native if native == english else f"{native} ({english})"


def known(code) -> bool:
    return code in languages.CATALOG or code in EXTRA_TARGETS


def _m2m(code):
    """M2M100's code for a Sorph language, or None when it has none."""
    code = _TO_M2M.get(code, code)
    return code if code in M2M_CODES else None


def route(source: str, target, llm: bool = False):
    """How `source` speech becomes `target` text: "llm", "m2m", "whisper",
    or None (translation off, same language, or no way to do this pair).
    `llm`: a local LLM is there to translate."""
    if not target or target == source or not known(target):
        return None
    if llm:
        return "llm"
    if _m2m(source) and _m2m(target):
        return "m2m"
    if target == "en":
        return "whisper"
    return None


def targets(source: str, llm: bool = False) -> list:
    """Every language `source` can be translated into, by English name."""
    codes = list(languages.CATALOG) + list(EXTRA_TARGETS)
    return sorted((c for c in codes if route(source, c, llm)),
                  key=lambda c: english_name(c).lower())


def join(a: str, b: str, target: str) -> str:
    """Append translated text `b` to `a` the way `target` is written."""
    if not (a and b):
        return a or b
    return a + ("" if target in NO_SPACE else " ") + b


def sentences(text: str) -> list:
    return [s.strip() for s in _SENTENCES.split(text) if s and s.strip()]


# ---------------------------------------------------------------- engine

class Translator:
    """M2M100 behind a lock, loaded on first use. `llm` adds the LLM
    route: a callable (system prompt, text) → answer or None, such as
    gemma.Server.chat or ollama_chat(model)."""

    def __init__(self, threads: int = 4, llm=None):
        self.threads = threads
        self.llm = llm
        self._model = None
        self._sp = None
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self._model is not None

    @staticmethod
    def cached() -> bool:
        """Is the model on disk already (no download needed)?"""
        try:
            _snapshot(local_only=True)
            return True
        except Exception:
            return False

    def load(self):
        """Load the model (downloading it the first time). Idempotent;
        raises when it is neither cached nor downloadable."""
        with self._lock:
            if self._model is not None:
                return
            import ctranslate2
            import sentencepiece
            try:
                path = _snapshot(local_only=True)
            except Exception:
                print("Downloading the translation model (490 MB, once)...",
                      flush=True)
                path = _snapshot(local_only=False)
            self._sp = sentencepiece.SentencePieceProcessor(
                model_file=os.path.join(path, "sentencepiece.bpe.model"))
            self._model = ctranslate2.Translator(
                path, device="cpu", compute_type="int8",
                intra_threads=self.threads)

    def translate(self, text: str, source: str, target: str,
                  use_llm: bool = False) -> str:
        """`text` in `target`. Raises when no engine can do the pair."""
        text = text.strip()
        if not text or source == target:
            return text
        src, tgt = _m2m(source), _m2m(target)
        if use_llm and self.llm:
            out = llm_translate(self.llm, text, source, target)
            if out:
                return out
            # M2M100 steps in only when it is already here: a dictation
            # must not wait for a 490 MB download
            if not (src and tgt and (self.ready or self.cached())):
                raise RuntimeError("the translation model did not answer")
            print("warning: the LLM did not translate; using M2M100",
                  flush=True)
        if not (src and tgt):
            raise ValueError(f"no translation from {source} to {target}")
        self.load()
        parts = sentences(text)
        if src != "en" and tgt != "en":
            parts = self._m2m_batch(parts, src, "en")
            src = "en"
        out = self._m2m_batch(parts, src, tgt)
        return ("" if target in NO_SPACE else " ").join(p for p in out if p)

    def _m2m_batch(self, parts, src, tgt):
        batch, owner = [], []
        for i, part in enumerate(parts):
            pieces = self._sp.encode(part, out_type=str)
            for a in range(0, len(pieces), MAX_PIECES):
                batch.append([f"__{src}__"] + pieces[a:a + MAX_PIECES]
                             + ["</s>"])
                owner.append(i)
        with self._lock:
            results = self._model.translate_batch(
                batch, target_prefix=[[f"__{tgt}__"]] * len(batch),
                beam_size=4, repetition_penalty=1.1,
                no_repeat_ngram_size=4, max_decoding_length=256)
        out = [""] * len(parts)
        for i, result in zip(owner, results):
            piece = self._sp.decode(result.hypotheses[0][1:]).strip()
            out[i] = (out[i] + " " + piece).strip()
        return out


def _snapshot(local_only: bool) -> str:
    from huggingface_hub import snapshot_download
    return snapshot_download(M2M_REPO, revision=M2M_REVISION,
                             allow_patterns=M2M_FILES,
                             local_files_only=local_only)


# ---------------------------------------------------------------- LLM route

_PROMPT = ("You are a translator. Translate the user's text from {source} "
           "to {target}. Reply with the translation only: no notes, no "
           "quotation marks, no explanations. Keep names, numbers and "
           "punctuation style.")


def llm_translate(llm, text: str, source: str, target: str):
    """Translation from a local LLM, or None when it fails or answers
    with something that cannot be one (empty, or many times too long)."""
    try:
        out = llm(_PROMPT.format(source=english_name(source),
                                 target=english_name(target)), text)
    except Exception as exc:
        print(f"warning: LLM translation failed: {exc}", flush=True)
        return None
    out = (out or "").strip().strip('"“”')
    if not out or len(out) > 6 * len(text) + 40:
        return None
    return out


def ollama_chat(model: str, url: str = OLLAMA_URL):
    """An `llm` callable backed by a running Ollama (--ollama installs)."""
    def chat(system: str, user: str):
        payload = json.dumps({
            "model": model,
            "stream": False,
            "keep_alive": "60m",
            "options": {"temperature": 0},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }).encode()
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
                return json.loads(resp.read())["message"]["content"]
        except (urllib.error.URLError, TimeoutError, OSError, ValueError,
                KeyError, TypeError):
            return None
    return chat
