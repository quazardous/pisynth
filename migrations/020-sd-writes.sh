#!/usr/bin/env bash
# 020 — cut SD-card writes so a power cut is less likely to corrupt the card (#681, phase A).
# No boot change. Reversible:
#   rm /etc/systemd/journald.conf.d/90-pisynth-volatile.conf && systemctl restart systemd-journald
#   systemctl unmask apt-daily.timer apt-daily-upgrade.timer && systemctl enable --now apt-daily.timer apt-daily-upgrade.timer
set -euo pipefail

# journald in RAM: logs no longer written to /var/log/journal (they don't survive a reboot).
CONF=/etc/systemd/journald.conf.d/90-pisynth-volatile.conf
install -d -m 0755 /etc/systemd/journald.conf.d
cat > "$CONF" <<'EOF'
# pisynth (#681): keep the journal in RAM — no SD writes during play.
[Journal]
Storage=volatile
RuntimeMaxUse=16M
EOF
echo "[020] wrote $CONF"
# Existing files in /var/log/journal are left as-is (still readable history); journald
# just stops writing there.
systemctl restart systemd-journald
echo "[020] journald storage: volatile (RuntimeMaxUse=16M)"

# The appliance must not upgrade packages behind the user's back (SD writes, and it can
# break a working synth). Updates go through deploy / install.sh.
for unit in apt-daily.timer apt-daily-upgrade.timer; do
    systemctl disable --now "$unit" 2>/dev/null || true
    systemctl mask "$unit"          2>/dev/null || true
    echo "[020] masked $unit"
done

# Generated sounds now live in the UI's tmpfs RuntimeDirectory (/run/pisynth); the old
# on-disk copies are regenerable → drop them.
if [[ -d "$TARGET_HOME/.config/pisynth/sounds" ]]; then
    rm -rf "$TARGET_HOME/.config/pisynth/sounds"
    echo "[020] removed $TARGET_HOME/.config/pisynth/sounds (regenerated in /run/pisynth)"
fi
