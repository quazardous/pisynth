"""Shared test setup. The pure modules run without hardware; only `evdev` (the touchscreen
binding, Linux kernel headers to build) is missing on a dev laptop, so stub it before any
`pisynth` import. Nothing here talks to a real device."""
import sys
import types

if "evdev" not in sys.modules:
    try:
        import evdev  # noqa: F401  — use the real one when present (on the Pi)
    except ImportError:
        stub = types.ModuleType("evdev")
        stub.ecodes = types.SimpleNamespace(EV_ABS=3, EV_KEY=1, ABS_X=0, ABS_Y=1, BTN_TOUCH=330)
        stub.InputDevice = object
        stub.list_devices = lambda: []
        sys.modules["evdev"] = stub
