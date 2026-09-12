"""Synth control-plane adapter (#308): fluidsynth's TCP shell client.

Implements io.interfaces.SynthBackend. `channels` (the MIDI channels select()
broadcasts to) is injected so this module reads no app config.
"""
import re
import socket
import time


class Fluid:
    """Client for fluidsynth's TCP shell (:9800). Fire-and-forget for control
    commands (gain/select); query() for listings (fonts/inst)."""

    def __init__(self, host, port, channels=range(16)):
        self.host, self.port, self.sock = host, port, None
        self.channels = channels                   # MIDI chans select() targets (#308, was KBD_CHANNELS)

    @property
    def online(self):
        return self.sock is not None

    def connect(self):
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=1)
            self._drain()                              # swallow any banner/prompt
        except OSError:
            self.sock = None
        return self.online

    def _drain(self):
        """Discard whatever replies are already buffered, WITHOUT waiting (#2408: this used to
        block 0.3 s on every command, on the UI thread). Marks the link down on EOF."""
        sock = self.sock
        old = sock.gettimeout()
        sock.setblocking(False)                        # (MSG_DONTWAIT still waits on a timeout socket)
        try:
            while True:
                if not sock.recv(4096):                # server closed the connection
                    self.sock = None
                    return
        except (BlockingIOError, InterruptedError):
            pass
        except OSError:
            self.sock = None
        finally:
            sock.settimeout(old)

    def alive(self):
        """Cheap liveness check, no round-trip: drains buffered replies without waiting and
        notices a closed connection (the synth exited or restarted)."""
        if self.sock is not None:
            self._drain()
        return self.online

    def send(self, *cmds):
        if not self.online and not self.connect():
            return False
        try:
            self.sock.settimeout(1.0)
            self.sock.sendall(("\n".join(cmds) + "\n").encode())
            self._drain()                              # keep the socket reply buffer clean
            return True
        except OSError:
            self.sock = None
            return False

    def query(self, cmd, idle=0.3, overall=2.0):
        """Send a command and collect the reply lines. Waits up to `overall` for the reply to
        START — fluidsynth runs shell commands one at a time, so after a slow `load` the next
        reply only comes once it is done (#375) — then stops after `idle` s of silence, since
        the shell has no end-of-reply marker (#2408: it used to give up after the first `idle`
        of silence, so `overall` never applied)."""
        if not self.online and not self.connect():
            return []
        self._drain()                                  # stale replies must not pose as this one
        if not self.online and not self.connect():
            return []
        try:
            self.sock.settimeout(1.0)
            self.sock.sendall((cmd + "\n").encode())
        except OSError:
            self.sock = None
            return []
        chunks, deadline = [], time.monotonic() + overall
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                break
            try:
                self.sock.settimeout(min(idle, left) if chunks else left)
                data = self.sock.recv(4096)
            except socket.timeout:
                break
            except OSError:
                self.sock = None
                break
            if not data:                               # server closed the connection
                self.sock = None
                break
            chunks.append(data)
        return b"".join(chunks).decode(errors="ignore").splitlines()

    def fonts(self, overall=2.0):
        """[(sfid, path), ...] of loaded soundfonts, in load order. `overall` bounds the
        wait — raised by load() so a slow `load` reply isn't cut short (#375)."""
        out = []
        for ln in self.query("fonts", overall=overall):
            m = re.match(r"\s*(\d+)\s+(.*\.(?:sf2|sf3))\s*$", ln, re.I)
            if m:
                out.append((int(m.group(1)), m.group(2)))
        return out

    def presets(self, sfid):
        """[(bank, prog, name), ...] for a soundfont (fluidsynth `inst`)."""
        out = []
        for ln in self.query(f"inst {sfid}"):
            m = re.match(r"\s*(\d+)-(\d+)\s+(.+?)\s*$", ln)
            if m:
                out.append((int(m.group(1)), int(m.group(2)), m.group(3)))
        return out

    def select(self, sfid, bank, prog):
        cmds = []
        for ch in self.channels:
            cmds += [f"cc {ch} 0 0", f"cc {ch} 32 0", f"select {ch} {sfid} {bank} {prog}"]
        self.send(*cmds)

    def select_one(self, ch, sfid, bank, prog):
        """Select a preset on a SINGLE channel (#655): used to put the metronome's click
        (a GM drum kit, bank 128) on its reserved channel without touching the keyboard ones."""
        return self.send(f"select {ch} {sfid} {bank} {prog}")

    def load(self, path, timeout=45):
        """Load a soundfont and return its new font id, or None. Used to keep a single
        soundfont resident at a time (#334). fluidsynth processes the shell serially, so the
        follow-up `fonts` only replies once the load has finished — wait up to `timeout`s
        for it, since big SF2 take 10-20s on a Pi 3B+ (#375)."""
        if not self.send(f'load "{path}"'):
            return None
        key = path.rsplit("/", 1)[-1]
        for sfid, p in self.fonts(overall=timeout):
            if p.rsplit("/", 1)[-1] == key:
                return sfid
        return None

    def unload(self, sfid):
        """Unload a soundfont by id (#334)."""
        self.send(f"unload {sfid}")

    def set_gain(self, gain):
        self.send(f"gain {gain:.2f}")
