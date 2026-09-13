"""pisynth-web — the web companion's server (#658/#659), on aiohttp (#2428). Thick phone, thin Pi.

ONE long-lived asyncio process, warm from boot: everything is loaded at startup (app files + their
gzip copies in RAM, TLS context, sessions), then the Pi only does what the phone physically can't:

- serve the app files (once — the page's service worker caches them),
- pair a phone (one-time QR token → session cookie, see auth.py),
- relay raw MIDI to the paired phone over one WebSocket, as 7-byte binary frames,
- run what must happen on the Pi: demo playback (demo.py), the synth settings relay (uilink.py),
  the MIDI library's files (library.py).

The public app is HTTPS (the phone's mic and service worker need a secure context); a second app,
plain HTTP on 127.0.0.1, is the admin API the touch UI uses (pairing token, unpair, stop demo).
"""
import asyncio
import collections
import functools
import gzip
import hashlib
import json
import os
import socket
import ssl
import time
from urllib.parse import unquote

from aiohttp import WSMsgType, web

from .auth import Auth
from .demo import DemoPlayer, ShellSink, validate_events
from .library import MAX_UPLOAD, LibraryError
from .uilink import UiLink

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
SESSION_COOKIE = "pisynth_session"
MAX_BODY = 1024                                 # every request body but a MIDI upload
MAX_WS_QUEUE = 2048                             # frames waiting for one phone; beyond, it's dropped
MAX_CMDS_PER_S = 30                             # phone → Pi commands (demo batches), per socket
SESSION_MAX_AGE = 315360000

_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
          ".mjs": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
          ".json": "application/json", ".webmanifest": "application/manifest+json",
          ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon"}
_SECURITY_HEADERS = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
                     "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; "
                                                "connect-src 'self'; frame-ancestors 'none'"}
_ROUTES = ("/", "/latency", "/demo", "/sound", "/play", "/listen", "/about")   # app screens → index.html


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
    if "/index.html" in assets:
        for url in _ROUTES:
            assets[url] = assets["/index.html"]
    return assets


def cert_fingerprint(cert_path):
    """SHA-256 fingerprint of a PEM certificate, as AA:BB:… (what browsers display)."""
    with open(cert_path) as f:
        der = ssl.PEM_cert_to_DER_cert(f.read())
    h = hashlib.sha256(der).hexdigest().upper()
    return ":".join(h[i:i + 2] for i in range(0, len(h), 2))


def make_ssl_context(cert, key):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(cert, key)
    return ctx


# ---- small helpers ----
def text(status, message=""):
    return web.Response(status=status, text=message)


def jsonr(obj, status=200):
    return web.json_response(obj, status=status, dumps=lambda o: json.dumps(o, separators=(",", ":")))


def same_origin(request):
    origin = request.headers.get("Origin", "")
    return not origin or origin.split("://", 1)[-1] == request.headers.get("Host", "")


def paired(handler):
    """Route guard: a paired phone only, and same-origin for anything that changes state."""
    @functools.wraps(handler)
    async def guarded(self, request):
        if not self.auth.valid(request.cookies.get(SESSION_COOKIE, "")):
            return text(401, "pair this phone first")
        if request.method not in ("GET", "HEAD") and not same_origin(request):
            return text(403, "cross-origin")
        return await handler(self, request)
    return guarded


async def _security_headers(request, response):
    for k, v in _SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)


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


class Phone:
    """One connected WebSocket. Frames are queued without waiting and sent by its own task, so the
    MIDI hot path never awaits a slow phone; one that falls MAX_WS_QUEUE frames behind is dropped.
    Also the `owner` of a demo (demo.py only compares identities)."""

    def __init__(self, ws):
        self.ws = ws
        self.queue = asyncio.Queue(MAX_WS_QUEUE)
        self.task = asyncio.ensure_future(self._pump())

    def push(self, data):
        try:
            self.queue.put_nowait(data)
            return True
        except asyncio.QueueFull:
            return False

    def send_json(self, obj):
        return self.push(json.dumps(obj, separators=(",", ":")))

    def is_closing(self):
        return self.ws.closed

    async def _pump(self):
        try:
            while True:
                data = await self.queue.get()
                if isinstance(data, bytes):
                    await self.ws.send_bytes(data)
                else:
                    await self.ws.send_str(data)
        except (ConnectionError, RuntimeError, asyncio.CancelledError):
            pass

    async def close(self):
        self.task.cancel()
        await self.ws.close()


class WebCompanion:
    def __init__(self, auth, assets, host="0.0.0.0", port=8443, admin_port=9811,
                 ssl_ctx=None, fingerprint="", admin_host="127.0.0.1", synth=("127.0.0.1", 9800),
                 ui=("127.0.0.1", 9810), library=None):
        self.auth, self.assets = auth, assets
        self.library = library                       # MidiLibrary (#2421), or None
        self.host, self.port, self.admin_port, self.admin_host = host, port, admin_port, admin_host
        self.ssl_ctx, self.fingerprint = ssl_ctx, fingerprint
        self.clients = set()                         # Phone objects of live WebSockets
        self.frames = 0
        self.relay_us = collections.deque(maxlen=4096)   # seq read → frame queued to the phones
        self.synth = synth
        self.demo = None                             # DemoPlayer, created with the loop (#2416)
        self.ui = UiLink(*ui, on_state=self._broadcast_synth_state)   # synth settings API (#2417)
        self._loop = None
        self._runners = []

    # ---- apps ----
    def public_app(self):
        app = web.Application(client_max_size=MAX_UPLOAD + 1)     # only /api/midi uploads may be that big
        app.on_response_prepare.append(_security_headers)
        app.router.add_get("/ws", self.ws_handler)
        app.router.add_post("/pair", self.pair)
        app.router.add_get("/api/session", self.session)
        app.router.add_post("/api/unpair", self.unpair)
        app.router.add_get("/api/midi", self.midi_tree)
        app.router.add_post("/api/midi", self.midi_upload)
        app.router.add_post("/api/midi-folders", self.midi_mkdir)
        app.router.add_get("/api/midi/{path:.+}", self.midi_file)
        app.router.add_delete("/api/midi/{path:.+}", self.midi_delete)
        app.router.add_get("/{tail:.*}", self.static)
        return app

    def admin_app(self):
        app = web.Application(client_max_size=MAX_BODY)
        app.router.add_post("/admin/token", self.admin_token)
        app.router.add_post("/admin/forget", self.admin_forget)
        app.router.add_post("/admin/demo/stop", self.admin_demo_stop)
        app.router.add_get("/admin/stats", self.admin_stats)
        return app

    # ---- MIDI hot path (feed runs on the source thread) ----
    def feed(self, payload, t_read_ns=None):
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(self._broadcast, bytes(payload), t_read_ns)

    def _broadcast(self, frame, t_read_ns=None):
        for phone in list(self.clients):
            if phone.is_closing() or not phone.push(frame):
                self._drop(phone)                    # dead or hopelessly slow phone
        self.frames += 1
        if t_read_ns is not None:
            self.relay_us.append((time.monotonic_ns() - t_read_ns) // 1000)

    def _drop(self, phone):
        self.clients.discard(phone)
        asyncio.ensure_future(phone.close())

    def _disconnect_all(self):
        for phone in list(self.clients):
            self._drop(phone)

    def _broadcast_synth_state(self, state):
        """The UI's watch stream → every paired phone (changes made on the box show up live)."""
        for phone in list(self.clients):
            if not phone.is_closing():
                phone.send_json({"t": "synth", "state": state})

    # ---- public: pairing ----
    async def pair(self, request):
        if (request.content_length or 0) > MAX_BODY:
            return text(413, "too large")
        try:
            token = json.loads(await request.read() or b"{}").get("token", "")
        except (ValueError, AttributeError):
            return text(400, "bad request")
        session_id = self.auth.redeem(token)
        if not session_id:
            return jsonr({"error": "invalid or expired pairing code"}, 403)
        if self.demo:
            self.demo.stop()                         # a new browser takes over: its predecessor's demo ends
        self._disconnect_all()                       # the previously paired browser is cut off now
        resp = jsonr({"paired": True})
        resp.set_cookie(SESSION_COOKIE, session_id, path="/", max_age=SESSION_MAX_AGE,
                        httponly=True, secure=True, samesite="Strict")
        return resp

    async def session(self, request):
        return web.Response(status=204 if self.auth.valid(request.cookies.get(SESSION_COOKIE, "")) else 401)

    @paired
    async def unpair(self, request):
        """The paired browser unpairs itself (Settings → About, #2419). One paired browser at a time,
        so this forgets every session — same as Unpair on the pisynth screen."""
        if self.demo:
            self.demo.stop()
        self.auth.forget_all()
        self._disconnect_all()
        resp = web.Response(status=204)
        resp.set_cookie(SESSION_COOKIE, "", path="/", max_age=0, httponly=True, secure=True, samesite="Strict")
        return resp

    # ---- public: MIDI library (#2421) — file work runs off the loop ----
    async def _library_call(self, fn, *args):
        if self.library is None:
            return text(404, "no MIDI library")
        try:
            return await asyncio.to_thread(fn, *args)
        except LibraryError as e:
            return jsonr({"error": e.message}, e.code)
        except OSError:
            return jsonr({"error": "storage error"}, 500)

    @staticmethod
    def _sub(request):
        return unquote(request.raw_path.split("?", 1)[0][len("/api/midi/"):])   # %2F stays a slash, then checked

    @paired
    async def midi_tree(self, request):
        r = await self._library_call(lambda: self.library.tree())
        return r if isinstance(r, web.Response) else jsonr({"entries": r})

    @paired
    async def midi_file(self, request):
        r = await self._library_call(lambda p: self.library.read(p), self._sub(request))
        if isinstance(r, web.Response):
            return r
        return web.Response(body=r, headers={"Content-Type": "audio/midi", "Cache-Control": "no-cache"})

    @paired
    async def midi_upload(self, request):
        data = await request.read()                  # over client_max_size → aiohttp answers 413
        q = request.query
        r = await self._library_call(lambda: self.library.save(q.get("dir", ""), q.get("name", ""), data))
        return r if isinstance(r, web.Response) else jsonr({"path": r}, 201)

    @paired
    async def midi_mkdir(self, request):
        r = await self._library_call(lambda: self.library.mkdir(request.query.get("path", "")))
        return r if isinstance(r, web.Response) else jsonr({"path": r}, 201)

    @paired
    async def midi_delete(self, request):
        r = await self._library_call(lambda p: self.library.delete(p), self._sub(request))
        return r if isinstance(r, web.Response) else web.Response(status=204)

    # ---- public: app files ----
    async def static(self, request):
        asset = self.assets.get(request.path)
        if asset is None:
            return text(404, "not found")
        headers = {"ETag": asset.etag, "Cache-Control": "no-cache"}   # revalidate by ETag; the service worker caches
        if request.headers.get("If-None-Match") == asset.etag:
            return web.Response(status=304, headers=headers)
        body = asset.body
        if asset.gz and "gzip" in request.headers.get("Accept-Encoding", ""):
            body = asset.gz
            headers.update({"Content-Encoding": "gzip", "Vary": "Accept-Encoding"})
        headers["Content-Type"] = asset.ctype
        return web.Response(body=body, headers=headers)

    # ---- public: the WebSocket ----
    async def ws_handler(self, request):
        if not self.auth.valid(request.cookies.get(SESSION_COOKIE, "")):
            return text(401, "pair this phone first")
        if not same_origin(request):
            return text(403, "cross-origin")         # cross-site WebSocket hijacking
        ws = web.WebSocketResponse(heartbeat=30, max_msg_size=MAX_BODY * 16)   # phones only send small commands
        await ws.prepare(request)
        sock = request.transport.get_extra_info("socket") if request.transport else None
        if sock is not None:
            try:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)   # no Nagle: notes leave now
            except OSError:
                pass
        phone = Phone(ws)
        self.clients.add(phone)
        rate = _RateLimit(MAX_CMDS_PER_S)
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT and rate.allow():
                    await self._command(phone, msg.data)     # a JSON command from the phone (#2416)
        finally:
            self.clients.discard(phone)
            phone.task.cancel()
            if self.demo:
                self.demo.release_owner(phone)       # the phone left: no stuck notes
        return ws

    async def _command(self, phone, payload):
        """Phone → Pi commands. Demo mode (#2416): {"t":"play","reset":bool,"ev":[[ms,status,d1,d2],…]}
        schedules a batch on the Pi's clock; {"t":"stop"} releases everything. Synth settings (#2417):
        {"t":"synth","op":"get"|"set",…} is relayed to the touch UI."""
        try:
            msg = json.loads(payload)
        except ValueError:
            return
        if not isinstance(msg, dict) or self.demo is None:
            return
        kind = msg.get("t")
        if kind == "synth":
            op = msg.get("op")
            if op not in ("get", "set"):
                return
            fwd = {"op": op} if op == "get" else {"op": "set", "key": msg.get("key"), "value": msg.get("value")}
            reply = await self.ui.request(fwd)
            if not phone.is_closing():
                phone.send_json({"t": "synth", "op": op, "req": msg.get("req"), **reply})
        elif kind == "stop":
            self.demo.stop()
            phone.send_json({"t": "demo", "state": "stopped"})
        elif kind == "play":
            events = validate_events(msg.get("ev"))
            if events is None:
                phone.send_json({"t": "demo", "state": "error", "error": "bad batch"})
                return
            reset = bool(msg.get("reset"))
            if reset and not await self.demo.sink.ensure():
                phone.send_json({"t": "demo", "state": "error", "error": "synth unreachable"})
                return
            n = self.demo.play(events, reset, owner=phone)
            if reset:
                phone.send_json({"t": "demo", "state": "playing", "lead_ms": 150, "scheduled": n})

    # ---- admin (plain HTTP, 127.0.0.1 only — the touch UI) ----
    async def admin_token(self, request):
        token, ttl = self.auth.new_token()
        return jsonr({"token": token, "ttl": ttl, "port": self.port, "fingerprint": self.fingerprint})

    async def admin_forget(self, request):
        self.auth.forget_all()
        self._disconnect_all()                       # paired phones are disconnected right away
        return jsonr({"sessions": 0})

    async def admin_demo_stop(self, request):
        if self.demo:
            owner = self.demo.owner
            self.demo.stop()
            if owner is not None and not owner.is_closing():
                owner.send_json({"t": "demo", "state": "stopped", "by": "pisynth"})   # tell the phone
        return jsonr({"stopped": True})

    async def admin_stats(self, request):
        return jsonr(self.stats())

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
        """Listen on both ports (port 0 = pick one; the chosen ports are written back)."""
        self._loop = asyncio.get_running_loop()
        self.demo = DemoPlayer(ShellSink(*self.synth), self._loop)
        self.ui.start_watch()
        for app, host, attr, ssl_ctx in ((self.public_app(), self.host, "port", self.ssl_ctx),
                                         (self.admin_app(), self.admin_host, "admin_port", None)):
            runner = web.AppRunner(app, access_log=None, handle_signals=False)
            await runner.setup()
            await web.TCPSite(runner, host, getattr(self, attr), ssl_context=ssl_ctx).start()
            setattr(self, attr, runner.addresses[0][1])
            self._runners.append(runner)

    async def stop(self):
        self._disconnect_all()
        for runner in self._runners:
            await runner.cleanup()
        self._runners.clear()

    async def serve(self):
        await self.start()
        try:
            await asyncio.Event().wait()
        finally:
            await self.stop()


def make_app(**kw):
    """Convenience for tests / __main__: Auth + preloaded assets + server."""
    auth = kw.pop("auth", None) or Auth(kw.pop("sessions_path", None))
    assets = kw.pop("assets", None) or load_static(kw.pop("static_dir", STATIC_DIR))
    return WebCompanion(auth, assets, **kw)
