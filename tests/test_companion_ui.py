"""Touch-UI side of the web companion (#659): admin client, QR panel, Home QR slot."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from pisynth.io.companion import CompanionClient
from pisynth.screens import companion as C
from pisynth.ui.menu import MenuScreen


def test_url_and_fingerprint_helpers():
    assert C.companion_url("192.168.50.23", 8443, "tok") == "https://192.168.50.23:8443/#k=tok"
    assert C.short_fingerprint("AA:BB:CC:DD:EE:FF:11:22") == "AA:BB:CC:DD:EE:FF…"
    assert C.short_fingerprint("AA:BB") == "AA:BB" and C.short_fingerprint("") == ""
    plain = {"token": "tok", "port": 8443}
    assert C.pairing_url("192.168.50.23", plain) == "https://192.168.50.23:8443/#k=tok"
    assert C.pairing_url("192.168.50.23", {**plain, "setup_port": 8080}) == "http://192.168.50.23:8080/#k=tok"   # #2427


@pytest.fixture
def admin():
    calls = []

    class H(BaseHTTPRequestHandler):
        def _send(self, obj):
            body = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            calls.append(self.path)
            self._send({"token": "t1", "ttl": 120, "port": 8443, "fingerprint": "AA:BB"} if self.path == "/admin/token"
                       else {"sessions": 0})

        def do_GET(self):
            calls.append(self.path)
            self._send({"clients": 1, "sessions": 3, "frames": 9, "relay_us": {}})

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", calls
    srv.shutdown()


def test_client_calls_the_admin_api(admin):
    base, calls = admin
    c = CompanionClient(base)
    assert c.token()["token"] == "t1"
    assert c.stats()["sessions"] == 3
    assert c.forget_all() is True
    assert calls == ["/admin/token", "/admin/stats", "/admin/forget"]


def test_client_fails_soft_when_service_is_down():
    c = CompanionClient("http://127.0.0.1:1", timeout=0.5)
    assert c.token() is None and c.stats() is None and c.forget_all() is False


class Host(C.CompanionMixin):
    def __init__(self, client):
        self.fb = type("FB", (), {"h": 320})()
        self.view = type("V", (), {"BAR_H": 53})()
        self.stack = [MenuScreen("pisynth", [])]
        self.toasts, self.renders = [], 0
        self._companion_init()
        self.companion = client

    cur = property(lambda self: self.stack[-1])

    def toast(self, msg, secs=3.0):
        self.toasts.append(msg)

    def render(self):
        self.renders += 1

    def _dialog(self, title, yes_label, on_yes, no_label="Cancel", on_no=None):
        self.stack.append(MenuScreen(title, []))
        self.dialog_yes = on_yes


class FakeClient:
    def token(self):
        if not self.up:
            return None
        self.minted += 1
        return {"token": f"t{self.minted}", "ttl": 120, "port": 8443, "fingerprint": "AA:BB"}

    def __init__(self, up=True, sessions=0, clients=0):
        self.up, self.minted, self.sessions, self.clients = up, 0, sessions, clients

    demo = False
    stopped = 0

    def stats(self, timeout=None):
        return {"clients": self.clients, "sessions": self.sessions, "demo": {"active": self.demo}} if self.up else None

    def stop_demo(self):
        self.stopped += 1
        return True


def test_qr_screen_opens_with_url_and_refreshes_before_expiry(monkeypatch):
    monkeypatch.setattr(C, "local_ip", lambda: "10.0.0.5")
    monkeypatch.setattr(C, "qr_image", lambda url, size: ("QR", url, size))
    h = Host(FakeClient())
    h._open_pair_qr()
    panel = h.cur.panel
    assert h.cur.title == C.QR_TITLE and panel["qr"] == ("QR", "https://10.0.0.5:8443/#k=t1", 320 - 53 - 16)
    assert "https://10.0.0.5:8443" in panel["lines"]
    assert h._companion_tick(h._qr_expires - C.REFRESH_MARGIN_S - 5) is True and h.companion.minted == 1
    assert h._companion_tick(h._qr_expires - C.REFRESH_MARGIN_S + 1) is True and h.companion.minted == 2
    h.stack.pop()
    assert h._companion_tick(10**9) is False                    # not on the QR screen: nothing


def test_qr_follows_the_pis_current_ip_and_opens_the_setup_page(monkeypatch):
    """No address is stored anywhere: every refresh reads the Pi's IP again (DHCP can change it)."""
    ip = {"now": "10.0.0.5"}
    monkeypatch.setattr(C, "local_ip", lambda: ip["now"])
    monkeypatch.setattr(C, "qr_image", lambda url, size: url)
    client = FakeClient()
    client.token = lambda: {"token": "t", "ttl": 120, "port": 8443, "setup_port": 8080, "ca_fingerprint": "CA:FE"}
    h = Host(client)
    h._open_pair_qr()
    assert h.cur.panel["qr"] == "http://10.0.0.5:8080/#k=t" and "CA:FE" in h.cur.panel["lines"]
    ip["now"] = "10.0.0.99"                                     # the Pi got a new address
    h._companion_tick(h._qr_expires)
    assert h.cur.panel["qr"] == "http://10.0.0.99:8080/#k=t"


def test_qr_screen_toasts_when_service_is_off():
    h = Host(FakeClient(up=False))
    h._open_pair_qr()
    assert h.toasts == ["Web companion not running"] and len(h.stack) == 1
    assert h._paired_label() == "service off"


def test_home_bar_hit_areas_do_not_overlap():
    from pisynth.ui.renderer import Renderer
    r = Renderer.__new__(Renderer)
    r.BAR_H = 53
    metro = [x for x in range(0, 480) if r._home_metro_hit(x)]
    qr = [x for x in range(0, 480) if r._home_qr_hit(x)]
    assert metro and qr and max(metro) < min(qr)
    assert min(metro) > 56                                        # the cog keeps x ≤ 56


def test_companion_state_from_stats():
    assert Host(FakeClient(up=False))._companion_state() == "none"
    assert Host(FakeClient(sessions=0))._companion_state() == "none"
    assert Host(FakeClient(sessions=1))._companion_state() == "paired"
    assert Host(FakeClient(sessions=1, clients=1))._companion_state() == "live"


def test_pairing_opens_directly_when_nobody_is_paired(monkeypatch):
    monkeypatch.setattr(C, "local_ip", lambda: "10.0.0.5")
    monkeypatch.setattr(C, "qr_image", lambda url, size: None)
    h = Host(FakeClient())
    h._request_pair()
    assert h.cur.title == C.QR_TITLE and len(h.stack) == 2


def test_pairing_warns_when_a_browser_is_paired_then_replaces(monkeypatch):
    monkeypatch.setattr(C, "local_ip", lambda: "10.0.0.5")
    monkeypatch.setattr(C, "qr_image", lambda url, size: None)
    h = Host(FakeClient(sessions=1, clients=1))
    h._request_pair()
    assert h.cur.title == "Replace paired browser?" and "disconnected" in h.cur.footer
    assert h.companion.minted == 0                                  # no code shown before confirming
    h.dialog_yes()
    assert [m.title for m in h.stack] == ["pisynth", C.QR_TITLE]    # warning replaced by the QR


def test_companion_build_reads_the_hash_of_the_built_app():
    import json
    from pathlib import Path
    built = json.loads((Path(__file__).resolve().parents[1] / "web" / "static" / "build.json").read_text())
    assert C.companion_build() == built["hash"] and len(built["hash"]) >= 8          # Vite's content hash of the entry chunk


def test_home_slot_stops_a_running_demo_instead_of_pairing():
    c = FakeClient(sessions=1, clients=1)
    c.demo = True
    h = Host(c)
    assert h._companion_state() == "demo"
    h._request_pair()
    assert c.stopped == 1 and h.toasts == ["Demo stopped"] and len(h.stack) == 1 and c.minted == 0
