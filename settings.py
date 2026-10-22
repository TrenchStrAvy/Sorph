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
