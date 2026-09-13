"""web/server.py over real loopback sockets: HTTPS with a throwaway self-signed cert, pairing, the
MIDI WebSocket, the library and the loopback admin API (#659, aiohttp since #2428)."""
import asyncio
import gzip
import json
import shutil
import subprocess
import time

import aiohttp
import pytest
from yarl import URL

from web.auth import Auth
from web.server import WebCompanion, cert_fingerprint, load_static, make_ssl_context

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="needs openssl to mint a test cert")


@pytest.fixture(scope="module")
def cert(tmp_path_factory):
    d = tmp_path_factory.mktemp("tls")
    c, k = str(d / "cert.pem"), str(d / "key.pem")
    subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                    "-nodes", "-keyout", k, "-out", c, "-days", "1", "-subj", "/CN=pisynth-test"],
                   check=True, capture_output=True)
    return c, k


@pytest.fixture
def static(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>pisynth</title>" + "x" * 500)
    (tmp_path / "sw.js").write_text("self.addEventListener('fetch', () => {});")
    return str(tmp_path)


def run(coro):
    return asyncio.run(asyncio.wait_for(coro, 20))


class Harness:
    def __init__(self, cert, static, library=None, ca=None):
        self.app = WebCompanion(Auth(), load_static(static), host="127.0.0.1", port=0, admin_port=0,
                                ssl_ctx=make_ssl_context(*cert), fingerprint=cert_fingerprint(cert[0]),
                                synth=("127.0.0.1", 1), ui=("127.0.0.1", 1), library=library,
                                ca_cert=ca, setup_port=0 if ca else None, setup_host="127.0.0.1")

    async def __aenter__(self):
        await self.app.start()
        self.port, self.admin_port = self.app.port, self.app.admin_port
        # no cookie jar (tests pass Cookie by hand), no auto-gunzip (tests look at the bytes)
        self.http_session = aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar(), auto_decompress=False)
        return self

    async def __aexit__(self, *exc):
        await self.http_session.close()
        await self.app.stop()

    def url(self, path, admin=False):
        base = f"http://127.0.0.1:{self.admin_port}" if admin else f"https://127.0.0.1:{self.port}"
        return URL(base + path, encoded=True)                    # keep %2F etc. exactly as written

    async def http(self, method, path, headers=None, body=b"", admin=False):
        async with self.http_session.request(method, self.url(path, admin), headers=headers or {},
                                             data=body or None, ssl=False) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, await r.read()

    async def pair(self):
        _, _, tok = await self.http("POST", "/admin/token", admin=True)
        code, h, _ = await self.http("POST", "/pair", body=json.dumps({"token": json.loads(tok)["token"]}).encode())
        assert code == 200
        return h["set-cookie"].split(";")[0]

    async def ws(self, cookie=None, origin=None):
        """(status, ws or None)."""
        headers = {"Cookie": cookie} if cookie else {}
        if origin:
            headers["Origin"] = origin
        try:
            ws = await self.http_session.ws_connect(self.url("/ws"), headers=headers, ssl=False, autoping=True)
            self.hello = json.loads((await asyncio.wait_for(ws.receive(), 5)).data)   # the server greets first
            return 101, ws
        except aiohttp.WSServerHandshakeError as e:
            return e.status, None


def test_static_is_served_gzipped_with_etag_and_304(cert, static):
    async def go():
        async with Harness(cert, static) as h:
            code, hd, body = await h.http("GET", "/", {"Accept-Encoding": "gzip"})
            assert code == 200 and hd["content-encoding"] == "gzip" and gzip.decompress(body).startswith(b"<!doctype")
            assert "default-src 'self'" in hd["content-security-policy"] and hd["x-content-type-options"] == "nosniff"
            assert hd["server"] == "pisynth"                                     # no framework name/version
            code, _, _ = await h.http("GET", "/index.html", {"If-None-Match": hd["etag"]})
            assert code == 304
            for route in ("/latency", "/play", "/listen", "/about", "/sound", "/demo", "/display"):
                assert (await h.http("GET", route))[0] == 200, route
            assert (await h.http("GET", "/../../etc/passwd"))[0] == 404
            assert (await h.http("DELETE", "/"))[0] == 405
    run(go())


def test_setup_page_serves_only_the_ca_and_its_instructions(cert, static):
    async def go():
        async with Harness(cert, static, ca=cert[0]) as h:              # (the test cert stands in for the CA)
            fp = cert_fingerprint(cert[0])
            _, _, tok = await h.http("POST", "/admin/token", admin=True)
            info = json.loads(tok)
            assert info["setup_port"] == h.app.setup_port and info["ca_fingerprint"] == fp
            base = f"http://127.0.0.1:{h.app.setup_port}"
            async with h.http_session.get(base + "/") as r:
                page = await r.text()
                assert r.status == 200 and fp in page and f'data-port="{h.port}"' in page
                assert 'id="anyway"' in page                                    # the CA is optional (a warning to accept)
                assert "connect-src 'self' https:" in r.headers["Content-Security-Policy"]
            async with h.http_session.get(base + "/pisynth-ca.crt") as r:
                assert r.status == 200 and (await r.text()).startswith("-----BEGIN CERTIFICATE-----")
                assert r.headers["Content-Type"] == "application/x-x509-ca-cert"
            async with h.http_session.get(base + "/pisynth-ca.cer") as r:
                der = await r.read()
                assert r.status == 200 and der[0] == 0x30                       # DER SEQUENCE
            async with h.http_session.get(base + "/setup.js") as r:
                assert r.status == 200 and "no-cors" in await r.text()
            for path in ("/api/session", "/ws", "/admin/token", "/pair"):         # nothing else on plain HTTP
                async with h.http_session.get(base + path) as r:
                    assert r.status == 404, path
        async with Harness(cert, static) as h:                                   # no CA: no setup page, plain token
            _, _, tok = await h.http("POST", "/admin/token", admin=True)
            assert "setup_port" not in json.loads(tok) and h.app.setup_port is None
    run(go())


def test_pairing_flow_and_single_use_token(cert, static):
    async def go():
        async with Harness(cert, static) as h:
            assert (await h.http("GET", "/api/session"))[0] == 401
            code, _, tok = await h.http("POST", "/admin/token", admin=True)
            info = json.loads(tok)
            assert code == 200 and info["port"] == h.port and info["fingerprint"].count(":") == 31
            body = json.dumps({"token": info["token"]}).encode()
            code, hd, _ = await h.http("POST", "/pair", body=body)
            cookie = hd["set-cookie"]
            assert code == 200 and "HttpOnly" in cookie and "Secure" in cookie and "SameSite=Strict" in cookie
            assert (await h.http("GET", "/api/session", {"Cookie": cookie.split(";")[0]}))[0] == 204
            assert (await h.http("POST", "/pair", body=body))[0] == 403            # replay
            assert (await h.http("POST", "/pair", body=b"not json"))[0] == 400
            assert (await h.http("POST", "/pair", body=b"x" * 5000))[0] == 413
    run(go())


def test_the_paired_browser_can_unpair_itself(cert, static):
    async def go():
        async with Harness(cert, static) as h:
            assert (await h.http("POST", "/api/unpair"))[0] == 401
            c = {"Cookie": await h.pair()}
            assert (await h.http("GET", "/api/unpair", c))[0] in (404, 405)      # only POST unpairs
            assert (await h.http("POST", "/api/unpair", {**c, "Origin": "https://evil.example"}))[0] == 403
            code, hd, _ = await h.http("POST", "/api/unpair", c)
            assert code == 204 and "Max-Age=0" in hd["set-cookie"]
            assert (await h.http("GET", "/api/session", c))[0] == 401
    run(go())


def test_midi_library_routes(cert, static, tmp_path):
    from web.library import MidiLibrary
    midi = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x01\xe0" + b"\0" * 64
    lib = MidiLibrary(tmp_path / "midi")

    async def go():
        async with Harness(cert, static, library=lib) as h:
            assert (await h.http("GET", "/api/midi"))[0] == 401                          # pair first
            c = {"Cookie": await h.pair()}
            code, _, body = await h.http("POST", "/api/midi?dir=Mes%20morceaux&name=F%C3%BCr%20Elise.mid", c, midi)
            assert code == 201 and json.loads(body)["path"] == "Mes morceaux/Für Elise.mid"
            evil = {**c, "Origin": "https://evil.example"}
            assert (await h.http("POST", "/api/midi?name=x.mid", evil, midi))[0] == 403    # cross-site
            code, _, body = await h.http("GET", "/api/midi", c)
            paths = [e["path"] for e in json.loads(body)["entries"]]
            assert paths == ["Mes morceaux", "Mes morceaux/Für Elise.mid"]
            code, hd, body = await h.http("GET", "/api/midi/Mes%20morceaux/F%C3%BCr%20Elise.mid", c)
            assert code == 200 and body == midi and hd["content-type"] == "audio/midi"
            assert (await h.http("GET", "/api/midi/..%2F..%2Fetc%2Fpasswd.mid", c))[0] == 400
            assert (await h.http("POST", "/api/midi?name=big.mid", c, midi + b"\0" * (1 << 20)))[0] == 413
            assert (await h.http("POST", "/pair", c, b"x" * 5000))[0] == 413              # big bodies: upload only
            assert (await h.http("POST", "/api/midi-folders?path=Vide", c))[0] == 201
            assert (await h.http("DELETE", "/api/midi/Mes%20morceaux", c))[0] == 409       # not empty
            assert (await h.http("DELETE", "/api/midi/Mes%20morceaux/F%C3%BCr%20Elise.mid", c))[0] == 204
            assert (await h.http("DELETE", "/api/midi/Vide", c))[0] == 204
    run(go())


def test_admin_api_is_not_on_the_public_port(cert, static):
    async def go():
        async with Harness(cert, static) as h:
            assert (await h.http("POST", "/admin/token"))[0] in (404, 405)   # no such route publicly
            assert all(host == "127.0.0.1" for host, _ in h.app._runners[1].addresses)
    run(go())


def test_websocket_requires_session_and_same_origin(cert, static):
    async def go():
        async with Harness(cert, static) as h:
            assert (await h.ws())[0] == 401
            cookie = await h.pair()
            assert (await h.ws(cookie, origin="https://evil.example"))[0] == 403
            code, ws = await h.ws(cookie, origin=f"https://127.0.0.1:{h.port}")
            assert code == 101
            await ws.close()
    run(go())


def test_midi_frames_reach_every_phone_and_stats_record_relay(cert, static):
    async def go():
        async with Harness(cert, static) as h:
            cookie = await h.pair()
            phones = [(await h.ws(cookie))[1] for _ in range(2)]
            await asyncio.sleep(0.05)
            h.app.feed(bytes((0x90, 60, 100, 0, 0, 0, 42)), t_read_ns=None)
            for ws in phones:
                msg = await asyncio.wait_for(ws.receive(), 5)
                assert msg.type == aiohttp.WSMsgType.BINARY and msg.data == bytes((0x90, 60, 100, 0, 0, 0, 42))
            h.app.feed(b"\x80<\x00\x00\x00\x00\x2b", t_read_ns=time.monotonic_ns())
            await asyncio.sleep(0.05)
            _, _, st = await h.http("GET", "/admin/stats", admin=True)
            st = json.loads(st)
            assert st["clients"] == 2 and st["frames"] == 2 and st["relay_us"]["n"] == 1
            for ws in phones:
                await ws.close()
    run(go())


def test_a_phone_that_stops_reading_is_dropped_not_buffered(cert, static, monkeypatch):
    import web.server as srv
    monkeypatch.setattr(srv, "MAX_WS_QUEUE", 4)

    async def go():
        async with Harness(cert, static) as h:
            _, ws = await h.ws(await h.pair())
            await asyncio.sleep(0.05)
            phone = next(iter(h.app.clients))
            phone.sending = True                                    # a send stuck on a full socket: frames pile up
            for _ in range(4):
                h.app._broadcast(b"\x90<d\x00\x00\x00\x00")
            assert h.app.clients and len(phone.backlog) == 4
            h.app._broadcast(b"\x90<d\x00\x00\x00\x00")             # one too many
            assert not h.app.clients
            await ws.close()
    run(go())


def test_forget_all_disconnects_phones_and_revokes_cookies(cert, static):
    async def go():
        async with Harness(cert, static) as h:
            cookie = await h.pair()
            _, ws = await h.ws(cookie)
            await asyncio.sleep(0.05)
            await h.http("POST", "/admin/forget", admin=True)
            msg = await asyncio.wait_for(ws.receive(), 5)
            assert msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING)
            assert (await h.http("GET", "/api/session", {"Cookie": cookie}))[0] == 401
    run(go())


def test_ping_is_answered_and_close_is_clean(cert, static):
    async def go():
        async with Harness(cert, static) as h:
            _, ws = await h.ws(await h.pair())
            await ws.ping(b"hi")                                    # aiohttp answers the pong itself
            await ws.send_str('{"t":"stop"}')
            msg = await asyncio.wait_for(ws.receive(), 5)
            assert json.loads(msg.data) == {"t": "demo", "state": "stopped"}
            await ws.close()
            assert ws.closed
    run(go())


def test_pairing_another_browser_disconnects_the_first(cert, static):
    async def go():
        async with Harness(cert, static) as h:
            first = await h.pair()
            _, ws = await h.ws(first)
            await asyncio.sleep(0.05)
            second = await h.pair()
            msg = await asyncio.wait_for(ws.receive(), 5)
            assert msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING)
            assert (await h.http("GET", "/api/session", {"Cookie": first}))[0] == 401
            assert (await h.http("GET", "/api/session", {"Cookie": second}))[0] == 204
    run(go())


def test_hello_says_whether_the_simulator_can_play_along(cert, static):
    class FakeSim:
        def __init__(self):
            self.songs, self.stopped = [], 0

        def play_song(self, notes, in_ms):
            self.songs.append((notes, in_ms))

        def stop_song(self):
            self.stopped += 1

    async def go():
        async with Harness(cert, static) as h:
            _, ws = await h.ws(await h.pair())
            assert h.hello == {"t": "hello", "sim": False}
            await ws.send_json({"t": "sim", "notes": [[0, 100, 60]], "in_ms": 50})     # ignored: no simulator
            await ws.close()
        async with Harness(cert, static) as h:
            h.app.sim = FakeSim()
            _, ws = await h.ws(await h.pair())
            assert h.hello == {"t": "hello", "sim": True}
            await ws.send_json({"t": "sim", "notes": [[0, 100, 60], [200, 300, 64]], "in_ms": 1500})
            await ws.send_json({"t": "sim", "notes": [[0, 100, 999]], "in_ms": 0})     # invalid note: refused
            await ws.send_json({"t": "sim_stop"})
            await asyncio.sleep(0.2)
            assert h.app.sim.songs == [([(0.0, 100.0, 60), (200.0, 300.0, 64)], 1500.0)] and h.app.sim.stopped == 1
            await ws.close()
    run(go())
