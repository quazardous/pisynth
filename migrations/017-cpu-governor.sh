#!/usr/bin/env bash
# 017 — pin the CPU governor to `performance` (#660, perf T1). The Pi 3B+ ships with the
# `ondemand` governor, which idles the 4 Cortex-A53 cores at 600 MHz and ramps up lazily —
# that ramp lag shows up as xruns / extra latency on the audio path. fluidsynth wants the
# cores at full clock; `performance` holds them at 1.4 GHz. scaling_governor is runtime
# sysfs state (not a /boot config), so it must be re-applied on every boot → a tiny oneshot
# service. Applied immediately here via `enable --now`, so no reboot is needed.
set -euo pipefail

UNIT=/etc/systemd/system/pisynth-cpu-governor.service
cat > "$UNIT" <<'EOF'
[Unit]
Description=pisynth: pin CPU governor to performance (#660)
ConditionPathExists=/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c 'for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do [ -w "$g" ] && echo performance > "$g"; done'

[Install]
WantedBy=multi-user.target
EOF
echo "[017] wrote $UNIT"

systemctl daemon-reload
systemctl enable --now pisynth-cpu-governor.service
echo "[017] CPU governor pinned to performance (now + every boot)."

# Echo the result into the deploy log for confirmation.
for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo "[017] $g = $(cat "$g" 2>/dev/null || echo '?')"
done
