"""Bluetooth pairing-manager backend (#287/#301): a non-blocking worker around
bluetoothctl. Self-contained — no app config leaks in.
"""
import queue
import re
import subprocess
import threading
import time

_DEV_RE = re.compile(r"Device\s+([0-9A-F:]{17})", re.I)


def any_connected():
    """True if any Bluetooth device is currently connected (#306 Home indicator).
    Standalone one-shot — doesn't need the Bluetooth worker (which only runs while the
    pairing screen is open). Cheap enough for the throttled Home status poll."""
    try:
        r = subprocess.run(["bluetoothctl", "devices", "Connected"],
                           capture_output=True, text=True, timeout=4)
    except (OSError, subprocess.SubprocessError):
        return False
    return any(_DEV_RE.match(ln.strip()) for ln in r.stdout.splitlines())


class Bluetooth:
    """Pairing manager backend (#287). ALL bluetoothctl work runs in a background worker
    thread (#298 fix): the earlier version called bluetoothctl synchronously in the single
    -threaded UI loop, which froze touch for seconds. Now the worker maintains a cached
    device list and executes actions from a queue; the UI reads the cache and submits jobs
    without ever blocking. `open()`/`close()` start/stop the worker when the screen is shown."""

    DEV_RE = re.compile(r"Device\s+([0-9A-F:]{17})\s*(.*)", re.I)

    def __init__(self):
        self._scan_proc = None
        self._cache = []
        self._lock = threading.Lock()
        self._jobs = None
        self._worker = None
        self._open = False
        self._alias = {}               # mac -> friendly name resolved via `info` (#301)
        self.last_result = None        # short status string for the UI footer

    # ---- subprocess helpers — only ever called from the worker thread ----
    def _run(self, *args, timeout=8):
        try:
            r = subprocess.run(["bluetoothctl", *args],
                               capture_output=True, text=True, timeout=timeout)
            return r.returncode == 0, r.stdout
        except (OSError, subprocess.SubprocessError):
            return False, ""

    def _macs(self, *filt):
        out = set()
        for ln in self._run("devices", *filt, timeout=5)[1].splitlines():
            m = self.DEV_RE.match(ln.strip())
            if m:
                out.add(m.group(1))
        return out

    def _alias_for(self, mac):
        """Friendly name from `bluetoothctl info` (Alias, else Name), cached per mac.
        `devices` sometimes lists a device by MAC only until its name resolves (#301)."""
        if mac in self._alias:
            return self._alias[mac]
        name = ""
        for ln in self._run("info", mac, timeout=5)[1].splitlines():
            ln = ln.strip()
            if ln.startswith("Alias:"):
                name = ln.split(":", 1)[1].strip(); break
            if ln.startswith("Name:") and not name:
                name = ln.split(":", 1)[1].strip()
        if name and name != mac:
            self._alias[mac] = name
        return name

    def _query(self):
        # Scan-aware listing (#301: "le forget devrait faire disparaître le device").
        # `bluetoothctl devices` (no filter) keeps listing discovered/advertising
        # devices long after `remove` — and now that scan persists, an in-range device
        # is re-discovered the instant it's forgotten, so it never leaves the list.
        # Fix: when NOT scanning, list only PAIRED devices (authoritative — a forgotten
        # device is unpaired, so it drops immediately). While scanning, list everything
        # so new devices still appear to be paired.
        scanning = self._scan_proc is not None and self._scan_proc.poll() is None
        paired, connected = self._macs("Paired"), self._macs("Connected")
        filt = () if scanning else ("Paired",)
        out = []
        for ln in self._run("devices", *filt, timeout=5)[1].splitlines():
            m = self.DEV_RE.match(ln.strip())
            if m:
                mac = m.group(1)
                name = m.group(2).strip()
                if not name or name == mac:        # no friendly name in the listing → ask info
                    name = self._alias_for(mac) or mac
                out.append((mac, name, mac in paired, mac in connected))
        return out

    def _set_scan(self, on):
        """Persistent discovery via an interactive bluetoothctl held open on a stdin pipe.
        `bluetoothctl scan on` as a one-shot with stdin=DEVNULL hits EOF and exits at once,
        and BlueZ then drops the discovery registered to that D-Bus client — so the old code
        scanned for a split second and quit (#301: "le scan marche pas"). Keeping the process
        alive on an open pipe keeps the discovery client (and the scan) alive."""
        alive = self._scan_proc is not None and self._scan_proc.poll() is None
        if on and not alive:
            try:
                self._scan_proc = subprocess.Popen(
                    ["bluetoothctl"], stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self._scan_proc.stdin.write(b"scan on\n")
                self._scan_proc.stdin.flush()
            except OSError:
                self._scan_proc = None
        elif not on and self._scan_proc is not None:
            try:                                    # stop discovery cleanly, then leave the prompt
                self._scan_proc.stdin.write(b"scan off\nquit\n")
                self._scan_proc.stdin.flush()
                self._scan_proc.stdin.close()
            except (OSError, ValueError):
                pass
            try:
                self._scan_proc.wait(timeout=2)
            except subprocess.SubprocessError:
                self._scan_proc.kill()
            self._scan_proc = None
            self._run("scan", "off", timeout=3)     # belt-and-braces if the pipe write was lost

    def _do(self, action, arg):
        if action == "scan":
            self._set_scan(arg)
        elif action == "pair":
            self._run("pair", arg, timeout=30)      # may wait on the agent; verdict checked below
            self._run("trust", arg, timeout=5)
            self._run("connect", arg, timeout=15)
        elif action == "connect":
            self._run("connect", arg, timeout=15)
        elif action == "disconnect":
            self._run("disconnect", arg, timeout=10)
        elif action == "remove":
            # Clean forget (#301: "le forget ne supprime pas assez proprement"): a bare
            # `remove` on a connected/trusted device leaves the live link up and the trust
            # flag set, so BlueZ auto-reconnects it. Tear it down in order first.
            self._run("disconnect", arg, timeout=10)
            self._run("untrust", arg, timeout=5)
            self._run("remove", arg, timeout=10)
            self._alias.pop(arg, None)              # drop the cached friendly name too
        with self._lock:                            # reflect the action immediately
            self._cache = self._query()
        if action in ("pair", "connect"):
            self.last_result = self._verdict(arg)
        elif action == "disconnect":
            self.last_result = "disconnected"
        elif action == "remove":
            self.last_result = "removed"

    def _verdict(self, mac):
        """Report what BlueZ ACTUALLY says after a pair/connect — not bluetoothctl's exit
        code, which lies (it returns 0 even after 'Failed to connect'). #301: a dual-mode
        headset (e.g. Sony WH-1000XM4) can bring up its LE transport — BlueZ flags it
        `Connected` — while never bonding (`Paired` stays empty), so the device keeps
        blinking in pairing mode even though the old code flashed 'connected ✓'. Truth =
        the refreshed Paired/Connected sets in the cache."""
        paired = connected = False
        for m, _name, p, c in self._cache:
            if m == mac:
                paired, connected = p, c
                break
        if connected and paired:
            return "connected ✓"
        if connected:
            return "connected, not paired"          # link up (often LE-only) but no bond → still pairing
        if paired:
            return "paired, not connected"
        return "failed — try again"

    def _loop(self):
        self._run("power", "on", timeout=5)
        with self._lock:
            self._cache = self._query()
        last = time.monotonic()
        while self._open:
            try:
                job = self._jobs.get(timeout=0.5)
            except queue.Empty:
                job = None
            if job:
                self._do(*job)
            if time.monotonic() - last >= 2.0:      # periodic device refresh (in this thread)
                last = time.monotonic()
                with self._lock:
                    self._cache = self._query()
        self._set_scan(False)                       # cleanup on close

    # ---- UI-facing: non-blocking ----
    def open(self):
        if self._open:
            return
        self._open = True
        self.last_result = None
        self._jobs = queue.Queue()
        self._worker = threading.Thread(target=self._loop, daemon=True)
        self._worker.start()

    def close(self):
        self._open = False
        if self._jobs is not None:
            self._jobs.put(None)                    # wake the loop so it exits promptly
        self._worker = None

    def devices(self):
        with self._lock:
            return list(self._cache)

    def submit(self, action, arg, pending):
        """Queue an action for the worker; `pending` is shown in the footer meanwhile."""
        self.last_result = pending
        if self._jobs is not None:
            self._jobs.put((action, arg))
