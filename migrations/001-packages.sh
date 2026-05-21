#!/usr/bin/env bash
# 001 — system packages + audio group.
set -euo pipefail

echo "[001] ensuring non-free-firmware apt component..."
for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do
    [[ -f "$f" ]] || continue
    if grep -qE '^[^#]*\bnon-free\b' "$f" && ! grep -qE '\bnon-free-firmware\b' "$f"; then
        sed -i -E 's/(^[^#]*\bnon-free\b)/\1 non-free-firmware/' "$f"
        echo "  patched: $f"
    fi
done

echo "[001] apt update + install fluidsynth stack..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    fluidsynth \
    alsa-utils \
    musescore-general-soundfont \
    fluid-soundfont-gm \
    rsync \
    netcat-openbsd

echo "[001] best-effort WiFi firmware..."
# Note: NOT firmware-misc-nonfree here — on a Pi it drags in useless Intel/NVIDIA
# graphics blobs (~66 MB + initramfs regen). The Pi's WiFi uses firmware-brcm80211.
for pkg in firmware-brcm80211 firmware-realtek; do
    DEBIAN_FRONTEND=noninteractive apt-get install -y "$pkg" || echo "  (skip $pkg)"
done

echo "[001] adding $TARGET_USER to audio group..."
usermod -a -G audio "$TARGET_USER" || true
