"""Web companion screens (#659): pair a phone with a QR code, list / forget paired phones.

Mixin for app.App. Opened from the QR glyph next to the metronome on Home (david), or from
Settings → Web companion. The QR carries `https://<Pi LAN IP>:<port>/#k=<one-time token>`;
the token is minted by pisynth-web (io/companion.py) and refreshed before it expires while
the screen is open. Cross-feature helpers (toast, _confirm, render) resolve via the MRO.
"""
import time

from ..core.system import local_ip
from ..io.companion import CompanionClient
from ..ui.menu import Item, MenuScreen
from ..ui.qr import qr_image

QR_TITLE = "Pair a phone"
REFRESH_MARGIN_S = 20                                   # mint a new code this long before expiry


def companion_build():
    """Build hash of the phone app pisynth-web serves (web/static/build.json, written by the
    Svelte build — the same hash versions the service worker). '?' if unknown."""
    import json
    import os
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # …/lib/pisynth or ui/
    for base in (os.path.join(here, "web"), os.path.join(os.path.dirname(here), "web")):
        try:
            with open(os.path.join(base, "static", "build.json")) as f:
                return json.load(f).get("hash", "?")
        except (OSError, ValueError):
            continue
    return "?"


def companion_url(ip, port, token):
    return f"https://{ip}:{port}/#k={token}"


def pairing_url(ip, info):
    """What the QR opens. With pisynth's own CA (#2427): the plain-HTTP setup page, which forwards a
    phone that already trusts the CA straight to the app and walks a new one through installing
    it; the code stays in the #fragment. Without it: the HTTPS app directly (old behaviour)."""
    if info.get("setup_port"):
        return f"http://{ip}:{info['setup_port']}/#k={info['token']}"
    return companion_url(ip, info["port"], info["token"])


def short_fingerprint(fp, groups=6):
    parts = (fp or "").split(":")
    return ":".join(parts[:groups]) + ("…" if len(parts) > groups else "")


class CompanionMixin:
    def _companion_init(self):
        self.companion = CompanionClient()
        self._qr_expires = 0.0
        self._st_companion = "none"                     # none | paired | live — Home QR colour

    def _companion_state(self):
        """From the service's stats: 'live' (browser connected), 'paired' (session, not connected),
        'none' (nobody paired, or the service is off). Loopback call, short timeout."""
        st = self.companion.stats(timeout=0.5)
        if not st:
            return "none"
        if (st.get("demo") or {}).get("active"):
            return "demo"                                 # the phone is playing a demo through the synth (#2416)
        return "live" if st.get("clients") else "paired" if st.get("sessions") else "none"

    # ---- pairing QR ----
    def _request_pair(self):
        """Home QR / Settings entry: when a browser is already paired, warn first — pairing
        another one disconnects it (one paired browser at a time)."""
        self._st_companion = self._companion_state()    # fresh, not the 3 s-old poll
        if self._st_companion == "demo":                # while a demo plays, the slot is its stop button (#2416)
            self.companion.stop_demo()
            self._st_companion = "live"
            self.toast("Demo stopped")
            return
        if self._st_companion == "none":
            self._open_pair_qr()
            return
        self._dialog("Replace paired browser?", "Pair a new one", self._confirm_replace)
        self.cur.footer = "The current browser will be disconnected."
        self.render()

    def _confirm_replace(self):
        self.stack.pop()                                # drop the warning; Back from the QR goes Home
        self._open_pair_qr()

    def _open_pair_qr(self):
        screen = MenuScreen(QR_TITLE, [])
        if not self._refresh_pair_qr(screen):
            self.toast("Web companion not running")
            return
        self.stack.append(screen)
        self.render()

    def _refresh_pair_qr(self, screen):
        info = self.companion.token()
        if not info:
            return False
        ip = local_ip()
        url = pairing_url(ip, info)
        self._qr_expires = time.monotonic() + info["ttl"]
        if info.get("setup_port"):                      # pisynth's CA (#2427): the page guides a new phone
            lines = ["Scan to pair", "with your phone, on the", "same Wi-Fi as pisynth", "",
                     "First time: the page shows", "how to trust pisynth.", "",
                     "Certificate fingerprint:", short_fingerprint(info.get("ca_fingerprint", ""))]
        else:
            lines = ["Scan to pair", "with your phone, on the", "same Wi-Fi as pisynth", "",
                     f"https://{ip}:{info['port']}", "",
                     "Accept the certificate once:", short_fingerprint(info.get("fingerprint", ""))]
        screen.panel = {"qr": qr_image(url, self.fb.h - self.view.BAR_H - 16), "lines": lines,
                        "expires": self._qr_expires}
        return True

    def _companion_tick(self, now):
        """Idle tick: keep the QR valid while it's on screen, and repaint the countdown."""
        cur = self.cur
        if getattr(cur, "panel", None) is None or cur.title != QR_TITLE:
            return False
        if now >= self._qr_expires - REFRESH_MARGIN_S:
            self._refresh_pair_qr(cur)
        return True

    # ---- Settings → Web companion ----
    def _companion_menu(self):
        return MenuScreen("Web companion", [
            Item(QR_TITLE, on_select=self._request_pair, submenu=True),
            Item("Paired browser", value=self._paired_label),
            Item("Unpair", on_select=(lambda: self._confirm("Unpair", self._forget_phones)), submenu=True),
        ])

    def _paired_label(self):
        st = self.companion.stats()
        if st is None:
            return "service off"
        return "connected" if st.get("clients") else "yes" if st.get("sessions") else "none"

    def _forget_phones(self):
        ok = self.companion.forget_all()
        self._close_dialog()
        self._st_companion = "none" if ok else self._st_companion
        self.toast("Browser unpaired" if ok else "Web companion not running")
