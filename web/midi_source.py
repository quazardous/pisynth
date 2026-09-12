"""Live MIDI source for the web companion (#659).

One `aseqdump` subscription to the keyboard, opened once at startup and kept open, read on
a dedicated thread (ALSA-seq allows many subscribers: fluidsynth and the touch UI keep
theirs). Each event is packed into a 7-byte binary message — the raw MIDI bytes plus a
timestamp — and handed to the server's thread-safe `feed`. No JSON, no interpretation:
the phone decodes and does everything else.

Wire format (big-endian): status u8 · data1 u8 · data2 u8 · t_ms u32 (monotonic ms, wraps).
`parse_line` / `pack` are pure and unit-tested off-device; the reader needs ALSA seq.
"""
import re
import struct
import subprocess
import threading
import time

FRAME = struct.Struct(">BBBI")

# aseqdump lines, e.g. " 24:0   Note on                 0, note 60, velocity 100"
#                      " 24:0   Control change          0, controller 64, value 127"
_EVENT_RE = re.compile(
    r"(Note on|Note off|Control change)\s+(\d+),\s+(?:note|controller)\s+(\d+),\s+(?:velocity|value)\s+(\d+)",
    re.I)
_STATUS = {"note on": 0x90, "note off": 0x80, "control change": 0xB0}


def parse_line(line):
    """An aseqdump line → (status, data1, data2) raw MIDI bytes, or None for other events.
    A velocity-0 note-on stays a note-on: that's what the keyboard sent (the phone knows)."""
    m = _EVENT_RE.search(line)
    if not m:
        return None
    kind, ch, d1, d2 = m.group(1).lower(), int(m.group(2)), int(m.group(3)), int(m.group(4))
    if not (0 <= ch <= 15 and 0 <= d1 <= 127 and 0 <= d2 <= 127):
        return None
    return (_STATUS[kind] | ch, d1, d2)


def pack(status, d1, d2, t_ms):
    return FRAME.pack(status, d1, d2, t_ms & 0xFFFFFFFF)


def auto_port():
    """The first hardware MIDI input (client carrying `card=`), port 0 — the keyboard. ''
    if none is plugged in."""
    try:
        out = subprocess.run(["aconnect", "-i"], capture_output=True, text=True, timeout=4).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    for ln in out.splitlines():
        m = re.match(r"client\s+\d+\s*:\s*'(.+?)'\s*\[(.*)\]", ln)
        if m and "card=" in m.group(2):
            return f"{m.group(1)}:0"
    return ""


class AlsaSeqSource:
    """Streams the keyboard's events as packed frames to `on_frame(frame, t_read_ns)`."""

    def __init__(self, on_frame, port=""):
        self.on_frame = on_frame
        self.port = port
        self._proc = None
        self._thread = None
        self._stop = threading.Event()

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="midi-source", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        proc, self._proc = self._proc, None
        if proc is not None:
            try:
                proc.terminate()
            except OSError:
                pass

    def _loop(self):
        while not self._stop.is_set():
            port = self.port or auto_port()
            if not port:                              # no keyboard yet → wait and retry
                if self._stop.wait(2.0):
                    break
                continue
            try:
                # stdbuf -oL: line-buffer aseqdump's stdout, else glibc block-buffers it on a
                # pipe and single key-presses stall (same trick as the touch UI's monitor).
                self._proc = subprocess.Popen(["stdbuf", "-oL", "aseqdump", "-p", port],
                                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                              text=True, bufsize=1)
            except OSError:
                if self._stop.wait(2.0):
                    break
                continue
            proc = self._proc
            for line in proc.stdout:                  # blocks per line; terminate() ends it
                t_ns = time.monotonic_ns()
                ev = parse_line(line)
                if ev:
                    self.on_frame(pack(*ev, t_ns // 1_000_000), t_ns)
                if self._stop.is_set():
                    break
            self._proc = None
            if not self._stop.is_set():               # aseqdump ended (keyboard unplugged) → retry
                self._stop.wait(1.0)
