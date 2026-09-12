"""`python3 -m web` — the pisynth-web service (#659): one warm process, started at boot.

Env: PISYNTH_WEB_PORT (8443), PISYNTH_WEB_ADMIN_PORT (9811, 127.0.0.1 only),
PISYNTH_WEB_CERT / PISYNTH_WEB_KEY (/etc/pisynth/web/{cert,key}.pem, migration 022),
PISYNTH_WEB_MIDI_SOURCE (aseqdump | sim | pi — dev stack, #2415), PISYNTH_WEB_MIDI_PORT
(aseqdump target; default: the first hardware keyboard), PISYNTH_WEB_ADMIN_HOST (127.0.0.1),
PISYNTH_WEB_SESSIONS (~/.config/pisynth/web_sessions.json).
"""
import asyncio
import os
import sys

from .auth import Auth
from .midi_source import make_source
from .server import WebCompanion, cert_fingerprint, load_static, make_ssl_context


def _persist_hook():
    """Read-only root (#681): write paired sessions through to the SD card. The pisynth
    package sits next to us on PYTHONPATH on the Pi; without it this is a no-op."""
    try:
        from pisynth.core.persist import request_persist
        return request_persist
    except ImportError:
        return None


def main():
    cert = os.environ.get("PISYNTH_WEB_CERT", "/etc/pisynth/web/cert.pem")
    key = os.environ.get("PISYNTH_WEB_KEY", "/etc/pisynth/web/key.pem")
    sessions = os.path.expanduser(os.environ.get("PISYNTH_WEB_SESSIONS", "~/.config/pisynth/web_sessions.json"))
    try:
        ssl_ctx, fingerprint = make_ssl_context(cert, key), cert_fingerprint(cert)
    except (OSError, ValueError) as e:
        print(f"[pisynth-web] no usable TLS certificate ({e}) — run the deploy (migration 022)", file=sys.stderr)
        sys.exit(1)
    app = WebCompanion(Auth(sessions, on_saved=_persist_hook()), load_static(),   # all warm before listening
                       port=int(os.environ.get("PISYNTH_WEB_PORT", "8443")),
                       admin_port=int(os.environ.get("PISYNTH_WEB_ADMIN_PORT", "9811")),
                       ssl_ctx=ssl_ctx, fingerprint=fingerprint,
                       admin_host=os.environ.get("PISYNTH_WEB_ADMIN_HOST", "127.0.0.1"))
    src = make_source(app.feed, os.environ)
    print(f"[pisynth-web] https :{app.port} · admin 127.0.0.1:{app.admin_port} · "
          f"{len(app.assets)} assets in RAM · {app.auth.session_count} paired phone(s) · "
          f"MIDI: {os.environ.get('PISYNTH_WEB_MIDI_SOURCE', 'aseqdump')}", flush=True)
    src.start()
    try:
        asyncio.run(app.serve())
    except KeyboardInterrupt:                        # Ctrl+C / dev auto-reload: quiet exit
        pass
    finally:
        src.stop()


if __name__ == "__main__":
    main()
