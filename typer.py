"""Inline typing for Sorph: put words into the focused field as they
are recognized, and correct them in place.

The overlay is not involved. LiveTyper remembers what it has typed so far;
each update() diffs it word by word against the new text and fixes only
the words that changed, in place: arrow left to the change, Backspace it,
type the replacement, arrow back to the end. That is how a preview that
said "how it work" becomes "how it works and" a second later, and how a
re-decode that changes the first word fixes that word without wiping and
retyping the whole sentence after it.

Where the app allows it, edits behind the end of the text skip the arrow
keys: the word is swapped through the Accessibility API (select its range,
replace the selected text, put the caret back), so the caret never visibly
travels. Apps that don't support that (terminals, some web and Electron
fields) are noticed once and get the arrow keys from then on.

Keystrokes are raw Quartz keyboard events carrying a Unicode string and no
modifier flags, so they type correctly even while the dictation hotkey
(Right-Option) is physically held, and they never look like the Q/W/E
language quick keys to flow.py's own listener (key code 0 / 51 only).
"""

from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventKeyboardSetUnicodeString,
    CGEventPost,
    CGEventSetFlags,
    CGEventSetIntegerValueField,
    kCGEventSourceUserData,
    kCGHIDEventTap,
)

BACKSPACE_VK = 51
LEFT_VK = 123
RIGHT_VK = 124
ARROW_FLAGS = 0xA00000        # numeric pad + fn, as a real arrow key sends
CHUNK = 16                    # unicode chars per synthetic key event
TAG = 0x4C0CA1F1              # marks our events so flow.py's listener
                              # never mistakes them for Option+A / Q / W / E


import difflib
import re
import time

_WORD = re.compile(r"\S+")


def _norm(word: str) -> str:
    return re.sub(r"[^\w]", "", word).lower()


def plan(typed: str, new: str, floor: int = 0, soft: bool = False):
    """[(start, end, replacement)] in `typed` coordinates, ascending and
    non-overlapping, that turn `typed` into `new` word by word.

    Words are diffed as a sequence, so a changed word early on is one
    small edit and the words after it stay where they are. Exact mode
    compares words as written. Soft mode (live preview) compares them
    ignoring case and punctuation and keeps the typed spelling: the
    preview model's comma or capital may differ from the final model's,
    and rewriting for a comma is flicker for nothing. The final pass runs
    exact and settles it.

    Characters before `floor` are committed and never touched, so a later
    correction can only reach the current utterance. Pure."""
    f = min(floor, len(typed))
    base_t = base_n = 0
    if f:
        # committed text stays; resume after the same *word* in `new`, since
        # its spelling of those words ("coast." vs "coast") may differ
        j = len(_WORD.findall(typed[:f]))
        nw = list(_WORD.finditer(new))
        base_t = f
        base_n = nw[j - 1].end() if 0 < j <= len(nw) else (0 if j == 0 else len(new))
    t, n = typed[base_t:], new[base_n:]
    tw = list(_WORD.finditer(t))
    nw = list(_WORD.finditer(n))
    key = _norm if soft else (lambda w: w)
    tk = [key(m.group()) for m in tw]
    nk = [key(m.group()) for m in nw]
    # the last typed word is re-synced when the text continues past it:
    # a preview ends "test." but the sentence goes on "test how it"
    if soft and tw and len(nw) > len(tw):
        tk[-1] = tw[-1].group()
        nk[len(tw) - 1] = nw[len(tw) - 1].group()

    def span(words, i1, i2):
        # the gap before word i1 through the end of word i2-1, so spacing
        # travels with the words it separates; at the very start, word i1
        # through the gap after word i2-1 instead
        if i1:
            return words[i1 - 1].end(), words[i2 - 1].end() if i2 > i1 else words[i1 - 1].end()
        if i2 < len(words):
            return 0, words[i2].start()
        return 0, words[-1].end() if words else 0

    edits = []
    ops = difflib.SequenceMatcher(None, tk, nk, autojunk=False).get_opcodes()
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            continue
        a, b = span(tw, i1, i2)
        c, d = span(nw, j1, j2)
        edits.append((base_t + a, base_t + b, n[c:d]))
    # text after the last word (rare: trailing whitespace) follows `new`
    tail_t = tw[-1].end() if tw else 0
    tail_n = nw[-1].end() if nw else 0
    if t[tail_t:] != n[tail_n:]:
        if edits and edits[-1][1] == base_t + tail_t:
            a, b, r = edits.pop()
            edits.append((a, len(typed), r + n[tail_n:]))
        else:
            edits.append((base_t + tail_t, len(typed), n[tail_n:]))
    return [_trim(typed, *e) for e in edits]


def _trim(typed, a, b, r):
    """Shrink an edit by the characters it would delete and retype
    unchanged: "work" -> "works and" only types "s and"."""
    old = typed[a:b]
    p = 0
    while p < min(len(old), len(r)) and old[p] == r[p]:
        p += 1
    q = 0
    while q < min(len(old), len(r)) - p and old[-1 - q] == r[-1 - q]:
        q += 1
    return a + p, b - q, r[p:len(r) - q]


def apply(typed: str, edits) -> str:
    """What the field reads after `edits`. Pure."""
    for a, b, r in reversed(edits):
        typed = typed[:a] + r + typed[b:]
    return typed


def _post(vk, text=None, flags=0):
    for is_press in (True, False):
        ev = CGEventCreateKeyboardEvent(None, vk, is_press)
        CGEventSetFlags(ev, flags)
        CGEventSetIntegerValueField(ev, kCGEventSourceUserData, TAG)
        if text:
            CGEventKeyboardSetUnicodeString(ev, len(text), text)
        CGEventPost(kCGHIDEventTap, ev)


# ---------------------------------------------------------------- in place, via AX

try:
    from ApplicationServices import (
        AXUIElementCopyAttributeValue,
        AXUIElementCreateSystemWide,
        AXUIElementGetPid,
        AXUIElementSetAttributeValue,
        AXValueCreate,
        AXValueGetValue,
        kAXFocusedUIElementAttribute,
        kAXSelectedTextAttribute,
        kAXSelectedTextRangeAttribute,
        kAXValueAttribute,
        kAXValueCFRangeType,
    )
    _system = AXUIElementCreateSystemWide()
except Exception:                       # no AX: arrow keys only
    _system = None

AX_SETTLE_SEC = 0.15          # how long an app may take to show an AX edit
_no_ax = set()                # pids whose fields ignored an AX edit


def _u16(text: str) -> int:
    """Length in UTF-16 units, which is how AX counts characters."""
    return len(text.encode("utf-16-le")) // 2


def _get(element, attr):
    err, value = AXUIElementCopyAttributeValue(element, attr, None)
    return value if err == 0 else None


def _set_range(element, loc, length=0) -> bool:
    rng = AXValueCreate(kAXValueCFRangeType, (loc, length))
    return AXUIElementSetAttributeValue(
        element, kAXSelectedTextRangeAttribute, rng) == 0


def _field_state(element):
    """(field text, caret) with the caret in UTF-16 units, or None when the
    field doesn't tell us or has a selection."""
    value = _get(element, kAXValueAttribute)
    rng = _get(element, kAXSelectedTextRangeAttribute)
    if not isinstance(value, str) or rng is None:
        return None
    ok, (loc, length) = AXValueGetValue(rng, kAXValueCFRangeType, None)
    if not ok or length:
        return None
    return str(value), loc


def ax_edit(typed: str, edits):
    """Apply `edits` (none touching the end of `typed`) in the focused
    field without moving the visible caret. Returns the field's text from
    where our typing starts to the caret when the field took the edits,
    None when it didn't (nothing changed: the caller uses the arrow keys)."""
    if _system is None or not edits:
        return None
    element = _get(_system, kAXFocusedUIElementAttribute)
    if element is None:
        return None
    err, pid = AXUIElementGetPid(element, None)
    if err != 0 or pid in _no_ax:
        return None
    state = _field_state(element)
    if state is None:
        return None
    value, caret = state
    v16 = value.encode("utf-16-le")
    base = caret - _u16(typed)
    # the field must read what we typed, ending at the caret
    if base < 0 or v16[2 * base:2 * caret] != typed.encode("utf-16-le"):
        return None
    for a, b, r in reversed(edits):
        start = base + _u16(typed[:a])
        if not (_set_range(element, start, _u16(typed[a:b]))
                and AXUIElementSetAttributeValue(
                    element, kAXSelectedTextAttribute, r) == 0):
            break
    expected = apply(typed, edits)
    end = base + _u16(expected)
    deadline = time.time() + AX_SETTLE_SEC
    while True:
        state = _field_state(element) or (value, None)
        if state[0] != value or time.time() > deadline:
            break
        time.sleep(0.01)
    now = state[0]
    if now == value:                        # the field ignored us
        _set_range(element, caret)
        _no_ax.add(pid)
        return None
    _set_range(element, end)
    n16 = now.encode("utf-16-le")
    field = n16[2 * base:2 * end].decode("utf-16-le", "replace")
    if field != expected:                   # took it, but not as asked
        _no_ax.add(pid)
    return field


def type_text(text: str):
    for i in range(0, len(text), CHUNK):
        _post(0, text[i:i + CHUNK])


def backspace(n: int):
    for _ in range(n):
        _post(BACKSPACE_VK)


def move(n: int):
    """Move the caret n characters right (negative: left)."""
    vk = RIGHT_VK if n > 0 else LEFT_VK
    for _ in range(abs(n)):
        _post(vk, flags=ARROW_FLAGS)


class LiveTyper:
    def __init__(self):
        self.typed = ""
        self.floor = 0

    def reset(self):
        self.typed = ""
        self.floor = 0

    def commit(self):
        """Everything typed so far is final: later updates only append or
        correct text beyond this point."""
        self.floor = len(self.typed)

    def update(self, new: str, soft: bool = False):
        """Make the field read `new` (or, in soft mode, the same words),
        touching only the words that changed; returns (backspaces, chars
        typed). The caret starts and ends at the end of the text: edits
        behind it go through AX when the app allows, else the arrow keys."""
        edits = plan(self.typed, new, self.floor, soft)
        end = len(self.typed)
        behind = [e for e in edits if e[1] < end]
        if behind:
            field = ax_edit(self.typed, behind)
            if field is not None:
                edits = [e for e in edits if e[1] == end]
                if field != apply(self.typed, behind):
                    # the app changed more than asked: resync, retype tail
                    self.typed = field
                    edits = plan(self.typed, new, self.floor, soft)
                else:
                    shift = sum(len(r) - (b - a) for a, b, r in behind)
                    self.typed = field
                    edits = [(a + shift, b + shift, r) for a, b, r in edits]
        caret = len(self.typed)
        n_del = n_typed = 0
        for a, b, r in reversed(edits):      # right to left: earlier
            move(b - caret)                  # offsets stay valid
            backspace(b - a)
            type_text(r)
            caret = a + len(r)
            n_del += b - a
            n_typed += len(r)
        self.typed = apply(self.typed, edits)
        move(len(self.typed) - caret)
        return n_del, n_typed
