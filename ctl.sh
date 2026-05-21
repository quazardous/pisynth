#!/usr/bin/env bash
# ctl.sh — send a command to the running UI control socket on the Pi (:9810).
# Usage:
#   ./ctl.sh state
#   ./ctl.sh action next_preset
#   ./ctl.sh action gain_up
#   ./ctl.sh tap 100 200
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
for c in "$REPO_DIR/pisynth.conf" "$REPO_DIR/pisynth.conf.dist"; do
    [ -n "${PISYNTH_HOST:-}" ] && break
    [ -f "$c" ] && . "$c"
done
PI="${PISYNTH_HOST:-pi@raspberrypi.local}"
ssh "$PI" "printf '%s\n' '$*' | nc -q 1 127.0.0.1 9810"
