#!/usr/bin/env bash
# probe.sh — run READ-ONLY diagnostics on the Pi over SSH and print them here.
# Same host resolution as deploy.sh / ctl.sh / shot.sh (PISYNTH_HOST from
# pisynth.conf, env overrides).
#
# CONTRACT (ticket #277): unlike deploy.sh, probe.sh never rsyncs the repo and
# never runs apply.sh / sync.sh / migrations / package installs. It does NOT
# modify the installed app, its config, or persistent system state — it only
# inspects hardware + service state. The one exception, `backlight-toggle`, is an
# explicit, self-restoring hardware probe (drives a GPIO then puts it back).
#
# Usage:
#   ./probe.sh                  # default read-only snapshot (host, audio, MIDI, services, UI, backlight)
#   ./probe.sh audio            # ALSA cards + playback devices + MIDI inputs
#   ./probe.sh backlight        # SPI panel backlight: sysfs + GPIO18 + display overlay (read-only)
#   ./probe.sh backlight-toggle [bcm] # drive GPIO<bcm> (default 22) low 3s then restore — WATCH the panel (#277)
#   ./probe.sh services         # piano / pisynth-ui / midi-bridge status + recent logs
#   ./probe.sh ui               # UI control-socket state (:9810)
#   ./probe.sh '<command>'      # run an arbitrary command on the Pi (you own what you pass)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
for c in "$REPO_DIR/pisynth.conf" "$REPO_DIR/pisynth.conf.dist"; do
    [ -n "${PISYNTH_HOST:-}" ] && break
    [ -f "$c" ] && . "$c"
done
PI="${PISYNTH_HOST:-pi@raspberrypi.local}"

remote()  { ssh "$PI" "$@"; }                  # snippets are best-effort: guard with `|| true` inside
section() { printf '\n===== %s =====\n' "$1"; }

probe_audio() {
    section "ALSA cards (/proc/asound/cards)"; remote 'cat /proc/asound/cards || true'
    section "Playback devices (aplay -l)";     remote 'aplay -l 2>&1 || true'
    section "MIDI inputs (aconnect -i)";       remote 'aconnect -i 2>&1 || true'
}

probe_backlight() {
    section "Backlight sysfs (/sys/class/backlight)"
    remote 'for d in /sys/class/backlight/*; do [ -e "$d" ] || continue; echo "$d:"; \
            for k in bl_power brightness max_brightness actual_brightness type; do \
              [ -e "$d/$k" ] && printf "  %s=%s\n" "$k" "$(cat "$d/$k" 2>/dev/null)"; \
            done; done || true'
    section "GPIO 18 state (pinctrl/raspi-gpio get 18)"
    remote 'pinctrl get 18 2>&1 || raspi-gpio get 18 2>&1 || echo "no pinctrl/raspi-gpio"'
    section "Display overlay (config.txt)"
    remote 'grep -nE "dtoverlay|piscreen|tft35|spi=" /boot/firmware/config.txt 2>/dev/null \
            || grep -nE "dtoverlay|piscreen|tft35|spi=" /boot/config.txt 2>/dev/null || true'
    section "Backlight/panel kernel msgs (dmesg, may need root)"
    remote 'dmesg 2>/dev/null | grep -iE "backlight|ili9486|fb_ili|fbtft|piscreen|tft" | tail -20 \
            || echo "(empty or needs root: ./probe.sh \"sudo dmesg | grep -i backlight\")"'
}

probe_backlight_toggle() {
    # goodtft/LCD-wiki 3.5" ILI9486 backlight is typically BCM GPIO22 (phys pin 15),
    # exposed by the tft35a overlay as backlight=15 (#277). Override: backlight-toggle <bcm>.
    # Polarity-agnostic: reads the current level and drives the OPPOSITE for 3s, then
    # restores — so it works whether the backlight enable is active-high or active-low.
    local g="${1:-22}"
    section "GPIO$g backlight toggle — WATCH the panel (#277)"
    echo "Flipping GPIO$g to the opposite of its current level for 3s, then restoring. Watch the panel."
    remote "command -v pinctrl >/dev/null || { echo 'pinctrl not found'; exit 0; }; \
            st=\$(pinctrl get $g 2>/dev/null); echo \"before: \$st\"; \
            case \"\$st\" in *lo*) op=dh; back=dl;; *) op=dl; back=dh;; esac; \
            echo \"driving \$op for 3s...\"; \
            pinctrl set $g op \$op 2>&1 || { echo 'set failed (try with sudo)'; exit 0; }; \
            sleep 3; pinctrl set $g op \$back 2>&1 || true; \
            echo \"restored: \$(pinctrl get $g 2>/dev/null)\""
    echo "(Level restored. If the panel changed during those 3s, GPIO$g IS the backlight line.)"
}

probe_services() {
    for u in piano pisynth-ui midi-bridge; do
        section "$u.service"
        remote "systemctl is-active $u.service 2>&1; systemctl status $u.service --no-pager -n 8 2>&1 || true"
    done
}

probe_ui() {
    section "UI control state (:9810)"
    remote 'printf "state\n" | nc -q 1 127.0.0.1 9810 2>&1 || echo "(UI socket not answering)"'
}

echo "probe → $PI  (read-only; does not modify the app)"
case "${1:-default}" in
    default)          section "host"; remote 'uname -a; hostname'
                      probe_audio; probe_services; probe_ui; probe_backlight ;;
    audio)            probe_audio ;;
    backlight)        probe_backlight ;;
    backlight-toggle) probe_backlight_toggle "${2:-}" ;;
    services)         probe_services ;;
    ui)               probe_ui ;;
    *)                section "remote: $*"; remote "$*" ;;
esac
