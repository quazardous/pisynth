#!/usr/bin/env bash
# 014 — PyYAML for the UI's preferences file (#303). Local prefs moved from
# settings.json to a single documented ~/.config/pisynth/settings.yaml; the UI
# (and start-piano.sh) read/write it with PyYAML. One-time package install —
# the UI code itself is redeployed every apply by sync.sh.
set -euo pipefail

echo "[014] installing python3-yaml..."
apt-get update -qq || true
DEBIAN_FRONTEND=noninteractive apt-get install -y python3-yaml
echo "[014] PyYAML present — settings.yaml supported (legacy settings.json auto-imported on first UI run)."
