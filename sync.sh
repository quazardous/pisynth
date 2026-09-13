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
# Web companion service (#659): the Python package + the BUILT phone app (web/static). The Svelte
# sources (web/app) and their node_modules never go to the Pi.
rsync -a --delete --exclude __pycache__ --exclude app/ "$REPO_DIR/web/" /usr/local/lib/pisynth/web/
[[ -f "$REPO_DIR/tools/fbshot.py" ]] && install -m 0755 "$REPO_DIR/tools/fbshot.py" /usr/local/lib/pisynth/fbshot.py

# Runtime shell scripts
install -m 0755 "$REPO_DIR/start-piano.sh"    /usr/local/bin/start-piano.sh
install -m 0755 "$REPO_DIR/midi-bridge.sh"    /usr/local/bin/midi-bridge.sh
install -m 0755 "$REPO_DIR/hdmi-connected.sh" /usr/local/bin/pisynth-hdmi-connected
install -m 0755 "$REPO_DIR/readonly.sh"       /usr/local/sbin/pisynth-readonly   # read-only root helper (#681)
install -m 0755 "$REPO_DIR/web-cert.sh"       /usr/local/sbin/pisynth-web-cert   # companion HTTPS: local CA (#2427)
PISYNTH_CERT_GROUP="$(id -gn "$TARGET_USER")" /usr/local/sbin/pisynth-web-cert ensure || echo "[sync] warning: pisynth-web-cert failed"

# systemd units (so unit edits take effect every deploy)
for u in piano midi-bridge pisynth-ui pisynth-web; do
    install -m 0644 "$REPO_DIR/$u.service" "/etc/systemd/system/$u.service"
done
sed -i -E "s/^User=.*/User=$TARGET_USER/" \
    /etc/systemd/system/piano.service \
    /etc/systemd/system/midi-bridge.service \
    /etc/systemd/system/pisynth-ui.service \
    /etc/systemd/system/pisynth-web.service
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

# MIDI library (#2421): the starter set + the repo's midi/ folder, linked into ~/midi (subfolders
# kept); files uploaded from the web companion live there as real files and are left alone.
install -d -o "$TARGET_USER" -g "$TARGET_USER" "$TARGET_HOME/midi"
runuser -u "$TARGET_USER" -- bash "$REPO_DIR/midi-sync.sh" "$REPO_DIR" "$TARGET_HOME/midi"

# Restart order matters: the UI and pisynth-web hold connections to the synth shell (:9800). Stop
# them FIRST so they close those connections (TIME_WAIT lands on their side), then restart the synth
# (it can rebind :9800 at once — no ~60 s wait, #2410/#2416), then start them again with the new code.
# Audio is restarted only if already running (don't grab hardware here).
systemctl stop pisynth-ui.service pisynth-web.service 2>/dev/null || true
systemctl is-active --quiet piano.service      && systemctl restart piano.service      || true
systemctl is-active --quiet midi-bridge.service && systemctl restart midi-bridge.service || true
systemctl start pisynth-ui.service 2>/dev/null || true
systemctl is-enabled --quiet pisynth-web.service && systemctl start pisynth-web.service || true   # warm again with the new code (#659)
echo "[sync] code, units, soundfonts re-deployed."
