"""Display output adapters (#308): the SPI framebuffer + its backlight.

Implement io.interfaces.Display / BacklightControl so the 3.5" SPI panel can be
swapped (e.g. for HDMI) without touching the UI layer. `partial` (dirty-row
updates, #284) is injected so this module reads no app config.
"""
import glob
import os

import numpy as np


class Framebuffer:
    def __init__(self, dev, partial=False):
        self.dev = dev
        node = os.path.basename(os.path.realpath(dev))
        with open(f"/sys/class/graphics/{node}/virtual_size") as f:
            self.w, self.h = (int(v) for v in f.read().strip().split(","))
        self.partial = partial                      # #284: dirty-row updates (injected; was RENDER_MODE)
        self._prev = None                           # last frame, for diffing

    @staticmethod
    def _encode(img):
        """PIL image -> (h, w) little-endian RGB565 array."""
        arr = np.asarray(img.convert("RGB"), dtype=np.uint16)
        rgb565 = ((arr[..., 0] >> 3) << 11) | ((arr[..., 1] >> 2) << 5) | (arr[..., 2] >> 3)
        return rgb565.astype("<u2")

    @staticmethod
    def _row_band(prev, frame):
        """Smallest [r0, r1) row range covering every row that differs between two
        frames. None when identical; full range when prev is missing/mismatched."""
        if prev is None or prev.shape != frame.shape:
            return (0, frame.shape[0])
        diff = np.any(frame != prev, axis=1)
        if not diff.any():
            return None
        rows = np.nonzero(diff)[0]
        return (int(rows[0]), int(rows[-1]) + 1)

    def blit(self, img):
        frame = self._encode(img)
        if not self.partial:
            with open(self.dev, "wb") as f:
                f.write(frame.tobytes())
            return
        band = self._row_band(self._prev, frame)
        self._prev = frame
        if band is None:
            return                                  # nothing changed: no SPI traffic
        r0, r1 = band
        if r0 == 0 and r1 == self.h:
            with open(self.dev, "wb") as f:
                f.write(frame.tobytes())
        else:                                       # seek to the changed band only
            with open(self.dev, "r+b") as f:
                f.seek(r0 * self.w * 2)
                f.write(frame[r0:r1].tobytes())

    def blit_rows(self, img, r0, r1):
        """Write ONLY framebuffer rows [r0, r1) — a targeted partial update regardless of the
        global full/partial mode (#668). The Home metronome pulse uses it to repaint just the
        top bar per beat, so it's cheap on the slow SPI panel instead of a full-frame write."""
        frame = self._encode(img)
        with open(self.dev, "r+b") as f:
            f.seek(r0 * self.w * 2)
            f.write(frame[r0:r1].tobytes())
        if self.partial:
            self._prev = frame                       # keep the diff base coherent in partial mode


class Backlight:
    """SPI panel backlight via /sys/class/backlight/*/bl_power (0=on, 4=off).
    No-op if absent or not writable — migration 010 grants `video` write access."""

    def __init__(self):
        found = glob.glob("/sys/class/backlight/*/bl_power")
        self.path = found[0] if found else None

    def set(self, on):
        if not self.path:
            return False
        try:
            with open(self.path, "w") as f:
                f.write("0" if on else "4")        # FB_BLANK_UNBLANK / POWERDOWN
            return True
        except OSError:
            return False
