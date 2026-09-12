#!/usr/bin/env bash
# deploy.sh — the ONE command, run from the laptop:
#     ./deploy.sh
# Syncs this repo to the Pi and applies migrations + app sync. sudo may ask the Pi's
# password (via ssh -t), depending on the Pi. Everything is logged to deploy.log so the
# result can be reviewed afterwards. Pi target comes from pisynth.conf (see
# pisynth.conf.dist); the PISYNTH_HOST env var overrides it.
#
# Read-only root (#681): if the Pi runs with the overlay on, apply.sh turns it off,
# reboots and exits 75; we wait for the Pi to come back and run the deploy again on a
# writable root (apply.sh switches the overlay back on at the end if PISYNTH_READONLY=1).

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

ssh_ok() { ssh -o BatchMode=yes -o ConnectTimeout=5 "$PI" true </dev/null >/dev/null 2>&1; }

# Wait for the Pi to go down (reboot scheduled 3 s after apply.sh exits), then back up.
wait_for_reboot() {
    local t
    for t in $(seq 1 30); do ssh_ok || break; sleep 2; done
    echo "  … Pi is rebooting, waiting for SSH"
    for t in $(seq 1 60); do
        sleep 5
        if ssh_ok; then echo "  … Pi is back"; return 0; fi
    done
    echo "✗ Pi did not come back within 5 min" >&2
    return 1
}

echo
echo "===== deploy $(date -Is)  →  $PI ====="

# Web companion (#659): rebuild the phone app when the Svelte toolchain is installed here, so
# the Pi never serves a stale build. (web/static is committed; Node is never needed on the Pi.)
if [[ -d "$REPO_DIR/web/app/node_modules" ]] && command -v npm >/dev/null; then
    echo "→ build web companion (web/app → web/static)"
    npm --prefix "$REPO_DIR/web/app" run --silent build >/dev/null
fi

rc=0
for pass in 1 2; do
    echo "→ rsync  $REPO_DIR/  →  $PI:~/pisynth/"
    rsync -az --delete \
        --exclude '.git' \
        --exclude '*.bak' \
        --exclude 'deploy.log' \
        --exclude 'last-shot.png' \
        --exclude 'node_modules' \
        --exclude '/dev/certs' --exclude '/dev/state' \
        "$REPO_DIR"/ "$PI":pisynth/

    echo "→ apply migrations + sync on $PI (sudo)"
    rc=0
    ssh -t "$PI" 'sudo bash ~/pisynth/apply.sh' || rc=$?
    [[ $rc -eq 75 && $pass -eq 1 ]] || break
    echo "→ read-only root was on: turned off for this deploy, resuming after the reboot"
    wait_for_reboot || { rc=1; break; }
done

echo "===== end $(date -Is)  rc=$rc ====="
exit "$rc"
