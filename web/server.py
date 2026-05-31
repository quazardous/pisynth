#!/usr/bin/env python3
"""pisynth-web — the learning-companion web server (#658/#659).

ONE asyncio process (mono-worker, david's call): serves the mobile-first static app
once, then fans out the live MIDI stream to every connected browser over a WebSocket.
Ultra-light on the wire — only note on/off events, a few bytes each; all rendering and
exercise logic live in the browser (we exploit the phone, spare the Pi 3B+). The sound
stays on the Pi (fluidsynth) — nothing audio crosses the wire.

Stdlib only (asyncio) — no extra dependency — so it stays light and self-contained. The
WebSocket framing is minimal on purpose: server→client text frames, plus enough client
frame decoding to honour PING and CLOSE. The MIDI source is injected (a thread that
calls `feed()`); io/midi_source.py provides the real ALSA-seq reader, tests a fake.
"""
import asyncio
import base64
import hashlib
import json
import os
import struct

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
_TYPES = {".html": "text/html; charset=utf-8", ".js": "application/javascript",
          ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml",
          ".ico": "image/x-icon"}

# ---- WebSocket framing (RFC 6455, the slice we need) ----

def accept_key(client_key):
    """Sec-WebSocket-Accept for a client's Sec-WebSocket-Key (RFC 6455 handshake)."""
    return base64.b64encode(hashlib.sha1((client_key + WS_GUID).encode()).digest()).decode()


def encode_text(payload):
    """A single unfragmented server→client TEXT frame (unmasked, as the server must)."""
    data = payload.encode()
    n = len(data)
    hdr = bytearray([0x81])                          # FIN=1, opcode=1 (text)
    if n < 126:
        hdr.append(n)
    elif n < 65536:
        hdr.append(126)
        hdr += struct.pack(">H", n)
    else:
        hdr.append(127)
        hdr += struct.pack(">Q", n)
    return bytes(hdr) + data


def decode_frames(buf):
    """Consume complete frames from bytearray `buf`, return [(opcode, payload_bytes), ...].
    Leaves any partial trailing frame in `buf` for the next read. Client frames are masked."""
    out = []
    while True:
        if len(buf) < 2:
            break
        b0, b1 = buf[0], buf[1]
        opcode = b0 & 0x0F
        masked = b1 & 0x80
        ln = b1 & 0x7F
        idx = 2
        if ln == 126:
            if len(buf) < 4:
                break
            ln = struct.unpack(">H", buf[2:4])[0]
            idx = 4
        elif ln == 127:
            if len(buf) < 10:
                break
            ln = struct.unpack(">Q", buf[2:10])[0]
            idx = 10
        need = idx + (4 if masked else 0) + ln
        if len(buf) < need:
            break
        if masked:
            mask = buf[idx:idx + 4]
            idx += 4
            payload = bytes(buf[idx + i] ^ mask[i % 4] for i in range(ln))
        else:
            payload = bytes(buf[idx:idx + ln])
        del buf[:idx + ln]
        out.append((opcode, payload))
    return out


def _parse_headers(blob):
    """{lower-name: value} from a raw HTTP request head (bytes), + the request line."""
    lines = blob.decode("latin1").split("\r\n")
    req = lines[0] if lines else ""
    headers = {}
    for ln in lines[1:]:
        if ":" in ln:
            k, v = ln.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return req, headers


class WebCompanion:
    """The asyncio server: static files + a MIDI-fan-out WebSocket (#659)."""

    def __init__(self, host="0.0.0.0", port=8080, static_dir=STATIC_DIR):
        self.host, self.port, self.static_dir = host, port, static_dir
        self.clients = set()                         # set[asyncio.StreamWriter] of live WS peers
        self._loop = None

    # ---- MIDI ingress (called from the reader thread) ----
    def feed(self, msg):
        """Thread-safe: queue a MIDI event dict for broadcast to all browsers (#659).
        Tiny on the wire — e.g. {'t':'on','n':60,'v':100}."""
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(self._broadcast, json.dumps(msg, separators=(",", ":")))

    def _broadcast(self, text):
        frame = encode_text(text)
        for w in list(self.clients):
            try:
                w.write(frame)
            except Exception:                        # dead peer → drop it
                self.clients.discard(w)

    # ---- connections ----
    async def _handle(self, reader, writer):
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=10)
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError, OSError):
            writer.close()
            return
        req, headers = _parse_headers(head)
        if headers.get("upgrade", "").lower() == "websocket":
            await self._serve_ws(reader, writer, headers)
        else:
            await self._serve_static(writer, req)

    async def _serve_ws(self, reader, writer, headers):
        key = headers.get("sec-websocket-key", "")
        writer.write(("HTTP/1.1 101 Switching Protocols\r\n"
                      "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {accept_key(key)}\r\n\r\n").encode())
        await writer.drain()
        self.clients.add(writer)
        buf = bytearray()
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                buf += data
                for opcode, payload in decode_frames(buf):
                    if opcode == 0x8:                # CLOSE
                        return
                    if opcode == 0x9:                # PING → PONG
                        writer.write(bytes([0x8A, len(payload)]) + payload)
                # (client→server data frames are ignored: the browser is display-only here)
        except (OSError, asyncio.IncompleteReadError):
            pass
        finally:
            self.clients.discard(writer)
            try:
                writer.close()
            except OSError:
                pass

    async def _serve_static(self, writer, req):
        path = "/"
        parts = req.split(" ")
        method = parts[0] if parts else ""
        if len(parts) >= 2:
            path = parts[1].split("?", 1)[0]
        if method != "GET":
            self._http(writer, 405, b"method not allowed")
        else:
            self._http_file(writer, path)
        try:
            await writer.drain()
        except OSError:
            pass
        writer.close()

    def _resolve(self, path):
        """Map a URL path to a safe file under static_dir, or None if it escapes / is missing."""
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        full = os.path.normpath(os.path.join(self.static_dir, rel))
        if not full.startswith(os.path.abspath(self.static_dir) + os.sep) and full != os.path.abspath(self.static_dir):
            return None                              # path traversal → refuse
        return full if os.path.isfile(full) else None

    def _http_file(self, writer, path):
        full = self._resolve(path)
        if not full:
            self._http(writer, 404, b"not found")
            return
        try:
            with open(full, "rb") as f:
                body = f.read()
        except OSError:
            self._http(writer, 404, b"not found")
            return
        ctype = _TYPES.get(os.path.splitext(full)[1].lower(), "application/octet-stream")
        self._http(writer, 200, body, ctype)

    @staticmethod
    def _http(writer, code, body, ctype="text/plain; charset=utf-8"):
        reason = {200: "OK", 404: "Not Found", 405: "Method Not Allowed"}.get(code, "OK")
        writer.write((f"HTTP/1.1 {code} {reason}\r\nContent-Type: {ctype}\r\n"
                      f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode() + body)

    async def serve(self):
        self._loop = asyncio.get_running_loop()
        server = await asyncio.start_server(self._handle, self.host, self.port)
        async with server:
            await server.serve_forever()
