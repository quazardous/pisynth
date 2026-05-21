#!/usr/bin/env bash
# 015 — enable-linger for the synth user so its PipeWire session runs at boot (#301).
# Bluetooth A2DP output routes the synth through the user's PipeWire/PulseAudio graph
# (start-piano.sh's pulseaudio branch). On a headless appliance nobody logs in, so without
# lingering /run/user/<uid> and the pipewire user services never start and the BT sink is
# unreachable. enable-linger starts the user manager (and socket-activates PipeWire) at
# boot regardless of login. Harmless and idempotent for the ALSA-only default path.
set -euo pipefail

echo "[015] enabling user lingering for $TARGET_USER (PipeWire session at boot, BT audio #301)..."
loginctl enable-linger "$TARGET_USER"
echo "[015] linger=$(loginctl show-user "$TARGET_USER" -p Linger --value 2>/dev/null || echo '?')"
