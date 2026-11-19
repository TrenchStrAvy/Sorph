"""Music ducking: turn whatever is playing down while you dictate.

When the hotkey goes down and something is playing on the default output
device (Music, Spotify, a browser, a video call — any app: CoreAudio's
"running somewhere" flag), the system volume glides down to the level
picked in the menu bar, as a share of your current volume, before the mic
opens. After release it glides back. It moves the system volume rather
than one player's, so it works for every app.

If you change the volume yourself while ducked, Sorph keeps your setting
and does not restore. The volume to restore is also saved in settings, so
a crash mid-dictation is undone at the next launch.

CoreAudio is called through ctypes; anything missing (no output device,
a device without volume control such as HDMI) just means no ducking.
"""

import ctypes
import ctypes.util
import queue
import struct
import threading
import time

import settings

DUCK_SEC = 0.15               # glide down: quick, the mic is about to open
RESTORE_SEC = 0.4             # glide back up: gentler
STEP_SEC = 0.015
TOUCHED = 0.02                # volume moved this far from ours → user did it


def _fourcc(code: str) -> int:
    return struct.unpack(">I", code.encode())[0]


class _Address(ctypes.Structure):
    _fields_ = [("selector", ctypes.c_uint32),
                ("scope", ctypes.c_uint32),
                ("element", ctypes.c_uint32)]


SYSTEM_OBJECT = 1
GLOBAL = _fourcc("glob")
OUTPUT = _fourcc("outp")
DEFAULT_OUTPUT = _fourcc("dOut")
RUNNING_SOMEWHERE = _fourcc("gone")
VIRTUAL_MAIN_VOLUME = _fourcc("vmvc")   # one 0–1 scalar for all channels
MUTE = _fourcc("mute")

try:
    _ca = ctypes.CDLL(ctypes.util.find_library("CoreAudio"))
except (OSError, TypeError):
    _ca = None


def _get(obj, selector, scope, ctype):
    if _ca is None:
        return None
    addr = _Address(selector, scope, 0)
    value = ctype()
    size = ctypes.c_uint32(ctypes.sizeof(value))
    status = _ca.AudioObjectGetPropertyData(
        ctypes.c_uint32(obj), ctypes.byref(addr), 0, None,
        ctypes.byref(size), ctypes.byref(value))
    return value.value if status == 0 else None


def _output_device():
    dev = _get(SYSTEM_OBJECT, DEFAULT_OUTPUT, GLOBAL, ctypes.c_uint32)
    return dev or None


def is_playing() -> bool:
    """Some app is sending audio to the default output device."""
    dev = _output_device()
    return bool(dev and _get(dev, RUNNING_SOMEWHERE, GLOBAL, ctypes.c_uint32))


def is_muted() -> bool:
    dev = _output_device()
    return bool(dev and _get(dev, MUTE, OUTPUT, ctypes.c_uint32))


def get_volume():
    """System output volume 0–1, or None when the device has none."""
    dev = _output_device()
    return _get(dev, VIRTUAL_MAIN_VOLUME, OUTPUT, ctypes.c_float) if dev else None


def set_volume(volume: float) -> bool:
    dev = _output_device()
    if not dev or _ca is None:
        return False
    addr = _Address(VIRTUAL_MAIN_VOLUME, OUTPUT, 0)
    value = ctypes.c_float(min(1.0, max(0.0, volume)))
    return _ca.AudioObjectSetPropertyData(
        ctypes.c_uint32(dev), ctypes.byref(addr), 0, None,
        ctypes.sizeof(value), ctypes.byref(value)) == 0


class Ducker:
    """duck() before recording, restore() after; both return at once.

    One worker thread does the glides in order, so a quick second press
    during a restore glides straight back down from wherever it got to.
    """

    def __init__(self):
        self.saved = None       # volume to come back to while ducked
        self.ours = None        # the last volume we set
        self._jobs = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def duck(self):
        # ask now, before the mic opens: on a headset that is both input
        # and output, our own recording would count as "playing"
        self._jobs.put(("duck", is_playing()))

    def restore(self):
        self._jobs.put(("restore", None))

    def recover(self):
        """Undo a duck a previous run never restored (crash, kill)."""
        saved = settings.get_duck_restore()
        if saved is None:
            return
        settings.clear_duck_restore()
        now = get_volume()
        if now is not None and now < saved:
            set_volume(saved)

    # -- worker

    def _run(self):
        while True:
            job, playing = self._jobs.get()
            try:
                if job == "duck":
                    self._duck(playing)
                else:
                    self._restore()
            except Exception as exc:   # ducking is a nicety, never fatal
                print(f"warning: music ducking failed: {exc}", flush=True)
            finally:
                self._jobs.task_done()

    def _touched(self) -> bool:
        now = get_volume()
        return now is None or (self.ours is not None
                               and abs(now - self.ours) > TOUCHED)

    def _duck(self, playing: bool):
        level = settings.get_duck_level()
        if level is None:
            return
        if self.saved is None:
            if not playing or is_muted():
                return
            volume = get_volume()
            if not volume:
                return
            self.saved = volume
            self.ours = volume
            settings.set_duck_restore(volume)
        elif self._touched():          # user moved it during a restore
            self._forget()
            return
        self._glide(self.saved * level / 100, DUCK_SEC)

    def _restore(self):
        if self.saved is None:
            return
        if self._touched():
            self._forget()
            return
        if self._glide(self.saved, RESTORE_SEC):
            self._forget()

    def _forget(self):
        self.saved = self.ours = None
        settings.clear_duck_restore()

    def _glide(self, target: float, seconds: float) -> bool:
        """Ease the volume to `target`. Stops early (False) when a newer
        job is waiting or the user grabs the volume."""
        start = self.ours if self.ours is not None else get_volume()
        steps = max(1, round(seconds / STEP_SEC))
        for i in range(1, steps + 1):
            if not self._jobs.empty():
                return False
            if self._touched():
                self._forget()
                return False
            t = i / steps
            t = t * t * (3 - 2 * t)                    # smoothstep
            volume = start + (target - start) * t
            if not set_volume(volume):
                return False
            self.ours = get_volume()   # the device may round what we set
            time.sleep(STEP_SEC)
        return True
