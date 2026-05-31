#!/usr/bin/env python3
"""Entry point for the pisynth web companion (#659): wire the live ALSA-seq MIDI source
into the WebSocket server and run the single asyncio loop. Started by the pisynth-web
systemd unit (added in a later slice). Run standalone: `python3 web/run.py`.

Env: PISYNTH_WEB_PORT (default 8080), PISYNTH_WEB_MIDI_PORT (aseqdump target; default
auto-discovers the keyboard)."""
import asyncio
import os

from server import WebCompanion          # sibling import (run from web/ → on sys.path)
from midi_source import AlsaSeqSource


def main():
    app = WebCompanion(port=int(os.environ.get("PISYNTH_WEB_PORT", "8080")))
    src = AlsaSeqSource(on_event=app.feed, port=os.environ.get("PISYNTH_WEB_MIDI_PORT", ""))
    src.start()
    try:
        asyncio.run(app.serve())
    finally:
        src.stop()


if __name__ == "__main__":
    main()
