from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

DEVICES = [
    {"name": "Built-in Microphone", "max_input_channels": 2},
    {"name": "Speakers", "max_input_channels": 0},
    {"name": "DJI MIC MINI", "max_input_channels": 2},
]


class FakeStream:
    def __init__(self, device=None, **kwargs):
        if device == 2 and FakeStream.refuse:
            raise RuntimeError("device busy")
        self.device = device
        self.closed = False

    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        self.closed = True


class MicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["LOCALFLOW_SETTINGS"] = str(Path(self.tmp.name) / "s.json")
        import settings
        import mics
        self.settings = importlib.reload(settings)
        self.mics = importlib.reload(mics)
        FakeStream.refuse = False
        sd = self.mics.sd
        self.patches = [
            mock.patch.object(sd, "_terminate"),
            mock.patch.object(sd, "_initialize"),
            mock.patch.object(sd, "query_devices", lambda: DEVICES),
            mock.patch.object(sd, "InputStream", FakeStream),
            mock.patch.object(sd, "default", mock.Mock(device=[2, 1])),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self) -> None:
        for p in self.patches:
            p.stop()
        os.environ.pop("LOCALFLOW_SETTINGS", None)
        self.tmp.cleanup()

    def test_setting_round_trips(self) -> None:
        self.assertIsNone(self.settings.get_mic())
        self.settings.set_mic("DJI MIC MINI")
        self.assertEqual(self.settings.get_mic(), "DJI MIC MINI")
        self.settings.set_mic(None)
        self.assertIsNone(self.settings.get_mic())

    def test_lists_inputs_only(self) -> None:
        self.assertEqual(self.mics.inputs(),
                         (["Built-in Microphone", "DJI MIC MINI"], "DJI MIC MINI"))

    def test_opens_the_chosen_mic_by_name(self) -> None:
        self.settings.set_mic("DJI MIC MINI")
        stream = self.mics.open_stream(samplerate=16000)
        self.assertEqual(stream.device, 2)
        self.assertEqual(self.mics._open, 1)
        self.mics.close_stream(stream)
        self.assertEqual(self.mics._open, 0)

    def test_falls_back_to_default(self) -> None:
        self.settings.set_mic("Unplugged Mic")
        self.assertIsNone(self.mics.open_stream().device)
        self.mics._open = 0
        FakeStream.refuse = True
        self.settings.set_mic("DJI MIC MINI")
        self.assertIsNone(self.mics.open_stream().device)

    def test_no_refresh_while_a_stream_is_open(self) -> None:
        stream = self.mics.open_stream()
        self.mics.sd._terminate.reset_mock()
        self.mics.inputs()
        self.mics.sd._terminate.assert_not_called()
        self.mics.close_stream(stream)
        self.mics.inputs()
        self.mics.sd._terminate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
