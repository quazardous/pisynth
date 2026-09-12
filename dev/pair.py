#!/usr/bin/env python3
"""Pair a phone with the local dev stack (#2415): mint a one-time token through the admin API
and print the URL + a QR code in the terminal. `make pair` (or APP=8443 for the built app)."""
import json
import os
import socket
import sys
import urllib.request


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 53))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    admin = os.environ.get("ADMIN", "http://127.0.0.1:9811")
    port = os.environ.get("APP", "5173")
    host = os.environ.get("LAN_IP") or lan_ip()
    req = urllib.request.Request(admin + "/admin/token", method="POST", data=b"")
    with urllib.request.urlopen(req, timeout=5) as r:
        info = json.load(r)
    url = f"https://{host}:{port}/#k={info['token']}"
    print(f"\n  {url}\n  valid {info['ttl']} s · single use · cert {info['fingerprint'][:23]}…\n")
    try:
        import segno
        segno.make(url, error="m").terminal(compact=True)
    except ImportError:
        print("  (pip install segno for a terminal QR code)", file=sys.stderr)


if __name__ == "__main__":
    main()
