#!/usr/bin/env bash
# 010 — let the UI power the SPI panel backlight on/off for screen-sleep (ticket
# #277). The fbtft backlight `bl_power` (0=on, 4=off) is root-only by default;
# the UI runs as the human user in group `video`. A udev rule hands `video`
# write access to bl_power (brightness is already video-writable but max=0, so
# bl_power is the only real on/off knob on this panel). Applied immediately too,
# so no reboot needed.
set -euo pipefail

RULE=/etc/udev/rules.d/99-pisynth-backlight.rules
cat > "$RULE" <<'EOF'
# pisynth: let group `video` power the SPI panel backlight on/off (screen sleep)
SUBSYSTEM=="backlight", RUN+="/bin/chgrp video /sys/class/backlight/%k/bl_power", RUN+="/bin/chmod g+w /sys/class/backlight/%k/bl_power"
EOF
echo "[010] wrote $RULE"

udevadm control --reload-rules
udevadm trigger --subsystem-match=backlight --action=add || true

# Apply now too (the trigger above can race / not re-run RUN on some setups).
shopt -s nullglob
for bl in /sys/class/backlight/*/bl_power; do
    chgrp video "$bl" && chmod g+w "$bl" && echo "[010] perms set on $bl"
done
shopt -u nullglob
