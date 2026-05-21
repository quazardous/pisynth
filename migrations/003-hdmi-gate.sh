#!/usr/bin/env bash
# 003 — desktop only when HDMI is attached (gate lightdm with an ExecCondition).
set -euo pipefail

if [[ -f /usr/lib/systemd/system/lightdm.service || -f /etc/systemd/system/lightdm.service ]]; then
    echo "[003] gating lightdm to HDMI presence..."
    install -d -m 0755 /etc/systemd/system/lightdm.service.d
    install -m 0644 "$REPO_DIR/lightdm-hdmi-only.conf" \
        /etc/systemd/system/lightdm.service.d/hdmi-only.conf
    systemctl daemon-reload
    echo "  done (effective next boot / next lightdm start)"
else
    echo "[003] lightdm not present — skipping desktop gate."
fi
