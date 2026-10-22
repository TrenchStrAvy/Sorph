"""Menu-bar presence for flow.py — a mic icon with a status menu.

Gives the app a home when it runs headless (LaunchAgent, no terminal):
you can see it's alive, pick the dictation language, add or remove
languages, assign quick keys, and quit. Must be created on the main
thread, before AppHelper.runEventLoop().

Menu layout:
    Sorph — hold Right-Option to dictate
    model small.en · cleanup gemma3:4b
    ─────
    Microphone: DJI MIC MINI ▸   (system default or a named input,
                                  listed fresh each time it opens)
    Language: Deutsch ▸   (enabled languages, checkmark on current)
    Quick keys ▸          (Q/W/E/R/T → language, while hotkey is held)
    Add language ▸        (full Whisper catalog, grouped A–Z)
    Remove language ▸
    ─────
    Sphere position ▸
    Music ducking: 20% ▸  (on/off, and a slider for how far it goes down)
    ─────
    Quit Sorph
"""

import os
import subprocess

import objc
from AppKit import (
    NSControlStateValueOff,
    NSControlStateValueOn,
    NSColor,
    NSFont,
    NSImage,
    NSMenu,
    NSMenuItem,
    NSSlider,
    NSStatusBar,
    NSTextField,
    NSVariableStatusItemLength,
    NSView,
)
from Foundation import NSObject
from PyObjCTools import AppHelper

import languages
import mics
import settings

GROUPS = ("A–D", "E–H", "I–M", "N–R", "S–Z")


def _group_for(name: str) -> str:
    c = name[:1].upper()
    for g in GROUPS:
        lo, hi = g.split("–")
        if lo <= c <= hi:
            return g
    return GROUPS[-1]


def _menubar_icon():
    """The Sorph sphere in full colour (assets/menubar-color@2x.png), with
    the system mic symbol as a fallback. Returns (image, is_template)."""
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "assets", "menubar-color@2x.png")
    icon = NSImage.alloc().initWithContentsOfFile_(path)
    if icon is not None:
        icon.setSize_((18, 18))
        return icon, False
    return (NSImage.imageWithSystemSymbolName_accessibilityDescription_(
        "mic.fill", "Sorph"), True)


def _duck_label(level, short=False):
    if level is None:
        return "Off"
    if level == 0:
        return "Silent" if short else "Lower to silence"
    return f"{level}%" if short else f"Lower to {level}% of the volume"


def _item(title, action=None, target=None, represented=None, enabled=True):
    entry = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        title, action, "")
    if target is not None:
        entry.setTarget_(target)
    if represented is not None:
        entry.setRepresentedObject_(represented)
    entry.setEnabled_(enabled)
    return entry


class MenuBar(NSObject):

    def initWithStatusText_language_onLanguage_onPosition_onMove_(
            self, status_text, language, on_language, on_position, on_move):
        self = objc.super(MenuBar, self).init()
        if self is None:
            return None
        self.on_language = on_language
        self.on_position = on_position
        self.on_move = on_move
        self.moving = False
        self.language = language

        # keep a reference on self — a GC'd status item vanishes from the bar
        self.item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength)
        icon, template = _menubar_icon()
        if icon is not None:
            icon.setTemplate_(template)   # colour sphere; mic is a template
            self.item.button().setImage_(icon)
        else:
            self.item.button().setTitle_("◎")

        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)
        menu.addItem_(_item("Sorph — hold Right-Option to dictate",
                            enabled=False))
        self.status = _item(status_text, enabled=False)
        menu.addItem_(self.status)
        menu.addItem_(NSMenuItem.separatorItem())

        self.mic_item = _item("Microphone")
        mic_menu = NSMenu.alloc().initWithTitle_("Microphone")
        mic_menu.setAutoenablesItems_(False)
        mic_menu.setDelegate_(self)       # menuNeedsUpdate_: list on open
        self.mic_item.setSubmenu_(mic_menu)
        menu.addItem_(self.mic_item)

        self.language_item = _item("Language")
        self.language_item.setSubmenu_(NSMenu.alloc().initWithTitle_("Language"))
        menu.addItem_(self.language_item)

        self.quick_item = _item("Quick keys")
        self.quick_item.setSubmenu_(NSMenu.alloc().initWithTitle_("Quick keys"))
        menu.addItem_(self.quick_item)

        self.add_item = _item("Add language")
        self.add_item.setSubmenu_(self._build_catalog_menu())
        menu.addItem_(self.add_item)

        self.remove_item = _item("Remove language")
        self.remove_item.setSubmenu_(NSMenu.alloc().initWithTitle_("Remove"))
        menu.addItem_(self.remove_item)

        menu.addItem_(NSMenuItem.separatorItem())
        self.position_item = _item("Sphere position")
        self.position_item.setSubmenu_(
            NSMenu.alloc().initWithTitle_("Sphere position"))
        menu.addItem_(self.position_item)

        self.duck_item = _item("Music ducking")
        self.duck_item.setSubmenu_(self._build_duck_menu())
        menu.addItem_(self.duck_item)

        menu.addItem_(NSMenuItem.separatorItem())
        menu.addItem_(NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit Sorph", b"terminate:", "q"))
        self.item.setMenu_(menu)
        self._rebuild()
        return self

    # -- building

    @objc.python_method
    def _build_catalog_menu(self):
        """Add language ▸ A–D ▸ Afrikaans (Afrikaans) …"""
        root = NSMenu.alloc().initWithTitle_("Add language")
        root.setAutoenablesItems_(False)
        groups = {}
        for code in languages.sorted_codes():
            g = _group_for(languages.english_name(code))
            if g not in groups:
                sub = NSMenu.alloc().initWithTitle_(g)
                sub.setAutoenablesItems_(False)
                holder = _item(g)
                holder.setSubmenu_(sub)
                root.addItem_(holder)
                groups[g] = sub
            groups[g].addItem_(_item(
                f"{languages.english_name(code)} — {languages.native_name(code)}",
                b"addLanguage:", self, code))
        return root

    @objc.python_method
    def _build_duck_menu(self):
        """On/off, then a 0–100 % slider. Built once and only updated in
        place: rebuilding would pull the slider out from under the mouse."""
        sub = NSMenu.alloc().initWithTitle_("Music ducking")
        sub.setAutoenablesItems_(False)
        self.duck_toggle = _item("Lower playing audio while dictating",
                                 b"toggleDucking:", self)
        sub.addItem_(self.duck_toggle)

        view = NSView.alloc().initWithFrame_(((0, 0), (270, 48)))
        self.duck_text = NSTextField.labelWithString_("")
        self.duck_text.setFont_(NSFont.menuFontOfSize_(13))
        self.duck_text.setFrame_(((21, 26), (235, 17)))
        view.addSubview_(self.duck_text)
        self.duck_slider = NSSlider.sliderWithValue_minValue_maxValue_target_action_(
            settings.get_duck_slider(), 0, 100, self, b"duckSliderMoved:")
        self.duck_slider.setContinuous_(True)
        self.duck_slider.setNumberOfTickMarks_(5)      # 0 25 50 75 100
        self.duck_slider.setFrame_(((19, 4), (237, 21)))
        view.addSubview_(self.duck_slider)
        holder = NSMenuItem.alloc().init()
        holder.setView_(view)
        sub.addItem_(holder)
        return sub

    @objc.python_method
    def _refresh_duck(self):
        on = settings.is_ducking()
        level = settings.get_duck_slider()
        self.duck_toggle.setState_(NSControlStateValueOn if on
                                   else NSControlStateValueOff)
        self.duck_slider.setIntegerValue_(level)
        self.duck_slider.setEnabled_(on)
        self.duck_text.setStringValue_(_duck_label(level))
        self.duck_text.setTextColor_(NSColor.labelColor() if on
                                     else NSColor.disabledControlTextColor())
        self.duck_item.setTitle_(
            f"Music ducking: {_duck_label(level if on else None, True)}")

    @objc.python_method
    def _refresh_mic_title(self):
        self.mic_item.setTitle_(
            f"Microphone: {settings.get_mic() or 'System default'}")

    def menuNeedsUpdate_(self, menu):
        """Fill the Microphone submenu as it opens, so a mic plugged in a
        moment ago is there and the default's name is current."""
        if menu != self.mic_item.submenu():
            return
        menu.removeAllItems()
        try:
            names, default = mics.inputs()
        except Exception as exc:
            print(f"warning: could not list microphones: {exc}", flush=True)
            names, default = [], None
        chosen = settings.get_mic()
        title = "System default" + (f" ({default})" if default else "")
        entry = _item(title, b"chooseMic:", self, "")
        entry.setState_(NSControlStateValueOn if chosen is None
                        else NSControlStateValueOff)
        menu.addItem_(entry)
        menu.addItem_(NSMenuItem.separatorItem())
        for name in names:
            entry = _item(name, b"chooseMic:", self, name)
            entry.setState_(NSControlStateValueOn if name == chosen
                            else NSControlStateValueOff)
            menu.addItem_(entry)
        if chosen and chosen not in names:
            entry = _item(f"{chosen} (not connected)", enabled=False)
            entry.setState_(NSControlStateValueOn)
            menu.addItem_(entry)

    @objc.python_method
    def _rebuild(self):
        """Refresh the Language, Quick keys and Remove submenus from settings."""
        enabled = settings.get_languages()
        keys = settings.get_quick_keys()
        key_for = {code: slot for slot, code in keys.items()}

        lang_menu = self.language_item.submenu()
        lang_menu.removeAllItems()
        lang_menu.setAutoenablesItems_(False)
        for code in enabled:
            title = languages.label(code)
            if code in key_for:
                title += f"    ⌥{key_for[code].upper()}"
            entry = _item(title, b"chooseLanguage:", self, code)
            entry.setState_(NSControlStateValueOn if code == self.language
                            else NSControlStateValueOff)
            lang_menu.addItem_(entry)
        self.language_item.setTitle_(
            f"Language: {languages.native_name(self.language)}")

        quick_menu = self.quick_item.submenu()
        quick_menu.removeAllItems()
        quick_menu.setAutoenablesItems_(False)
        quick_menu.addItem_(_item("While holding Right-Option, tap a key to "
                                  "switch language:", enabled=False))
        for slot in settings.QUICK_KEY_SLOTS:
            current = keys.get(slot)
            label = (f"{slot.upper()}  →  {languages.native_name(current)}"
                     if current else f"{slot.upper()}  →  (none)")
            holder = _item(label)
            sub = NSMenu.alloc().initWithTitle_(slot)
            sub.setAutoenablesItems_(False)
            for code in enabled:
                entry = _item(languages.label(code), b"assignQuickKey:", self,
                              {"slot": slot, "code": code})
                entry.setState_(NSControlStateValueOn if code == current
                                else NSControlStateValueOff)
                sub.addItem_(entry)
            sub.addItem_(NSMenuItem.separatorItem())
            sub.addItem_(_item("None", b"assignQuickKey:", self,
                               {"slot": slot, "code": None}))
            holder.setSubmenu_(sub)
            quick_menu.addItem_(holder)

        remove_menu = self.remove_item.submenu()
        remove_menu.removeAllItems()
        remove_menu.setAutoenablesItems_(False)
        for code in enabled:
            remove_menu.addItem_(_item(languages.label(code),
                                       b"removeLanguage:", self, code,
                                       enabled=len(enabled) > 1))

        pos_menu = self.position_item.submenu()
        pos_menu.removeAllItems()
        pos_menu.setAutoenablesItems_(False)
        current = settings.get_position()
        pos_menu.addItem_(_item("Done moving" if self.moving
                                else "Move freely…", b"toggleMove:", self))
        pos_menu.addItem_(NSMenuItem.separatorItem())
        for pos in settings.POSITIONS:
            entry = _item(pos.replace("-", " ").capitalize(),
                          b"choosePosition:", self, pos)
            entry.setState_(NSControlStateValueOn if pos == current
                            else NSControlStateValueOff)
            pos_menu.addItem_(entry)
        if current == settings.CUSTOM:
            xy = settings.get_position_xy()
            entry = _item(f"Custom ({xy[0]:.0f}, {xy[1]:.0f})", enabled=False)
            entry.setState_(NSControlStateValueOn)
            pos_menu.addItem_(entry)

        self._refresh_mic_title()
        self._refresh_duck()

    # -- actions (main thread)

    def chooseLanguage_(self, sender):
        code = sender.representedObject()
        self._apply_language(code)
        if self.on_language:
            self.on_language(code)

    def addLanguage_(self, sender):
        code = sender.representedObject()
        settings.add_language(code)
        self._rebuild()

    def removeLanguage_(self, sender):
        code = sender.representedObject()
        settings.remove_language(code)
        if self.language == code:
            new = settings.get_language()
            self._apply_language(new)
            if self.on_language:
                self.on_language(new)
        self._rebuild()

    def choosePosition_(self, sender):
        pos = sender.representedObject()
        if self.moving:
            self.moving = False
            if self.on_move:
                self.on_move(False)
        settings.set_position(pos)
        self._rebuild()
        if self.on_position:
            self.on_position(pos)

    def chooseMic_(self, sender):
        # takes effect on the next recording: the mic opens per dictation
        settings.set_mic(sender.representedObject() or None)
        self._refresh_mic_title()

    def toggleDucking_(self, sender):
        settings.set_ducking(not settings.is_ducking())
        self._refresh_duck()

    def duckSliderMoved_(self, sender):
        level = int(round(sender.doubleValue()))
        if level != settings.get_duck_slider():
            settings.set_duck_level(level)
        self.duck_text.setStringValue_(_duck_label(level))
        self.duck_item.setTitle_(f"Music ducking: {_duck_label(level, True)}")

    def toggleMove_(self, sender):
        self.moving = not self.moving
        if self.on_move:
            self.on_move(self.moving)
        self._rebuild()

    def finish_move(self):
        """End move mode (Enter key); safe from any thread."""
        AppHelper.callAfter(self._finish_move)

    @objc.python_method
    def _finish_move(self):
        if not self.moving:
            return
        self.moving = False
        if self.on_move:
            self.on_move(False)
        self._rebuild()

    def assignQuickKey_(self, sender):
        info = sender.representedObject()
        settings.set_quick_key(info["slot"], info["code"])
        self._rebuild()

    # -- called from the app (any thread)

    def set_language(self, code):
        """Reflect a language change in the menu; safe from any thread."""
        AppHelper.callAfter(self._apply_language, code)

    @objc.python_method
    def _apply_language(self, code):
        self.language = code
        self._rebuild()

    def set_status(self, text):
        """Update the second line of the menu; safe from any thread."""
        AppHelper.callAfter(self.status.setTitle_, text)


DOCK_APP = "/Applications/Sorph.app"


def show_in_dock():
    """Open the Sorph launcher quietly; while Sorph runs it stays in the Dock as the
    running dot (see launcher/LocalFlowLauncher.swift, DockCompanion)."""
    if os.path.isdir(DOCK_APP):
        subprocess.Popen(["/usr/bin/open", "-g", DOCK_APP],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def create_menubar(status_text, language="en", on_language=None,
                   on_position=None, on_move=None):
    bar = (MenuBar.alloc()
           .initWithStatusText_language_onLanguage_onPosition_onMove_(
               status_text, language, on_language, on_position, on_move))
    show_in_dock()
    return bar
