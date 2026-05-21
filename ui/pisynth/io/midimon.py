"""MIDI monitor backend (#331): reads note events from a chosen ALSA-seq source via
`aseqdump` on a background thread, so the Test-keyboard screen can light up keys live.
Reads the keyboard DIRECTLY (ALSA seq), independent of fluidsynth — so it works even when
the synth is down (it isolates 'does the keyboard send MIDI?' from 'does the synth play?').
"""
import os
import re
import subprocess
import threading

# aseqdump line, e.g.: " 28:0   Note on                 0, note 60, velocity 100"
_NOTE_RE = re.compile(r"Note (on|off)\b.*?\bnote (\d+).*?\bvelocity (\d+)", re.I)


class MidiMonitor:
    def __init__(self):
        self.active = set()          # MIDI note numbers currently held down
        self.last = None             # last note-on number (for the readout)
        self.count = 0               # total note-ons seen (proves MIDI is flowing)
        self.lo = self.hi = None     # min/max note seen → the 'detected layout' range
        self._proc = None
        self._thread = None
        self._stop = threading.Event()
        self._wake = None            # write-end of a pipe; ping the UI per event

    def set_wake(self, fd):
        self._wake = fd

    def open(self, port):
        """Start dumping `port` (an `aseqdump -p` target, e.g. 'Keystation 61 MK3')."""
        self.close()
        self.active, self.last, self.count, self.lo, self.hi = set(), None, 0, None, None
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, args=(port,), daemon=True)
        self._thread.start()

    def close(self):
        self._stop.set()
        if self._proc is not None:
            try:
                self._proc.terminate()
            except OSError:
                pass
            self._proc = None
        self._thread = None

    def _loop(self, port):
        try:
            self._proc = subprocess.Popen(["aseqdump", "-p", port], stdout=subprocess.PIPE,
                                          stderr=subprocess.DEVNULL, text=True, bufsize=1)
        except OSError:
            return
        for line in self._proc.stdout:                # blocks per line; terminate() ends it
            if self._stop.is_set():
                break
            self._feed(line)

    def _feed(self, line):
        m = _NOTE_RE.search(line)
        if not m:
            return
        on, note, vel = m.group(1).lower() == "on", int(m.group(2)), int(m.group(3))
        if on and vel > 0:                            # note on (velocity 0 == note off, MIDI convention)
            self.active.add(note)
            self.last = note
            self.count += 1
            self.lo = note if self.lo is None else min(self.lo, note)
            self.hi = note if self.hi is None else max(self.hi, note)
        else:
            self.active.discard(note)
        if self._wake is not None:
            try:
                os.write(self._wake, b"x")
            except OSError:
                pass
