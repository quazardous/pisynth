#!/usr/bin/env bash
# 006 — neutralize the packaged fluidsynth USER service.
# The Debian `fluidsynth` package ships /usr/lib/systemd/user/fluidsynth.service
# and enables it in every user session. That second fluidsynth would fight our
# piano.service for the USB sound card / MIDI. We run our own instance only.
set -euo pipefail

systemctl --global disable fluidsynth.service 2>/dev/null || true
systemctl --global mask    fluidsynth.service 2>/dev/null || true
# Stop it in the target user's session if it happens to be running right now.
pkill -u "$TARGET_USER" -x fluidsynth 2>/dev/null || true

echo "[006] packaged fluidsynth user service disabled + masked."
