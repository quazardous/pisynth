"""Live MIDI source for the web companion (#659).

Reads note events straight off the ALSA sequencer via `aseqdump` on a background thread
and hands each one to a callback (the web server's thread-safe `feed`). It takes its OWN
aseqdump subscription to the keyboard, so it coexists with fluidsynth and the touch UI's
monitor (ALSA-seq allows many subscribers). Stdlib only; no dependency on the pisynth
package — the web service stays self-contained.

The reader is Pi-only (needs ALSA seq); `parse_note` is pure and unit-tested off-device.
"""
import re
import subprocess
import threading

# aseqdump line, e.g.: " 24:0   Note on                 0, note 60, velocity 100"
_NOTE_RE = re.compile(r"Note (on|off)\b.*?\bnote (\d+).*?\bvelocity (\d+)", re.I)


def parse_note(line):
    """An aseqdump line → {"t":"on","n":N,"v":V} / {"t":"off","n":N}, or None. Velocity-0
    note-on is a note-off (MIDI convention)."""
    m = _NOTE_RE.search(line)
    if not m:
        return None
    on = m.group(1).lower() == "on"
    note, vel = int(m.group(2)), int(m.group(3))
    if on and vel > 0:
        return {"t": "on", "n": note, "v": vel}
    return {"t": "off", "n": note}


def auto_port():
    """Best-guess aseqdump target: the first hardware MIDI input (a client carrying
    `card=`), port 0 — i.e. the keyboard. '' if none found (no keyboard plugged in)."""
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
    """Streams the keyboard's note events to `on_event` (a dict) off a background thread."""

    def __init__(self, on_event, port=""):
        self.on_event = on_event
        self.port = port
        self._proc = None
        self._thread = None
        self._stop = threading.Event()

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._proc is not None:
            try:
                self._proc.terminate()
            except OSError:
                pass
            self._proc = None

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
            for line in self._proc.stdout:            # blocks per line; terminate() ends it
                if self._stop.is_set():
                    break
                msg = parse_note(line)
                if msg:
                    self.on_event(msg)
            self._proc = None
            if not self._stop.is_set():               # aseqdump died (keyboard unplugged?) → retry
                self._stop.wait(1.0)
