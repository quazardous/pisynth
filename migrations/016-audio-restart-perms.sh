#!/usr/bin/env bash
# 016 — let the touch UI restart piano.service from Settings → Audio (#311).
# Choosing an output device offers "Restart audio now?"; the UI runs as the run-as
# user with no login session, so `systemctl restart piano.service` hits polkit's
# org.freedesktop.systemd1.manage-units and is denied → the dialog could only ever
# say "applies on next restart". A rule grants that user manage rights on the synth
# units. polkit watches rules.d and reloads live — no reboot needed.
set -euo pipefail

RULE=/etc/polkit-1/rules.d/53-pisynth-units.rules
cat > "$RULE" <<EOF
// pisynth: allow the run-as user to (re)start the synth units from the touch UI (#311)
polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.systemd1.manage-units" &&
        subject.user == "$TARGET_USER") {
        var unit = action.lookup("unit");
        if (unit == "piano.service" || unit == "midi-bridge.service") {
            return polkit.Result.YES;
        }
    }
});
EOF
echo "[016] wrote $RULE (manage piano/midi-bridge for $TARGET_USER)"

systemctl reload polkit 2>/dev/null || systemctl reload polkit.service 2>/dev/null || true
