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


def companion_url(ip, port, token):
    return f"https://{ip}:{port}/#k={token}"


def short_fingerprint(fp, groups=6):
    parts = (fp or "").split(":")
    return ":".join(parts[:groups]) + ("…" if len(parts) > groups else "")


class CompanionMixin:
    def _companion_init(self):
        self.companion = CompanionClient()
        self._qr_expires = 0.0

    # ---- pairing QR ----
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
        url = companion_url(ip, info["port"], info["token"])
        self._qr_expires = time.monotonic() + info["ttl"]
        screen.panel = {
            "qr": qr_image(url, self.fb.h - self.view.BAR_H - 16),
            "lines": ["Scan to pair", "with your phone, on the", "same Wi-Fi as pisynth", "",
                      f"https://{ip}:{info['port']}", "",
                      "Accept the certificate once:", short_fingerprint(info.get("fingerprint", ""))],
            "expires": self._qr_expires,
        }
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
            Item(QR_TITLE, on_select=self._open_pair_qr, submenu=True),
            Item("Paired phones", value=self._paired_label),
            Item("Forget all phones", on_select=(lambda: self._confirm("Forget all phones", self._forget_phones)),
                 submenu=True),
        ])

    def _paired_label(self):
        st = self.companion.stats()
        if st is None:
            return "service off"
        live = f" · {st['clients']} live" if st.get("clients") else ""
        return f"{st['sessions']}{live}"

    def _forget_phones(self):
        ok = self.companion.forget_all()
        self._close_dialog()
        self.toast("All phones forgotten" if ok else "Web companion not running")
