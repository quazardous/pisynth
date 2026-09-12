#!/usr/bin/env bash
# midi-bridge.sh — listens to the Keystation D-pad on MIDI port :1 and forwards the
# 5 buttons to the touch UI's control socket (:9810):
#   ←  98  : previous soundfont        (action prev_font)
#   →  99  : next soundfont            (action next_font)
#   ↑  96  : previous preset           (action prev_preset)
#   ↓  97  : next preset               (action next_preset)
#   ●  100 : first soundfont, default preset (action first_font)
#
# The UI owns the synth state: it keeps a single soundfont resident (#334), persists the
# choice and redraws the screen. The bridge used to address fluidsynth directly with
# soundfont ids 1..N (one per file on disk), which no longer exist in single-font mode
# ("No SoundFont with id = 2" at boot) and clobbered the metronome drum kit on channel 9.
#
# Feedback beep: the UI's navigation beep (GM percussion on channel 9, kind/volume from
# Settings → Navigation), sent before the action so it isn't muted by the font load.
#
# To avoid the raw D-pad notes leaking into the piano sound, this bridge disconnects
# port :1 from fluidsynth on startup. The UI stops this service while its own MIDI
# navigation owns the D-pad (screens/nav.py).
#
# Sourced config: ~/.local/synth.conf

set -uo pipefail

CONFIG_FILE="${SYNTH_CONFIG:-${HOME}/.local/synth.conf}"
if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
fi

DEVICE="${MIDI_BRIDGE_DEVICE:-Keystation 61 MK3:1}"
UI_HOST="${UI_HOST:-127.0.0.1}"
UI_PORT="${PISYNTH_CTL_PORT:-9810}"
# Set to 0 to silence the D-pad beep. Preset switching still works.
FEEDBACK_ENABLED="${FEEDBACK_ENABLED:-1}"

log() { echo "[bridge] $*"; }

# One command per connection: the UI answers a single line, then closes.
ui_cmd() {
    printf '%s\n' "$1" | timeout 2 nc -q 1 "$UI_HOST" "$UI_PORT" 2>/dev/null
}

# Wait for the UI control socket to be reachable.
log "waiting for the UI control socket on $UI_HOST:$UI_PORT..."
for _ in $(seq 1 60); do
    if timeout 1 bash -c "</dev/tcp/$UI_HOST/$UI_PORT" 2>/dev/null; then
        break
    fi
    sleep 1
done

# Disconnect Keystation:1 from fluidsynth so the raw D-pad notes don't play
# the current piano preset.
fs_client=$(aconnect -l 2>/dev/null | awk '/FLUID Synth/ { for (i=1;i<=NF;i++) if ($i ~ /^[0-9]+:$/) { gsub(":","",$i); print $i; exit } }')
if [[ -n "${fs_client:-}" ]]; then
    if aconnect -d "$DEVICE" "${fs_client}:0" 2>/dev/null; then
        log "disconnected '$DEVICE' from fluidsynth (${fs_client}:0)"
    fi
fi

log "listening on '$DEVICE' → UI :$UI_PORT (feedback: $([[ "$FEEDBACK_ENABLED" == "1" ]] && echo on || echo off))"

stdbuf -oL aseqdump -p "$DEVICE" 2>/dev/null \
| while IFS= read -r line; do
    # Match any Note On with non-zero velocity (velocity 0 is a Note Off by MIDI convention).
    [[ "$line" == *"Note on"* && "$line" != *"velocity 0"* ]] || continue
    note=$(echo "$line" | awk '{gsub(",",""); print $6}')
    case "$note" in
        98)  action=prev_font ;;
        99)  action=next_font ;;
        96)  action=prev_preset ;;
        97)  action=next_preset ;;
        100) action=first_font ;;
        *)   continue ;;
    esac
    [[ "$FEEDBACK_ENABLED" == "1" ]] && ui_cmd "action beep" >/dev/null
    log "note $note → $action: $(ui_cmd "action $action" || echo 'UI unreachable')"
done
