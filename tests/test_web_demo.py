"""Demo mode (#2416): Pi-side scheduling of phone-sent notes into fluidsynth's shell."""
import asyncio
import json

import pytest

from web import demo as D


class Sink:
    def __init__(self):
        self.lines, self.times = [], []
        self.loop = None

    @property
    def connected(self):
        return True

    async def ensure(self):
        return True

    def write(self, lines):
        for ln in lines:
            self.lines.append(ln)
            self.times.append(self.loop.time() if self.loop else 0)


def test_validate_events():
    assert D.validate_events([[0, 0x90, 60, 100], [120.5, 0x80, 60, 0]]) == [(0.0, 0x90, 60, 100), (120.5, 0x80, 60, 0)]
    for bad in (None, "x", [[0, 0x90, 60]], [[0, 0xF0, 1, 2]], [[-1, 0x90, 60, 1]], [[0, 0x90, 128, 1]],
                [[0, 0x90, "60", 1]], [[0, 0x90, 60, 1]] * (D.MAX_BATCH + 1), [[D.MAX_SPAN_MS + 1, 0x90, 60, 1]]):
        assert D.validate_events(bad) is None


def test_to_shell_folds_channels_keeps_drums_and_pedal_only():
    assert D.to_shell(0x93, 60, 90)[0] == "noteon 0 60 90"
    assert D.to_shell(0x99, 36, 90)[0] == "noteon 9 36 90"
    assert D.to_shell(0x90, 60, 0)[0] == "noteoff 0 60"
    assert D.to_shell(0x80, 60, 12)[0] == "noteoff 0 60"
    assert D.to_shell(0xB0, 64, 127)[0] == "cc 0 64 127"
    assert D.to_shell(0xB0, 7, 100) is None                 # volume etc. stay the user's


def run(coro):
    return asyncio.run(asyncio.wait_for(coro, 10))


def test_plays_in_order_on_the_pi_clock_and_stop_releases_everything():
    async def go():
        loop = asyncio.get_running_loop()
        sink = Sink()
        sink.loop = loop
        p = D.DemoPlayer(sink, loop)
        t = loop.time()
        p.play([(0, 0x90, 60, 100), (100, 0x90, 64, 100), (200, 0xB0, 64, 127), (300, 0x80, 60, 0)], reset=True, owner="a")
        await asyncio.sleep(0.5)
        assert sink.lines == ["noteon 0 60 100", "noteon 0 64 100", "cc 0 64 127", "noteoff 0 60"]
        gaps = [round((b - a) * 1000) for a, b in zip(sink.times, sink.times[1:])]
        assert all(90 <= g <= 115 for g in gaps), gaps               # 100 ms apart, ±jitter
        assert 0.14 <= sink.times[0] - t <= 0.2                      # anchored LEAD_MS ahead
        assert p.active and p.stats()["sent"] == 4
        p.stop()
        assert sink.lines[-2:] == ["noteoff 0 64", "cc 0 64 0"]      # held note + pedal released
        assert not p.active
    run(go())


def test_a_long_rest_does_not_reset_the_timeline():
    async def go():
        loop = asyncio.get_running_loop()
        sink = Sink()
        sink.loop = loop
        p = D.DemoPlayer(sink, loop)
        t = loop.time()
        p.play([(0, 0x90, 60, 90), (10, 0x80, 60, 0)], reset=True, owner="a")
        await asyncio.sleep(0.3)
        p.play([(600, 0x90, 62, 90)], reset=False, owner="a")         # next batch after a silence
        await asyncio.sleep(0.6)
        assert sink.lines[-1] == "noteon 0 62 90"
        assert 0.7 <= sink.times[-1] - t <= 0.8                      # 150 ms lead + 600 ms, not re-anchored
    run(go())


def test_only_the_owner_extends_and_disconnect_stops():
    async def go():
        loop = asyncio.get_running_loop()
        sink = Sink()
        sink.loop = loop
        p = D.DemoPlayer(sink, loop)
        p.play([(0, 0x90, 60, 90), (5000, 0x80, 60, 0)], reset=True, owner="a")
        assert p.play([(10, 0x90, 70, 90)], reset=False, owner="b") is False
        await asyncio.sleep(0.25)
        p.release_owner("b")
        assert p.active
        p.release_owner("a")
        assert not p.active and sink.lines[-1] == "noteoff 0 60"
    run(go())


def test_events_the_pi_is_too_late_for_are_dropped():
    async def go():
        loop = asyncio.get_running_loop()
        sink = Sink()
        sink.loop = loop
        p = D.DemoPlayer(sink, loop)
        p.play([(0, 0x90, 60, 90)], reset=True, owner="a")
        p._t0 -= 1.0                                                  # pretend the timeline started 1 s ago
        p.play([(100, 0x90, 61, 90)], reset=False, owner="a")
        assert p.dropped == 1
    run(go())


# ---- through the real server + a fake fluidsynth shell ----
@pytest.fixture
def fake_shell():
    got = []

    async def handle(r, w):
        while True:
            line = await r.readline()
            if not line:
                break
            got.append((asyncio.get_running_loop().time(), line.decode().strip()))
    return got, handle


def test_phone_play_command_reaches_the_synth_shell(tmp_path, fake_shell):
    pytest.importorskip("ssl")
    from tests.test_web_server import Harness, cert as _cert  # noqa: F401  (reuse the TLS harness)
    import shutil
    import subprocess
    if shutil.which("openssl") is None:
        pytest.skip("needs openssl")
    c, k = str(tmp_path / "c.pem"), str(tmp_path / "k.pem")
    subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                    "-nodes", "-keyout", k, "-out", c, "-days", "1", "-subj", "/CN=t"], check=True, capture_output=True)
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("x")
    got, handle = fake_shell

    async def go():
        shell = await asyncio.start_server(handle, "127.0.0.1", 0)
        async with Harness((c, k), str(static)) as h:
            h.app.synth = ("127.0.0.1", shell.sockets[0].getsockname()[1])
            h.app.demo.sink.port = h.app.synth[1]
            cookie = await h.pair()
            _, ws = await h.ws(cookie)
            await ws.send_json({"t": "play", "reset": True, "ev": [[0, 144, 60, 100], [50, 128, 60, 0]]})
            reply = json.loads((await asyncio.wait_for(ws.receive(), 5)).data)
            assert reply["state"] == "playing"
            await asyncio.sleep(0.4)
            assert [ln for _, ln in got] == ["noteon 0 60 100", "noteoff 0 60"]
            assert h.app.stats()["demo"]["sent"] == 2
            await ws.close()
        shell.close()
    run(go())


def test_synth_settings_are_relayed_to_the_ui_and_state_pushed(tmp_path):
    """#2417: phone {"t":"synth"} → pisynth-web → fake touch-UI JSON socket → reply; UI watch → phone."""
    import shutil
    import subprocess
    from tests.test_web_server import Harness
    if shutil.which("openssl") is None:
        pytest.skip("needs openssl")
    c, k = str(tmp_path / "c.pem"), str(tmp_path / "k.pem")
    subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                    "-nodes", "-keyout", k, "-out", c, "-days", "1", "-subj", "/CN=t"], check=True, capture_output=True)
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("x")
    seen, watchers = [], []

    async def fake_ui(r, w):
        msg = json.loads(await r.readline())
        seen.append(msg)
        if msg["op"] == "watch":
            watchers.append(w)
            w.write(b'{"state": {"gain": 2.5}}\n')
            await w.drain()
            await asyncio.sleep(5)
            return
        w.write(json.dumps({"ok": True, "state": {"gain": msg.get("value", 2.5)}}).encode() + b"\n")
        await w.drain()
        w.close()

    async def ws_json(ws):
        return json.loads((await asyncio.wait_for(ws.receive(), 5)).data)

    async def go():
        ui = await asyncio.start_server(fake_ui, "127.0.0.1", 0)
        async with Harness((c, k), str(static)) as h:
            h.app.ui.port = ui.sockets[0].getsockname()[1]
            h.app.ui._watch_task.cancel()
            h.app.ui._watch_task = None
            cookie = await h.pair()
            _, ws = await h.ws(cookie)
            await asyncio.sleep(0.05)
            h.app.ui.start_watch()
            pushed = await ws_json(ws)                                       # UI watch → phone
            assert pushed == {"t": "synth", "state": {"gain": 2.5}}
            await ws.send_json({"t": "synth", "op": "set", "key": "gain", "value": 3.1, "req": 7})
            reply = await ws_json(ws)
            assert reply["op"] == "set" and reply["req"] == 7 and reply["ok"] and reply["state"]["gain"] == 3.1
            assert {"op": "set", "key": "gain", "value": 3.1} in seen
            await ws.send_json({"t": "synth", "op": "delete_everything"})         # not relayed
            await asyncio.sleep(0.1)
            assert all(m["op"] in ("watch", "set", "companion") for m in seen)
            assert {"op": "companion", "live": True} in seen                  # #2658: the UI knows a phone is here
            await ws.close()
        ui.close()
    run(go())
