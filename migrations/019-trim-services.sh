#!/usr/bin/env bash
# 019 — trim unused daemons to free RAM/CPU for the audio path (#661, perf T2). The box is
# a synth appliance: it never mounts NFS and runs no RPC services, yet the stock image keeps
# the NFS/RPC client stack running (rpcbind also leaves a network port open). Mask the safe
# set david approved ("Merge" on the 🟢 proposal); the optional cuts (avahi / udisks2 /
# accounts-daemon) were deliberately left in place. Fully reversible: `systemctl unmask <unit>`.
set -euo pipefail

for unit in nfs-blkmap.service rpcbind.service rpcbind.socket; do
    systemctl disable --now "$unit" 2>/dev/null || true   # stop + clear enablement
    systemctl mask "$unit"          2>/dev/null || true   # prevent any future (socket/dep) start
    echo "[019] masked $unit"
done
echo "[019] NFS/RPC stack trimmed (re-enable with: systemctl unmask <unit>)."
