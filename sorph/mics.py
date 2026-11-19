"""Microphone choice for Sorph: which input device the recorder opens.

The choice is stored by device *name* (settings "mic"), since PortAudio's
indices shift whenever a device is plugged in or out. None means the macOS
system default input.

PortAudio reads the device list once, at initialization, so it would miss
a mic plugged in later and keep using the old system default. refresh()
re-initializes it (a few ms) whenever no stream is open: before every
recording and whenever the menu lists the inputs.
"""

import threading

import sounddevice as sd

import settings

_lock = threading.Lock()
_open = 0                     # streams currently open; refresh waits for 0


def _refresh_locked():
    if _open == 0:
        sd._terminate()
        sd._initialize()


def inputs():
    """(names of the input devices, name of the system default input)."""
    with _lock:
        _refresh_locked()
        devices = sd.query_devices()
        try:
            default = devices[sd.default.device[0]]["name"]
        except Exception:
            default = None
    names = []
    for d in devices:
        if d["max_input_channels"] > 0 and d["name"] not in names:
            names.append(d["name"])
    return names, default


def _index(name):
    if name is None:
        return None
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and d["name"] == name:
            return i
    return None


def open_stream(**kwargs):
    """Start an InputStream on the chosen mic. Falls back to the system
    default when the chosen one is unplugged or refuses to open."""
    global _open
    with _lock:
        _refresh_locked()
        chosen = settings.get_mic()
        device = _index(chosen)
        if chosen and device is None:
            print(f"warning: microphone {chosen!r} not found; "
                  f"using the system default", flush=True)
        try:
            stream = sd.InputStream(device=device, **kwargs)
            stream.start()
        except Exception as exc:
            if device is None:
                raise
            print(f"warning: could not open {chosen!r} ({exc}); "
                  f"using the system default", flush=True)
            stream = sd.InputStream(**kwargs)
            stream.start()
        _open += 1
    return stream


def close_stream(stream):
    global _open
    with _lock:
        try:
            stream.stop()
            stream.close()
        finally:
            _open = max(0, _open - 1)
