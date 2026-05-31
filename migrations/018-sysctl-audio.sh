#!/usr/bin/env bash
# 018 — keep the audio process out of swap (#661, perf T2). The Pi 3B+ defaults to
# vm.swappiness=60, which lets the kernel page out idle anonymous memory aggressively —
# on a 905 MB box running fluidsynth + a large soundfont + the touch UI, the render
# thread's pages can be evicted and a later access stalls it → an audible glitch. Lower
# it to 10 (reclaim file cache first; swap anon only under real pressure). Persistent via
# sysctl.d; applied immediately so no reboot is needed.
set -euo pipefail

CONF=/etc/sysctl.d/90-pisynth-audio.conf
cat > "$CONF" <<'EOF'
# pisynth (#661): keep the audio process resident — avoid paging-induced glitches.
vm.swappiness = 10
EOF
echo "[018] wrote $CONF"

sysctl --system >/dev/null 2>&1 || sysctl -p "$CONF" 2>/dev/null || true
echo "[018] vm.swappiness now = $(cat /proc/sys/vm/swappiness 2>/dev/null || echo '?')"
