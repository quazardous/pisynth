#!/usr/bin/env bash
# shot.sh — pull a screenshot of the Pi's SPI screen to the laptop.
# Usage: ./shot.sh [outfile]      (default: ./last-shot.png)
# Reads /dev/fb0 on the Pi via fbshot.py and saves a PNG locally.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
for c in "$REPO_DIR/pisynth.conf" "$REPO_DIR/pisynth.conf.dist"; do
    [ -n "${PISYNTH_HOST:-}" ] && break
    [ -f "$c" ] && . "$c"
done
PI="${PISYNTH_HOST:-pi@raspberrypi.local}"
OUT="${1:-$REPO_DIR/last-shot.png}"

ssh "$PI" 'python3 /usr/local/lib/pisynth/fbshot.py -' > "$OUT"
echo "saved $OUT ($(wc -c < "$OUT") bytes)"
