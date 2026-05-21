"""Pointer-input adapter (#308): the ADS7846 resistive touchscreen via evdev.

Implements io.interfaces.PointerInput.
"""
import os

from evdev import InputDevice, ecodes, list_devices


class Touch:
    def __init__(self):
        self.dev = None
        for path in list_devices():
            d = InputDevice(path)
            if "ADS7846" in d.name or "Touchscreen" in d.name:
                self.dev = d
                break
        if self.dev is None:
            raise RuntimeError("no ADS7846 touchscreen found in /dev/input")
        os.set_blocking(self.dev.fd, False)
        self.affine = None
        self._rx = self._ry = None
        self._touching = False

    def fileno(self):
        return self.dev.fd

    def set_affine(self, coeffs):
        self.affine = coeffs

    def map(self, rx, ry):
        a, b, c, d, e, f = self.affine
        return int(a * rx + b * ry + c), int(d * rx + e * ry + f)

    def held_pos(self):
        """Current finger position (mapped x, y) while the screen is being touched, else
        None. Lets the controller implement hold-to-repeat on +/- steppers (#314) without
        touching read_taps (which still reports completed taps on release)."""
        if self._touching and self.affine and self._rx is not None and self._ry is not None:
            return self.map(self._rx, self._ry)
        return None

    def read_taps(self):
        """Non-blocking drain → mapped (x, y) taps, reported on release.
        ADS7846 sends BTN_TOUCH press before the coords, so latch on press."""
        taps = []
        try:
            events = list(self.dev.read())
        except BlockingIOError:
            return taps
        for ev in events:
            if ev.type == ecodes.EV_ABS:
                if ev.code == ecodes.ABS_X:
                    self._rx = ev.value
                elif ev.code == ecodes.ABS_Y:
                    self._ry = ev.value
            elif ev.type == ecodes.EV_KEY and ev.code == ecodes.BTN_TOUCH:
                if ev.value == 1:
                    self._touching = True
                elif ev.value == 0 and self._touching:
                    self._touching = False
                    if self.affine and self._rx is not None and self._ry is not None:
                        taps.append(self.map(self._rx, self._ry))
        return taps

    def wait_raw_tap(self):
        """Block for one press+release; return raw (rx, ry)."""
        rx = ry = None
        touching = False
        for ev in self.dev.read_loop():
            if ev.type == ecodes.EV_ABS:
                if ev.code == ecodes.ABS_X:
                    rx = ev.value
                elif ev.code == ecodes.ABS_Y:
                    ry = ev.value
            elif ev.type == ecodes.EV_KEY and ev.code == ecodes.BTN_TOUCH:
                if ev.value == 1:
                    touching = True
                elif ev.value == 0 and touching and rx is not None and ry is not None:
                    return (rx, ry)
