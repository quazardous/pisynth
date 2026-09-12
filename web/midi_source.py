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


class CommandSource(AlsaSeqSource):
    """Same parsing, any command printing aseqdump lines — e.g. the Pi's keyboard over SSH
    (dev bridge, #2415): `ssh <pi> aseqdump -p <keyboard>`. Reconnects when it ends."""

    def __init__(self, on_frame, argv):
        super().__init__(on_frame)
        self.argv = argv

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._proc = subprocess.Popen(self.argv, stdin=subprocess.PIPE,   # held open: EOF = we're gone
                                              stdout=subprocess.PIPE, stderr=None,   # errors → service log
                                              text=True, bufsize=1)
            except OSError:
                if self._stop.wait(3.0):
                    break
                continue
            for line in self._proc.stdout:
                t_ns = time.monotonic_ns()
                ev = parse_line(line)
                if ev:
                    self.on_frame(pack(*ev, t_ns // 1_000_000), t_ns)
                if self._stop.is_set():
                    break
            self._proc = None
            if not self._stop.is_set():
                self._stop.wait(3.0)


def pi_bridge_argv(host):
    """SSH command streaming the Pi's first hardware keyboard as aseqdump lines (#2415)."""
    remote = ("p=$(LC_ALL=C aconnect -i | sed -n \"s/^client [0-9]* *: '\\(.*\\)' \\[.*card=.*/\\1/p\" | head -n1); "
              "[ -n \"$p\" ] || { echo 'no MIDI keyboard on the Pi' >&2; sleep 5; exit 1; }; "
              # No tty, so a dropped SSH session sends no SIGHUP: aseqdump would outlive it. Keep
              # it as a child and kill it once our stdin (the SSH channel) closes.
              "stdbuf -oL aseqdump -p \"$p:0\" & a=$!; cat >/dev/null; kill $a")
    return ["ssh", "-o", "BatchMode=yes", "-o", "ServerAliveInterval=10", host, remote]


# ---- simulator (dev, #2415): plausible playing with no keyboard at all ----
SIM_PATTERNS = {
    # (notes, hold seconds) steps; chords are lists; None = rest
    "scale": [([n], 0.25) for n in (60, 62, 64, 65, 67, 69, 71, 72)] + [(None, 0.5)],
    "chords": [([48, 60, 64, 67], 1.0), ([45, 57, 60, 64], 1.0), ([41, 57, 60, 65], 1.0), ([43, 55, 59, 62, 65], 1.0)],
    "arpeggio": [([n], 0.15) for n in (57, 60, 64, 69, 72, 69, 64, 60)],
}


class SimSource:
    """Plays SIM_PATTERNS in a loop (scale → chords with sustain pedal → arpeggio), with
    human-ish velocity jitter, as the same 7-byte frames. `speed` scales the tempo."""

    def __init__(self, on_frame, speed=1.0, seed=None):
        import random
        self.on_frame, self.speed = on_frame, max(0.1, float(speed))
        self._rng = random.Random(seed)
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="midi-sim", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _send(self, status, d1, d2):
        t_ns = time.monotonic_ns()
        self.on_frame(pack(status, d1, d2, t_ns // 1_000_000), t_ns)

    def steps(self):
        """The event script, as (delay_s, status, d1, d2) — pure, for tests."""
        out = []
        for name in ("scale", "chords", "arpeggio"):
            pedal = name == "chords"
            if pedal:
                out.append((0.0, 0xB0, 64, 127))
            for notes, hold in SIM_PATTERNS[name]:
                if notes is None:
                    out.append((hold, None, 0, 0))
                    continue
                for i, n in enumerate(notes):
                    out.append((0.012 if i else 0.0, 0x90, n, self._rng.randint(60, 110)))   # rolled chord
                out.append((hold, None, 0, 0))
                for n in notes:
                    out.append((0.0, 0x80, n, 0))
            if pedal:
                out.append((0.0, 0xB0, 64, 0))
            out.append((0.6, None, 0, 0))
        return out

    def _loop(self):
        while not self._stop.is_set():
            for delay, status, d1, d2 in self.steps():
                if delay and self._stop.wait(delay / self.speed):
                    return
                if status is not None:
                    self._send(status, d1, d2)


def make_source(on_frame, env):
    """Pick the MIDI source from the environment: aseqdump (default, on the Pi) | sim | pi."""
    kind = env.get("PISYNTH_WEB_MIDI_SOURCE", "aseqdump")
    if kind == "sim":
        return SimSource(on_frame, speed=env.get("PISYNTH_WEB_SIM_SPEED", "1"))
    if kind == "pi":
        host = env.get("PISYNTH_HOST", "")
        if not host:
            raise SystemExit("[pisynth-web] PISYNTH_WEB_MIDI_SOURCE=pi needs PISYNTH_HOST")
        return CommandSource(on_frame, pi_bridge_argv(host))
    return AlsaSeqSource(on_frame, port=env.get("PISYNTH_WEB_MIDI_PORT", ""))
