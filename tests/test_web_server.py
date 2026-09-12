"""web/server.py over real loopback sockets: HTTPS with a throwaway self-signed cert,
pairing, the MIDI WebSocket, the loopback admin API (#659)."""
import asyncio
import base64
import gzip
import json
import os
import shutil
import ssl
import subprocess

import pytest

from web.auth import Auth
from web.server import (WebCompanion, cert_fingerprint, decode_frames, encode_frame, load_static,
                        make_ssl_context)

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
    (tmp_path / "latency.html").write_text("<!doctype html><title>latency</title>")
    (tmp_path / "sw.js").write_text("self.addEventListener('fetch', () => {});")
    return str(tmp_path)


def run(coro):
    return asyncio.run(asyncio.wait_for(coro, 20))


class Harness:
    def __init__(self, cert, static, library=None):
        self.app = WebCompanion(Auth(), load_static(static), host="127.0.0.1", port=0, admin_port=0,
                                ssl_ctx=make_ssl_context(*cert), fingerprint=cert_fingerprint(cert[0]),
                                library=library)
        self.client_ctx = ssl.create_default_context()
        self.client_ctx.check_hostname = False
        self.client_ctx.verify_mode = ssl.CERT_NONE

    async def __aenter__(self):
        self.public, self.admin = await self.app.start()
        self.port = self.public.sockets[0].getsockname()[1]
        self.admin_port = self.admin.sockets[0].getsockname()[1]
        self.app.port = self.port
        return self

    async def __aexit__(self, *exc):
        for s in (self.public, self.admin):
            s.close()
        for w in list(self.app.clients):
            w.close()

    async def http(self, method, path, headers=None, body=b"", admin=False):
        port = self.admin_port if admin else self.port
        r, w = await asyncio.open_connection("127.0.0.1", port, ssl=None if admin else self.client_ctx)
        hdrs = {"Host": f"127.0.0.1:{port}", "Content-Length": str(len(body)), **(headers or {})}
        w.write((f"{method} {path} HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in hdrs.items())
                 + "\r\n").encode() + body)
        raw = await r.read()
        w.close()
        head, _, payload = raw.partition(b"\r\n\r\n")
        lines = head.decode().split("\r\n")
        code = int(lines[0].split()[1])
        h = {ln.split(":", 1)[0].lower(): ln.split(":", 1)[1].strip() for ln in lines[1:] if ":" in ln}
        return code, h, payload

    async def pair(self):
        _, _, tok = await self.http("POST", "/admin/token", admin=True)
        code, h, _ = await self.http("POST", "/pair", body=json.dumps({"token": json.loads(tok)["token"]}).encode())
        assert code == 200
        return h["set-cookie"].split(";")[0]

    async def ws(self, cookie=None, origin=None):
        r, w = await asyncio.open_connection("127.0.0.1", self.port, ssl=self.client_ctx)
        key = base64.b64encode(os.urandom(16)).decode()
        hdrs = {"Host": f"127.0.0.1:{self.port}", "Upgrade": "websocket", "Connection": "Upgrade",
                "Sec-WebSocket-Key": key, "Sec-WebSocket-Version": "13"}
        if cookie:
            hdrs["Cookie"] = cookie
        if origin:
            hdrs["Origin"] = origin
        w.write(("GET /ws HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in hdrs.items()) + "\r\n").encode())
        head = await r.readuntil(b"\r\n\r\n")
        return int(head.split()[1]), r, w


def test_static_is_served_gzipped_with_etag_and_304(cert, static):
    async def go():
        async with Harness(cert, static) as h:
            code, hd, body = await h.http("GET", "/", {"Accept-Encoding": "gzip"})
            assert code == 200 and hd["content-encoding"] == "gzip" and gzip.decompress(body).startswith(b"<!doctype")
            assert "default-src 'self'" in hd["content-security-policy"]
            code, _, _ = await h.http("GET", "/index.html", {"If-None-Match": hd["etag"]})
            assert code == 304
            assert (await h.http("GET", "/latency"))[0] == 200
            for route in ("/play", "/listen", "/about", "/sound", "/demo"):
                assert (await h.http("GET", route))[0] == 200, route
            assert (await h.http("GET", "/../../etc/passwd"))[0] == 404
            assert (await h.http("DELETE", "/"))[0] == 405
    run(go())


def test_the_paired_browser_can_unpair_itself(cert, static):
    async def go():
        async with Harness(cert, static) as h:
            assert (await h.http("POST", "/api/unpair"))[0] == 401
            c = {"Cookie": await h.pair()}
            assert (await h.http("GET", "/api/unpair", c))[0] == 405
            assert (await h.http("POST", "/api/unpair", {**c, "Origin": "https://evil.example"}))[0] == 403
            code, hd, _ = await h.http("POST", "/api/unpair", c)
            assert code == 204 and "Max-Age=0" in hd["set-cookie"]
            assert (await h.http("GET", "/api/session", c))[0] == 401
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
            assert h.admin.sockets[0].getsockname()[0] == "127.0.0.1"
    run(go())


def test_websocket_requires_session_and_same_origin(cert, static):
    async def go():
        async with Harness(cert, static) as h:
            assert (await h.ws())[0] == 401
            cookie = await h.pair()
            assert (await h.ws(cookie, origin="https://evil.example"))[0] == 403
            code, _, w = await h.ws(cookie, origin=f"https://127.0.0.1:{h.port}")
            assert code == 101
            w.close()
    run(go())


def test_midi_frames_reach_every_phone_and_stats_record_relay(cert, static):
    async def go():
        async with Harness(cert, static) as h:
            cookie = await h.pair()
            phones = [await h.ws(cookie) for _ in range(2)]
            await asyncio.sleep(0.05)
            h.app.feed(bytes((0x90, 60, 100, 0, 0, 0, 42)), t_read_ns=None)
            for _, r, _ in phones:
                buf = bytearray(await asyncio.wait_for(r.readexactly(9), 5))
                assert decode_frames(buf) == [(0x2, bytes((0x90, 60, 100, 0, 0, 0, 42)))]
            import time as _t
            h.app.feed(b"\x80<\x00\x00\x00\x00\x2b", t_read_ns=_t.monotonic_ns())
            await asyncio.sleep(0.05)
            _, _, st = await h.http("GET", "/admin/stats", admin=True)
            st = json.loads(st)
            assert st["clients"] == 2 and st["frames"] == 2 and st["relay_us"]["n"] == 1
            for _, _, w in phones:
                w.close()
    run(go())


def test_forget_all_disconnects_phones_and_revokes_cookies(cert, static):
    async def go():
        async with Harness(cert, static) as h:
            cookie = await h.pair()
            _, r, _ = await h.ws(cookie)
            await asyncio.sleep(0.05)
            await h.http("POST", "/admin/forget", admin=True)
            assert await asyncio.wait_for(r.read(), 5) == b""                    # socket closed
            assert (await h.http("GET", "/api/session", {"Cookie": cookie}))[0] == 401
    run(go())


def test_ping_gets_pong_and_close_is_echoed(cert, static):
    async def go():
        async with Harness(cert, static) as h:
            cookie = await h.pair()
            _, r, w = await h.ws(cookie)
            mask = b"\x01\x02\x03\x04"
            masked = bytes(b ^ mask[i % 4] for i, b in enumerate(b"hi"))
            w.write(bytes((0x89, 0x80 | 2)) + mask + masked)
            buf = bytearray(await asyncio.wait_for(r.readexactly(4), 5))
            assert decode_frames(buf) == [(0xA, b"hi")]
            w.write(bytes((0x88, 0x80 | 0)) + mask)
            assert (await asyncio.wait_for(r.readexactly(2), 5))[0] == 0x88
    run(go())


def test_encode_frame_lengths():
    assert encode_frame(b"x" * 7)[:2] == bytes((0x82, 7))
    assert encode_frame(b"x" * 300)[:4] == bytes((0x82, 126, 1, 44))


def test_pairing_another_browser_disconnects_the_first(cert, static):
    async def go():
        async with Harness(cert, static) as h:
            first = await h.pair()
            _, r, _ = await h.ws(first)
            await asyncio.sleep(0.05)
            second = await h.pair()
            assert await asyncio.wait_for(r.read(), 5) == b""                    # first browser cut off
            assert (await h.http("GET", "/api/session", {"Cookie": first}))[0] == 401
            assert (await h.http("GET", "/api/session", {"Cookie": second}))[0] == 204
    run(go())
