from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from AppKit import NSApplication

NSApplication.sharedApplication()


class DashboardTests(unittest.TestCase):
    """The dashboard, built but never shown: its state and its messages."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["LOCALFLOW_SETTINGS"] = str(
            Path(self.tmp.name) / "settings.json")
        import settings
        self.settings = importlib.reload(settings)
        import dashboard
        self.dashboard = dashboard
        dashboard.settings = self.settings
        p = mock.patch.object(dashboard.mics, "inputs",
                              return_value=(["Desk Mic"], "Built-in"))
        p.start()
        self.addCleanup(p.stop)
        self.state = {"language": "fr", "to": "ar"}
        self.calls = []
        self.dash = dashboard.create_dashboard()
        self.dash.bind(dict(
            language=lambda: self.state["language"],
            translate_to=lambda: self.state["to"], llm=True,
            on_language=lambda c: (self.state.update(language=c),
                                   self.calls.append(("language", c))),
            on_translate=lambda c: (self.state.update(to=c),
                                    self.calls.append(("translate", c))),
            on_position=lambda p: self.calls.append(("position", p)),
            on_changed=lambda: self.calls.append(("changed",))))

    def tearDown(self) -> None:
        self.dash.window.close()
        os.environ.pop("LOCALFLOW_SETTINGS", None)
        self.tmp.cleanup()
        import settings
        self.dashboard.settings = importlib.reload(settings)

    def test_fixed_size(self) -> None:
        size = self.dash.window.contentView().frame().size
        self.assertEqual((size.width, size.height), (830, 420))
        self.assertFalse(self.dash.window.styleMask() & (1 << 3))  # resizable

    def test_loading_then_ready(self) -> None:
        d = self.dash
        self.assertEqual(d.state()["phase"], "loading")
        self.assertNotIn("presets", d.state())
        self.assertTrue(d.state(full=True)["logo"].startswith("data:image/png"))
        self.assertRegex(d.state(full=True)["version"],
                         r"^v\d+\.\d+\.\d+( · dev)?$")
        with mock.patch.object(self.dashboard, "ROOT", "/nonexistent"):
            self.assertEqual(self.dashboard.version(), "")

        d._stage("loading speech model", 0.3)
        self.assertEqual(d.state()["caption"], "loading speech model…")
        d._ready()
        state = d.state()
        self.assertEqual(state["phase"], "ready")
        self.assertEqual((state["language"], state["translateTo"]),
                         ("fr", "ar"))
        self.assertEqual(state["settings"]["micDefault"], "Built-in")
        self.assertNotIn("logo", state)

    def test_version_follows_the_changelog(self) -> None:
        import version
        log = Path(self.tmp.name) / "CHANGELOG.md"
        log.write_text("# Changelog\n\n## v0.9.0 — today\n\n## v0.8.0\n")
        self.assertEqual(version.current(self.tmp.name), "v0.9.0")
        log.write_text("# Changelog\n\n## Unreleased\n\n## v0.9.0\n")
        self.assertEqual(version.current(self.tmp.name), "v0.9.0 · dev")
        log.write_text("# Changelog\n")
        self.assertEqual(version.current(self.tmp.name), "")

    def test_default_presets_then_saved_ones(self) -> None:
        s, d = self.settings, self.dash
        self.assertEqual(s.get_presets()[0], {"speak": "en", "write": None})
        self.assertEqual(len(s.get_presets()), 4)
        d.handle({"type": "save", "speak": "fr", "write": "ja"})
        self.assertIn({"speak": "fr", "write": "ja"}, s.get_presets())
        self.assertEqual(self.calls, [("translate", "ja")])     # and in use
        d.handle({"type": "save", "speak": "fr", "write": "ja"})  # no twin
        d.handle({"type": "save", "speak": "xx", "write": ""})    # no such
        self.assertEqual(len(s.get_presets()), 5)
        view = self.dashboard.preset_view(s.get_presets()[-1])
        self.assertEqual((view["speakName"], view["writeName"],
                          view["writeNative"]),
                         ("French", "Japanese", "日本語"))
        d.handle({"type": "remove", "speak": "fr", "write": "ja"})
        d.handle({"type": "remove", "speak": "fr", "write": "ja"})  # gone
        self.assertEqual(len(s.get_presets()), 4)

    def test_starter_cards_stay_put_when_the_language_changes(self) -> None:
        s = self.settings
        before = s.get_presets()
        s.set_language("fr")
        self.assertEqual(s.get_presets(), before)
        self.assertEqual(s.load()["presets"], before)

    def test_write_field_lists_what_the_spoken_language_reaches(self) -> None:
        d = self.dash
        d._ready()
        d.cb["llm"] = False                     # M2M100: te only reaches en
        self.assertIn("ja", [l["code"] for l in d.state()["writeAll"]])
        d.handle({"type": "pair", "speak": "te", "write": "en"})
        self.assertEqual(self.calls, [("language", "te"),
                                      ("translate", "en")])
        self.assertEqual([l["code"] for l in d.state()["writeAll"]], ["en"])

    def test_pickers_list_languages_by_english_name(self) -> None:
        d = self.dash
        d._ready()
        names = [l["name"] for l in d.state()["speakAll"]]
        self.assertEqual(names, sorted(names, key=str.lower))
        self.assertEqual(d.state()["speakAll"][0],
                         {"code": "af", "name": "Afrikaans",
                          "native": "Afrikaans"})
        names = [l["name"] for l in d.state()["writeAll"]]
        self.assertEqual(names, sorted(names, key=str.lower))

    def test_the_last_preset_cannot_be_removed(self) -> None:
        s = self.settings
        for _ in range(6):
            s.remove_preset(0)
        self.assertEqual(len(s.get_presets()), 1)

    def test_choosing_a_pair_switches_sorph(self) -> None:
        d = self.dash
        d.handle({"type": "pair", "speak": "en", "write": "de"})
        self.assertEqual(self.calls, [("language", "en"),
                                      ("translate", "de")])
        self.calls.clear()
        d.handle({"type": "pair", "speak": "en", "write": ""})  # dictation
        self.assertEqual(self.calls, [("translate", None)])
        self.calls.clear()
        d.handle({"type": "pair", "speak": "xx", "write": "zz"})
        self.assertEqual(self.calls, [])

    def test_pickers(self) -> None:
        d = self.dash
        d.handle({"type": "pair", "speak": "fr", "write": "ja"})
        self.assertEqual(self.calls, [("translate", "ja")])
        d.handle({"type": "pair", "speak": "de", "write": ""})
        self.assertEqual(self.calls[1:], [("language", "de"),
                                          ("translate", None)])

    def test_settings_messages(self) -> None:
        d, s = self.dash, self.settings
        for key, value in (("tone", False), ("corrections", False),
                           ("duck", 35), ("ducking", False),
                           ("mic", "Desk Mic"), ("position", "top-right")):
            d.handle({"type": "set", "key": key, "value": value})
        self.assertFalse(s.is_tone())
        self.assertFalse(s.is_self_corrections())
        self.assertFalse(s.is_ducking())
        self.assertEqual(s.get_duck_slider(), 35)
        self.assertEqual(s.get_mic(), "Desk Mic")
        self.assertEqual(s.get_position(), "top-right")
        self.assertIn(("position", "top-right"), self.calls)
        d.handle({"type": "word", "entry": "Ollama"})
        self.assertEqual(s.get_dictionary(), ["Ollama"])
        d.handle({"type": "unword", "entry": "Ollama"})
        self.assertEqual(s.get_dictionary(), [])

    def test_look_is_two_steps_and_works_before_the_app_is_up(self) -> None:
        d, s = self.dash, self.settings
        d.cb = None
        self.assertEqual(s.get_theme(), "auto")
        for system_dark in (True, False):
            s.set_theme("auto")
            with mock.patch.object(self.dashboard, "system_is_dark",
                                   return_value=system_dark):
                looks = []
                for _ in range(4):
                    d.handle({"type": "theme"})
                    looks.append(d.state()["dark"])
            # every click changes the look, whatever macOS is set to
            self.assertEqual(looks, [not system_dark, system_dark] * 2)
        d.handle({"type": "pair", "speak": "en", "write": ""})  # no app yet
        self.assertEqual(self.calls, [])

    def test_quick_keys_and_the_users_languages(self) -> None:
        d, s = self.dash, self.settings
        d._ready()
        state = d.state()["settings"]
        self.assertEqual(state["slots"], ["q", "w", "e", "r", "t"])
        self.assertEqual(state["quickKeys"], {"q": "de", "w": "fr", "e": "en"})
        d.handle({"type": "quick", "slot": "r", "speak": "fr"})
        d.handle({"type": "quick", "slot": "q", "speak": ""})
        d.handle({"type": "quick", "slot": "x", "speak": "fr"})    # no such key
        # one key per language: French moved from W to R
        self.assertEqual(s.get_quick_keys(), {"e": "en", "r": "fr"})
        self.calls.clear()
        d.handle({"type": "unlang", "speak": "de"})
        self.assertNotIn("de", s.get_languages())
        self.assertEqual(self.calls, [("changed",)])
        self.settings.set_language("en")
        self.state["language"] = "en"
        self.calls.clear()
        d.handle({"type": "unlang", "speak": "en"})     # the one in use
        self.assertEqual(self.calls[0][0], "language")

    def test_sphere_move_mode(self) -> None:
        d = self.dash
        d._ready()
        self.assertFalse(d.state()["settings"]["moving"])
        moved = []
        d.cb.update(moving=lambda: True, on_move=lambda: moved.append(1))
        d.handle({"type": "move"})
        self.assertEqual(moved, [1])
        self.assertTrue(d.state()["settings"]["moving"])


if __name__ == "__main__":
    unittest.main()
