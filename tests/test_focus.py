from __future__ import annotations

import unittest
from unittest import mock

import flow
import focus


class FakeElement:
    """What AX reports for one focused element."""

    def __init__(self, role, text_range=False, settable=False):
        self.role = role
        self.text_range = text_range
        self.settable = settable


def _copy(element, attr, _):
    if attr == focus.kAXRoleAttribute:
        return 0, element.role
    if attr == focus.kAXSelectedTextRangeAttribute and element.text_range:
        return 0, "range"
    return -25212, None                     # kAXErrorNoValue


def _settable(element, attr, _):
    return 0, element.settable


class IsTextInputTests(unittest.TestCase):
    def setUp(self):
        patches = [
            mock.patch.object(focus, "AXUIElementCopyAttributeValue", _copy),
            mock.patch.object(focus, "AXUIElementIsAttributeSettable",
                              _settable),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_text_roles(self) -> None:
        for role in ("AXTextField", "AXTextArea", "AXComboBox"):
            self.assertTrue(focus.is_text_input(FakeElement(role)), role)

    def test_finder_file_list_is_not_text(self) -> None:
        for role in ("AXOutline", "AXList", "AXScrollArea", "AXGroup"):
            self.assertFalse(focus.is_text_input(FakeElement(role)), role)

    def test_web_editor_with_a_text_cursor(self) -> None:
        editor = FakeElement("AXGroup", text_range=True, settable=True)
        self.assertTrue(focus.is_text_input(editor))

    def test_read_only_text_is_not_an_input(self) -> None:
        label = FakeElement("AXStaticText", text_range=True, settable=False)
        self.assertFalse(focus.is_text_input(label))

    def test_nothing_focused(self) -> None:
        self.assertFalse(focus.is_text_input(None))


def _bare_app(preview="inline"):
    """A FlowApp without models or audio: just enough to start a recording."""
    app = flow.FlowApp.__new__(flow.FlowApp)
    app.preview = preview
    app.typer = mock.Mock()
    app.recorder = mock.Mock()
    app.ducker = mock.Mock()
    app.overlay = None
    app.locked = False
    return app


class PreviewModeTests(unittest.TestCase):
    def _start(self, target, preview="inline"):
        app = _bare_app(preview)
        with mock.patch.object(flow.focus, "capture", return_value=target), \
             mock.patch.object(flow.threading, "Thread"), \
             mock.patch.object(flow.typer, "LiveTyper"):
            app._start_recording()
        return app._preview_state["preview"]

    def _target(self, editable):
        return focus.FocusTarget(object(), 1, "App", "AXRole", editable)

    def test_text_field_types_inline(self) -> None:
        self.assertEqual(self._start(self._target(True)), "inline")

    def test_finder_falls_back_to_the_card(self) -> None:
        self.assertEqual(self._start(self._target(False)), "card")

    def test_no_accessibility_falls_back_to_the_card(self) -> None:
        self.assertEqual(self._start(None), "card")

    def test_card_and_off_are_left_alone(self) -> None:
        self.assertEqual(self._start(None, "off"), "off")
        self.assertEqual(self._start(self._target(True), "card"), "card")

    def test_llm_partials_only_paint_the_card(self) -> None:
        app = _bare_app()
        self.assertIsNone(app._show_partial("a b", {"preview": "inline"}))
        self.assertIsNotNone(app._show_partial("a b", {"preview": "card"}))


if __name__ == "__main__":
    unittest.main()
