from __future__ import annotations

import unittest
from unittest import mock

import typer

RANGE = typer.kAXSelectedTextRangeAttribute
VALUE = typer.kAXValueAttribute
SELECTED = typer.kAXSelectedTextAttribute
FOCUSED = typer.kAXFocusedUIElementAttribute


def _u16(text):
    return text.encode("utf-16-le")


class FakeField:
    """A text field as AX sees it: a value and a selected range, counted
    in UTF-16 units like AppKit."""

    def __init__(self, value, accepts=True):
        self.value = value
        self.sel = (len(_u16(value)) // 2, 0)
        self.accepts = accepts
        self.ranges = []           # every selection we were asked to make

    def copy(self, element, attr, _):
        if attr == FOCUSED:
            return 0, self
        if attr == VALUE:
            return 0, self.value
        if attr == RANGE:
            return 0, ("range", self.sel)
        return -1, None

    def set(self, element, attr, value):
        if attr == RANGE:
            self.sel = value[1]
            self.ranges.append(self.sel)
            return 0
        if attr == SELECTED:
            if self.accepts:
                loc, n = self.sel
                v = _u16(self.value)
                self.value = (v[:2 * loc] + _u16(value)
                              + v[2 * (loc + n):]).decode("utf-16-le")
                self.sel = (loc + len(_u16(value)) // 2, 0)
            return 0
        return -1


class AxEditTests(unittest.TestCase):
    def run_update(self, field, typed, new, soft=False):
        keys = []
        typer._no_ax.clear()
        with mock.patch.multiple(
                typer,
                _system=object(),
                AXUIElementCopyAttributeValue=field.copy,
                AXUIElementSetAttributeValue=field.set,
                AXUIElementGetPid=lambda el, _: (0, 42),
                AXValueCreate=lambda kind, rng: ("range", rng),
                AXValueGetValue=lambda v, kind, _: (True, v[1]),
                AX_SETTLE_SEC=0,
                move=lambda n: keys.append(("move", n)) if n else None,
                backspace=lambda n: keys.append(("del", n)) if n else None,
                type_text=lambda t: keys.append(("type", t)) if t else None):
            ty = typer.LiveTyper()
            ty.typed = typed
            ty.update(new, soft=soft)
        return ty, keys

    def test_fixes_an_early_word_without_moving_the_caret(self) -> None:
        field = FakeField("Notes: we go home")
        ty, keys = self.run_update(field, "we go home", "so we go home and")
        self.assertEqual(field.value, "Notes: so we go home")
        self.assertEqual(field.sel, (len("Notes: so we go home"), 0))
        # the tail is typed as usual, no arrow keys at all
        self.assertEqual(keys, [("type", " and")])
        self.assertEqual(ty.typed, "so we go home and")

    def test_falls_back_to_arrows_when_the_field_ignores_ax(self) -> None:
        field = FakeField("we go home", accepts=False)
        ty, keys = self.run_update(field, "we go home", "so we go home")
        self.assertEqual(keys, [("move", -10), ("type", "so "), ("move", 10)])
        self.assertEqual(field.sel, (10, 0))      # caret put back
        self.assertIn(42, typer._no_ax)           # remembered for this app
        self.assertEqual(ty.typed, "so we go home")

    def test_falls_back_when_the_field_does_not_match(self) -> None:
        field = FakeField("something else entirely")
        ty, keys = self.run_update(field, "we go home", "so we go home")
        self.assertEqual(field.value, "something else entirely")
        self.assertIn(("type", "so "), keys)

    def test_counts_utf16_like_ax(self) -> None:
        field = FakeField("🎉 hi there")
        ty, keys = self.run_update(field, "hi there", "hey there")
        self.assertEqual(field.value, "🎉 hey there")
        self.assertEqual(field.sel, (len(_u16("🎉 hey there")) // 2, 0))
        self.assertEqual(keys, [])


if __name__ == "__main__":
    unittest.main()
