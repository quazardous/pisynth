#!/usr/bin/env bash
# 002 — install runtime scripts, user config, soundfonts, systemd units.
set -euo pipefail

echo "[002] installing scripts -> /usr/local/bin..."
install -m 0755 "$REPO_DIR/start-piano.sh"    /usr/local/bin/start-piano.sh
install -m 0755 "$REPO_DIR/midi-bridge.sh"    /usr/local/bin/midi-bridge.sh
install -m 0755 "$REPO_DIR/wifi-connect.sh"   /usr/local/bin/wifi-connect.sh
install -m 0755 "$REPO_DIR/hdmi-connected.sh" /usr/local/bin/pisynth-hdmi-connected

echo "[002] user config -> $TARGET_HOME/.local/synth.conf..."
install -d -m 0755 -o "$TARGET_USER" -g "$TARGET_USER" "$TARGET_HOME/.local"
if [[ ! -f "$TARGET_HOME/.local/synth.conf" ]]; then
    install -m 0644 -o "$TARGET_USER" -g "$TARGET_USER" \
        "$REPO_DIR/synth.conf.example" "$TARGET_HOME/.local/synth.conf"
fi

echo "[002] seeding $TARGET_HOME/soundfonts..."
install -d -m 0755 -o "$TARGET_USER" -g "$TARGET_USER" "$TARGET_HOME/soundfonts"
for entry in \
    "01-MuseScore_General.sf3:/usr/share/sounds/sf3/MuseScore_General.sf3" \
    "02-FluidR3_GM.sf2:/usr/share/sounds/sf2/FluidR3_GM.sf2" \
; do
    name="${entry%%:*}"; src="${entry#*:}"; dst="$TARGET_HOME/soundfonts/$name"
    if [[ -f "$src" && ! -e "$dst" ]]; then
        ln -s "$src" "$dst"; chown -h "$TARGET_USER:$TARGET_USER" "$dst"
        echo "  linked $name"
    fi
done

echo "[002] systemd units (User=$TARGET_USER)..."
install -m 0644 "$REPO_DIR/piano.service"       /etc/systemd/system/piano.service
install -m 0644 "$REPO_DIR/midi-bridge.service" /etc/systemd/system/midi-bridge.service
sed -i -E "s/^User=.*/User=$TARGET_USER/" \
    /etc/systemd/system/piano.service \
    /etc/systemd/system/midi-bridge.service
systemctl daemon-reload
systemctl enable piano.service midi-bridge.service
