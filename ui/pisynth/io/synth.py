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
            self.sock.settimeout(0.3)
            self._drain()                              # swallow any banner/prompt
        except OSError:
            self.sock = None
        return self.online

    def _drain(self):
        try:
            while self.sock.recv(4096):
                pass
        except OSError:
            pass

    def send(self, *cmds):
        if not self.online and not self.connect():
            return False
        try:
            self.sock.sendall(("\n".join(cmds) + "\n").encode())
            self._drain()                              # keep the socket reply buffer clean
            return True
        except OSError:
            self.sock = None
            return False

    def query(self, cmd, idle=0.3, overall=2.0):
        """Send a command and collect the reply lines (read until idle)."""
        if not self.online and not self.connect():
            return []
        try:
            self.sock.settimeout(idle)
            self.sock.sendall((cmd + "\n").encode())
        except OSError:
            self.sock = None
            return []
        chunks, deadline = [], time.time() + overall
        while time.time() < deadline:
            try:
                data = self.sock.recv(4096)
            except socket.timeout:
                break
            except OSError:
                self.sock = None
                break
            if not data:
                break
            chunks.append(data)
        return b"".join(chunks).decode(errors="ignore").splitlines()

    def fonts(self):
        """[(sfid, path), ...] of loaded soundfonts, in load order."""
        out = []
        for ln in self.query("fonts"):
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

    def set_gain(self, gain):
        self.send(f"gain {gain:.2f}")
