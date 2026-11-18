from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

import flow
import focus
import muxpane


def _dead_pid() -> int:
    """A pid that belonged to a process that has exited."""
    p = subprocess.Popen(["/usr/bin/true"])
    p.wait()
    return p.pid


class HandoffFolder(unittest.TestCase):
    """Each test gets its own Muxpane support folder."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = self.tmp.name
        os.mkdir(os.path.join(self.folder, "events"))
        patch = mock.patch.object(muxpane, "FOLDER", self.folder)
        patch.start()
        self.addCleanup(patch.stop)

    def write_target(self, **fields):
        record = {"pane": "%22", "name": "Muxpane", "ts": 1.0, "pid": os.getpid()}
        record.update(fields)
        with open(os.path.join(self.folder, "answer-target.json"), "w") as f:
            json.dump(record, f)

    def events(self):
        folder = os.path.join(self.folder, "events")
        return sorted(os.listdir(folder))


class ReadTargetTests(HandoffFolder):
    def test_a_live_muxpane_target_is_read(self) -> None:
        self.write_target()
        self.assertEqual(muxpane.read_target(), {"pane": "%22", "name": "Muxpane"})

    def test_no_file_no_target(self) -> None:
        self.assertIsNone(muxpane.read_target())

    def test_a_file_left_by_a_muxpane_that_is_gone_is_ignored(self) -> None:
        self.write_target(pid=_dead_pid())
        self.assertIsNone(muxpane.read_target())

    def test_a_broken_file_is_ignored(self) -> None:
        with open(os.path.join(self.folder, "answer-target.json"), "w") as f:
            f.write("{not json")
        self.assertIsNone(muxpane.read_target())
        self.write_target(pane="")
        self.assertIsNone(muxpane.read_target())


class DeliverTests(HandoffFolder):
    def test_the_text_becomes_one_complete_event(self) -> None:
        self.assertTrue(muxpane.deliver({"pane": "%22", "name": "Muxpane"}, "  ship it \n"))
        names = self.events()
        self.assertEqual(len(names), 1)
        self.assertTrue(names[0].endswith("-sorph.json"))   # no .tmp left behind
        with open(os.path.join(self.folder, "events", names[0])) as f:
            event = json.load(f)
        self.assertEqual(event["hook_event_name"], "SorphReply")
        self.assertEqual(event["pane"], "%22")
        self.assertEqual(event["text"], "ship it")

    def test_nothing_said_nothing_sent(self) -> None:
        self.assertFalse(muxpane.deliver({"pane": "%22", "name": "Muxpane"}, "   "))
        self.assertEqual(self.events(), [])

    def test_announce_and_withdraw(self) -> None:
        self.assertTrue(muxpane.announce())
        path = os.path.join(self.folder, "sorph.json")
        with open(path) as f:
            self.assertEqual(json.load(f), {"handoff": 1, "pid": os.getpid()})
        muxpane.withdraw()
        self.assertFalse(os.path.exists(path))

    def test_no_muxpane_no_announcement(self) -> None:
        with mock.patch.object(muxpane, "FOLDER", os.path.join(self.folder, "absent")):
            self.assertFalse(muxpane.announce())
            self.assertFalse(muxpane.deliver({"pane": "%1", "name": "x"}, "hi"))


class RecordingTests(HandoffFolder):
    def _app(self):
        app = flow.FlowApp.__new__(flow.FlowApp)
        app.__dict__.update(preview="inline", typer=mock.Mock(), recorder=mock.Mock(),
                            ducker=mock.Mock(), overlay=mock.Mock(), locked=False,
                            translate_to=None, muxpane_target=None)
        return app

    def _start(self, app):
        target = focus.FocusTarget(object(), 1, "Terminal", "AXTextArea", True)
        with mock.patch.object(flow.focus, "capture", return_value=target), \
             mock.patch.object(flow.threading, "Thread"), \
             mock.patch.object(flow.typer, "LiveTyper"):
            app._start_recording()

    def test_a_muxpane_dictation_shows_in_the_card_with_its_target(self) -> None:
        self.write_target(name="Slate", pane="%7")
        app = self._app()
        self._start(app)
        self.assertEqual(app._preview_state["preview"], "card")   # never typed in front
        self.assertEqual(app._preview_state["muxpane"], {"pane": "%7", "name": "Slate"})
        app.overlay.set_muxpane.assert_called_with(True)
        app.overlay.set_note.assert_called_with("→ Slate · %7")

    def test_without_a_target_sorph_types_as_always(self) -> None:
        app = self._app()
        self._start(app)
        self.assertEqual(app._preview_state["preview"], "inline")
        self.assertIsNone(app._preview_state["muxpane"])
        app.overlay.set_muxpane.assert_called_with(False)


if __name__ == "__main__":
    unittest.main()
