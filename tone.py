"""Per-app tone: write the way the app in front is written in.

Sorph knows which app the dictation lands in, so the last cleanup step can
follow that app's habits:

* standard  documents, mail, browsers, everything unknown: full sentences,
            closed with a period.
* casual    chat apps (Messages, Slack, Discord, WhatsApp, …): a one-line
            message carries no final period.
* plain     terminals and code editors: nothing is added, and a single
            line gets no final period (it would end up in a command or a
            prompt).

Only the ending changes; words, capitals and inner punctuation stay as
dictated. Menu bar → "Per-app tone" turns it off (everything standard).
"""

import re

STANDARD, CASUAL, PLAIN = "standard", "casual", "plain"

_CASUAL_IDS = {
    "com.apple.MobileSMS", "com.tinyspeck.slackmacgap", "com.hnc.Discord",
    "net.whatsapp.WhatsApp", "ru.keepcoder.Telegram", "org.telegram.desktop",
    "org.whispersystems.signal-desktop", "com.facebook.archon",
    "com.microsoft.teams2", "com.microsoft.teams",
}
_CASUAL_NAMES = {"messages", "slack", "discord", "whatsapp", "telegram",
                 "signal", "messenger", "microsoft teams"}
_PLAIN_IDS = {
    "com.apple.Terminal", "com.googlecode.iterm2", "com.mitchellh.ghostty",
    "dev.warp.Warp-Stable", "net.kovidgoyal.kitty", "org.alacritty",
    "com.github.wez.wezterm", "co.zeit.hyper", "com.microsoft.VSCode",
    "com.todesktop.230313mzl4w4u92", "com.apple.dt.Xcode", "dev.zed.Zed",
    "com.sublimetext.4",
}
_PLAIN_PREFIXES = ("com.jetbrains.",)
_PLAIN_NAMES = {"terminal", "iterm2", "iterm", "ghostty", "warp", "kitty",
                "alacritty", "wezterm", "hyper", "cmux", "code", "cursor",
                "visual studio code", "xcode", "zed", "sublime text"}

_SENTENCE_BREAK = re.compile(r"[.!?…]\s")


def style_for(target) -> str:
    """Style for a focus.FocusTarget (None: standard)."""
    if target is None:
        return STANDARD
    bundle = getattr(target, "bundle_id", "") or ""
    name = (getattr(target, "app_name", "") or "").strip().lower()
    if bundle in _CASUAL_IDS or name in _CASUAL_NAMES:
        return CASUAL
    if (bundle in _PLAIN_IDS or bundle.startswith(_PLAIN_PREFIXES)
            or name in _PLAIN_NAMES):
        return PLAIN
    return STANDARD


def closes(style: str) -> bool:
    """Should cleanup end the text with a period when it has none?"""
    return style == STANDARD


def apply(text: str, style: str) -> str:
    """Last step after cleanup: a single line loses its final period in
    casual and plain apps. Several sentences, "?", "!" and "…" stay."""
    if style == STANDARD or not text:
        return text
    if (text.endswith(".") and not text.endswith("..")
            and not _SENTENCE_BREAK.search(text)):
        return text[:-1]
    return text
