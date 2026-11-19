"""Personal dictionary for Sorph: words Whisper should know.

An entry is one of

* a word or name, spelled the way it should be written: "Ollama",
  "Terraform", "tmux". Whisper is told to expect it (faster-whisper's
  hotwords), and whenever it comes out in another case ("ollama") the
  spelling of the entry wins.
* a fix for a mishearing, "heard = written": "terror form = Terraform",
  "Olama = Ollama". Every "heard" in a transcript becomes "written", and
  "written" is also given to Whisper as a word to expect.

Entries live in settings ("dictionary"); the menu bar and --add-word edit
them.
"""

import re

MAX_HOTWORD_CHARS = 400       # the hint shares Whisper's prompt budget
_SPLIT = re.compile(r"\s*(?:=|->|→)\s*")


def parse(entry: str):
    """(heard or None, written) for one entry."""
    parts = _SPLIT.split(entry.strip(), maxsplit=1)
    if len(parts) == 2 and parts[0] and parts[1]:
        return parts[0], parts[1]
    return None, entry.strip()


def hotwords(entries) -> str:
    """The words to bias Whisper towards, as one string ("" for none)."""
    out, size = [], 0
    for entry in entries:
        word = parse(entry)[1]
        if not word or word in out:
            continue
        if size + len(word) + 1 > MAX_HOTWORD_CHARS:
            break
        out.append(word)
        size += len(word) + 1
    return " ".join(out)


def _pattern(phrase: str):
    words = [re.escape(w) for w in phrase.split()]
    return re.compile(r"(?<![\w'’])" + r"\s+".join(words) + r"(?![\w'’])",
                      re.IGNORECASE | re.UNICODE)


def apply(text: str, entries) -> str:
    """Rewrite mishearings and settle the spelling of dictionary words."""
    if not text:
        return text
    for entry in entries:
        heard, written = parse(entry)
        if not written:
            continue
        for phrase in ([heard] if heard else []) + [written]:
            text = _pattern(phrase).sub(lambda _m: written, text)
    return text
