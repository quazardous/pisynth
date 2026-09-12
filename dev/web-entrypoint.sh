#!/bin/sh
# Dev entrypoint (#2415): mint a self-signed cert once (shared with the Vite container), then run
# pisynth-web and restart it whenever a Python file under web/ changes.
set -eu
CERTS=/repo/dev/certs
if [ ! -s "$CERTS/cert.pem" ]; then
    mkdir -p "$CERTS"
    openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
        -keyout "$CERTS/key.pem" -out "$CERTS/cert.pem" -days 3650 \
        -subj "/CN=pisynth-dev" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" 2>/dev/null
    echo "[dev] generated $CERTS/cert.pem"
fi
bash /repo/midi-sync.sh /repo "${PISYNTH_MIDI_DIR:-/repo/dev/state/midi}"   # starter set + midi/ (#2421)
exec watchfiles --filter python "python3 -m web" /repo/web
