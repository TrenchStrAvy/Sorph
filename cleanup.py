"""Transcript cleanup for Sorph.

Two flavours, both returning plain text:

* rule_cleanup()   — deterministic: drop filler words, capitalize sentence
                     starts, close the last sentence. Instant, never rewrites.
* self_correct()   — resolve spoken corrections ("Tuesday, actually no,
                     Wednesday"), by rule.
* ollama_cleanup() — optional LLM pass, streamed token by token so the UI
                     can show the correction as it happens, and guarded: an
                     answer that drops, invents or paraphrases content is
                     discarded in favour of the raw transcript.

word_diff() marks what changed between two versions so the overlay can
strike out removed words and highlight edited ones.
"""

import difflib
import json
import re
import urllib.error
import urllib.request

import languages

OLLAMA_URL = "http://localhost:11434/api/chat"
FIRST_TOKEN_TIMEOUT = 4       # seconds to wait for the model to start
STREAM_TIMEOUT = 15           # hard cap on the whole cleanup pass

SYSTEM_PROMPT = (
    "You are a dictation cleanup tool. The user message is text dictated in "
    "{language}. Return the same text with punctuation and capitalization "
    "fixed and filler words (um, uh, äh, ähm, euh) removed. Keep every other "
    "word exactly as it is. Never translate, never answer or comment, never "
    "add or drop content. Output only the corrected text."
)

# Filler words Whisper writes out. Per language, so a token that is a real
# word elsewhere ("er" in German, "hum" in English) is only stripped where it
# is noise. English fillers are applied everywhere: they leak into every
# language's speech.
FILLERS = {
    "en": {"um", "umm", "uh", "uhm", "uhh", "erm", "hmm", "mm", "mhm"},
    "de": {"äh", "ähm", "ähh", "hm", "hmm", "mhm", "mmh"},
    "fr": {"euh", "euhh", "hum", "hem"},
    "es": {"em", "ehm"},
    "nl": {"uh", "uhm", "ehm"},
}

# a period ends a sentence unless it is part of an ellipsis ("..." marks a
# pause in Whisper output, not a full stop)
_SENTENCE_END = re.compile(
    r"""((?:(?<!\.)\.(?!\.)|[!?])["'”’)\]]*\s+)(\w)""", re.UNICODE)


def _filler_pattern(language: str):
    words = set(FILLERS["en"]) | FILLERS.get(language, set())
    alts = "|".join(sorted(map(re.escape, words), key=len, reverse=True))
    # the filler plus any comma/ellipsis glued to it, e.g. "um," or "äh…"
    return re.compile(rf"(?<![\w'’])(?:{alts})(?![\w'’])[,…]?\s*",
                      re.IGNORECASE | re.UNICODE)


def rule_cleanup(text: str, language: str = "en", close: bool = True,
                 capitalize_first: bool = True) -> str:
    """Filler removal + sentence capitalization + closing punctuation.

    `close=False` leaves the end open (a mid-dictation pause is not a full
    stop); `capitalize_first=False` continues a sentence that is already
    under way."""
    text = text.strip()
    if not text:
        return text
    text = _filler_pattern(language).sub("", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)      # "word ," → "word,"
    text = re.sub(r"\s{2,}", " ", text).strip()
    text = re.sub(r"^[,;:]\s*", "", text)               # leading orphan comma
    if not text:
        return text
    if capitalize_first:
        text = text[0].upper() + text[1:]
    text = _SENTENCE_END.sub(lambda m: m.group(1) + m.group(2).upper(), text)
    if close and text[-1].isalnum():
        text += "."
    return text


def ends_sentence(text: str) -> bool:
    """Does a following utterance start a new sentence?"""
    return not text or text.rstrip()[-1] in ".!?…"


def join(a: str, b: str) -> str:
    return (a + " " + b).strip() if a and b else (a or b)


# ---------------------------------------------------------------- sanity

_HAS_TEXT = re.compile(r"\w", re.UNICODE)


def strip_repeats(text: str, min_runs: int = 3) -> str:
    """Cut a decoder loop: once a phrase of 1–4 words repeats `min_runs`
    times back to back ("the the the", "a bit of a bit of a bit of"), keep
    the text up to the first occurrence only. Junk with no letters or
    digits ("//") becomes empty."""
    if not _HAS_TEXT.search(text):
        return ""
    words = text.split()
    norm = [_norm(w) for w in words]
    for i in range(len(norm)):
        for p in range(1, 5):
            runs = 1
            while (i + (runs + 1) * p <= len(norm)
                   and norm[i + runs * p:i + (runs + 1) * p] == norm[i:i + p]):
                runs += 1
            if runs >= min_runs:
                return " ".join(words[:i + p])
    return text


# ---------------------------------------------------------------- plausibility

MAX_COMPRESSION = 2.4         # text this repetitive is a decoder loop
MAX_CHARS_PER_SEC = 30        # nobody dictates faster than this
QUIET_NO_SPEECH = 0.25        # below the voice gate, the decoder must be
QUIET_LOGPROB = -1.0          # this sure there is speech at all


def plausible_segment(avg_logprob: float, no_speech_prob: float,
                      compression_ratio: float, voiced: bool = True) -> bool:
    """Keep a decoded segment? Whisper writes fluent sentences for faint
    background sound (a TV, music, someone else talking); those segments
    come with a raised no-speech score or low confidence. Audio as loud as
    the user's voice (`voiced`) gets the benefit of the doubt; quieter
    audio has to convince."""
    if compression_ratio > MAX_COMPRESSION:
        return False
    if voiced:
        return not (no_speech_prob > 0.6 and avg_logprob < -1.0)
    return no_speech_prob <= QUIET_NO_SPEECH and avg_logprob >= QUIET_LOGPROB


def plausible_length(text: str, seconds: float) -> bool:
    """More text than could be spoken in the time is invented."""
    return len(text) <= MAX_CHARS_PER_SEC * seconds + 20


# ---------------------------------------------------------------- self-corrections

# "X, actually no, Y" keeps Y. Cues are English; other languages pass
# through untouched.
_DELETE_CUES = ("scratch that", "strike that")
_STRONG_CUES = ("sorry i meant", "actually no", "no actually", "no wait",
                "wait no", "or rather", "i meant")
_WEAK_CUES = ("i mean",)      # also a filler: only after a comma or dash


def _cue_pattern():
    def alt(phrases):
        return "|".join(r"[,]?\s+".join(map(re.escape, p.split()))
                        for p in sorted(phrases, key=len, reverse=True))
    return re.compile(
        rf"(?<![\w'’])(?:(?P<delete>{alt(_DELETE_CUES)})"
        rf"|(?P<strong>{alt(_STRONG_CUES)})"
        rf"|(?P<weak>{alt(_WEAK_CUES)}))(?![\w'’])", re.IGNORECASE)


_CUE = _cue_pattern()
_LEAD = re.compile(r"[\s,.;:!?…–—-]*$")
_TRAIL = re.compile(r"^[\s,.;:!…–—-]*")
_CLAUSE = re.compile(r"^[^,.;:!?…]+")
_LAST_SENTENCE = re.compile(r"""^(.*[.!?]["'”’)\]]*\s+)?(.*)$""", re.DOTALL)


def _correct_once(text: str) -> str:
    for m in _CUE.finditer(text):
        pre, post = text[:m.start()], text[m.end():]
        lead = _LEAD.search(pre).group()
        trail = _TRAIL.match(post).group()
        before, after = pre[:len(pre) - len(lead)], post[len(trail):]
        if not before.strip():
            continue                    # nothing said yet to correct
        punctuated = bool(lead.strip() or trail.strip())
        head, clause = _LAST_SENTENCE.match(before).groups()
        head = head or ""
        if m.group("delete"):
            if not (punctuated or not after):
                continue
            return (head + after).strip()
        said = _CLAUSE.match(after)
        if said is None or not punctuated:
            continue
        fix = said.group().split()
        if m.group("weak"):
            new_sentence = any(c in lead for c in ".!?")
            if not lead.strip() or (new_sentence and len(fix) > 2):
                continue
        old = clause.split()
        if not fix or not old:
            continue
        # resume at the word the correction starts over from ("to John, no
        # wait, to Mary"), else swap as many words as were said again
        first = _norm(fix[0])
        at = next((j for j in range(len(old) - 1, -1, -1)
                   if first and _norm(old[j]) == first),
                  max(0, len(old) - len(fix)))
        if (at > 0 and old[at][:1].islower() and fix[0][:1].isupper()
                and fix[0] != "I" and not fix[0].startswith(("I'", "I’"))):
            fix[0] = fix[0][0].lower() + fix[0][1:]   # no new sentence here
        return head + " ".join(old[:at] + fix) + after[said.end():]
    return text


def self_correct(text: str, language: str = "en") -> str:
    """Resolve spoken corrections: "at five, I mean six" → "at six";
    "Call Tom. Scratch that. Email him." → "Email him."."""
    if language != "en" or not text:
        return text
    for _ in range(8):
        new = _correct_once(text)
        if new == text:
            break
        text = new
    return text


# ---------------------------------------------------------------- diffing

def _norm(token: str) -> str:
    return re.sub(r"[^\w]", "", token, flags=re.UNICODE).lower()


def word_diff(old: str, new: str):
    """[(word, style)] over the words of `new`, with removed words of `old`
    interleaved. style ∈ {"same", "changed", "removed"}. Case and
    punctuation are ignored when matching, so "hello" → "Hello," is "same".
    """
    a, b = old.split(), new.split()
    sm = difflib.SequenceMatcher(a=[_norm(t) for t in a],
                                 b=[_norm(t) for t in b], autojunk=False)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            out.extend((t, "same") for t in b[j1:j2])
        elif op == "delete":
            out.extend((t, "removed") for t in a[i1:i2])
        elif op == "insert":
            out.extend((t, "changed") for t in b[j1:j2])
        else:  # replace
            out.extend((t, "removed") for t in a[i1:i2])
            out.extend((t, "changed") for t in b[j1:j2])
    return out


def faithful(raw: str, cleaned: str) -> bool:
    """Did the model only edit, or did it rewrite? Cleanup may drop fillers
    and fix spelling, so allow a little drift; reject anything that loses
    or invents a chunk of the sentence."""
    a = [_norm(t) for t in raw.split()]
    b = [_norm(t) for t in cleaned.split()]
    a = [t for t in a if t]
    b = [t for t in b if t]
    if not b:
        return False
    if abs(len(a) - len(b)) > max(2, 0.25 * len(a)):
        return False
    return difflib.SequenceMatcher(a=a, b=b, autojunk=False).ratio() >= 0.75


# ---------------------------------------------------------------- LLM pass

def ollama_cleanup(text: str, language: str = "en", model: str = "gemma3:4b",
                   on_partial=None) -> str:
    """Stream a cleanup from Ollama. `on_partial(text_so_far)` fires per
    token. Returns the raw text on timeout, error or an unfaithful answer."""
    payload = json.dumps({
        "model": model,
        "stream": True,
        "keep_alive": "60m",
        "options": {"temperature": 0},
        "messages": [
            {"role": "system",
             "content": SYSTEM_PROMPT.format(
                 language=languages.english_name(language))},
            {"role": "user", "content": text},
        ],
    }).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
    out = ""
    try:
        import time
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=FIRST_TOKEN_TIMEOUT) as resp:
            for line in resp:
                if time.time() - t0 > STREAM_TIMEOUT:
                    return text
                chunk = json.loads(line)
                out += chunk.get("message", {}).get("content", "")
                if on_partial is not None:
                    on_partial(out)
                if chunk.get("done"):
                    break
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError):
        return text
    cleaned = out.strip().strip('"“”')
    return cleaned if faithful(text, cleaned) else text


def ollama_warmup(model: str, on_done=None):
    """Load the model into RAM so the first dictation doesn't pay the
    cold start. Runs synchronously; call from a thread."""
    payload = json.dumps({"model": model, "messages": [],
                          "keep_alive": "60m"}).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=120).read()
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
