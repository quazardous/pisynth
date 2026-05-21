#!/usr/bin/env bash
# sync.sh — re-deploy everything that changes between iterations: app code,
# runtime scripts, systemd unit files, and sideloaded soundfonts. Run on EVERY
# apply by apply.sh (not ledgered), as root. Migrations stay for one-time setup;
# this makes ordinary edits take effect on each ./deploy.sh.
# Inherits TARGET_USER / TARGET_HOME / REPO_DIR from apply.sh.
set -euo pipefail

# App package (#308): ui/pisynth/ → /usr/local/lib/pisynth/pisynth/, run by the
# service via `python3 -m pisynth` (PYTHONPATH=/usr/local/lib/pisynth). The bundled
# icon font (#306) ships inside the package at pisynth/assets/ (ICON_FONT is
# resolved relative to app.py). rsync handles the future io/ · core/ · ui/ subdirs.
install -d -m 0755 /usr/local/lib/pisynth
rm -f /usr/local/lib/pisynth/pisynth-ui.py          # superseded by the package
rsync -a --delete --exclude __pycache__ "$REPO_DIR/ui/pisynth/" /usr/local/lib/pisynth/pisynth/
[[ -f "$REPO_DIR/tools/fbshot.py" ]] && install -m 0755 "$REPO_DIR/tools/fbshot.py" /usr/local/lib/pisynth/fbshot.py

# Runtime shell scripts
install -m 0755 "$REPO_DIR/start-piano.sh"    /usr/local/bin/start-piano.sh
install -m 0755 "$REPO_DIR/midi-bridge.sh"    /usr/local/bin/midi-bridge.sh
install -m 0755 "$REPO_DIR/hdmi-connected.sh" /usr/local/bin/pisynth-hdmi-connected

# systemd units (so unit edits take effect every deploy)
for u in piano midi-bridge pisynth-ui; do
    install -m 0644 "$REPO_DIR/$u.service" "/etc/systemd/system/$u.service"
done
sed -i -E "s/^User=.*/User=$TARGET_USER/" \
    /etc/systemd/system/piano.service \
    /etc/systemd/system/midi-bridge.service \
    /etc/systemd/system/pisynth-ui.service
systemctl daemon-reload

# Sideloaded soundfonts: link any .sf2/.sf3 dropped in the repo's soundfonts/
# into ~/soundfonts (the dir scanned by start-piano.sh). rsync brought them
# under $REPO_DIR/soundfonts, so we just symlink — no copy of big files.
shopt -s nullglob
for sf in "$REPO_DIR"/soundfonts/*.sf2 "$REPO_DIR"/soundfonts/*.sf3; do
    dst="$TARGET_HOME/soundfonts/$(basename "$sf")"
    ln -sfn "$sf" "$dst"
    chown -h "$TARGET_USER:$TARGET_USER" "$dst"
    echo "[sync] soundfont linked: $(basename "$sf")"
done
shopt -u nullglob

# Restart the UI; restart audio only if already running (don't grab hardware here).
systemctl restart pisynth-ui.service 2>/dev/null || true
systemctl is-active --quiet piano.service      && systemctl restart piano.service      || true
systemctl is-active --quiet midi-bridge.service && systemctl restart midi-bridge.service || true
echo "[sync] code, units, soundfonts re-deployed."
