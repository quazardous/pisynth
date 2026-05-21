#!/usr/bin/env bash
# 005 — control UI dependencies + service (one-time).
# The UI code itself (ui/pisynth-ui.py, tools/fbshot.py) is (re)deployed on
# EVERY apply by sync.sh, so edits take effect without a new migration.
set -euo pipefail

echo "[005] python deps for the framebuffer UI..."
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3-pil python3-numpy python3-evdev

echo "[005] systemd unit (User=$TARGET_USER)..."
install -m 0644 "$REPO_DIR/pisynth-ui.service" /etc/systemd/system/pisynth-ui.service
sed -i -E "s/^User=.*/User=$TARGET_USER/" /etc/systemd/system/pisynth-ui.service
systemctl daemon-reload
systemctl enable pisynth-ui.service
echo "[005] UI service enabled (code deployed by sync.sh)."
