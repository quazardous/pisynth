"""io/synth.Fluid against a fake fluidsynth TCP shell. Like the real one, the fake handles
commands one at a time on a connection, so a slow `load` delays every later reply."""
import socket
import threading
import time

import pytest

from pisynth.io.synth import Fluid


class FakeFluid:
    def __init__(self, load_delay=0.0):
        self.load_delay = load_delay
        self.fonts = {1: "/sf/01-A.sf3"}
        self.received = []
        self.srv = socket.socket()
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(4)
        self.port = self.srv.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while True:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(c,), daemon=True).start()

    def _serve(self, c):
        buf = b""
        with c:
            while True:
                try:
                    d = c.recv(4096)
                except OSError:
                    return
                if not d:
                    return
                buf += d
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    self._handle(c, line.decode())

    def _handle(self, c, line):
        self.received.append(line)
        cmd, _, arg = line.partition(" ")
        if cmd == "fonts":
            c.sendall(b"ID  Name\n" + b"".join(f"{i:3d}  {p}\n".encode() for i, p in sorted(self.fonts.items())))
        elif cmd == "inst":
            c.sendall(b"000-000 Grand Piano\n000-004 Rhodes\n128-000 Standard\n")
        elif cmd == "load":
            time.sleep(self.load_delay)
            sfid = max(self.fonts) + 1
            self.fonts[sfid] = arg.strip('"')
            c.sendall(f"loaded SoundFont has ID {sfid}\n".encode())
        # select / cc / gain / noteon: silent, like fluidsynth

    def close(self):
        self.srv.close()


@pytest.fixture
def fake():
    f = FakeFluid()
    yield f
    f.close()


def test_fonts_and_presets_are_parsed(fake):
    fs = Fluid("127.0.0.1", fake.port)
    assert fs.fonts() == [(1, "/sf/01-A.sf3")]
    assert fs.presets(1) == [(0, 0, "Grand Piano"), (0, 4, "Rhodes"), (128, 0, "Standard")]


def test_select_broadcasts_to_the_configured_channels(fake):
    fs = Fluid("127.0.0.1", fake.port, channels=[0, 1])
    fs.select(1, 0, 4)
    fs.fonts()                                        # round-trip so the server has read it all
    assert fake.received[:6] == ["cc 0 0 0", "cc 0 32 0", "select 0 1 0 4",
                                 "cc 1 0 0", "cc 1 32 0", "select 1 1 0 4"]


def test_offline_is_reported_not_raised():
    fs = Fluid("127.0.0.1", 1)                        # nothing listens on port 1
    assert fs.connect() is False and fs.fonts() == [] and fs.send("gain 1") is False


def test_quick_query_does_not_wait_for_the_overall_timeout(fake):
    fs = Fluid("127.0.0.1", fake.port)
    fs.connect()
    t = time.monotonic()
    assert fs.fonts(overall=30)
    assert time.monotonic() - t < 2.0


def test_slow_load_still_returns_the_new_font_id():
    fake = FakeFluid(load_delay=1.5)
    try:
        fs = Fluid("127.0.0.1", fake.port)
        assert fs.load("/sf/05-Big.sf2", timeout=10) == 2
    finally:
        fake.close()


def test_send_does_not_block_the_caller(fake):
    fs = Fluid("127.0.0.1", fake.port)
    fs.connect()
    t = time.monotonic()
    for _ in range(5):
        fs.send("noteon 9 76 60")
    assert time.monotonic() - t < 0.2
