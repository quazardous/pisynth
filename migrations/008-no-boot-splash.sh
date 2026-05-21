#!/usr/bin/env bash
# 008 — kill the boot splash. plymouth draws a "welcome" splash on the SPI panel
# during boot, mis-centred (it lays out for the wrong geometry). We don't want
# anything on the panel until pisynth-ui takes it over, so:
#   - drop `splash` from cmdline.txt (the plymouth graphical-splash trigger)
#   - add `plymouth.enable=0` (so plymouth never grabs /dev/fb0 at all)
#   - add `disable_splash=1` to config.txt (kills the early rainbow square too)
# `quiet` stays, and fbcon=map:1 (migration 007) keeps console text off fb0, so
# the panel is simply black until the UI renders. Reboot to apply.
set -euo pipefail

CMD=/boot/firmware/cmdline.txt
[[ -f "$CMD" ]] || CMD=/boot/cmdline.txt
CFG=/boot/firmware/config.txt
[[ -f "$CFG" ]] || CFG=/boot/config.txt

changed=0

if grep -qw "splash" "$CMD"; then
    sed -i -E '1 s/[[:space:]]+splash\b//g' "$CMD"   # cmdline.txt is one line
    echo "[008] removed 'splash' from $CMD"; changed=1
else
    echo "[008] 'splash' already absent from $CMD"
fi

if grep -qw "plymouth.enable=0" "$CMD"; then
    echo "[008] plymouth.enable=0 already set in $CMD"
else
    sed -i '1 s/$/ plymouth.enable=0/' "$CMD"
    echo "[008] added plymouth.enable=0 to $CMD"; changed=1
fi

if grep -qE '^disable_splash=1' "$CFG"; then
    echo "[008] disable_splash=1 already set in $CFG"
else
    echo 'disable_splash=1' >> "$CFG"
    echo "[008] added disable_splash=1 to $CFG"; changed=1
fi

# Boot config changed → ask apply.sh to reboot at the end of this deploy.
if [[ $changed -eq 1 && -n "${PISYNTH_REBOOT_FLAG:-}" ]]; then
    echo "008: boot splash disabled (cmdline.txt / config.txt)" >> "$PISYNTH_REBOOT_FLAG"
fi
echo "[008] boot splash disabled (reboot ships with the deploy)"
