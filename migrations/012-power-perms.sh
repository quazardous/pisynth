#!/usr/bin/env bash
# 012 — let the touch UI reboot / power off the box from Settings → Tools (#297).
# logind gates reboot/power-off via polkit; the UI runs as the run-as user with no
# login session, so a rule grants that user the login1 power actions. polkit watches
# rules.d and reloads live — no reboot needed.
set -euo pipefail

RULE=/etc/polkit-1/rules.d/52-pisynth-power.rules
cat > "$RULE" <<EOF
// pisynth: allow the run-as user to reboot / power off from the touch UI (#297)
polkit.addRule(function(action, subject) {
    if ((action.id == "org.freedesktop.login1.reboot" ||
         action.id == "org.freedesktop.login1.reboot-multiple-sessions" ||
         action.id == "org.freedesktop.login1.power-off" ||
         action.id == "org.freedesktop.login1.power-off-multiple-sessions") &&
        subject.user == "$TARGET_USER") {
        return polkit.Result.YES;
    }
});
EOF
echo "[012] wrote $RULE (reboot/power-off for $TARGET_USER)"

systemctl reload polkit 2>/dev/null || systemctl reload polkit.service 2>/dev/null || true
