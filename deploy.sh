#!/usr/bin/env bash
# deploy.sh — the ONE command, run from the laptop:
#     ./deploy.sh
# Syncs this repo to the Pi and applies migrations + app sync. Asks the sudo
# password once (via ssh -t). Everything is logged to deploy.log so the result
# can be reviewed afterwards. Pi target comes from pisynth.conf (see
# pisynth.conf.dist); the PISYNTH_HOST env var overrides it.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
for c in "$REPO_DIR/pisynth.conf" "$REPO_DIR/pisynth.conf.dist"; do
    [ -n "${PISYNTH_HOST:-}" ] && break
    [ -f "$c" ] && . "$c"
done
PI="${PISYNTH_HOST:-pi@raspberrypi.local}"
LOG="$REPO_DIR/deploy.log"

# Log everything (stdout+stderr) while keeping stdin on the real terminal so
# the ssh/sudo password prompt still works.
exec > >(tee -a "$LOG") 2>&1

echo
echo "===== deploy $(date -Is)  →  $PI ====="

echo "→ rsync  $REPO_DIR/  →  $PI:~/pisynth/"
rsync -az --delete \
    --exclude '.git' \
    --exclude '*.bak' \
    --exclude 'deploy.log' \
    --exclude 'last-shot.png' \
    "$REPO_DIR"/ "$PI":pisynth/

echo "→ apply migrations + sync on $PI (sudo)"
ssh -t "$PI" 'sudo bash ~/pisynth/apply.sh'

echo "===== end $(date -Is)  rc=$? ====="
