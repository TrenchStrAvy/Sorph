from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

import cleanup
import dictionary
import tone


class PlausibilityTests(unittest.TestCase):
    def test_voiced_speech_is_kept(self) -> None:
        self.assertTrue(cleanup.plausible_segment(-0.86, 0.12, 0.5))
        self.assertTrue(cleanup.plausible_segment(-1.3, 0.4, 0.8))

    def test_loop_is_dropped_even_when_voiced(self) -> None:
        self.assertFalse(cleanup.plausible_segment(-0.84, 0.34, 3.68))

    def test_quiet_audio_must_convince(self) -> None:
        # values measured on background-only clips
        self.assertFalse(cleanup.plausible_segment(-0.90, 0.45, 0.76, False))
        self.assertFalse(cleanup.plausible_segment(-1.52, 0.13, 0.68, False))
        # soft but real speech still passes
        self.assertTrue(cleanup.plausible_segment(-0.5, 0.05, 0.8, False))

    def test_more_text_than_time(self) -> None:
        self.assertFalse(cleanup.plausible_length("x" * 342, 2.8))
        self.assertTrue(cleanup.plausible_length("Almost every time.", 0.8))


class SelfCorrectionTests(unittest.TestCase):
    def check(self, said: str, written: str) -> None:
        self.assertEqual(cleanup.self_correct(said), written)

    def test_replaces_the_corrected_words(self) -> None:
        self.check("Let's meet Tuesday, actually no, Wednesday.",
                   "Let's meet Wednesday.")
        self.check("Let's meet Tuesday. Actually, no, Wednesday.",
                   "Let's meet Wednesday.")
        self.check("The meeting is at five, I mean six.",
                   "The meeting is at six.")
        self.check("Use the red one or rather, the blue one for the header.",
                   "Use the blue one for the header.")

    def test_resumes_at_the_repeated_word(self) -> None:
        self.check("Send it to John, no wait, to Mary Smith.",
                   "Send it to Mary Smith.")

    def test_chained(self) -> None:
        self.check("First Tuesday, actually no, Wednesday, no wait, Thursday.",
                   "First Thursday.")

    def test_scratch_that_drops_the_sentence(self) -> None:
        self.check("I'll call Tom on Monday. Scratch that. I'll email him.",
                   "I'll email him.")
        self.check("Keep this. Call Tom, scratch that, email him.",
                   "Keep this. email him.")

    def test_ordinary_speech_is_untouched(self) -> None:
        for text in ("It's actually no problem at all.",
                     "You know what I mean, right?",
                     "What do I mean by that?",
                     "I mean, it works.",
                     "It's good. I mean, it's really good.",
                     "Actually no, let's go.",
                     "There's a file called foo, delete that."):
            self.check(text, text)

    def test_other_languages_pass_through(self) -> None:
        text = "Dienstag, actually no, Mittwoch."
        self.assertEqual(cleanup.self_correct(text, "de"), text)


class DictionaryTests(unittest.TestCase):
    ENTRIES = ["Ollama", "terror form = Terraform", "Olama -> Ollama", "tmux"]

    def test_parse(self) -> None:
        self.assertEqual(dictionary.parse("Ollama"), (None, "Ollama"))
        self.assertEqual(dictionary.parse("terror form = Terraform"),
                         ("terror form", "Terraform"))

    def test_hotwords_are_the_written_forms_once(self) -> None:
        self.assertEqual(dictionary.hotwords(self.ENTRIES),
                         "Ollama Terraform tmux")
        self.assertEqual(dictionary.hotwords([]), "")

    def test_apply(self) -> None:
        self.assertEqual(
            dictionary.apply("run olama, then Olama and the terror  form "
                             "in TMUX", self.ENTRIES),
            "run Ollama, then Ollama and the Terraform in tmux")

    def test_whole_words_only(self) -> None:
        self.assertEqual(dictionary.apply("Olamas platform", self.ENTRIES),
                         "Olamas platform")


class ToneTests(unittest.TestCase):
    class Target:
        def __init__(self, bundle_id="", app_name=""):
            self.bundle_id, self.app_name = bundle_id, app_name

    def test_styles(self) -> None:
        T = self.Target
        self.assertEqual(tone.style_for(None), tone.STANDARD)
        self.assertEqual(tone.style_for(T("com.apple.mail", "Mail")),
                         tone.STANDARD)
        self.assertEqual(tone.style_for(T("com.tinyspeck.slackmacgap")),
                         tone.CASUAL)
        self.assertEqual(tone.style_for(T("", "Messages")), tone.CASUAL)
        self.assertEqual(tone.style_for(T("com.apple.Terminal")), tone.PLAIN)
        self.assertEqual(tone.style_for(T("com.jetbrains.pycharm")),
                         tone.PLAIN)

    def test_single_line_loses_its_period(self) -> None:
        self.assertEqual(tone.apply("See you at six.", tone.CASUAL),
                         "See you at six")
        self.assertEqual(tone.apply("See you at six.", tone.STANDARD),
                         "See you at six.")

    def test_everything_else_stays(self) -> None:
        for text in ("One. Two.", "Really?", "Wait...", "No way!", ""):
            self.assertEqual(tone.apply(text, tone.PLAIN), text)

    def test_only_standard_closes(self) -> None:
        self.assertTrue(tone.closes(tone.STANDARD))
        self.assertFalse(tone.closes(tone.CASUAL))
        self.assertFalse(tone.closes(tone.PLAIN))


class VoiceGateTests(unittest.TestCase):
    def setUp(self) -> None:
        import flow
        self.flow = flow

    def _audio(self, level: float, seconds: float = 2.0):
        rng = np.random.default_rng(1)
        n = int(seconds * self.flow.SAMPLE_RATE)
        return rng.normal(0, level, n).astype(np.float32)

    def test_gate_follows_the_voice(self) -> None:
        f = self.flow
        self.assertEqual(f.voice_gate(None), f.SILENCE_RMS)
        self.assertEqual(f.voice_gate(0.02), f.SILENCE_RMS)   # never lower
        self.assertAlmostEqual(f.voice_gate(0.2), 0.05)

    def test_level_rises_at_once_and_falls_slowly(self) -> None:
        f = self.flow
        loud = f.learn_level(None, self._audio(0.2))
        self.assertAlmostEqual(loud, 0.2, delta=0.02)
        self.assertAlmostEqual(f.learn_level(0.05, self._audio(0.2)), loud)
        after_quiet = f.learn_level(loud, self._audio(0.02))
        self.assertGreater(after_quiet, 0.8 * loud)
        self.assertLess(after_quiet, loud)

    def test_silence_teaches_nothing(self) -> None:
        self.assertIsNone(self.flow.learn_level(0.2, self._audio(0.001)))


class Segment:
    def __init__(self, text, start, end, logprob=-0.4, no_speech=0.02,
                 ratio=0.9):
        self.text, self.start, self.end = text, start, end
        self.avg_logprob, self.no_speech_prob = logprob, no_speech
        self.compression_ratio = ratio


class FakeModel:
    def __init__(self, segments):
        self.segments, self.options = segments, None

    def transcribe(self, audio, **options):
        self.options = options
        return iter(self.segments), None


class TranscriberFilterTests(unittest.TestCase):
    """Transcriber.transcribe with a stand-in model: which segments
    survive, without loading Whisper."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["LOCALFLOW_SETTINGS"] = str(
            Path(self.tmp.name) / "settings.json")
        import settings
        self.settings = importlib.reload(settings)
        import flow
        self.flow = flow
        flow.settings = self.settings

    def tearDown(self) -> None:
        os.environ.pop("LOCALFLOW_SETTINGS", None)
        self.tmp.cleanup()
        import settings
        self.flow.settings = importlib.reload(settings)

    def _transcriber(self, segments):
        t = self.flow.Transcriber.__new__(self.flow.Transcriber)
        t.model = FakeModel(segments)
        t.language, t.decode = "en", {}
        import threading
        t._switch = threading.RLock()
        return t

    def _audio(self):
        # 1 s of background (0.02), then 2 s at voice level (0.2)
        rng = np.random.default_rng(2)
        sr = self.flow.SAMPLE_RATE
        return np.concatenate([rng.normal(0, 0.02, sr),
                               rng.normal(0, 0.2, 2 * sr)]).astype(np.float32)

    def test_background_segment_is_dropped_voice_kept(self) -> None:
        t = self._transcriber([
            Segment("This is a public space.", 0.0, 0.9, -1.4, 0.31),
            Segment("Almost every time.", 1.1, 2.8, -0.9, 0.3)])
        self.assertEqual(t.transcribe(self._audio(), gate=0.05),
                         "Almost every time.")

    def test_without_a_gate_both_are_kept(self) -> None:
        t = self._transcriber([
            Segment("This is a public space.", 0.0, 0.9, -1.4, 0.31),
            Segment("Almost every time.", 1.1, 2.8, -0.9, 0.3)])
        self.assertEqual(t.transcribe(self._audio()),
                         "This is a public space. Almost every time.")

    def test_confident_quiet_speech_is_kept(self) -> None:
        t = self._transcriber([Segment("Speaking softly.", 0.0, 0.9)])
        self.assertEqual(t.transcribe(self._audio(), gate=0.05),
                         "Speaking softly.")

    def test_loop_spread_over_segments_is_cut(self) -> None:
        t = self._transcriber(
            [Segment("You know.", 1.0, 1.5)]
            + [Segment(w, 1.5, 2.9) for w in ["It's", "the stomach."] * 6])
        self.assertEqual(t.transcribe(self._audio(), gate=0.05),
                         "You know. It's the stomach.")

    def test_decode_budget_and_dictionary(self) -> None:
        self.settings.add_dictionary("Olama = Ollama")
        t = self._transcriber([Segment("run olama", 1.1, 2.8)])
        self.assertEqual(t.transcribe(self._audio(), gate=0.05), "run Ollama")
        self.assertEqual(t.model.options["hotwords"], "Ollama")
        self.assertEqual(t.model.options["max_new_tokens"],
                         3 * self.flow.TOKENS_PER_SEC + 16)


class NewSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["LOCALFLOW_SETTINGS"] = str(
            Path(self.tmp.name) / "settings.json")
        import settings
        self.settings = importlib.reload(settings)

    def tearDown(self) -> None:
        os.environ.pop("LOCALFLOW_SETTINGS", None)
        self.tmp.cleanup()

    def test_dictionary_round_trip(self) -> None:
        s = self.settings
        self.assertEqual(s.get_dictionary(), [])
        s.add_dictionary("  Ollama ")
        s.add_dictionary("ollama")            # same word again
        s.add_dictionary("terror form = Terraform")
        self.assertEqual(s.get_dictionary(),
                         ["Ollama", "terror form = Terraform"])
        s.remove_dictionary("Ollama")
        self.assertEqual(s.get_dictionary(), ["terror form = Terraform"])

    def test_switches_default_on(self) -> None:
        s = self.settings
        self.assertTrue(s.is_self_corrections())
        self.assertTrue(s.is_tone())
        s.set_self_corrections(False)
        s.set_tone(False)
        self.assertFalse(s.is_self_corrections())
        self.assertFalse(s.is_tone())

    def test_voice_level_is_per_mic(self) -> None:
        s = self.settings
        self.assertIsNone(s.get_voice_level("DJI MIC MINI"))
        s.set_voice_level("DJI MIC MINI", 0.21)
        s.set_voice_level(None, 0.08)
        self.assertEqual(s.get_voice_level("DJI MIC MINI"), 0.21)
        self.assertEqual(s.get_voice_level(None), 0.08)


if __name__ == "__main__":
    unittest.main()
