#!/usr/bin/env bash
# install.sh — one-shot end-user installer for pisynth (#291).
#
# For an end user (vs the dev `deploy.sh`/migration workflow): copy this repo onto the
# Pi, then run ONE command:
#
#     sudo ./install.sh
#
# It installs everything in a SINGLE apt batch (from packages.list), then configures the
# appliance (systemd units, screen overlay, console, polkit perms, HDMI gate) and reboots
# — by handing off to apply.sh. Idempotent and re-runnable. On a fresh Pi nothing is
# "replayed": each step runs once. The migrations/ stay the canonical setup steps (shared
# package list via packages.list, so the two never drift).
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "Run as root:  sudo ./install.sh" >&2; exit 1; }
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"

mapfile -t PKGS < <(grep -vE '^[[:space:]]*(#|$)' "$HERE/packages.list")
echo "=== pisynth installer ==="
echo "[install] ${#PKGS[@]} packages in one batch (packages.list) + setup, then reboot."

echo "[install] apt update + install..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y "${PKGS[@]}"
# Best-effort Wi-Fi/BT firmware (may be absent on some images; not fatal).
for pkg in firmware-brcm80211 firmware-realtek; do
    DEBIAN_FRONTEND=noninteractive apt-get install -y "$pkg" || echo "  (skip $pkg)"
done

echo "[install] configuring appliance + reboot (via apply.sh)..."
exec bash "$HERE/apply.sh"
