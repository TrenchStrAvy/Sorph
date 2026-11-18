"""The hand-off with Muxpane (the agents bar that reads coding agents aloud).

While Muxpane offers to send an answer to one of its agents, it keeps
answer-target.json in its support folder: the tmux pane, the agent's name,
and Muxpane's pid. When Sorph's key goes down and that file is there (and
Muxpane is still running), this dictation is for that agent: the words show
in the overlay's card instead of being typed, the orb takes Muxpane's
colours with a small "→ name · pane" caption, and the finished text goes
back to Muxpane as an event file, which sends it to the pane.

Sorph announces that it knows this in sorph.json, so Muxpane stops opening
its own reply field for Sorph to type into. Every step is best-effort: when
Muxpane is not installed nothing here does anything.
"""

import json
import os
import time

FOLDER = os.path.expanduser("~/Library/Application Support/Muxpane")


def _target_path():
    return os.path.join(FOLDER, "answer-target.json")


def _sorph_path():
    return os.path.join(FOLDER, "sorph.json")


def _alive(pid) -> bool:
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True                 # exists, owned by someone else
    except OSError:
        return False
    return True


def announce() -> bool:
    """Tell Muxpane this Sorph takes the hand-off (only if Muxpane is
    installed: its folder is never created here)."""
    if not os.path.isdir(FOLDER):
        return False
    try:
        tmp = _sorph_path() + ".%d.tmp" % os.getpid()
        with open(tmp, "w") as f:
            json.dump({"handoff": 1, "pid": os.getpid()}, f)
        os.replace(tmp, _sorph_path())
        return True
    except OSError:
        return False


def withdraw():
    """Sorph is quitting: remove the announcement if it is ours."""
    try:
        with open(_sorph_path()) as f:
            if json.load(f).get("pid") != os.getpid():
                return
        os.remove(_sorph_path())
    except (OSError, ValueError, AttributeError):
        pass


def read_target():
    """The agent Muxpane would send this dictation to, or None:
    {"pane": "%22", "name": "Muxpane"}."""
    try:
        with open(_target_path()) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    pane, name = data.get("pane"), data.get("name")
    if not (isinstance(pane, str) and pane and isinstance(name, str)):
        return None
    if not _alive(data.get("pid")):
        return None                 # left behind by a Muxpane that is gone
    return {"pane": pane, "name": name}


def caption(target) -> str:
    return f"→ {target['name']} · {target['pane']}"


def deliver(target, text: str) -> bool:
    """Hand the finished dictation to Muxpane, which sends it to the pane.
    Written as a .tmp file and renamed, so Muxpane never reads half."""
    text = (text or "").strip()
    if not text or not target:
        return False
    folder = os.path.join(FOLDER, "events")
    if not os.path.isdir(folder):
        return False
    event = {"hook_event_name": "SorphReply", "pane": target["pane"],
             "text": text, "ts": time.time()}
    name = "%d-sorph" % time.time_ns()
    tmp = os.path.join(folder, name + ".tmp")
    try:
        with open(tmp, "w") as f:
            json.dump(event, f)
        os.replace(tmp, os.path.join(folder, name + ".json"))
        return True
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False
