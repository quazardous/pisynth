"""`python3 -m web` — the pisynth-web service (#659): one warm process, started at boot.

Env: PISYNTH_WEB_PORT (8443), PISYNTH_WEB_ADMIN_PORT (9811, 127.0.0.1 only),
PISYNTH_WEB_CERT / PISYNTH_WEB_KEY (/etc/pisynth/web/{cert,key}.pem, migration 022),
PISYNTH_WEB_MIDI_SOURCE (aseqdump | sim | pi — dev stack, #2415), PISYNTH_WEB_MIDI_PORT
(aseqdump target; default: the first hardware keyboard), PISYNTH_WEB_ADMIN_HOST (127.0.0.1),
PISYNTH_WEB_SESSIONS (~/.config/pisynth/web_sessions.json), PISYNTH_MIDI_DIR (the MIDI library,
~/midi), PISYNTH_REPO (the deployed repo its links point into, ~/pisynth) — #2421,
PISYNTH_WEB_CA (/etc/pisynth/web/ca.pem) + PISYNTH_WEB_SETUP_PORT (8080; "" = off): the plain-HTTP
setup page that installs pisynth's CA on a phone (#2427).
"""
import asyncio
import os
import sys

from .auth import Auth
from .library import MidiLibrary
from .midi_source import SimSource, make_source
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
        print(f"[pisynth-web] no usable TLS certificate ({e}) — run the deploy (pisynth-web-cert ensure)", file=sys.stderr)
        sys.exit(1)
    setup_port = os.environ.get("PISYNTH_WEB_SETUP_PORT", "8080")
    repo = os.path.expanduser(os.environ.get("PISYNTH_REPO", "~/pisynth"))
    library = MidiLibrary(os.path.expanduser(os.environ.get("PISYNTH_MIDI_DIR", "~/midi")),
                          {"starter": os.path.join(repo, "library", "midi"), "pc": os.path.join(repo, "midi")},
                          on_changed=_persist_hook())
    app = WebCompanion(Auth(sessions, on_saved=_persist_hook()), load_static(),   # all warm before listening
                       library=library,
                       ca_cert=os.environ.get("PISYNTH_WEB_CA", "/etc/pisynth/web/ca.pem"),
                       setup_port=int(setup_port) if setup_port else None,
                       port=int(os.environ.get("PISYNTH_WEB_PORT", "8443")),
                       admin_port=int(os.environ.get("PISYNTH_WEB_ADMIN_PORT", "9811")),
                       ssl_ctx=ssl_ctx, fingerprint=fingerprint,
                       admin_host=os.environ.get("PISYNTH_WEB_ADMIN_HOST", "127.0.0.1"),
                       synth=(os.environ.get("PISYNTH_WEB_SYNTH_HOST", "127.0.0.1"),
                              int(os.environ.get("PISYNTH_WEB_SYNTH_PORT", "9800"))))
    src = make_source(app.feed, os.environ)
    if isinstance(src, SimSource):
        app.sim = src                                # dev stack: the simulator can play along the phone's song
    setup = f"setup http :{app.setup_port} · " if app.ca_pem and app.setup_port else "no CA · "
    print(f"[pisynth-web] https :{app.port} · admin 127.0.0.1:{app.admin_port} · {setup}"
          f"{len(app.assets)} assets in RAM · {app.auth.session_count} paired phone(s) · MIDI library {library.root} · "
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
