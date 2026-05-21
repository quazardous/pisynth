#!/usr/bin/env bash
# 009 — one-shot catch-up reboot. Migrations 007 (fbcon=map:1) and 008 (splash
# off) edited /boot/firmware before apply.sh learned to auto-reboot, so their
# changes are on disk but not yet live (no reboot happened). Request the reboot
# here so it ships with the deploy.
#
# This is a one-time bridge: future boot-config migrations flag the reboot
# themselves (see docs/dev.md / $PISYNTH_REBOOT_FLAG), so no equivalent will be needed.
set -euo pipefail

if [[ -n "${PISYNTH_REBOOT_FLAG:-}" ]]; then
    echo "009: catch-up reboot for 007 (fbcon=map:1) + 008 (boot splash)" >> "$PISYNTH_REBOOT_FLAG"
    echo "[009] requested catch-up reboot (ships with this deploy)"
else
    echo "[009] PISYNTH_REBOOT_FLAG unset — reboot manually: sudo systemctl reboot"
fi
