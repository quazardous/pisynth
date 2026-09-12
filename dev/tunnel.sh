#!/usr/bin/env bash
# Debug the web companion deployed ON the Pi from this machine (#2415): forward its HTTPS port
# and its loopback-only admin API to localhost. Then: https://localhost:28443 and
# `ADMIN=http://127.0.0.1:19811 APP=28443 LAN_IP=localhost python3 dev/pair.py`.
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
[ -n "${PISYNTH_HOST:-}" ] || { [ -f "$REPO_DIR/pisynth.conf" ] && . "$REPO_DIR/pisynth.conf"; }
PI="${PISYNTH_HOST:?set PISYNTH_HOST or pisynth.conf}"
echo "→ $PI  https://localhost:28443 (companion) · http://127.0.0.1:19811 (admin)  — Ctrl+C to stop"
exec ssh -N -o ExitOnForwardFailure=yes -L 28443:127.0.0.1:8443 -L 19811:127.0.0.1:9811 "$PI"
