#!/usr/bin/env bash
# 013 — airplane mode (#299): install rfkill, let the run-as user toggle the radios
# (Wi-Fi + Bluetooth) from the touch UI without root, and make it VOLATILE — a reboot
# always comes back with the radios on.
set -euo pipefail

echo "[013] installing rfkill..."
apt-get update -qq || true
DEBIAN_FRONTEND=noninteractive apt-get install -y rfkill || echo "[013] (rfkill install failed — airplane mode will show 'failed')"

# Let group `netdev` write /dev/rfkill so the UI (run-as user is in netdev) can
# block/unblock radios without root.
RULE=/etc/udev/rules.d/99-pisynth-rfkill.rules
cat > "$RULE" <<'EOF'
# pisynth: group `netdev` may toggle radios via /dev/rfkill (airplane mode, #299)
SUBSYSTEM=="misc", KERNEL=="rfkill", GROUP="netdev", MODE="0664"
EOF
echo "[013] wrote $RULE"
usermod -aG netdev "$TARGET_USER" || true
udevadm control --reload-rules
udevadm trigger --subsystem-match=misc --action=add || true
# Apply now too (the trigger can miss).
[[ -e /dev/rfkill ]] && chgrp netdev /dev/rfkill && chmod g+w /dev/rfkill && echo "[013] perms set on /dev/rfkill" || true

# Make airplane mode VOLATILE: stop systemd from saving/restoring the radio block
# state across reboots, so a reboot always brings the radios back on.
systemctl disable --now systemd-rfkill.socket 2>/dev/null || true
systemctl mask systemd-rfkill.service systemd-rfkill.socket 2>/dev/null || true
echo "[013] systemd-rfkill masked — airplane mode does not persist across reboot"
