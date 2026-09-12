"""Demo mode (#2416): the phone plays a score THROUGH pisynth's synth.

The phone owns the music (file parsing, tempo, what to play); the Pi only turns timed notes
into sound, on its own clock — so Wi-Fi jitter never reaches the rhythm. The phone sends
short batches of upcoming events, each timed in ms from the start of the demo; the first
batch (`reset`) anchors that start LEAD_MS in the future. Events are fired from the asyncio
loop's timer into fluidsynth's local shell (`noteon` / `noteoff` / `cc`).

Safety: bounded batches, events validated, and every sounding note is released on stop,
on the phone's disconnect and when another browser is paired — never a stuck note.
"""
import asyncio
import collections

LEAD_MS = 150                 # anchor the timeline slightly in the future: first batch has time to land
LATE_DROP_MS = 250            # an event this late (the Pi was busy) is dropped, not played out of time
MAX_BATCH = 512
MAX_SPAN_MS = 10 * 60 * 1000  # a batch may not schedule further than 10 min ahead
DRUM_CHANNEL = 9              # GM percussion stays on its channel; everything else plays the keyboard's
KEYBOARD_CHANNEL = 0


def validate_events(events):
    """[[ms, status, d1, d2], ...] → list of tuples, or None if anything is off."""
    if not isinstance(events, list) or len(events) > MAX_BATCH:
        return None
    out = []
    for ev in events:
        if not (isinstance(ev, list) and len(ev) == 4 and all(isinstance(x, (int, float)) for x in ev)):
            return None
        ms, status, d1, d2 = float(ev[0]), int(ev[1]), int(ev[2]), int(ev[3])
        if not (0 <= ms <= MAX_SPAN_MS and 0x80 <= status <= 0xBF and 0 <= d1 <= 127 and 0 <= d2 <= 127):
            return None
        out.append((ms, status, d1, d2))
    return out


def to_shell(status, d1, d2):
    """Raw MIDI → one fluidsynth shell command (or None). Channels are folded onto the keyboard
    channel (the selected instrument), except GM drums on channel 9."""
    kind, ch = status & 0xF0, status & 0x0F
    ch = DRUM_CHANNEL if ch == DRUM_CHANNEL else KEYBOARD_CHANNEL
    if kind == 0x90 and d2 > 0:
        return f"noteon {ch} {d1} {d2}", ("on", ch, d1)
    if kind in (0x80, 0x90):
        return f"noteoff {ch} {d1}", ("off", ch, d1)
    if kind == 0xB0 and d1 == 64:                      # sustain pedal only
        return f"cc {ch} 64 {d2}", None
    return None


class ShellSink:
    """Persistent connection to fluidsynth's local shell. write() never blocks the loop; while
    (re)connecting, lines are dropped — a demo note late by a reconnect is worse than silence."""

    def __init__(self, host="127.0.0.1", port=9800):
        self.host, self.port = host, port
        self._writer = None
        self._drain_task = None

    @property
    def connected(self):
        return self._writer is not None and not self._writer.is_closing()

    async def ensure(self):
        if self.connected:
            return True
        try:
            reader, self._writer = await asyncio.wait_for(asyncio.open_connection(self.host, self.port), 2)
        except (OSError, asyncio.TimeoutError):
            self._writer = None
            return False
        self._drain_task = asyncio.ensure_future(self._drain(reader))
        return True

    async def _drain(self, reader):
        try:
            while await reader.read(4096):
                pass
        except OSError:
            pass
        self._writer = None

    def write(self, lines):
        if self.connected and lines:
            self._writer.write(("\n".join(lines) + "\n").encode())

    def close(self):
        if self._writer is not None:
            self._writer.close()
            self._writer = None


class DemoPlayer:
    def __init__(self, sink, loop=None):
        self.sink = sink
        self.loop = loop or asyncio.get_event_loop()
        self.owner = None                                 # the WebSocket that started it
        self._t0 = 0.0
        self._handles = []
        self._sounding = set()                            # (ch, note) currently on
        self._pedal = set()                               # channels with sustain down
        self._last_due = 0.0
        self.sent = 0
        self.dropped = 0
        self.late_ms = collections.deque(maxlen=4096)

    @property
    def active(self):
        """A demo is running: started and not stopped, and not past its last note (+2 s)."""
        return self.owner is not None and self.loop.time() <= self._last_due + 2.0

    def play(self, events, reset, owner=None):
        """Schedule a validated batch. `reset` starts a new timeline (stopping any current one)."""
        now = self.loop.time()
        if reset or self.owner is None:                   # a new timeline; a rest in the score must NOT reset it
            self.stop()
            self._t0 = now + LEAD_MS / 1000
            self._last_due = self._t0
            self.owner = owner
        elif owner is not self.owner:
            return False                                  # only the demo's owner extends it
        scheduled = 0
        for ms, status, d1, d2 in events:
            due = self._t0 + ms / 1000
            if due < now - LATE_DROP_MS / 1000:
                self.dropped += 1
                continue
            self._handles.append(self.loop.call_at(due, self._fire, due, status, d1, d2))
            self._last_due = max(self._last_due, due)
            scheduled += 1
        self._handles = [h for h in self._handles if not h.cancelled() and h.when() >= now - 1]
        return scheduled

    def _fire(self, due, status, d1, d2):
        late = self.loop.time() - due
        if late > LATE_DROP_MS / 1000:
            self.dropped += 1
            return
        cmd = to_shell(status, d1, d2)
        if cmd is None:
            return
        line, note = cmd
        if note:
            kind, ch, n = note
            (self._sounding.add if kind == "on" else self._sounding.discard)((ch, n))
        elif status & 0xF0 == 0xB0:
            ch = DRUM_CHANNEL if status & 0x0F == DRUM_CHANNEL else KEYBOARD_CHANNEL
            (self._pedal.add if d2 >= 64 else self._pedal.discard)(ch)
        self.sink.write([line])
        self.sent += 1
        self.late_ms.append(late * 1000)

    def stop(self):
        """Cancel everything pending and release every sounding note and pedal."""
        for h in self._handles:
            h.cancel()
        self._handles = []
        lines = [f"noteoff {ch} {n}" for ch, n in sorted(self._sounding)]
        lines += [f"cc {ch} 64 0" for ch in sorted(self._pedal)]
        self.sink.write(lines)
        self._sounding.clear()
        self._pedal.clear()
        self.owner = None

    def release_owner(self, owner):
        """The owning phone disconnected: stop its demo."""
        if owner is not None and owner is self.owner:
            self.stop()

    def stats(self):
        s = sorted(self.late_ms)

        def pct(p):
            return round(s[min(len(s) - 1, int(len(s) * p))], 2) if s else None
        return {"active": self.active, "sent": self.sent, "dropped": self.dropped,
                "late_ms": {"p50": pct(0.5), "p99": pct(0.99), "n": len(s)}}

