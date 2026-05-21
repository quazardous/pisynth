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
# The UI persists the ALSA card name into its settings.json. synth.conf's
# SOUNDCARD still wins if set; otherwise the UI choice; otherwise auto-detect.
UI_SETTINGS="${PISYNTH_SETTINGS:-${HOME}/.config/pisynth/settings.json}"
if [[ -z "${SOUNDCARD:-}" && -f "$UI_SETTINGS" ]]; then
    SOUNDCARD="$(grep -oP '"soundcard"\s*:\s*"\K[^"]+' "$UI_SETTINGS" 2>/dev/null || true)"
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
    -o "midi.autoconnect=1" \
    -o "synth.gain=${GAIN}" \
    -o "synth.reverb.active=1" \
    -o "synth.chorus.active=0" \
    "${sflist_ok[@]}"
