#!/usr/bin/env bash
# 004 — enable the SPI screen (ILI9486 + ADS7846 touch by default) via a device-tree
# overlay. Creates /dev/fb0 for the panel; touch shows up as an evdev device.
# The panel is described in hardware.conf (overlay name / params / SPI) so a different
# screen can be supported by editing that file instead of this migration.
set -euo pipefail

# Panel description (overlay, params, SPI). Defaults match the reference goodtft 3.5".
HW="$REPO_DIR/hardware.conf"
# shellcheck disable=SC1090
[[ -f "$HW" ]] && source "$HW"
SCREEN_OVERLAY="${SCREEN_OVERLAY:-piscreen}"
SCREEN_OVERLAY_PARAMS="${SCREEN_OVERLAY_PARAMS:-speed=16000000,rotate=90}"
SCREEN_SPI="${SCREEN_SPI:-on}"

overlay_line="dtoverlay=${SCREEN_OVERLAY}"
[[ -n "$SCREEN_OVERLAY_PARAMS" ]] && overlay_line+=",${SCREEN_OVERLAY_PARAMS}"

CFG=/boot/firmware/config.txt
[[ -f "$CFG" ]] || CFG=/boot/config.txt

changed=0
if ! grep -qE "^dtparam=spi=${SCREEN_SPI}\b" "$CFG"; then
    echo "dtparam=spi=${SCREEN_SPI}" >> "$CFG"; changed=1
fi
if ! grep -qxF "$overlay_line" "$CFG"; then
    echo "$overlay_line" >> "$CFG"; changed=1
fi

if [[ $changed -eq 1 ]]; then
    echo "[004] $CFG updated (spi=${SCREEN_SPI} + ${SCREEN_OVERLAY}) — REBOOT required for the screen."
else
    echo "[004] $CFG already has spi + ${SCREEN_OVERLAY}."
fi
