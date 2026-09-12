#!/usr/bin/env bash
# readonly.sh → /usr/local/sbin/pisynth-readonly — read-only root for the appliance (#681 phase B).
#
# Wraps Raspberry Pi OS's overlayroot (the same mechanism as `raspi-config` → Overlay FS):
# the SD root is mounted read-only under /media/root-ro and every write goes to a RAM
# overlay that is dropped at reboot, so an unplug can't corrupt the card.
#
#   pisynth-readonly status           active=0|1 configured=0|1   (now / after next boot)
#   pisynth-readonly enable           configure it for the next boot (installs overlayroot)
#   pisynth-readonly disable          configure it off for the next boot
#   pisynth-readonly persist PATH...  write-through: copy PATH (or its deletion) from the live
#                                     view down to the read-only SD root. Whitelisted paths
#                                     only; a no-op when the overlay is not active.
#
# enable/disable only edit cmdline.txt — the change applies on the next reboot (apply.sh /
# deploy.sh drive the reboots). The UI calls `sudo -n pisynth-readonly persist …` (sudoers
# grant from migration 021) so screen preferences and Bluetooth pairings survive a reboot.
set -euo pipefail

CMDLINE=/boot/firmware/cmdline.txt
[[ -f "$CMDLINE" ]] || CMDLINE=/boot/cmdline.txt
LOWER=/media/root-ro

die() { echo "pisynth-readonly: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || die "run as root"

active()     { grep -qw "overlayroot=tmpfs" /proc/cmdline; }
configured() { grep -qw "overlayroot=tmpfs" "$CMDLINE"; }

# Paths a screen action may persist. Resolved for the user who invoked sudo.
allowed() {
    local home; home="$(getent passwd "${SUDO_USER:-root}" | cut -d: -f6)"
    case "$1" in
        "$home/.config/pisynth/settings.yaml"|"$home/.config/pisynth/touch_cal.json") return 0 ;;
        "$home/.config/pisynth/web_sessions.json") return 0 ;;      # paired phones (#659)
        "$home/midi") return 0 ;;                                    # MIDI library: phone uploads (#2421)
        /var/lib/bluetooth) return 0 ;;
    esac
    return 1
}

persist() {
    local p rc=0
    for p in "$@"; do
        allowed "$p" || die "not persistable: $p"
        # The user owns ~/.config: refuse a symlinked parent on the SD side, or root would
        # write through it to wherever it points.
        [[ "$(realpath -m "$(dirname "$LOWER$p")")" == "$(dirname "$LOWER$p")" ]] \
            || die "refusing symlinked path: $p"
    done
    active || return 0                              # plain RW root: the write already hit the SD
    mount -o remount,rw "$LOWER"
    for p in "$@"; do
        if [[ -e "$p" ]]; then
            if [[ -d "$p" ]]; then
                mkdir -p "$LOWER$p"
                rsync -a --delete "$p/" "$LOWER$p/" || rc=1   # mirror: a forgotten device goes too
            else
                mkdir -p "$(dirname "$LOWER$p")"
                cp -a "$p" "$LOWER$p.pisynth-tmp" && mv -f "$LOWER$p.pisynth-tmp" "$LOWER$p" || rc=1
            fi
        elif [[ ! -d "$LOWER$p" ]]; then
            rm -f "${LOWER:?}$p" || rc=1            # file deleted in the live view (e.g. Reset config)
        fi
    done
    sync
    mount -o remount,ro "$LOWER" || echo "pisynth-readonly: warning: could not remount $LOWER ro" >&2
    return "$rc"
}

case "${1:-status}" in
    status)
        echo "active=$(active && echo 1 || echo 0) configured=$(configured && echo 1 || echo 0)" ;;
    enable)
        active && configured && { echo "already active"; exit 0; }
        dpkg -s overlayroot >/dev/null 2>&1 || DEBIAN_FRONTEND=noninteractive apt-get install -y overlayroot
        [[ -e /boot/firmware/initramfs8 || -e /boot/firmware/initramfs_2712 ]] \
            || die "no initramfs in /boot/firmware (needs auto_initramfs=1) — not enabling"
        configured || sed -i "1 s/^/overlayroot=tmpfs /" "$CMDLINE"
        echo "read-only root configured — takes effect on next boot" ;;
    disable)
        configured && sed -i "1 s/overlayroot=tmpfs //" "$CMDLINE"
        echo "read-only root disabled — takes effect on next boot" ;;
    persist)
        shift; [[ $# -gt 0 ]] || die "persist: no path"
        persist "$@" ;;
    *)
        die "usage: pisynth-readonly status|enable|disable|persist PATH..." ;;
esac
