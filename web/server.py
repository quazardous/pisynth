"""pisynth-web — the web companion's server (#658/#659). Thick phone, ultra-thin Pi.

ONE long-lived asyncio process, warm from boot: everything is loaded at startup (app files
+ their gzip copies in RAM, TLS context, sessions), then the Pi only does what the phone
physically can't:

- serve the app files (once — the page's service worker caches them),
- pair a phone (one-time QR token → session cookie, see auth.py),
- relay raw MIDI to every paired phone over one WebSocket, as 7-byte binary frames.

Everything else (note names, chords, notation, latency analysis, storage) runs in the
browser. Stdlib only. The public listener is HTTPS (the phone's mic and service worker
need a secure context); a second, plain-HTTP listener bound to 127.0.0.1 is the admin API
the touch UI uses to get a pairing token.
"""
import asyncio
import base64
import collections
import gzip
import hashlib
import json
import os
import socket
import ssl
import struct
import time
from urllib.parse import parse_qs, unquote

from .auth import Auth, cookie_value
from .demo import DemoPlayer, ShellSink, validate_events
from .library import MAX_UPLOAD, LibraryError
from .uilink import UiLink

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
SESSION_COOKIE = "pisynth_session"
MAX_BODY = 1024
MAX_WS_BACKLOG = 64 * 1024                      # a phone this far behind is dropped, not buffered
MAX_CMDS_PER_S = 30                             # phone → Pi commands (demo batches), per socket

_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
          ".mjs": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
          ".json": "application/json", ".webmanifest": "application/manifest+json",
          ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon"}
_REASON = {101: "Switching Protocols", 200: "OK", 201: "Created", 204: "No Content", 304: "Not Modified",
           400: "Bad Request", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found",
           405: "Method Not Allowed", 409: "Conflict", 413: "Payload Too Large", 500: "Internal Server Error"}
_SECURITY_HEADERS = ("X-Content-Type-Options: nosniff\r\nReferrer-Policy: no-referrer\r\n"
                     "Content-Security-Policy: default-src 'self'; img-src 'self' data:; "
                     "connect-src 'self'; frame-ancestors 'none'\r\n")
_ROUTES = {"/": "index.html", "/latency": "index.html", "/demo": "index.html", "/sound": "index.html",
           "/play": "index.html"}   # SPA routes → its shell


# ---- WebSocket framing (RFC 6455, the slice we need) ----
def accept_key(client_key):
    """Sec-WebSocket-Accept for a client's Sec-WebSocket-Key (RFC 6455 handshake)."""
    return base64.b64encode(hashlib.sha1((client_key + WS_GUID).encode()).digest()).decode()


def encode_frame(payload, opcode=0x2):
    """One unfragmented, unmasked server→client frame (binary by default)."""
    n = len(payload)
    if n < 126:
        hdr = bytes((0x80 | opcode, n))
    elif n < 65536:
        hdr = bytes((0x80 | opcode, 126)) + struct.pack(">H", n)
    else:
        hdr = bytes((0x80 | opcode, 127)) + struct.pack(">Q", n)
    return hdr + payload


def decode_frames(buf):
    """Consume complete frames from bytearray `buf` → [(opcode, payload), ...]; a partial
    trailing frame stays in `buf`. Client frames are masked."""
    out = []
    while len(buf) >= 2:
        opcode, masked, ln, idx = buf[0] & 0x0F, buf[1] & 0x80, buf[1] & 0x7F, 2
        if ln == 126:
            if len(buf) < 4:
                break
            ln, idx = struct.unpack(">H", buf[2:4])[0], 4
        elif ln == 127:
            if len(buf) < 10:
                break
            ln, idx = struct.unpack(">Q", buf[2:10])[0], 10
        need = idx + (4 if masked else 0) + ln
        if len(buf) < need:
            break
        if masked:
            mask = buf[idx:idx + 4]
            idx += 4
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(buf[idx:idx + ln]))
        else:
            payload = bytes(buf[idx:idx + ln])
        del buf[:idx + ln]
        out.append((opcode, payload))
    return out


class _RateLimit:
    """At most `n` events per rolling second (per socket)."""

    def __init__(self, n):
        self.n, self.times = n, collections.deque()

    def allow(self):
        now = time.monotonic()
        while self.times and now - self.times[0] > 1.0:
            self.times.popleft()
        if len(self.times) >= self.n:
            return False
        self.times.append(now)
        return True


# ---- static files, loaded once ----
Asset = collections.namedtuple("Asset", "body gz ctype etag")


def load_static(static_dir=STATIC_DIR):
    """{url path: Asset} for every file under static_dir, with a gzip copy and an ETag —
    computed once at startup, so serving is a memory write."""
    assets = {}
    for root, _, files in os.walk(static_dir):
        for name in files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, static_dir).replace(os.sep, "/")
            with open(full, "rb") as f:
                body = f.read()
            ctype = _TYPES.get(os.path.splitext(name)[1].lower(), "application/octet-stream")
            gz = gzip.compress(body, 9) if ctype.startswith(("text/", "application/j", "image/svg")) else None
            etag = '"' + hashlib.sha256(body).hexdigest()[:16] + '"'
            assets["/" + rel] = Asset(body, gz if gz and len(gz) < len(body) else None, ctype, etag)
    for url, rel in _ROUTES.items():
        if "/" + rel in assets:
            assets[url] = assets["/" + rel]
    return assets


def cert_fingerprint(cert_path):
    """SHA-256 fingerprint of a PEM certificate, as AA:BB:… (what browsers display)."""
    with open(cert_path) as f:
        der = ssl.PEM_cert_to_DER_cert(f.read())
    h = hashlib.sha256(der).hexdigest().upper()
    return ":".join(h[i:i + 2] for i in range(0, len(h), 2))


class Request:
    def __init__(self, method, path, headers, body=b"", query=""):
        self.method, self.path, self.headers, self.body = method, path, headers, body
        self.query = {k: v[0] for k, v in parse_qs(query).items()}


async def read_request(reader):
    """Parse one HTTP/1.1 request head (+ a small body) → Request, or None on garbage. Only a
    MIDI file upload (POST /api/midi) may carry a body larger than MAX_BODY."""
    head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=10)
    lines = head.decode("latin1").split("\r\n")
    parts = lines[0].split(" ")
    if len(parts) < 2:
        return None
    headers = {}
    for ln in lines[1:]:
        if ":" in ln:
            k, v = ln.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    body = b""
    path, _, query = parts[1].partition("?")
    length = int(headers.get("content-length", "0") or 0)
    limit = MAX_UPLOAD + 1 if (parts[0], path) == ("POST", "/api/midi") else MAX_BODY
    if length > limit:
        return Request(parts[0], "", headers, None)           # flagged: too large
    if length:
        body = await asyncio.wait_for(reader.readexactly(length), timeout=30 if length > MAX_BODY else 10)
    return Request(parts[0], path, headers, body, query)


def response(code, body=b"", ctype="text/plain; charset=utf-8", extra=""):
    return (f"HTTP/1.1 {code} {_REASON.get(code, 'OK')}\r\nContent-Type: {ctype}\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n{_SECURITY_HEADERS}{extra}\r\n"
            ).encode() + body


class WebCompanion:
    def __init__(self, auth, assets, host="0.0.0.0", port=8443, admin_port=9811,
                 ssl_ctx=None, fingerprint="", admin_host="127.0.0.1", synth=("127.0.0.1", 9800),
                 ui=("127.0.0.1", 9810), library=None):
        self.auth, self.assets = auth, assets
        self.library = library                       # MidiLibrary (#2421), or None
        self.host, self.port, self.admin_port, self.admin_host = host, port, admin_port, admin_host
        self.ssl_ctx, self.fingerprint = ssl_ctx, fingerprint
        self.clients = set()                         # StreamWriters of live WebSockets
        self.frames = 0
        self.relay_us = collections.deque(maxlen=4096)   # seq read → frame queued to sockets
        self.synth = synth
        self.demo = None                             # DemoPlayer, created with the loop (#2416)
        self.ui = UiLink(*ui, on_state=self._broadcast_synth_state)   # synth settings API (#2417)
        self._loop = None

    # ---- MIDI hot path (feed runs on the source thread) ----
    def feed(self, payload, t_read_ns=None):
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(self._broadcast, encode_frame(payload), t_read_ns)

    def _broadcast(self, frame, t_read_ns=None):
        for w in list(self.clients):
            if w.is_closing() or w.transport.get_write_buffer_size() > MAX_WS_BACKLOG:
                self.clients.discard(w)              # dead or hopelessly slow phone
                w.close()
                continue
            w.write(frame)
        self.frames += 1
        if t_read_ns is not None:
            self.relay_us.append((time.monotonic_ns() - t_read_ns) // 1000)

    # ---- public listener (HTTPS) ----
    async def _handle_public(self, reader, writer):
        try:
            req = await read_request(reader)
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError,
                ValueError, OSError, ssl.SSLError):
            writer.close()
            return
        if req is None:
            writer.write(response(400, b"bad request"))
        elif req.body is None:
            writer.write(response(413, b"too large"))
        elif req.path == "/ws":
            return await self._serve_ws(reader, writer, req)
        elif req.path == "/pair":
            writer.write(self._pair(req))
        elif req.path == "/api/session":
            ok = self.auth.valid(cookie_value(req.headers, SESSION_COOKIE))
            writer.write(response(204 if ok else 401))
        elif req.path in ("/api/midi", "/api/midi-folders") or req.path.startswith("/api/midi/"):
            writer.write(await self._library(req))
        elif req.method in ("GET", "HEAD"):
            writer.write(self._static(req))
        else:
            writer.write(response(405, b"method not allowed"))
        await self._finish(writer)

    def _pair(self, req):
        if req.method != "POST":
            return response(405, b"method not allowed")
        try:
            token = json.loads(req.body or b"{}").get("token", "")
        except (ValueError, AttributeError):
            return response(400, b"bad request")
        session_id = self.auth.redeem(token)
        if not session_id:
            return response(403, b'{"error":"invalid or expired pairing code"}', "application/json")
        if self.demo:
            self.demo.stop()                         # a new browser takes over: its predecessor's demo ends
        for w in list(self.clients):                 # the previously paired browser is cut off now
            w.close()
        self.clients.clear()
        cookie = (f"Set-Cookie: {SESSION_COOKIE}={session_id}; Path=/; Max-Age=315360000; "
                  "HttpOnly; Secure; SameSite=Strict\r\n")
        return response(200, b'{"paired":true}', "application/json", cookie)

    async def _library(self, req):
        """MIDI library (#2421), paired phone only:
        GET /api/midi → tree · GET /api/midi/<path> → file · POST /api/midi?dir=&name= (body = file)
        · POST /api/midi-folders?path= · DELETE /api/midi/<path>. File work runs off the loop."""
        h = req.headers
        if not self.auth.valid(cookie_value(h, SESSION_COOKIE)):
            return response(401, b"pair this phone first")
        origin = h.get("origin", "")
        if req.method not in ("GET", "HEAD") and origin and origin.split("://", 1)[-1] != h.get("host", ""):
            return response(403, b"cross-origin")
        if self.library is None:
            return response(404, b"no MIDI library")
        lib = self.library
        sub = unquote(req.path[len("/api/midi/"):]) if req.path.startswith("/api/midi/") else ""
        try:
            if (req.method, req.path) == ("GET", "/api/midi"):
                return self._json({"entries": await asyncio.to_thread(lib.tree)})
            if req.method == "GET" and sub:
                data = await asyncio.to_thread(lib.read, sub)
                return response(200, data, "audio/midi", "Cache-Control: no-cache\r\n")
            if (req.method, req.path) == ("POST", "/api/midi"):
                path = await asyncio.to_thread(lib.save, req.query.get("dir", ""), req.query.get("name", ""), req.body)
                return response(201, json.dumps({"path": path}).encode(), "application/json")
            if (req.method, req.path) == ("POST", "/api/midi-folders"):
                path = await asyncio.to_thread(lib.mkdir, req.query.get("path", ""))
                return response(201, json.dumps({"path": path}).encode(), "application/json")
            if req.method == "DELETE" and sub:
                await asyncio.to_thread(lib.delete, sub)
                return response(204)
        except LibraryError as e:
            return response(e.code, json.dumps({"error": e.message}).encode(), "application/json")
        except OSError:
            return response(500, b'{"error":"storage error"}', "application/json")
        return response(405, b"method not allowed")

    def _static(self, req):
        asset = self.assets.get(req.path)
        if asset is None:
            return response(404, b"not found")
        cache = "Cache-Control: no-cache\r\n"        # revalidate by ETag; the service worker caches
        if req.headers.get("if-none-match") == asset.etag:
            return response(304, extra=f"ETag: {asset.etag}\r\n{cache}")
        body, enc = asset.body, ""
        if asset.gz and "gzip" in req.headers.get("accept-encoding", ""):
            body, enc = asset.gz, "Content-Encoding: gzip\r\nVary: Accept-Encoding\r\n"
        extra = f"ETag: {asset.etag}\r\n{cache}{enc}"
        out = response(200, body, asset.ctype, extra)
        if req.method == "HEAD":
            out = out[:out.index(b"\r\n\r\n") + 4]
        return out

    async def _serve_ws(self, reader, writer, req):
        h = req.headers
        if not self.auth.valid(cookie_value(h, SESSION_COOKIE)):
            writer.write(response(401, b"pair this phone first"))
            return await self._finish(writer)
        origin = h.get("origin", "")
        if origin and origin.split("://", 1)[-1] != h.get("host", ""):
            writer.write(response(403, b"cross-origin"))   # cross-site WebSocket hijacking
            return await self._finish(writer)
        if h.get("upgrade", "").lower() != "websocket" or not h.get("sec-websocket-key"):
            writer.write(response(400, b"websocket upgrade expected"))
            return await self._finish(writer)
        sock = writer.get_extra_info("socket")
        if sock is not None:
            try:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)   # no Nagle: notes leave now
            except OSError:
                pass
        writer.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                      f"Connection: Upgrade\r\nSec-WebSocket-Accept: {accept_key(h['sec-websocket-key'])}"
                      "\r\n\r\n").encode())
        await writer.drain()
        self.clients.add(writer)
        buf = bytearray()
        rate = _RateLimit(MAX_CMDS_PER_S)
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                buf += data
                if len(buf) > MAX_BODY * 16:
                    break                            # phones only send tiny control frames
                for opcode, payload in decode_frames(buf):
                    if opcode == 0x8:                # CLOSE
                        writer.write(encode_frame(payload[:2], 0x8))
                        return
                    if opcode == 0x9:                # PING → PONG
                        writer.write(encode_frame(payload[:125], 0xA))
                    elif opcode == 0x1:              # text = a JSON command from the phone (#2416)
                        if rate.allow():
                            await self._command(writer, payload)
        except (OSError, asyncio.IncompleteReadError, ssl.SSLError):
            pass
        finally:
            self.clients.discard(writer)
            if self.demo:
                self.demo.release_owner(writer)      # the phone left: no stuck notes
            writer.close()

    async def _command(self, writer, payload):
        """Phone → Pi commands. Demo mode (#2416): {"t":"play","reset":bool,"ev":[[ms,status,d1,d2],…]}
        schedules a batch on the Pi's clock; {"t":"stop"} releases everything."""
        try:
            msg = json.loads(payload)
        except ValueError:
            return
        if not isinstance(msg, dict) or self.demo is None:
            return
        kind = msg.get("t")
        if kind == "synth":                          # settings API (#2417): relayed to the touch UI
            op = msg.get("op")
            if op not in ("get", "set"):
                return
            fwd = {"op": op} if op == "get" else {"op": "set", "key": msg.get("key"), "value": msg.get("value")}
            reply = await self.ui.request(fwd)
            if not writer.is_closing():
                self._send_json(writer, {"t": "synth", "op": op, "req": msg.get("req"), **reply})
            return
        if kind == "stop":
            self.demo.stop()
            self._send_json(writer, {"t": "demo", "state": "stopped"})
        elif kind == "play":
            events = validate_events(msg.get("ev"))
            if events is None:
                self._send_json(writer, {"t": "demo", "state": "error", "error": "bad batch"})
                return
            reset = bool(msg.get("reset"))
            if reset and not await self.demo.sink.ensure():
                self._send_json(writer, {"t": "demo", "state": "error", "error": "synth unreachable"})
                return
            n = self.demo.play(events, reset, owner=writer)
            if reset:
                self._send_json(writer, {"t": "demo", "state": "playing", "lead_ms": 150, "scheduled": n})

    def _broadcast_synth_state(self, state):
        """The UI's watch stream → every paired phone (changes made on the box show up live)."""
        frame = encode_frame(json.dumps({"t": "synth", "state": state}, separators=(",", ":")).encode(), 0x1)
        for w in list(self.clients):
            if not w.is_closing():
                w.write(frame)

    @staticmethod
    def _send_json(writer, obj):
        writer.write(encode_frame(json.dumps(obj, separators=(",", ":")).encode(), 0x1))

    @staticmethod
    async def _finish(writer):
        try:
            await writer.drain()
        except (OSError, ssl.SSLError):
            pass
        writer.close()

    # ---- admin listener (plain HTTP, 127.0.0.1 only — the touch UI) ----
    async def _handle_admin(self, reader, writer):
        try:
            req = await read_request(reader)
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError,
                ValueError, OSError):
            writer.close()
            return
        if req is None or req.body is None:
            writer.write(response(400))
        elif (req.method, req.path) == ("POST", "/admin/token"):
            token, ttl = self.auth.new_token()
            writer.write(self._json({"token": token, "ttl": ttl, "port": self.port,
                                     "fingerprint": self.fingerprint}))
        elif (req.method, req.path) == ("POST", "/admin/forget"):
            self.auth.forget_all()
            for w in list(self.clients):             # paired phones are disconnected right away
                w.close()
            self.clients.clear()
            writer.write(self._json({"sessions": 0}))
        elif (req.method, req.path) == ("POST", "/admin/demo/stop"):
            if self.demo:
                owner = self.demo.owner
                self.demo.stop()
                if owner is not None and not owner.is_closing():
                    self._send_json(owner, {"t": "demo", "state": "stopped", "by": "pisynth"})   # tell the phone
            writer.write(self._json({"stopped": True}))
        elif (req.method, req.path) == ("GET", "/admin/stats"):
            writer.write(self._json(self.stats()))
        else:
            writer.write(response(404))
        await self._finish(writer)

    @staticmethod
    def _json(obj):
        return response(200, json.dumps(obj).encode(), "application/json")

    def stats(self):
        s = sorted(self.relay_us)

        def pct(p):
            return s[min(len(s) - 1, int(len(s) * p))] if s else None
        return {"clients": len(self.clients), "sessions": self.auth.session_count,
                "demo": self.demo.stats() if self.demo else None,
                "frames": self.frames, "relay_us": {"p50": pct(0.5), "p99": pct(0.99),
                                                    "max": s[-1] if s else None, "n": len(s)}}

    # ---- run ----
    async def start(self):
        self._loop = asyncio.get_running_loop()
        self.demo = DemoPlayer(ShellSink(*self.synth), self._loop)
        self.ui.start_watch()
        public = await asyncio.start_server(self._handle_public, self.host, self.port, ssl=self.ssl_ctx)
        admin = await asyncio.start_server(self._handle_admin, self.admin_host, self.admin_port)
        return public, admin

    async def serve(self):
        public, admin = await self.start()
        async with public, admin:
            await asyncio.gather(public.serve_forever(), admin.serve_forever())


def make_ssl_context(cert, key):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(cert, key)
    return ctx


def make_app(**kw):
    """Convenience for tests / __main__: Auth + preloaded assets + server."""
    auth = kw.pop("auth", None) or Auth(kw.pop("sessions_path", None))
    assets = kw.pop("assets", None) or load_static(kw.pop("static_dir", STATIC_DIR))
    return WebCompanion(auth, assets, **kw)
