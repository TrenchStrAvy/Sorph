from __future__ import annotations

import importlib
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import flow
import focus
import languages
import translate


class RouteTests(unittest.TestCase):
    def test_off_or_same_language(self) -> None:
        self.assertIsNone(translate.route("fr", None))
        self.assertIsNone(translate.route("fr", ""))
        self.assertIsNone(translate.route("fr", "fr"))
        self.assertIsNone(translate.route("fr", "xx"))

    def test_any_pair_m2m_knows(self) -> None:
        self.assertEqual(translate.route("fr", "ar"), "m2m")
        self.assertEqual(translate.route("en", "ja"), "m2m")
        self.assertEqual(translate.route("jw", "en"), "m2m")   # jw is jv
        self.assertEqual(translate.route("en", "zu"), "m2m")   # target only

    def test_whisper_covers_the_rest_into_english(self) -> None:
        self.assertEqual(translate.route("te", "en"), "whisper")
        self.assertIsNone(translate.route("te", "fr"))
        self.assertIsNone(translate.route("fr", "te"))

    def test_an_llm_takes_every_pair(self) -> None:
        self.assertEqual(translate.route("fr", "ar", llm=True), "llm")
        self.assertEqual(translate.route("te", "fr", llm=True), "llm")
        self.assertEqual(translate.route("te", "en", llm=True), "llm")
        self.assertIsNone(translate.route("fr", "fr", llm=True))

    def test_targets(self) -> None:
        fr = translate.targets("fr")
        self.assertNotIn("fr", fr)
        self.assertIn("ar", fr)
        self.assertIn("zu", fr)
        self.assertNotIn("te", fr)
        self.assertEqual(translate.targets("te"), ["en"])
        self.assertIn("te", translate.targets("fr", llm=True))
        self.assertEqual(len(translate.targets("fr", llm=True)), 114)

    def test_every_spoken_language_reaches_english(self) -> None:
        for code in languages.CATALOG:
            if code != "en":
                self.assertIsNotNone(translate.route(code, "en"), code)

    def test_coverage_counts(self) -> None:
        both = [c for c in languages.CATALOG if translate._m2m(c)]
        self.assertEqual(len(both), 84)
        self.assertEqual(len(translate.EXTRA_TARGETS), 16)
        for code in translate.EXTRA_TARGETS:
            self.assertIn(code, translate.M2M_CODES)
            self.assertNotIn(code, languages.CATALOG)


class TextTests(unittest.TestCase):
    def test_sentences(self) -> None:
        self.assertEqual(
            translate.sentences("Ça va ? Oui. Version 3.5 marche… Bien"),
            ["Ça va ?", "Oui.", "Version 3.5 marche…", "Bien"])
        self.assertEqual(translate.sentences("你好。今天好吗？好"),
                         ["你好。", "今天好吗？", "好"])
        self.assertEqual(translate.sentences("  "), [])

    def test_join(self) -> None:
        self.assertEqual(translate.join("a", "b", "fr"), "a b")
        self.assertEqual(translate.join("今日。", "明日。", "ja"), "今日。明日。")
        self.assertEqual(translate.join("", "b", "fr"), "b")

    def test_labels_cover_target_only_languages(self) -> None:
        self.assertEqual(translate.label("ar"), languages.label("ar"))
        self.assertEqual(translate.label("ga"), "Gaeilge (Irish)")


class FakeSP:
    def encode(self, text, out_type=str):
        return text.split()

    def decode(self, pieces):
        return " ".join(pieces)


class FakeM2M:
    """Tags every piece with the target language instead of translating."""

    def __init__(self):
        self.calls = []

    def translate_batch(self, batch, target_prefix, **_):
        self.calls.append((batch[0][0], target_prefix[0][0], len(batch)))
        tag = target_prefix[0][0].strip("_")
        return [mock.Mock(hypotheses=[[prefix[0]]
                                      + [f"{tag}:{p.split(':')[-1]}"
                                         for p in tokens[1:-1]]])
                for tokens, prefix in zip(batch, target_prefix)]


def fake_translator(llm=None):
    t = translate.Translator(llm=llm)
    t._model, t._sp = FakeM2M(), FakeSP()
    return t


class TranslatorTests(unittest.TestCase):
    def test_english_side_is_one_hop(self) -> None:
        t = fake_translator()
        self.assertEqual(t.translate("bonjour. merci", "fr", "en"),
                         "en:bonjour. en:merci")
        self.assertEqual(t._model.calls, [("__fr__", "__en__", 2)])

    def test_other_pairs_go_through_english(self) -> None:
        t = fake_translator()
        self.assertEqual(t.translate("bonjour", "fr", "ar"), "ar:bonjour")
        self.assertEqual(t._model.calls, [("__fr__", "__en__", 1),
                                          ("__en__", "__ar__", 1)])

    def test_unspaced_targets_and_long_sentences(self) -> None:
        t = fake_translator()
        self.assertEqual(t.translate("a. b.", "en", "ja"), "ja:a.ja:b.")
        long = " ".join(["w"] * (translate.MAX_PIECES + 5))
        out = t.translate(long, "en", "fr")
        self.assertEqual(len(out.split()), translate.MAX_PIECES + 5)
        self.assertEqual(t._model.calls[-1][2], 2)      # decoded in two

    def test_nothing_to_do(self) -> None:
        t = fake_translator()
        self.assertEqual(t.translate("  ", "fr", "ar"), "")
        self.assertEqual(t.translate("salut", "fr", "fr"), "salut")
        self.assertEqual(t._model.calls, [])

    def test_unknown_pair_raises(self) -> None:
        with self.assertRaises(ValueError):
            fake_translator().translate("x", "te", "fr")

    def test_llm_first_then_m2m(self) -> None:
        llm = mock.Mock(return_value=' "مرحبا" ')
        t = fake_translator(llm)
        self.assertEqual(t.translate("bonjour", "fr", "ar", True), "مرحبا")
        system, user = llm.call_args.args
        self.assertIn("from French to Arabic", system)
        self.assertEqual(user, "bonjour")
        self.assertEqual(t._model.calls, [])
        llm.return_value = None             # no answer: M2M100 is loaded
        self.assertEqual(t.translate("bonjour", "fr", "ar", True),
                         "ar:bonjour")
        llm.return_value = "x" * 500        # not a translation of 7 letters
        self.assertEqual(t.translate("bonjour", "fr", "ar", True),
                         "ar:bonjour")
        llm.side_effect = OSError("down")
        self.assertEqual(t.translate("bonjour", "fr", "ar", True),
                         "ar:bonjour")

    def test_llm_silent_and_no_m2m_for_the_pair_raises(self) -> None:
        t = fake_translator(mock.Mock(return_value=None))
        with self.assertRaises(RuntimeError):
            t.translate("hello", "en", "te", True)

    def test_llm_is_not_asked_unless_routed(self) -> None:
        llm = mock.Mock(return_value="x")
        self.assertEqual(fake_translator(llm).translate("a", "en", "fr"),
                         "fr:a")
        llm.assert_not_called()

    def test_ollama_unreachable_is_none(self) -> None:
        chat = translate.ollama_chat("m", url="http://127.0.0.1:9/api/chat")
        self.assertIsNone(chat("system", "bonjour"))


class TranslateSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["LOCALFLOW_SETTINGS"] = str(
            Path(self.tmp.name) / "settings.json")
        import settings
        self.settings = importlib.reload(settings)

    def tearDown(self) -> None:
        os.environ.pop("LOCALFLOW_SETTINGS", None)
        self.tmp.cleanup()

    def test_off_by_default_and_round_trip(self) -> None:
        s = self.settings
        self.assertIsNone(s.get_translate_to())
        s.set_translate_to("ar")
        self.assertEqual(s.get_translate_to(), "ar")
        s.set_translate_to(None)
        self.assertIsNone(s.get_translate_to())


class NowPool:
    """Runs a submitted job at once, like the translation worker would."""

    def submit(self, fn, *args):
        result = fn(*args)
        return mock.Mock(result=lambda: result)


def _app(translate_to="ar", language="fr"):
    """A FlowApp without models, audio or UI, in translate mode."""
    app = flow.FlowApp.__new__(flow.FlowApp)
    app.__dict__.update(
        preview="inline", typer=mock.Mock(), recorder=mock.Mock(),
        ducker=mock.Mock(), overlay=None, menubar=None, window=None,
        locked=False, use_ollama=False, use_cleanup=False, llm=False,
        gemma=None,
        translate_to=translate_to, _hotkey_down=False,
        _type_lock=threading.Lock(), translator=fake_translator(),
        _translations=NowPool(),
        transcriber=mock.Mock(language=language))
    return app


def _target(editable=True):
    return focus.FocusTarget(object(), 1, "App", "AXRole", editable)


class FakeTyper:
    """Remembers what the field would read."""

    def __init__(self):
        self.typed, self.log = "", []

    def update(self, new, soft=False):
        self.typed = new
        self.log.append(("update", new))

    def commit(self):
        self.log.append(("commit",))

    def replace(self, new):
        self.typed = new
        self.log.append(("replace", new))


def _state(target, preview="inline", **extra):
    st = {"text": "", "committed": "", "translating": True, "parts": [],
          "target": target, "preview": preview, "seen_n": 0,
          "typer": FakeTyper()}
    st.update(extra)
    return st


class FlowTranslateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pasted = []
        for p in (
            mock.patch.object(flow, "inject_text",
                              side_effect=lambda text, target=None:
                              self.pasted.append(text)),
            mock.patch.object(flow.focus, "restore", return_value=True),
            mock.patch.object(flow.settings, "is_self_corrections",
                              return_value=False),
            mock.patch.object(flow.settings, "is_tone", return_value=False),
            mock.patch.object(flow.FlowApp, "_learn_voice"),
        ):
            p.start()
            self.addCleanup(p.stop)

    def test_translating_still_types_into_the_field(self) -> None:
        app = _app()
        with mock.patch.object(flow.focus, "capture",
                               return_value=_target()), \
             mock.patch.object(flow.threading, "Thread"), \
             mock.patch.object(flow.typer, "LiveTyper"):
            app._start_recording()
            st = app._preview_state
            self.assertEqual((st["preview"], st["translating"]),
                             ("inline", True))
            app.translate_to = None
            app._start_recording()
            self.assertFalse(app._preview_state["translating"])

    def test_unreachable_pair_dictates_normally(self) -> None:
        app = _app(translate_to="te")
        self.assertIsNone(app._route())
        self.assertEqual(_app(language="te", translate_to="en")._route(),
                         "whisper")

    def test_spoken_words_are_typed_then_swapped_for_the_translation(
            self) -> None:
        app, target = _app(), _target()
        st = _state(target)
        with mock.patch.object(app, "_final_tail",
                               return_value="bonjour tout le monde"):
            app._process_translated(None, target, None, st)
        self.assertEqual(st["typer"].log, [
            ("update", "bonjour tout le monde"),
            ("replace", "ar:Bonjour ar:tout ar:le ar:monde.")])
        self.assertEqual(self.pasted, [])
        app.recorder.release.assert_called_once()   # mic held for Muxpane

    def test_locked_sentences_stay_as_spoken_until_the_end(self) -> None:
        app, target = _app(), _target()
        st = _state(target)
        with mock.patch.object(app, "_show_allowed", return_value=True):
            app._commit(st, "bonjour", 100)
            app._commit(st, "merci.", 100)
        self.assertEqual(st["typer"].typed, "Bonjour merci.")
        self.assertNotIn("replace", [e[0] for e in st["typer"].log])
        self.assertEqual([f.result() for f in st["parts"]],
                         ["ar:Bonjour", "ar:merci."])     # ready early
        st["committed"] = st["typer"].typed
        with mock.patch.object(app, "_final_tail", return_value="au revoir"):
            app._process_translated(None, target, None, st)
        self.assertEqual(st["typer"].typed,
                         "ar:Bonjour ar:merci. ar:Au ar:revoir.")

    def test_outside_a_text_field_the_translation_is_pasted(self) -> None:
        app, target = _app(), _target()
        st = _state(target, preview="card")
        with mock.patch.object(app, "_final_tail", return_value="merci"):
            app._process_translated(None, target, None, st)
        self.assertEqual(self.pasted, ["ar:Merci."])
        self.assertEqual(st["typer"].log, [])

    def test_nothing_heard_writes_nothing(self) -> None:
        app, target = _app(), _target()
        st = _state(target)
        with mock.patch.object(app, "_final_tail", return_value=""):
            app._process_translated(None, target, None, st)
        self.assertEqual((self.pasted, st["typer"].log), ([], []))
        app.recorder.release.assert_called_once()

    def test_failed_translation_leaves_what_was_said(self) -> None:
        app, target = _app(), _target()
        app.translator.translate = mock.Mock(side_effect=RuntimeError("x"))
        st = _state(target)
        with mock.patch.object(app, "_final_tail", return_value="bonjour"):
            app._process_translated(None, target, None, st)
        self.assertEqual(st["typer"].typed, "Bonjour.")

    def test_whisper_route_asks_whisper_for_english(self) -> None:
        app = _app(translate_to="en", language="te")
        st = _state(_target())
        self.assertEqual(app._task(st), "translate")
        with mock.patch.object(app, "_final_tail",
                               return_value="hello there") as tail:
            app._process_translated(None, st["target"], None, st)
        self.assertEqual(tail.call_args.args[-1], "translate")
        self.assertEqual(st["typer"].typed, "Hello there.")
        self.assertEqual(app.translator._model.calls, [])
        self.assertEqual(_app()._task(_state(None)), "transcribe")

    def test_the_microphone_is_held_only_while_translating(self) -> None:
        for translating in (True, False):
            app = _app()
            app.__dict__.update(recording=True, record_started=0.0,
                                target=None, _preview_thread=None,
                                worker=mock.Mock(),
                                _preview_state={"translating": translating,
                                                "active": True})
            app._stop_recording()
            app.recorder.stop.assert_called_once_with(hold=translating)


class RecorderHoldTests(unittest.TestCase):
    def test_hold_keeps_the_stream_until_release(self) -> None:
        r = flow.Recorder()
        with mock.patch.object(flow.mics, "open_stream",
                               side_effect=["first", "second", "third"]), \
                mock.patch.object(flow.mics, "close_stream") as close:
            r.start()
            r.stop(hold=True)
            close.assert_not_called()
            r._on_audio([0.5] * 160)            # held: nothing is kept
            self.assertEqual(len(r.snapshot()), 0)
            r.release()
            close.assert_called_once_with("first")
            r.release()                          # idempotent
            self.assertEqual(close.call_count, 1)
            # a new recording during the hold closes the held stream, and
            # a late release() leaves the new one alone
            r.start()
            r.stop(hold=True)
            r.start()
            self.assertEqual(close.call_count, 2)
            r.release()
            self.assertEqual(close.call_count, 2)
            r.stop()
            self.assertEqual(close.call_count, 3)


class GemmaTests(unittest.TestCase):
    def setUp(self) -> None:
        import gemma
        self.gemma = gemma
        self.tmp = tempfile.TemporaryDirectory()
        p = mock.patch.object(gemma, "RUNTIME_ROOT", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_not_installed_without_runtime_or_weights(self) -> None:
        g = self.gemma
        with mock.patch.object(g, "model_path", return_value="/w.gguf"):
            self.assertFalse(g.installed())             # no llama-server
            server = g.server_path()
            server.parent.mkdir(parents=True)
            server.write_text("#!/bin/sh\n")
            server.chmod(0o755)
            with mock.patch.object(g, "supported", return_value=True):
                self.assertTrue(g.installed())
            with mock.patch.object(g, "supported", return_value=False):
                self.assertFalse(g.installed())         # macOS too old
        with mock.patch.object(g, "model_path", return_value=None), \
                mock.patch.object(g, "supported", return_value=True):
            self.assertFalse(g.installed())             # no weights

    def test_runtime_with_a_wrong_checksum_is_not_installed(self) -> None:
        g = self.gemma
        with mock.patch.object(g.urllib.request, "urlopen",
                               return_value=__import__("io").BytesIO(b"x")):
            with self.assertRaises(RuntimeError):
                g.install_runtime(say=lambda m: None)
        self.assertFalse(g.server_path().exists())

    def test_server_that_is_not_installed_answers_none(self) -> None:
        g = self.gemma
        with mock.patch.object(g, "model_path", return_value=None):
            server = g.Server()
            self.assertFalse(server.start())
            self.assertIsNone(server.chat("s", "u"))
            self.assertFalse(server.running)

    def test_app_picks_gemma_then_ollama_then_nothing(self) -> None:
        # Gemma counts before its weights are on disk: they are fetched
        # the first time translate mode needs them
        with mock.patch.object(flow.gemma, "available", return_value=True):
            server, llm = flow.translation_llm(False)
            self.assertIsNotNone(server)
            self.assertEqual(llm, server.chat)
            self.assertEqual(server.sleep_idle, flow.gemma.SLEEP_IDLE_SEC)
            server, _ = flow.translation_llm(False, keep_loaded=True)
            self.assertEqual(server.sleep_idle, flow.CLEANUP_IDLE_SEC)
        with mock.patch.object(flow.gemma, "available", return_value=False):
            self.assertEqual(flow.translation_llm(False), (None, None))
            server, llm = flow.translation_llm(True)
            self.assertIsNone(server)
            self.assertTrue(callable(llm))

    def test_turning_translate_off_stops_the_server(self) -> None:
        app = _app()
        app.gemma, app.llm = mock.Mock(running=False), True
        app.gemma.start.return_value = True
        self.assertEqual(app._route(), "llm")
        self.assertTrue(app._load_translator())
        app.gemma.start.assert_called_once()
        with mock.patch.object(flow.settings, "set_translate_to"), \
                mock.patch.object(flow.threading, "Thread") as thread:
            app.set_translate(None)
            thread.call_args.kwargs["target"]()
        app.gemma.stop.assert_called_once()

    def test_available_unless_opted_out_or_macos_too_old(self) -> None:
        g = self.gemma
        with mock.patch.object(g, "OPT_OUT", Path(self.tmp.name) / "no"):
            with mock.patch.object(g, "supported", return_value=True):
                self.assertTrue(g.available())
                g.OPT_OUT.write_text("")
                self.assertFalse(g.available())     # --no-translate
                g.OPT_OUT.unlink()
            with mock.patch.object(g, "supported", return_value=False):
                self.assertFalse(g.available())

    def test_weights_are_fetched_when_translate_first_needs_them(self) -> None:
        app = _app()
        app.gemma, app.llm = mock.Mock(running=False), True
        app.gemma.start.return_value = True
        seen = []
        app._tell = seen.append

        def install(say, progress):
            progress(0.5)
            progress(0.504)             # same percent: said once
            return True
        with mock.patch.object(flow.gemma, "installed", return_value=False), \
                mock.patch.object(flow.gemma, "install",
                                  side_effect=install) as fetch:
            self.assertTrue(app._load_translator())
        fetch.assert_called_once()
        app.gemma.start.assert_called_once()
        self.assertEqual(len([s for s in seen if s.endswith("50%")]), 1)
        # already on disk: no download
        with mock.patch.object(flow.gemma, "installed", return_value=True), \
                mock.patch.object(flow.gemma, "install") as fetch:
            self.assertTrue(app._load_translator())
        fetch.assert_not_called()

    def test_a_failed_download_does_not_start_the_server(self) -> None:
        app = _app()
        app.gemma, app.llm = mock.Mock(running=False), True
        with mock.patch.object(flow.gemma, "installed", return_value=False), \
                mock.patch.object(flow.gemma, "install",
                                  side_effect=OSError("offline")):
            self.assertFalse(app._load_translator())
        app.gemma.start.assert_not_called()

    def test_translate_off_keeps_the_server_the_cleanup_pass_uses(self) -> None:
        app = _app()
        app.gemma, app.llm, app.use_cleanup = mock.Mock(), True, True
        with mock.patch.object(flow.settings, "set_translate_to"), \
                mock.patch.object(flow.threading, "Thread") as thread:
            app.set_translate(None)
            thread.call_args.kwargs["target"]()
        app.gemma.stop.assert_not_called()

    def test_stream_reads_tokens_and_never_waits_for_a_cold_start(self) -> None:
        g = self.gemma
        server = g.Server()
        with mock.patch.object(g.threading, "Thread") as thread:
            self.assertIsNone(server.stream("s", "u"))      # not running
            thread.assert_called_once()                     # started for later
        server._proc = mock.Mock(poll=lambda: None)
        server._port, server._key = 1, "k"
        body = __import__("io").BytesIO(
            b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
            b'data: {"choices":[{"delta":{"content":" there."}}]}\n\n'
            b'data: [DONE]\n\n')
        partials = []
        with mock.patch.object(g.urllib.request, "urlopen",
                               return_value=body):
            self.assertEqual(server.stream("s", "u", partials.append),
                             "Hello there.")
        self.assertEqual(partials, ["Hello", "Hello there."])
        with mock.patch.object(g.urllib.request, "urlopen",
                               side_effect=OSError("down")):
            self.assertIsNone(server.stream("s", "u"))
        server._proc = None


class ToggleTests(unittest.TestCase):
    """Dictate ↔ Translate from the menu bar."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["LOCALFLOW_SETTINGS"] = str(
            Path(self.tmp.name) / "settings.json")
        import settings
        self.settings = importlib.reload(settings)
        flow.settings = self.settings

    def tearDown(self) -> None:
        os.environ.pop("LOCALFLOW_SETTINGS", None)
        self.tmp.cleanup()
        import settings
        flow.settings = importlib.reload(settings)

    def _toggle(self, app):
        went = []
        app.set_translate = went.append
        app.toggle_translate()
        return went

    def test_on_goes_to_the_last_language_translated_into(self) -> None:
        s = self.settings
        s.set_translate_to("ja")
        s.set_translate_to(None)
        self.assertEqual(s.get_last_target(), "ja")
        self.assertEqual(self._toggle(_app(translate_to=None)), ["ja"])

    def test_on_without_a_last_one_takes_one_of_the_users(self) -> None:
        # the user's languages are en, de, fr; French is being spoken
        self.assertEqual(self._toggle(_app(translate_to=None)), ["en"])
        self.settings.set_translate_to("fr")    # the last one is the spoken one
        self.assertEqual(self._toggle(_app(translate_to=None)), ["en"])

    def test_off_when_translating(self) -> None:
        self.assertEqual(self._toggle(_app(translate_to="ar")), [None])


if __name__ == "__main__":
    unittest.main()
