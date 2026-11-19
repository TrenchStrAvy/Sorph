"""Sorph's version, read from the changelog.

CHANGELOG.md is the one place the version is written down, so nothing
else has to be kept in step with it: a release is a new "## vX.Y.Z"
heading there, and the dashboard and the menu bar show it from the next
start. While there are unreleased changes above the newest release, the
version is marked "dev".
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the project folder


def current(root: str = ROOT) -> str:
    """"v0.8.0", or "v0.8.0 · dev" ahead of a release; "" when the
    changelog cannot be read."""
    try:
        with open(os.path.join(root, "CHANGELOG.md"), encoding="utf-8") as fh:
            headings = re.findall(r"^## +(\S+)", fh.read(), re.M)
    except OSError:
        return ""
    released = [h for h in headings if re.fullmatch(r"v\d+(\.\d+)+", h)]
    if not released:
        return ""
    dev = headings[0].lower() == "unreleased"
    return released[0] + (" · dev" if dev else "")
