#!/usr/bin/env bash
# start-piano.sh — boots a fluidsynth grand piano on the first non-HDMI USB sound card,
# auto-connecting any USB-MIDI input that's plugged in.

set -u

# Optional user config file: any variable defined there overrides the defaults below.
# Service runs as user pi, so HOME = /home/pi.
CONFIG_FILE="${SYNTH_CONFIG:-${HOME}/.local/synth.conf}"
if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
fi

# Audio device chosen in the touch UI (Settings → Audio device, ticket #282).
# The UI persists the ALSA card name into settings.yaml (#303). synth.conf's
# SOUNDCARD still wins if set; otherwise the UI choice; otherwise auto-detect.
UI_SETTINGS="${PISYNTH_SETTINGS:-${HOME}/.config/pisynth/settings.yaml}"
if [[ -z "${SOUNDCARD:-}" && -f "$UI_SETTINGS" ]]; then
    SOUNDCARD="$(python3 -c 'import sys,yaml; d=yaml.safe_load(open(sys.argv[1])) or {}; print(d.get("soundcard","") or "")' "$UI_SETTINGS" 2>/dev/null || true)"
fi
# Fallback: a pre-#303 settings.json that has not been migrated yet (no UI run since).
LEGACY_JSON="${HOME}/.config/pisynth/settings.json"
if [[ -z "${SOUNDCARD:-}" && -f "$LEGACY_JSON" ]]; then
    SOUNDCARD="$(grep -oP '"soundcard"\s*:\s*"\K[^"]+' "$LEGACY_JSON" 2>/dev/null || true)"
fi
# Never run the synth on HDMI (vc4hdmi): on a headless box HDMI audio has no consumer,
# so fluidsynth busy-loops — and at RT priority it starves the touch UI into a freeze
# (#311). Ignore a stale/mistaken HDMI choice and fall back to auto-detect (USB).
if [[ "${SOUNDCARD:-}" == *[Hh][Dd][Mm][Ii]* ]]; then
    log "ignoring HDMI audio output '$SOUNDCARD' (no consumer headless → fluidsynth runaway, #311); auto-detecting instead"
    SOUNDCARD=""
fi

# Bluetooth A2DP output (Settings → Audio device, ticket #301). When the UI has chosen a
# Bluetooth sink (settings.yaml: bluetooth.audio_sink = MAC), the synth routes to it via
# PipeWire's PulseAudio server. When EMPTY (the default) we never touch PipeWire and run
# ALSA-direct on the USB card — david's #301 ask: "si pas de périphérique BT → que ALSA".
BT_SINK_MAC="${BT_SINK_MAC:-}"
if [[ -z "$BT_SINK_MAC" && -f "$UI_SETTINGS" ]]; then
    BT_SINK_MAC="$(python3 -c 'import sys,yaml; d=yaml.safe_load(open(sys.argv[1])) or {}; print(((d.get("bluetooth") or {}).get("audio_sink")) or "")' "$UI_SETTINGS" 2>/dev/null || true)"
fi
# How long to wait for a chosen BT sink to (auto-)connect before falling back to ALSA.
BT_WAIT="${BT_WAIT:-20}"

# Chosen MIDI keyboard (settings.yaml: midi_keyboard = ALSA-seq client name). Empty (the
# default) = autoconnect ALL inputs; a specific name = route only that device (#326).
MIDI_KBD="${MIDI_KBD:-}"
if [[ -z "$MIDI_KBD" && -f "$UI_SETTINGS" ]]; then
    MIDI_KBD="$(python3 -c 'import sys,yaml; d=yaml.safe_load(open(sys.argv[1])) or {}; print(d.get("midi_keyboard","") or "")' "$UI_SETTINGS" 2>/dev/null || true)"
fi
# midi.autoconnect: 1 (grab all) when no specific keyboard; 0 + explicit connect otherwise.
MIDI_AUTOCONNECT=1
if [[ -n "$MIDI_KBD" ]]; then
    MIDI_AUTOCONNECT=0
    # fluidsynth replaces this shell on exec, so connect from a background helper: wait for
    # the synth's seq port to appear, then wire only the chosen keyboard's port 0 (#326).
    ( for _ in $(seq 1 30); do
        if aconnect -o 2>/dev/null | grep -q "FLUID Synth"; then
            aconnect "$MIDI_KBD" "FLUID Synth" 2>/dev/null && echo "[piano] MIDI: routed '$MIDI_KBD' -> FLUID Synth"
            break
        fi
        sleep 1
      done ) &
fi

SOUNDFONT="${SOUNDFONT:-/usr/share/sounds/sf3/MuseScore_General.sf3}"
# Where to look for .sf2/.sf3 files (and symlinks to them).
# Every file in this directory is loaded at startup, sorted by name.
# Rename with numeric prefix (01-..., 02-...) to control loading order.
SOUNDFONT_DIR="${SOUNDFONT_DIR:-${HOME}/soundfonts}"
# SOUNDFONTS = colon-separated list. If set, takes precedence over SOUNDFONT_DIR scan.
SOUNDFONTS="${SOUNDFONTS:-}"
GAIN="${GAIN:-2.5}"
PERIOD_SIZE="${PERIOD_SIZE:-256}"
PERIODS="${PERIODS:-4}"
WAIT_SECONDS="${WAIT_SECONDS:-60}"

log() { echo "[piano] $*"; }

# Resolve the PipeWire/Pulse sink node-name for a connected BT device, by MAC. PipeWire
# names a Bluetooth A2DP sink `bluez_output.AA_BB_CC_DD_EE_FF.<profile>` and exposes it
# under the same name to its PulseAudio server (#301). Read the live name from pw-dump so
# the profile suffix is whatever BlueZ actually negotiated; "" if no such sink is present.
bt_sink_name() {
    local mac_us="${1//:/_}"
    pw-dump 2>/dev/null | grep -oE "bluez_output\.${mac_us}[^\"]*" | head -n1 || true
}

# Wait up to BT_WAIT seconds for the chosen BT sink to appear (trusted devices auto-connect
# a few seconds after boot). Echoes the resolved sink name on success; non-zero on timeout.
wait_for_bt_sink() {
    local elapsed=0 name=""
    while (( elapsed < BT_WAIT )); do
        name="$(bt_sink_name "$1")"
        if [[ -n "$name" ]]; then
            echo "$name"
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    return 1
}

# Find the dedicated USB audio interface. /proc/asound/cards marks USB cards
# with "USB-Audio" — pick that card's bracketed name (used as plughw:NAME).
# This deliberately ignores the Pi's onboard cards (bcm2835 headphone jack and
# vc4hdmi), which would otherwise be chosen first by aplay's card order.
# USB-MIDI keyboards have no PCM playback, so they don't shadow the interface.
# A specific card can be forced with the SOUNDCARD env var.
find_usb_card() {
    if [[ -n "${SOUNDCARD:-}" ]]; then
        echo "$SOUNDCARD"
        return 0
    fi
    awk '/USB-Audio/ {
        if (match($0, /\[[^]]+\]/)) {
            name = substr($0, RSTART + 1, RLENGTH - 2)
            gsub(/ +$/, "", name)
            print name
            exit
        }
    }' /proc/asound/cards
}

# Wait until the USB sound card with PCM playback exists. The MIDI keyboard is
# deliberately NOT required (#276): fluidsynth starts on the audio interface
# alone and midi.autoconnect=1 grabs the Keystation whenever it's (re)plugged.
# This keeps the soundfont UI usable with the keyboard unplugged — previously
# the synth wouldn't start without a MIDI input, so the font tiles vanished.
wait_for_hardware() {
    local elapsed=0
    while (( elapsed < WAIT_SECONDS )); do
        local card; card="$(find_usb_card || true)"
        if [[ -n "$card" ]]; then
            echo "$card"
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    return 1
}

# Build the soundfont list. Priority:
#   1. SOUNDFONTS env var (colon-separated, explicit)
#   2. Scan of SOUNDFONT_DIR for *.sf2 / *.sf3 (sorted)
#   3. Fallback to single SOUNDFONT path
sflist=()
if [[ -n "$SOUNDFONTS" ]]; then
    IFS=':' read -ra sflist <<< "$SOUNDFONTS"
elif [[ -d "$SOUNDFONT_DIR" ]]; then
    shopt -s nullglob nocaseglob
    candidates=("$SOUNDFONT_DIR"/*.sf2 "$SOUNDFONT_DIR"/*.sf3)
    shopt -u nullglob nocaseglob
    if (( ${#candidates[@]} > 0 )); then
        # Sort alphabetically (use `01-…`, `02-…` prefixes to control order)
        IFS=$'\n' sflist=($(printf '%s\n' "${candidates[@]}" | sort))
        unset IFS
    fi
fi
if (( ${#sflist[@]} == 0 )); then
    sflist=("$SOUNDFONT")
fi

# Drop missing files; abort if nothing is left.
sflist_ok=()
for sf in "${sflist[@]}"; do
    if [[ -f "$sf" ]]; then
        sflist_ok+=("$sf")
    else
        log "soundfont missing, skipping: $sf"
    fi
done
if (( ${#sflist_ok[@]} == 0 )); then
    log "no soundfont available; bailing out (SOUNDFONT_DIR=$SOUNDFONT_DIR)"
    exit 1
fi

# --- Bluetooth A2DP output branch (#301) -----------------------------------------------
# If a BT sink was chosen, route the synth through PipeWire's PulseAudio server. This
# needs the user PipeWire session, which a system service reaches via XDG_RUNTIME_DIR;
# enable-linger keeps that session up at headless boot (migration 015). MIDI still comes
# in over alsa_seq, so the USB sound card is not required on this path. If the sink never
# shows up (device off / out of range), fall back to ALSA so there is still sound.
if [[ -n "$BT_SINK_MAC" ]]; then
    export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    log "Bluetooth audio sink requested: $BT_SINK_MAC (XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR)"
    log "waiting up to ${BT_WAIT}s for the sink to connect..."
    if SINK="$(wait_for_bt_sink "$BT_SINK_MAC")"; then
        log "routing synth to PipeWire/Pulse sink: $SINK"
        log "soundfonts (${#sflist_ok[@]}): ${sflist_ok[*]}"
        log "gain: $GAIN  driver: pulseaudio  config: ${CONFIG_FILE}$([[ -f "$CONFIG_FILE" ]] || echo ' (not present, defaults used)')"
        # A2DP is high-latency (~150-250ms) so realtime scheduling buys nothing here, and
        # if the pulse/BT output ever busy-loops, an RT audio thread STARVES the touch UI
        # into a freeze (#282/#311: fluidsynth hit 363% CPU at RT, UI got 2.7%). So this
        # branch runs the audio thread at NORMAL priority (audio.realtime-prio=0); combined
        # with the unit's CPUQuota a runaway can no longer lock up the box.
        exec /usr/bin/fluidsynth \
            --server --no-shell \
            --audio-driver=pulseaudio \
            --midi-driver=alsa_seq \
            -o "audio.pulseaudio.device=${SINK}" \
            -o "audio.realtime-prio=0" \
            -o "midi.autoconnect=${MIDI_AUTOCONNECT}" \
            -o "synth.gain=${GAIN}" \
            -o "synth.reverb.active=1" \
            -o "synth.chorus.active=0" \
            "${sflist_ok[@]}"
    fi
    log "Bluetooth sink $BT_SINK_MAC not available after ${BT_WAIT}s — falling back to ALSA"
fi
# ---------------------------------------------------------------------------------------

log "waiting for USB sound card (up to ${WAIT_SECONDS}s; MIDI keyboard optional)..."
CARD="$(wait_for_hardware)" || {
    log "timeout: no USB sound card detected"
    log "current /proc/asound/cards:"
    cat /proc/asound/cards
    log "current aconnect -i (MIDI inputs, optional):"
    aconnect -i 2>&1 || true
    exit 1
}

log "using ALSA card: plughw:${CARD}"
log "soundfonts (${#sflist_ok[@]}): ${sflist_ok[*]}"
log "gain: $GAIN  period: ${PERIOD_SIZE}x${PERIODS}  config: ${CONFIG_FILE}$([[ -f "$CONFIG_FILE" ]] || echo ' (not present, defaults used)')"

# plughw (vs hw) lets ALSA convert sample format/rate transparently — needed
# because some USB interfaces (e.g. M-Track Hub) only accept S24_3LE while
# fluidsynth outputs S16_LE or float.
exec /usr/bin/fluidsynth \
    --server --no-shell \
    --audio-driver=alsa \
    --midi-driver=alsa_seq \
    -o "audio.alsa.device=plughw:${CARD}" \
    -o "audio.period-size=${PERIOD_SIZE}" \
    -o "audio.periods=${PERIODS}" \
    -o "midi.autoconnect=${MIDI_AUTOCONNECT}" \
    -o "synth.gain=${GAIN}" \
    -o "synth.reverb.active=1" \
    -o "synth.chorus.active=0" \
    "${sflist_ok[@]}"
