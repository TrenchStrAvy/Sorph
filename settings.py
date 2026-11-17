"""Persistent user settings for Sorph.

Stored as JSON in ~/Library/Application Support/LocalFlow/settings.json so
choices survive restarts of the LaunchAgent. Reads and writes are
deliberately forgiving — a missing or corrupt file just means defaults.

Keys:
  language    current dictation language code (e.g. "de")
  languages   codes shown in the menu bar's Language submenu
  quick_keys  {"q": "de", ...} letters that switch language while the
              dictation hotkey is held
  position    where the sphere sits on screen: bottom-left (default),
              bottom-center, bottom-right, top-left, top-right
  duck_level  while dictating, playing audio is lowered to this percent
              of the current volume (0 = silent), set with a slider
  ducking     false turns music ducking off (the slider keeps its level)
  duck_restore  volume to put back after a duck that was never restored
  mic         name of the input device to record from; absent or null
              means the macOS system default input
  dictionary  personal dictionary entries: a word or name spelled the way
              it should be written ("Ollama"), or a fix for a mishearing
              ("terror form = Terraform")
  self_corrections  false keeps spoken corrections ("Tuesday, actually
              no, Wednesday") as they were said
  tone        false writes every app the same way (see tone.py)
  appearance.theme  look of Sorph's window: auto (default, follows
              macOS), light or dark
  presets     the dashboard's cards: [{"speak": "fr", "write": "ar"}, …];
              "write" null is plain dictation
  translate_to  language code to translate dictation into (see
              translate.py); absent or null means translate mode is off
  translate_last  the last language translated into, for switching
              translate mode back on
  voice_level {mic name: typical loudness of your voice}, learned from
              your dictations; background sound well below it is not
              taken for speech
"""

import json
import os
from pathlib import Path

import languages

DEFAULT_LANGUAGE = "en"
DEFAULT_LANGUAGES = ["en", "de", "fr"]
DEFAULT_QUICK_KEYS = {"q": "de", "w": "fr", "e": "en"}
QUICK_KEY_SLOTS = ["q", "w", "e", "r", "t"]   # assignable letters, left to right

# macOS virtual keycodes for the assignable letters
KEYCODES = {"q": 12, "w": 13, "e": 14, "r": 15, "t": 17}

SETTINGS_PATH = Path(
    os.environ.get("LOCALFLOW_SETTINGS")
    or Path.home() / "Library" / "Application Support" / "LocalFlow"
    / "settings.json"
)


def load() -> dict:
    try:
        with open(SETTINGS_PATH) as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save(**changes) -> dict:
    data = load()
    data.update(changes)
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_PATH.with_suffix(".json.tmp")
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, SETTINGS_PATH)
    return data


# ---------------------------------------------------------------- language

def get_language() -> str:
    lang = load().get("language", DEFAULT_LANGUAGE)
    return lang if lang in languages.CATALOG else DEFAULT_LANGUAGE


def set_language(code: str) -> str:
    if code not in languages.CATALOG:
        raise ValueError(f"unsupported language: {code}")
    enabled = get_languages()
    if code not in enabled:
        enabled.append(code)
        save(language=code, languages=enabled)
    else:
        save(language=code)
    return code


# ---------------------------------------------------------------- enabled list

def get_languages() -> list:
    """Codes shown in the Language menu, in menu order."""
    raw = load().get("languages", DEFAULT_LANGUAGES)
    if not isinstance(raw, list):
        raw = DEFAULT_LANGUAGES
    out = [c for c in raw if c in languages.CATALOG]
    return out or list(DEFAULT_LANGUAGES)


def add_language(code: str) -> list:
    if code not in languages.CATALOG:
        raise ValueError(f"unsupported language: {code}")
    enabled = get_languages()
    if code not in enabled:
        enabled.append(code)
        save(languages=enabled)
    return enabled


def remove_language(code: str) -> list:
    enabled = get_languages()
    if code in enabled and len(enabled) > 1:
        enabled.remove(code)
        changes = {"languages": enabled}
        if get_language() == code:
            changes["language"] = enabled[0]
        keys = {k: v for k, v in get_quick_keys().items() if v != code}
        if keys != get_quick_keys():
            changes["quick_keys"] = keys
        save(**changes)
    return enabled


# ---------------------------------------------------------------- quick keys

def get_quick_keys() -> dict:
    """{"q": "de", ...} — only valid slots and catalog codes survive."""
    raw = load().get("quick_keys", DEFAULT_QUICK_KEYS)
    if not isinstance(raw, dict):
        raw = DEFAULT_QUICK_KEYS
    return {k: v for k, v in raw.items()
            if k in QUICK_KEY_SLOTS and v in languages.CATALOG}


def set_quick_key(slot: str, code) -> dict:
    """Assign `code` to a letter, or clear it with code=None."""
    if slot not in QUICK_KEY_SLOTS:
        raise ValueError(f"unsupported quick key: {slot}")
    keys = get_quick_keys()
    if code is None:
        keys.pop(slot, None)
    else:
        if code not in languages.CATALOG:
            raise ValueError(f"unsupported language: {code}")
        keys = {k: v for k, v in keys.items() if v != code}  # one key per language
        keys[slot] = code
    save(quick_keys=keys)
    return keys


def quick_keys_by_keycode() -> dict:
    """{12: "de", ...} for the hotkey listener."""
    return {KEYCODES[k]: v for k, v in get_quick_keys().items()}


# ---------------------------------------------------------------- position

POSITIONS = ["bottom-left", "bottom-center", "bottom-right",
             "top-left", "top-right"]
CUSTOM = "custom"             # anywhere: dragged there, saved as position_xy
DEFAULT_POSITION = "bottom-left"


def get_position() -> str:
    data = load()
    pos = data.get("position", DEFAULT_POSITION)
    if pos == CUSTOM and get_position_xy() is not None:
        return CUSTOM
    return pos if pos in POSITIONS else DEFAULT_POSITION


def set_position(pos: str) -> str:
    if pos not in POSITIONS:
        raise ValueError(f"unsupported position: {pos}")
    save(position=pos)
    return pos


def get_position_xy():
    """(x, y) of the window's bottom-left corner in screen points when the
    sphere was dragged somewhere, else None."""
    xy = load().get("position_xy")
    if (isinstance(xy, list) and len(xy) == 2
            and all(isinstance(v, (int, float)) for v in xy)):
        return float(xy[0]), float(xy[1])
    return None


def set_position_xy(x: float, y: float) -> None:
    save(position=CUSTOM, position_xy=[round(float(x), 1),
                                       round(float(y), 1)])


# ---------------------------------------------------------------- music ducking

DEFAULT_DUCK_LEVEL = 20             # percent of the current volume


def get_duck_slider() -> int:
    """The slider's level 0-100, kept even while ducking is off."""
    level = load().get("duck_level", DEFAULT_DUCK_LEVEL)
    if isinstance(level, bool) or not isinstance(level, (int, float)):
        return DEFAULT_DUCK_LEVEL
    return int(min(100, max(0, level)))


def is_ducking() -> bool:
    data = load()
    if data.get("duck_level", 0) is None:     # older "off" setting
        return False
    return data.get("ducking", True) is not False


def get_duck_level():
    """Percent (0-100) to lower playing audio to while dictating, or None
    when ducking is off."""
    return get_duck_slider() if is_ducking() else None


def set_duck_level(level):
    """Percent 0-100 (turns ducking on), or None to turn it off."""
    if level is None:
        save(ducking=False)
        return None
    if isinstance(level, bool) or not isinstance(level, (int, float)) \
            or not 0 <= level <= 100:
        raise ValueError(f"unsupported duck level: {level}")
    save(duck_level=int(level), ducking=True)
    return int(level)


def set_ducking(on: bool) -> None:
    changes = {"ducking": bool(on)}
    if load().get("duck_level", 0) is None:
        changes["duck_level"] = DEFAULT_DUCK_LEVEL
    save(**changes)


def get_duck_restore():
    v = load().get("duck_restore")
    if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 < v <= 1:
        return float(v)
    return None


def set_duck_restore(volume: float) -> None:
    save(duck_restore=round(float(volume), 4))


def clear_duck_restore() -> None:
    if load().get("duck_restore") is not None:
        save(duck_restore=None)


# ---------------------------------------------------------------- microphone

def get_mic():
    """Name of the chosen input device, or None for the system default."""
    name = load().get("mic")
    return name if isinstance(name, str) and name else None


def set_mic(name) -> None:
    save(mic=name if isinstance(name, str) and name else None)


# ---------------------------------------------------------------- dictionary

MAX_DICTIONARY = 200


def get_dictionary() -> list:
    raw = load().get("dictionary", [])
    if not isinstance(raw, list):
        return []
    return [e.strip() for e in raw if isinstance(e, str) and e.strip()]


def add_dictionary(entry: str) -> list:
    entry = " ".join(str(entry).split())
    entries = get_dictionary()
    if entry and entry.lower() not in [e.lower() for e in entries] \
            and len(entries) < MAX_DICTIONARY:
        entries.append(entry)
        save(dictionary=entries)
    return entries


def remove_dictionary(entry: str) -> list:
    entries = [e for e in get_dictionary() if e != entry]
    save(dictionary=entries)
    return entries


# ---------------------------------------------------------------- cleanup options

def is_self_corrections() -> bool:
    return load().get("self_corrections", True) is not False


def set_self_corrections(on: bool) -> None:
    save(self_corrections=bool(on))


def is_tone() -> bool:
    return load().get("tone", True) is not False


def set_tone(on: bool) -> None:
    save(tone=bool(on))


# ---------------------------------------------------------------- window look

THEMES = ("auto", "light", "dark")


def get_theme() -> str:
    """Look of Sorph's window: auto (follows macOS), light or dark."""
    theme = load().get("appearance.theme")
    return theme if theme in THEMES else "auto"


def set_theme(theme: str) -> None:
    save(**{"appearance.theme": theme if theme in THEMES else "auto"})


# ---------------------------------------------------------------- presets

def default_presets() -> list:
    """Cards for a dashboard nobody has saved a preset in yet: plain
    dictation in the current language, and the first pairs among the
    languages in the menu."""
    enabled = get_languages()
    out = [{"speak": get_language(), "write": None}]
    out += [{"speak": a, "write": b}
            for a in enabled for b in enabled if a != b][:3]
    return out


def get_presets() -> list:
    """[{"speak": code, "write": code or None}]: the dashboard's cards."""
    raw = load().get("presets")
    if not isinstance(raw, list):
        # the starter cards are written down the first time they are
        # shown: they follow the language of that moment, and must not
        # change under the user when the language does
        presets = default_presets()
        save(presets=presets)
        return presets
    out = []
    for p in raw:
        if (isinstance(p, dict) and p.get("speak") in languages.CATALOG
                and (p.get("write") is None or isinstance(p.get("write"), str))):
            preset = {"speak": p["speak"], "write": p.get("write") or None}
            if preset not in out:
                out.append(preset)
    return out or default_presets()


def add_preset(speak: str, write=None) -> list:
    presets = get_presets()
    preset = {"speak": speak, "write": write or None}
    if speak in languages.CATALOG and preset not in presets:
        presets.append(preset)
        save(presets=presets)
    return presets


def remove_preset(index: int) -> list:
    presets = get_presets()
    if 0 <= index < len(presets) and len(presets) > 1:
        del presets[index]
        save(presets=presets)
    return presets


# ---------------------------------------------------------------- translate

def get_translate_to():
    """Language dictation is translated into, or None (translate off)."""
    code = load().get("translate_to")
    return code if isinstance(code, str) and code else None


def set_translate_to(code) -> None:
    if code:
        save(translate_to=code, translate_last=code)
    else:
        save(translate_to=None)


def get_last_target():
    """The language last translated into (kept while translate is off),
    so switching translate back on has somewhere to go. None: never."""
    code = load().get("translate_last")
    return code if isinstance(code, str) and code else None


# ---------------------------------------------------------------- voice level

def get_voice_level(mic=None):
    """Learned loudness (frame RMS) of the user's voice on `mic` (None:
    the system default input), or None before the first dictation."""
    levels = load().get("voice_level")
    v = levels.get(mic or "") if isinstance(levels, dict) else None
    if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 < v < 1:
        return float(v)
    return None


def set_voice_level(mic, level: float) -> None:
    levels = load().get("voice_level")
    levels = dict(levels) if isinstance(levels, dict) else {}
    levels[mic or ""] = round(float(level), 4)
    save(voice_level=levels)


# ---------------------------------------------------------------- models

def model_for_language(model_name: str, language: str) -> str:
    """Pick the whisper model that can actually decode `language`.

    The `.en` models are English-only; for any other language fall back to
    the multilingual sibling of the same size (small.en → small). When the
    user configured a multilingual model already, leave it alone.
    """
    if language != "en" and model_name.endswith(".en"):
        return model_name[: -len(".en")]
    return model_name
