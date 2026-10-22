from __future__ import annotations

import importlib
import os
import tempfile
import time
import unittest
from pathlib import Path


class FakeOutput:
    """Stands in for the CoreAudio calls: a volume knob and a playing flag."""

    def __init__(self, volume=0.8, playing=True, muted=False):
        self.volume = volume
        self.playing = playing
        self.muted = muted

    def install(self, ducking):
        ducking.is_playing = lambda: self.playing
        ducking.is_muted = lambda: self.muted
        ducking.get_volume = lambda: self.volume
        ducking.set_volume = self.set

    def set(self, v):
        self.volume = round(v, 4)
        return True


def settle(ducker, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if ducker._jobs.unfinished_tasks == 0:
            return
        time.sleep(0.01)
    raise AssertionError("ducker did not settle")


class DuckingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["LOCALFLOW_SETTINGS"] = str(
            Path(self.tmp.name) / "settings.json")
        import settings
        import ducking
        self.settings = importlib.reload(settings)
        self.ducking = importlib.reload(ducking)
        self.ducking.DUCK_SEC = self.ducking.RESTORE_SEC = 0.03
        self.ducking.STEP_SEC = 0.005
        self.out = FakeOutput()
        self.out.install(self.ducking)
        self.ducker = self.ducking.Ducker()

    def tearDown(self) -> None:
        os.environ.pop("LOCALFLOW_SETTINGS", None)
        self.tmp.cleanup()

    def test_settings_default_and_round_trip(self) -> None:
        s = self.settings
        self.assertEqual(s.get_duck_level(), 20)
        s.set_duck_level(0)
        self.assertEqual(s.get_duck_level(), 0)
        s.set_duck_level(None)
        self.assertIsNone(s.get_duck_level())
        self.assertEqual(s.get_duck_slider(), 0)     # slider keeps its spot
        s.set_ducking(True)
        self.assertEqual(s.get_duck_level(), 0)
        s.set_duck_level(100)
        self.assertEqual(s.get_duck_level(), 100)
        for bad in (-1, 101, "20", True):
            with self.assertRaises(ValueError):
                s.set_duck_level(bad)

    def test_old_null_level_means_off(self) -> None:
        self.settings.save(duck_level=None)
        self.assertIsNone(self.settings.get_duck_level())
        self.settings.set_ducking(True)
        self.assertEqual(self.settings.get_duck_level(), 20)

    def test_corrupt_level_falls_back_to_default(self) -> None:
        self.settings.save(duck_level="loud")
        self.assertEqual(self.settings.get_duck_level(), 20)

    def test_ducks_to_level_and_restores(self) -> None:
        self.settings.set_duck_level(25)
        self.ducker.duck()
        settle(self.ducker)
        self.assertAlmostEqual(self.out.volume, 0.2, places=3)
        self.assertEqual(self.settings.get_duck_restore(), 0.8)
        self.ducker.restore()
        settle(self.ducker)
        self.assertAlmostEqual(self.out.volume, 0.8, places=3)
        self.assertIsNone(self.settings.get_duck_restore())

    def test_nothing_playing_leaves_volume_alone(self) -> None:
        self.out.playing = False
        self.ducker.duck()
        self.ducker.restore()
        settle(self.ducker)
        self.assertEqual(self.out.volume, 0.8)

    def test_off_and_muted_leave_volume_alone(self) -> None:
        self.settings.set_duck_level(None)
        self.ducker.duck()
        settle(self.ducker)
        self.assertEqual(self.out.volume, 0.8)
        self.settings.set_duck_level(20)
        self.out.muted = True
        self.ducker.duck()
        settle(self.ducker)
        self.assertEqual(self.out.volume, 0.8)

    def test_user_volume_change_is_kept(self) -> None:
        self.ducker.duck()
        settle(self.ducker)
        self.out.volume = 0.5                  # user turns it up mid-dictation
        self.ducker.restore()
        settle(self.ducker)
        self.assertEqual(self.out.volume, 0.5)
        self.assertIsNone(self.ducker.saved)

    def test_quick_second_press_ducks_from_original(self) -> None:
        self.settings.set_duck_level(50)
        self.ducker.duck()
        self.ducker.restore()
        self.ducker.duck()                     # playing check still true
        settle(self.ducker)
        self.assertAlmostEqual(self.out.volume, 0.4, places=3)
        self.ducker.restore()
        settle(self.ducker)
        self.assertAlmostEqual(self.out.volume, 0.8, places=3)

    def test_recover_restores_after_crash(self) -> None:
        self.settings.set_duck_restore(0.8)
        self.out.volume = 0.16
        self.ducker.recover()
        self.assertEqual(self.out.volume, 0.8)
        self.assertIsNone(self.settings.get_duck_restore())


if __name__ == "__main__":
    unittest.main()
