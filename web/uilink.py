"""Link to the touch UI's control socket (#2417): the synth settings API, relayed to the phone.

The touch UI owns the synth state; pisynth-web only forwards the paired phone's `get`/`set`
requests to it (JSON lines on 127.0.0.1:9810) and streams its `watch` updates back — no
synth logic here. Reconnects on its own when the UI restarts.
"""
import asyncio
import json


class UiLink:
    def __init__(self, host="127.0.0.1", port=9810, on_state=None):
        self.host, self.port, self.on_state = host, port, on_state
        self._watch_task = None

    async def request(self, msg, timeout=15.0):
        """One JSON request → the UI's JSON reply (or an error dict). `get` can take a moment
        (it reads soundfont presets and the output volume)."""
        try:
            r, w = await asyncio.wait_for(asyncio.open_connection(self.host, self.port), 2)
        except (OSError, asyncio.TimeoutError):
            return {"ok": False, "error": "pisynth UI unreachable"}
        try:
            w.write((json.dumps(msg) + "\n").encode())
            await w.drain()
            line = await asyncio.wait_for(r.readline(), timeout)
            return json.loads(line) if line else {"ok": False, "error": "no reply"}
        except (OSError, asyncio.TimeoutError, ValueError):
            return {"ok": False, "error": "pisynth UI did not answer"}
        finally:
            w.close()

    def start_watch(self):
        if self._watch_task is None:
            self._watch_task = asyncio.ensure_future(self._watch())

    async def _watch(self):
        while True:
            try:
                r, w = await asyncio.wait_for(asyncio.open_connection(self.host, self.port), 2)
                w.write(b'{"op":"watch"}\n')
                await w.drain()
                while True:
                    line = await r.readline()
                    if not line:
                        break
                    try:
                        msg = json.loads(line)
                    except ValueError:
                        continue
                    if self.on_state and isinstance(msg, dict) and "state" in msg:
                        self.on_state(msg["state"])
                w.close()
            except (OSError, asyncio.TimeoutError):
                pass
            await asyncio.sleep(2.0)                  # UI restarting / not up yet
