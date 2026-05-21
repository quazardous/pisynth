#!/usr/bin/env bash
# 011 — let the UI manage Bluetooth via BlueZ for the pairing manager (#287).
# bluetoothctl talks to bluetoothd over D-Bus; pair/connect is gated by polkit, and
# the UI runs as the run-as user with no login session. A polkit rule grants that
# user the org.bluez actions so it can scan/pair/connect without root. polkit watches
# rules.d and reloads live — no reboot.
set -euo pipefail

RULE=/etc/polkit-1/rules.d/51-pisynth-bluetooth.rules
cat > "$RULE" <<EOF
// pisynth: allow the run-as user to manage BlueZ (scan/pair/connect) from the touch UI (#287)
polkit.addRule(function(action, subject) {
    if (action.id.indexOf("org.bluez.") == 0 && subject.user == "$TARGET_USER") {
        return polkit.Result.YES;
    }
});
EOF
echo "[011] wrote $RULE (BlueZ access for $TARGET_USER)"

# polkit auto-reloads rules.d; nudge it just in case (best-effort, no reboot).
systemctl reload polkit 2>/dev/null || systemctl reload polkit.service 2>/dev/null || true
