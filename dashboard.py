"""Sorph's dashboard: one fixed 830 × 420 window, drawn as a web page.

It opens when Sorph starts. While the models load it is the startup
screen (the orb revealed out of glass, a caption, a thin progress line);
then it becomes a gallery of preset cards, each a pair of languages
(speak → write). Turning the gallery to a card switches Sorph to that
pair; the two pickers under it choose any other pair, "Save preset" keeps
it as a card. The gear holds the settings, ◐ the look (auto, light, dark).
Closing the window only hides it: menu bar → Open Sorph, or a click on
Sorph in the Dock, brings it back.

The page is ui/index.html + ui/dist/dashboard.js (built once from ui/src
with `npm run build`; an install needs no Node). It runs in a WKWebView:
Python pushes the whole state as JSON (window.sorph.push), the page posts
small messages back ({type: "preset", index: 2}, …), handled in
Dashboard.handle.

Public methods are safe to call from any thread. As a startup screen it
answers to the same calls as splash.Splash: show, set_stage, finish.
"""

import base64
import json
import os
import re
import time

import objc
from AppKit import (
    NSAppearance,
    NSApplication,
    NSBackingStoreBuffered,
    NSColor,
    NSView,
    NSWindow,
)
from Foundation import (NSDistributedNotificationCenter, NSMakeRect, NSObject,
                        NSURL)
from PyObjCTools import AppHelper
from WebKit import WKUserContentController, WKWebView, WKWebViewConfiguration

import languages
import mics
import settings
import translate
import version as version_

W, H = 830, 420
SHOW_NOTIFICATION = "com.localflow.show-window"   # posted by the launcher
GRIP_H = 52                   # top strip of the page that drags the window
GRIP_CLEAR = 100              # its right end is left to the page's two buttons
REVEAL_SEC = 3.7              # the glass reveal, start to bare logo
ROOT = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(ROOT, "ui", "index.html")
LOGO = os.path.join(ROOT, "ui", "dist", "orb.png")
BACKGROUND = {False: (0.937, 0.937, 0.945), True: (0.043, 0.043, 0.059)}


def system_is_dark() -> bool:
    try:
        name = (NSApplication.sharedApplication().effectiveAppearance()
                .bestMatchFromAppearancesWithNames_(
                    ["NSAppearanceNameAqua", "NSAppearanceNameDarkAqua"]))
        return name == "NSAppearanceNameDarkAqua"
    except Exception:
        return False


def is_dark() -> bool:
    theme = settings.get_theme()
    return system_is_dark() if theme == "auto" else theme == "dark"


def version() -> str:
    """Sorph's version, as the dashboard shows it (see version.py)."""
    return version_.current(ROOT)


def _langs(codes):
    """Picker entries, in the order given (callers pass them by English
    name): the page shows and searches both names."""
    return [{"code": c, "name": translate.english_name(c),
             "native": translate.native_name(c)} for c in codes]


def preset_view(preset) -> dict:
    """A stored preset with the names its card shows."""
    speak, write = preset["speak"], preset.get("write") or ""
    return {
        "speak": speak, "write": write,
        "speakName": languages.english_name(speak),
        "writeName": translate.english_name(write) if write else "",
        "speakNative": languages.native_name(speak),
        "writeNative": translate.native_name(write) if write else "",
    }


def page_state(language: str, translate_to, llm: bool, status: str,
               moving: bool = False) -> dict:
    """Everything the ready page shows, read fresh from the settings."""
    enabled = settings.get_languages()
    if language not in enabled:
        enabled.append(language)
    possible = translate.targets(language, llm)
    target = translate_to if translate_to in possible else ""
    quick = [c for c in enabled if c in possible]
    try:
        names, default = mics.inputs()
    except Exception:
        names, default = [], None
    chosen = settings.get_mic() or ""
    if chosen and chosen not in names:
        names = names + [chosen]
    position = settings.get_position()
    positions = list(settings.POSITIONS)
    if position not in positions:
        positions.append(position)
    return {
        "dark": is_dark(), "theme": settings.get_theme(),
        "language": language, "translateTo": target,
        "speakQuick": _langs(enabled),
        "speakAll": _langs(languages.sorted_codes()),
        "writeQuick": _langs(quick),
        "writeAll": _langs(possible),
        "presets": [preset_view(p) for p in settings.get_presets()],
        "status": status,
        "settings": {
            "mics": names, "mic": chosen, "micDefault": default or "",
            "ducking": settings.is_ducking(),
            "duck": settings.get_duck_slider(),
            "corrections": settings.is_self_corrections(),
            "tone": settings.is_tone(),
            "position": position, "positions": positions,
            "moving": bool(moving),
            "dictionary": settings.get_dictionary(),
            "slots": list(settings.QUICK_KEY_SLOTS),
            "quickKeys": settings.get_quick_keys(),
        },
    }


class Grip(NSView):
    """An invisible strip over the top of the page: drag it to move the
    window. The web view under it takes every click for itself, so the
    window's own title bar never sees them."""

    def mouseDown_(self, event):
        self.window().performWindowDragWithEvent_(event)

    def acceptsFirstMouse_(self, event):
        return True                     # drag without activating first


class Dashboard(NSObject, protocols=[
        objc.protocolNamed("WKScriptMessageHandler")]):

    def init(self):
        self = objc.super(Dashboard, self).init()
        if self is None:
            return None
        self.cb = None                  # the app's callbacks, once it is up
        self.asked = 0                  # times the settings were asked for
        self.status = "ready"
        self.loading = {"phase": "loading", "caption": "starting…",
                        "progress": 0.05, "error": ""}
        self.shown_at = 0.0
        self._build()
        return self

    # -- building

    @objc.python_method
    def _build(self):
        mask = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 15)  # titled, closable,
        # miniaturizable, full-size content view: fixed size, not resizable
        self.window = (
            NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                NSMakeRect(0, 0, W, H), mask, NSBackingStoreBuffered, False))
        w = self.window
        w.setTitle_("Sorph")
        w.setTitlebarAppearsTransparent_(True)
        w.setTitleVisibility_(1)                    # hidden
        w.setReleasedWhenClosed_(False)
        w.setDelegate_(self)
        zoom = w.standardWindowButton_(2)           # the green button
        if zoom is not None:
            zoom.setHidden_(True)
        w.center()

        config = WKWebViewConfiguration.alloc().init()
        controller = WKUserContentController.alloc().init()
        controller.addScriptMessageHandler_name_(self, "sorph")
        config.setUserContentController_(controller)
        self.web = WKWebView.alloc().initWithFrame_configuration_(
            NSMakeRect(0, 0, W, H), config)
        self.web.setAutoresizingMask_(18)           # width + height
        try:
            self.web.setValue_forKey_(False, "drawsBackground")
        except Exception:
            pass                                    # a white flash at worst
        box = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, W, H))
        box.addSubview_(self.web)
        self.grip = Grip.alloc().initWithFrame_(
            NSMakeRect(0, H - GRIP_H, W - GRIP_CLEAR, GRIP_H))
        box.addSubview_(self.grip)      # above the page
        w.setContentView_(box)
        self._paint_window()
        self.web.loadFileURL_allowingReadAccessToURL_(
            NSURL.fileURLWithPath_(PAGE),
            NSURL.fileURLWithPath_(os.path.dirname(PAGE)))
        # a click on Sorph in the Dock (the launcher) opens the window
        NSDistributedNotificationCenter.defaultCenter(
            ).addObserver_selector_name_object_(
                self, b"showRequested:", SHOW_NOTIFICATION, None)

    @objc.python_method
    def _paint_window(self):
        dark = is_dark()
        r, g, b = BACKGROUND[dark]
        self.window.setBackgroundColor_(
            NSColor.colorWithSRGBRed_green_blue_alpha_(r, g, b, 1))
        self.window.setAppearance_(NSAppearance.appearanceNamed_(
            "NSAppearanceNameDarkAqua" if dark else "NSAppearanceNameAqua"))

    # -- state → page

    @objc.python_method
    def state(self, full: bool = False) -> dict:
        """What the page shows now. `full` adds what never changes (the
        logo, a quarter megabyte): sent once, when the page asks."""
        state = {"dark": is_dark(), "theme": settings.get_theme()}
        if full:
            state["logo"] = _logo_uri()
            state["version"] = version()
        state.update(self.loading)
        if self.cb is not None and self.loading["phase"] == "ready":
            state.update(page_state(self.cb["language"](),
                                    self.cb["translate_to"](),
                                    self.cb["llm"], self.status,
                                    self.cb.get("moving", bool)()))
        return state

    @objc.python_method
    def _push(self, full: bool = False):
        self._paint_window()
        self.web.evaluateJavaScript_completionHandler_(
            "window.sorph.push(%s)" % json.dumps(self.state(full)), None)

    # -- page → app (main thread)

    def userContentController_didReceiveScriptMessage_(self, controller,
                                                       message):
        body = dict(message.body())
        try:
            self.handle(body)
        except Exception as exc:        # a bad message must not take Sorph down
            print(f"warning: dashboard message failed: {exc}", flush=True)
        self._push(full=body.get("type") == "ready")

    @objc.python_method
    def handle(self, message: dict):
        kind = message.get("type")
        if kind == "theme":
            # two looks, one click each way: whatever shows now, the other.
            # ("auto" is where a new install starts; with macOS in dark
            # mode it looks the same as "dark", so a three-step round had
            # one click that seemed to do nothing.)
            settings.set_theme("light" if is_dark() else "dark")
            return
        if kind == "ready" or self.cb is None:
            return
        cb = self.cb
        speak = str(message.get("speak") or "")
        write = str(message.get("write") or "")
        if kind == "pair":              # a card, a field or a mode was chosen
            self._apply(speak, write)
        elif kind == "save":            # the pair becomes a card, in use
            if speak in languages.CATALOG and (
                    not write or write in translate.targets(speak, cb["llm"])):
                settings.add_preset(speak, write or None)
                self._apply(speak, write)
        elif kind == "remove":
            preset = {"speak": speak, "write": write or None}
            presets = settings.get_presets()
            if preset in presets:
                settings.remove_preset(presets.index(preset))
        elif kind == "quick":           # a quick key's language ("" = none)
            slot = str(message.get("slot") or "")
            if slot in settings.QUICK_KEY_SLOTS:
                settings.set_quick_key(slot, speak or None)
                cb["on_changed"]()
        elif kind == "unlang":          # a language leaves the user's list
            was = cb["language"]()
            settings.remove_language(speak)
            if was == speak and settings.get_language() != was:
                cb["on_language"](settings.get_language())
            cb["on_changed"]()
        elif kind == "move":            # drag the sphere anywhere, or stop
            if cb.get("on_move"):
                cb["on_move"]()
        elif kind == "word":
            settings.add_dictionary(str(message.get("entry") or ""))
            cb["on_changed"]()
        elif kind == "unword":
            settings.remove_dictionary(str(message.get("entry") or ""))
            cb["on_changed"]()
        elif kind == "set":
            self._set(str(message.get("key")), message.get("value"))
            cb["on_changed"]()

    @objc.python_method
    def _apply(self, speak: str, write: str):
        """Switch Sorph to speak → write ("" = plain dictation)."""
        cb = self.cb
        if speak in languages.CATALOG and speak != cb["language"]():
            cb["on_language"](speak)
        target = write if translate.known(write) else None
        if target != cb["translate_to"]():
            cb["on_translate"](target)

    @objc.python_method
    def _set(self, key: str, value):
        if key == "mic":
            settings.set_mic(str(value) or None)
        elif key == "ducking":
            settings.set_ducking(bool(value))
        elif key == "duck":
            settings.set_duck_level(int(value))
        elif key == "corrections":
            settings.set_self_corrections(bool(value))
        elif key == "tone":
            settings.set_tone(bool(value))
        elif key == "position" and value in settings.POSITIONS:
            settings.set_position(value)
            self.cb["on_position"](value)

    def windowDidBecomeKey_(self, notification):
        self._push()        # settings may have changed in the menu bar, and
                            # macOS may have switched between light and dark

    def showRequested_(self, notification):
        self._open()

    # -- called from the app (any thread)

    @objc.python_method
    def bind(self, callbacks):
        """callbacks: language(), translate_to(), llm (bool), and
        on_language(code), on_translate(code or None), on_position(pos),
        on_changed() (the menu bar should re-read the settings);
        optionally moving() and on_move() (the sphere's drag-anywhere
        mode: is it on, and switch it)."""
        self.cb = callbacks

    def show(self):
        """At startup: in front, without taking the keyboard from the app
        the user is in."""
        AppHelper.callAfter(self._show_quietly)

    @objc.python_method
    def _show_quietly(self):
        self.shown_at = time.time()
        self.window.orderFrontRegardless()

    def open(self):
        """Asked for by the user: in front and active."""
        AppHelper.callAfter(self._open)

    @objc.python_method
    def _open(self):
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self.window.makeKeyAndOrderFront_(None)
        self._push()

    def open_settings(self):
        """In front, with the settings showing."""
        AppHelper.callAfter(self._open_settings)

    @objc.python_method
    def _open_settings(self):
        self._open()
        self.asked += 1                 # a new number each time: the page
        self.web.evaluateJavaScript_completionHandler_(   # opens on change
            "window.sorph.push({openSettings: %d})" % self.asked, None)

    @objc.python_method
    def set_stage(self, caption, frac):
        """Startup progress: a short caption and 0..1."""
        AppHelper.callAfter(self._stage, caption, frac)

    @objc.python_method
    def _stage(self, caption, frac):
        self.loading.update(caption=caption + "…", progress=float(frac))
        self._push()

    @objc.python_method
    def finish(self, message=None):
        """Loading is over: the gallery (once the reveal has played out),
        or `message` when Sorph could not start."""
        AppHelper.callAfter(self._finish, message)

    @objc.python_method
    def _finish(self, message):
        if message:
            self.loading.update(error=message)
            self._push()
            return
        self.loading.update(caption="ready", progress=1.0)
        self._push()
        wait = max(0.4, REVEAL_SEC - (time.time() - self.shown_at))
        AppHelper.callLater(wait, self._ready)

    @objc.python_method
    def _ready(self):
        self.loading["phase"] = "ready"
        self._push()

    def refresh(self):
        AppHelper.callAfter(self._push)

    @objc.python_method
    def set_state(self, status):
        """Short lowercase status: listening…, translating…, ready."""
        AppHelper.callAfter(self._status, status)

    @objc.python_method
    def _status(self, status):
        self.status = status
        if self.window.isVisible():
            self._push()


_logo = None


def _logo_uri() -> str:
    """The orb as a data URL: the page reads its pixels, which a web view
    refuses for an image loaded from a file."""
    global _logo
    if _logo is None:
        try:
            with open(LOGO, "rb") as fh:
                _logo = ("data:image/png;base64,"
                         + base64.b64encode(fh.read()).decode())
        except OSError:
            _logo = ""
    return _logo


def create_dashboard():
    """Main thread only. Raises when the page was never built."""
    if not os.path.exists(os.path.join(ROOT, "ui", "dist", "dashboard.js")):
        raise RuntimeError("ui/dist/dashboard.js is missing")
    return Dashboard.alloc().init()
