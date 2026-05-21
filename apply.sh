#!/usr/bin/env bash
# apply.sh — idempotent migration runner for pisynth (think DB migrations).
#
# Workflow: rsync the repo onto the Pi, then run ONE command:
#     sudo bash ~/pisynth/apply.sh
# (or from the laptop in one shot: ./deploy.sh)
#
# It runs every migrations/NNN-*.sh that isn't recorded in the ledger yet,
# in numeric order, and records each on success. Re-running only applies new
# ones. Each migration receives, in its environment:
#     TARGET_USER  the human user (not root) the synth runs as
#     TARGET_HOME  that user's home directory
#     REPO_DIR     absolute path of this repo on the Pi
#
# Usage:
#     apply.sh            apply pending migrations
#     apply.sh --status   list applied / pending, do nothing
#     apply.sh --redo     re-run ALL migrations (ignore the ledger)

set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "Run as root:  sudo bash $0" >&2; exit 1; }

REPO_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
MIG_DIR="$REPO_DIR/migrations"
LEDGER_DIR=/var/lib/pisynth
LEDGER="$LEDGER_DIR/applied"

export REPO_DIR
# Target user the synth runs as. Order: pisynth.conf (PISYNTH_USER, rsync'd with
# the repo) → whoever ran sudo (SUDO_USER) → this file's owner. Lets the username
# be configured instead of hardcoded.
[[ -f "$REPO_DIR/pisynth.conf" ]] && . "$REPO_DIR/pisynth.conf"
export TARGET_USER="${PISYNTH_USER:-${SUDO_USER:-$(stat -c %U "$0")}}"
export TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"

mkdir -p "$LEDGER_DIR"
touch "$LEDGER"

applied() { grep -qxF "$1" "$LEDGER"; }

# --status: show state and exit.
if [[ "${1:-}" == "--status" ]]; then
    echo "ledger: $LEDGER   user: $TARGET_USER"
    shopt -s nullglob
    for mig in "$MIG_DIR"/[0-9]*.sh; do
        name="$(basename "$mig")"
        applied "$name" && echo "  [x] $name" || echo "  [ ] $name"
    done
    exit 0
fi

force=0
[[ "${1:-}" == "--redo" ]] && force=1

# Reboot coordination: a migration that changes boot config (cmdline.txt /
# config.txt / overlays) appends a reason line to $PISYNTH_REBOOT_FLAG. We reboot
# at the very end so the change ships in the SAME deploy — no manual step.
# Cleared at the start of every run; skip with PISYNTH_NO_REBOOT=1.
REBOOT_FLAG="$LEDGER_DIR/reboot-required"
rm -f "$REBOOT_FLAG"
export PISYNTH_REBOOT_FLAG="$REBOOT_FLAG"

ran=0
shopt -s nullglob
for mig in "$MIG_DIR"/[0-9]*.sh; do
    name="$(basename "$mig")"
    if [[ $force -eq 0 ]] && applied "$name"; then
        continue
    fi
    echo "── applying $name ──────────────────────────────"
    if bash "$mig"; then
        applied "$name" || echo "$name" >> "$LEDGER"
        echo "✓ $name"
        ran=$((ran + 1))
    else
        echo "✗ $name FAILED — stopping. Fix it and re-run." >&2
        exit 1
    fi
done

if [[ $ran -eq 0 ]]; then
    echo "No new migrations."
else
    echo "Applied $ran migration(s)."
fi

# Always re-deploy fast-changing app code (not ledgered).
if [[ -f "$REPO_DIR/sync.sh" ]]; then
    echo "── sync (every apply) ─────────────────────────"
    bash "$REPO_DIR/sync.sh"
fi

# A migration changed boot config → reboot now so it ships with this deploy.
if [[ -s "$REBOOT_FLAG" ]]; then
    echo "── reboot required by this deploy ─────────────"
    sed 's/^/  • /' "$REBOOT_FLAG"
    rm -f "$REBOOT_FLAG"
    if [[ -n "${PISYNTH_NO_REBOOT:-}" ]]; then
        echo "PISYNTH_NO_REBOOT set — skipping. Reboot later: sudo systemctl reboot"
    else
        echo "Rebooting in 3s (set PISYNTH_NO_REBOOT=1 to skip)…"
        # Schedule it just after we exit so apply.sh returns 0 and ssh closes cleanly.
        systemd-run --quiet --on-active=3s --unit=pisynth-deploy-reboot systemctl reboot \
            2>/dev/null || setsid -f bash -c 'sleep 3; systemctl reboot' || true
    fi
fi
