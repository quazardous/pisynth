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
# Host-local one-shots: local-migrations/NNN-*.sh (gitignored, but rsync'd by
# deploy.sh like pisynth.conf) run right after the repo migrations, same ledger
# and rules, recorded as "local/<name>". For per-device tweaks that must not ship
# to every install.
#
# Usage:
#     apply.sh            apply pending migrations
#     apply.sh --status   list applied / pending, do nothing
#     apply.sh --redo     re-run ALL migrations (ignore the ledger)

set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "Run as root:  sudo bash $0" >&2; exit 1; }

REPO_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
MIG_DIR="$REPO_DIR/migrations"
LOCAL_DIR="$REPO_DIR/local-migrations"
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

# All migrations in run order, one "<ledger key>|<path>" per line: the repo's first,
# then the host-local ones (keyed local/<name> so they can't collide).
all_migrations() {
    local mig
    shopt -s nullglob
    for mig in "$MIG_DIR"/[0-9]*.sh;   do echo "$(basename "$mig")|$mig"; done
    for mig in "$LOCAL_DIR"/[0-9]*.sh; do echo "local/$(basename "$mig")|$mig"; done
    shopt -u nullglob
}

# --status: show state and exit.
if [[ "${1:-}" == "--status" ]]; then
    echo "ledger: $LEDGER   user: $TARGET_USER"
    while IFS='|' read -r name mig; do
        applied "$name" && echo "  [x] $name" || echo "  [ ] $name"
    done < <(all_migrations)
    echo "read-only root: $(bash "$REPO_DIR/readonly.sh" status)   wanted: PISYNTH_READONLY=${PISYNTH_READONLY:-0}"
    exit 0
fi

force=0
[[ "${1:-}" == "--redo" ]] && force=1

# Schedule a reboot just after we exit, so apply.sh returns and ssh closes cleanly.
schedule_reboot() {
    systemd-run --quiet --on-active=3s --unit="pisynth-deploy-reboot-$$" systemctl reboot \
        2>/dev/null || setsid -f bash -c 'sleep 3; systemctl reboot' || true
}

# Read-only root (#681 phase B): with the overlay active, anything written now (this
# deploy included) would vanish at reboot. Turn it off, reboot, and let deploy.sh resume
# on a writable root (exit code 75 = "rebooting, run me again"). It is switched back on at
# the end of the resumed run when PISYNTH_READONLY=1.
if grep -qw "overlayroot=tmpfs" /proc/cmdline; then
    echo "── read-only root is active: turning it off for this deploy ──"
    if [[ -n "${PISYNTH_NO_REBOOT:-}" ]]; then
        echo "✗ PISYNTH_NO_REBOOT is set, but a deploy needs a reboot to leave read-only mode." >&2
        exit 1
    fi
    bash "$REPO_DIR/readonly.sh" disable
    echo "Rebooting in 3s; re-run the deploy once the Pi is back (deploy.sh does it for you)."
    schedule_reboot
    exit 75
fi

# Reboot coordination: a migration that changes boot config (cmdline.txt /
# config.txt / overlays) appends a reason line to $PISYNTH_REBOOT_FLAG. We reboot
# at the very end so the change ships in the SAME deploy — no manual step.
# Cleared at the start of every run; skip with PISYNTH_NO_REBOOT=1.
REBOOT_FLAG="$LEDGER_DIR/reboot-required"
rm -f "$REBOOT_FLAG"
export PISYNTH_REBOOT_FLAG="$REBOOT_FLAG"

ran=0
# fd 3, not stdin: a migration (apt-get, …) reading stdin must not swallow the list.
while IFS='|' read -r name mig <&3; do
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
done 3< <(all_migrations)

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

# Read-only root wanted? (pisynth.conf: PISYNTH_READONLY=1) Switch it on last, once
# everything above is on the SD; it takes effect with the reboot below.
if [[ "${PISYNTH_READONLY:-0}" == "1" ]]; then
    if ! bash "$REPO_DIR/readonly.sh" status | grep -q "configured=1"; then
        echo "── read-only root: enabling (PISYNTH_READONLY=1) ──"
        bash "$REPO_DIR/readonly.sh" enable
        echo "read-only root (overlayroot) enabled" >> "$REBOOT_FLAG"
    fi
elif bash "$REPO_DIR/readonly.sh" status | grep -q "configured=1"; then
    bash "$REPO_DIR/readonly.sh" disable            # configured by hand but not wanted
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
        schedule_reboot
    fi
fi
