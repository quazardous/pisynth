#!/usr/bin/env python3
"""MIDI relay benchmark for pisynth-web (#2428): time from a MIDI event entering the server
(`feed()`, as the ALSA reader calls it) to a paired WebSocket client receiving the frame.

In-process, loopback, plain HTTP (TLS costs the same whatever serves it). Uses aiohttp's client,
so it measures any server implementation the same way:

    uvx --with aiohttp python tools/bench_web.py [--n 3000] [--rate 500]
    python3 tools/bench_web.py            # on the Pi (python3-aiohttp, migration 023)
"""
import argparse
import asyncio
import os
import socket
import struct
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import aiohttp  # noqa: E402

from web.auth import Auth  # noqa: E402
from web.server import WebCompanion  # noqa: E402


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def pct(xs, p):
    return xs[min(len(xs) - 1, int(len(xs) * p))]


async def run(n, rate):
    port, admin = free_port(), free_port()
    app = WebCompanion(Auth(), {}, host="127.0.0.1", port=port, admin_port=admin,
                       synth=("127.0.0.1", free_port()), ui=("127.0.0.1", free_port()))
    await app.start()
    base = f"http://127.0.0.1:{port}"
    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as http:
        async with http.post(f"http://127.0.0.1:{admin}/admin/token") as r:
            token = (await r.json())["token"]
        async with http.post(f"{base}/pair", json={"token": token}) as r:
            cookie = r.headers["Set-Cookie"].split(";")[0]
        async with http.ws_connect(f"{base}/ws", headers={"Cookie": cookie}) as ws:
            await asyncio.sleep(0.2)
            sent = [0] * n
            recv = [0] * n

            def producer():                          # the ALSA reader thread
                period = 1.0 / rate
                for i in range(n):
                    payload = struct.pack(">BBBI", 0x90, 60, 100, i)
                    sent[i] = time.monotonic_ns()
                    app.feed(payload, sent[i])
                    time.sleep(period)

            t = threading.Thread(target=producer, daemon=True)
            t.start()
            got = 0
            while got < n:
                msg = await asyncio.wait_for(ws.receive(), 10)
                if msg.type != aiohttp.WSMsgType.BINARY:
                    continue
                i = struct.unpack(">BBBI", msg.data)[3]
                recv[i] = time.monotonic_ns()
                got += 1
            t.join()
    lat = sorted((recv[i] - sent[i]) // 1000 for i in range(n))
    stats = app.stats()["relay_us"]
    print(f"frames {n} @ {rate}/s · feed→client µs: p50 {pct(lat, .5)} p99 {pct(lat, .99)} max {lat[-1]}"
          f" · server relay µs: p50 {stats['p50']} p99 {stats['p99']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--rate", type=int, default=500)
    a = ap.parse_args()
    asyncio.run(run(a.n, a.rate))


if __name__ == "__main__":
    main()
