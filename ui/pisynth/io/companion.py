"""Web companion adapter (#659): the touch UI's side of pisynth-web's loopback admin API.

pisynth-web owns pairing; the UI only asks it for a one-time token to show as a QR code,
for the paired-phone count, and to forget every phone. Plain HTTP on 127.0.0.1 — never on
the LAN. Every call fails soft (None/False) when the service isn't running.
"""
import json
import os
import urllib.error
import urllib.request

ADMIN_URL = os.environ.get("PISYNTH_WEB_ADMIN", "http://127.0.0.1:9811")


class CompanionClient:
    def __init__(self, base=ADMIN_URL, timeout=1.5):
        self.base, self.timeout = base.rstrip("/"), timeout

    def _call(self, method, path, timeout=None):
        req = urllib.request.Request(self.base + path, method=method, data=b"" if method == "POST" else None)
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
                return json.load(r)
        except (urllib.error.URLError, OSError, ValueError):
            return None

    def token(self):
        """{token, ttl, port, fingerprint} or None."""
        return self._call("POST", "/admin/token")

    def forget_all(self):
        return self._call("POST", "/admin/forget") is not None

    def stats(self, timeout=None):
        """{clients, sessions, frames, relay_us} or None."""
        return self._call("GET", "/admin/stats", timeout)
