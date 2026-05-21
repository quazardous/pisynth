#!/usr/bin/env bash
# midi-bridge.sh — listens to the Keystation D-pad on MIDI port :1
# and translates the 5 buttons into:
#   1) fluidsynth preset/soundfont switching (broadcast to channels 0-14)
#   2) a short SFX "beep" on channel 15 (R2D2-ish feedback)
#
# Mapping (note number received on channel 0 of port :1):
#   ←  98  : previous soundfont
#   →  99  : next soundfont
#   ↑  96  : previous preset (variation)
#   ↓  97  : next preset
#   ●  100 : reset to soundfont 1, preset 0 (Acoustic Grand)
#
# To avoid the raw D-pad notes leaking into the main piano sound,
# this bridge disconnects port :1 from fluidsynth on startup.
#
# Sourced config: ~/.local/synth.conf

set -uo pipefail

CONFIG_FILE="${SYNTH_CONFIG:-${HOME}/.local/synth.conf}"
if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$CONFIG_FILE"
fi

DEVICE="${MIDI_BRIDGE_DEVICE:-Keystation 61 MK3:1}"
FS_HOST="${FS_HOST:-127.0.0.1}"
FS_PORT="${FS_PORT:-9800}"

# Auto-detect soundfont count by scanning the same dir as start-piano.sh.
SOUNDFONT_DIR="${SOUNDFONT_DIR:-${HOME}/soundfonts}"
if [[ -z "${NUM_SOUNDFONTS:-}" ]]; then
    if [[ -d "$SOUNDFONT_DIR" ]]; then
        shopt -s nullglob nocaseglob
        _sfs=("$SOUNDFONT_DIR"/*.sf2 "$SOUNDFONT_DIR"/*.sf3)
        shopt -u nullglob nocaseglob
        NUM_SOUNDFONTS=${#_sfs[@]}
    fi
    [[ "${NUM_SOUNDFONTS:-0}" -lt 1 ]] && NUM_SOUNDFONTS=1
fi

# Curated GM preset list for the main keyboard (channels 0-14). Bank=0 for all.
PRESETS_PROG=(0 1 4 5 6 7 16 17 19)
PRESETS_NAME=("Acoustic Grand" "Bright Piano" "Electric Piano" "EP Chorused" "Harpsichord" "Clavinet" "Drawbar Organ" "Percussive Organ" "Church Organ")
NUM_PRESETS=${#PRESETS_PROG[@]}

# SFX channel + preset for the D-pad "beep" feedback (always on sfont 1).
# GM 104 = "FX 8 (Sci-Fi)" — fitting R2D2 vibe in MuseScore_General.
FEEDBACK_CHANNEL="${FEEDBACK_CHANNEL:-15}"
FEEDBACK_PRESET="${FEEDBACK_PRESET:-104}"
FEEDBACK_VELOCITY="${FEEDBACK_VELOCITY:-110}"
FEEDBACK_DURATION="${FEEDBACK_DURATION:-0.08}"
# Channel-wide volume scaling for the feedback (CC 7, range 0-127).
# Independent of velocity — use this to make the D-pad beep quieter than the piano.
FEEDBACK_VOLUME="${FEEDBACK_VOLUME:-50}"
# Set to 0 to completely disable the D-pad beep (no preset assignment, no notes).
# Preset switching still works — only the audio feedback is muted.
FEEDBACK_ENABLED="${FEEDBACK_ENABLED:-1}"

# Per-direction pitch for the beep (R2D2-ish: high, distinct).
declare -A BEEP_NOTE=(
    [98]=60   # ← C4
    [99]=67   # → G4
    [96]=84   # ↑ C6
    [97]=72   # ↓ C5
    [100]=76  # ● E5
)

sf_idx=0
preset_idx=0

# Per-SF preset cache, populated at startup by query_sf_presets().
# Each soundfont has its own list of usable presets (curated entries that exist,
# or fallback to the SF's own presets if curation matches nothing).
declare -A SF_PROG    # key "sfid:idx" → GM program number
declare -A SF_NAME    # key "sfid:idx" → display name
declare -a SF_COUNT   # SF_COUNT[sfid] → number of usable presets

log() { echo "[bridge] $*"; }

# Send commands to fluidsynth's TCP shell. Pass one or more commands as args.
fs_cmd() {
    printf '%s\n' "$@" | timeout 2 nc -q 1 "$FS_HOST" "$FS_PORT" >/dev/null 2>&1
}

beep() {
    [[ "$FEEDBACK_ENABLED" == "1" ]] || return 0
    local note="$1"
    local k="${BEEP_NOTE[$note]:-72}"
    fs_cmd "noteon $FEEDBACK_CHANNEL $k $FEEDBACK_VELOCITY"
    # Schedule note-off in background so we don't block reading the next event.
    ( sleep "$FEEDBACK_DURATION"; fs_cmd "noteoff $FEEDBACK_CHANNEL $k" ) &
}

# Query fluidsynth for the actual presets present in a soundfont. Builds the
# per-SF preset list as: curated entries (PRESETS_PROG) that actually exist;
# if curation matches nothing (e.g. piano-only SF with only programs 0-3),
# fall back to the SF's own first 9 bank-0 presets.
query_sf_presets() {
    local sfid="$1"
    local raw
    raw=$(printf 'inst %d\n' "$sfid" | timeout 3 nc -q 1 "$FS_HOST" "$FS_PORT" 2>/dev/null || true)
    local -A avail_progs avail_names
    while IFS= read -r line; do
        # fluidsynth `inst` output: "000-NNN Some Name" (bank-prog name).
        # Only keep bank 0.
        if [[ "$line" =~ ^0+-([0-9]+)[[:space:]]+(.+)$ ]]; then
            local prog=$((10#${BASH_REMATCH[1]}))
            local name="${BASH_REMATCH[2]}"
            avail_progs[$prog]=1
            avail_names[$prog]="$name"
        fi
    done <<< "$raw"

    local idx=0 i prog
    # Pass 1 — filtered curated list.
    for i in "${!PRESETS_PROG[@]}"; do
        prog=${PRESETS_PROG[$i]}
        if [[ -n "${avail_progs[$prog]:-}" ]]; then
            SF_PROG[$sfid:$idx]=$prog
            SF_NAME[$sfid:$idx]="${PRESETS_NAME[$i]}"
            idx=$((idx + 1))
        fi
    done
    # Pass 2 — if curation matched nothing, use SF's own first 9 presets.
    if (( idx == 0 )); then
        local sorted
        sorted=$(printf '%s\n' "${!avail_progs[@]}" | sort -n | head -9)
        for prog in $sorted; do
            SF_PROG[$sfid:$idx]=$prog
            SF_NAME[$sfid:$idx]="${avail_names[$prog]}"
            idx=$((idx + 1))
        done
    fi
    SF_COUNT[$sfid]=$idx
}

apply() {
    local sfid=$((sf_idx + 1))                      # fluidsynth IDs are 1-based
    local count=${SF_COUNT[$sfid]:-0}
    if (( count == 0 )); then
        log "sf=$sfid has no usable presets; skipping apply"
        return 1
    fi
    # Bound preset_idx to the current SF's usable range. Necessary when
    # switching from a SF with many presets to one with fewer.
    if (( preset_idx >= count )); then
        preset_idx=0
    fi
    local prog=${SF_PROG[$sfid:$preset_idx]}
    local name=${SF_NAME[$sfid:$preset_idx]}
    # Broadcast preset to channels 0..14 (channel 15 reserved for feedback SFX).
    # Order: 14→0 so that channel 0 (almost certainly the main keyboard) is
    # written last and "wins" if any rapid command causes a state shuffle.
    # Also reset bank to 0 first then select, to avoid stale bank state.
    local cmds=()
    local ch
    for ch in $(seq 14 -1 0); do
        cmds+=("cc $ch 0 0")          # Bank Select MSB = 0
        cmds+=("cc $ch 32 0")         # Bank Select LSB = 0
        cmds+=("select $ch $sfid 0 $prog")
    done
    fs_cmd "${cmds[@]}"
    log "sf=$sfid preset=$prog ($name) [$((preset_idx+1))/$count]"
}

# Wait for fluidsynth's TCP server to be reachable.
log "waiting for fluidsynth on $FS_HOST:$FS_PORT..."
for _ in $(seq 1 60); do
    if timeout 1 bash -c "</dev/tcp/$FS_HOST/$FS_PORT" 2>/dev/null; then
        break
    fi
    sleep 1
done

# Build the per-SF usable preset map by querying fluidsynth for each SF's contents.
total_usable=0
for sfid in $(seq 1 "$NUM_SOUNDFONTS"); do
    query_sf_presets "$sfid"
    log "sf=$sfid: ${SF_COUNT[$sfid]:-0} usable presets"
    total_usable=$((total_usable + ${SF_COUNT[$sfid]:-0}))
done
if (( total_usable == 0 )); then
    log "WARN: no usable presets found across any SF — bridge will not be functional"
fi

if [[ "$FEEDBACK_ENABLED" == "1" ]]; then
    # Assign the SFX preset to the feedback channel (sfont 1, the first one loaded).
    # CC 7 scales the channel volume so the beep stays quieter than the piano.
    fs_cmd "select $FEEDBACK_CHANNEL 1 0 $FEEDBACK_PRESET" "cc $FEEDBACK_CHANNEL 7 $FEEDBACK_VOLUME"
    log "feedback: channel=$FEEDBACK_CHANNEL preset=$FEEDBACK_PRESET volume=$FEEDBACK_VOLUME"
else
    log "feedback: DISABLED (set FEEDBACK_ENABLED=1 in synth.conf to re-enable)"
fi

# Disconnect Keystation:1 from fluidsynth so the raw D-pad notes don't play
# the current piano preset on top of our beep.
fs_client=$(aconnect -l 2>/dev/null | awk '/FLUID Synth/ { for (i=1;i<=NF;i++) if ($i ~ /^[0-9]+:$/) { gsub(":","",$i); print $i; exit } }')
if [[ -n "${fs_client:-}" ]]; then
    if aconnect -d "$DEVICE" "${fs_client}:0" 2>/dev/null; then
        log "disconnected '$DEVICE' from fluidsynth (${fs_client}:0)"
    fi
fi

log "listening on '$DEVICE' (soundfonts:$NUM_SOUNDFONTS, total usable presets:$total_usable)"

stdbuf -oL aseqdump -p "$DEVICE" 2>/dev/null \
| while IFS= read -r line; do
    # Match any Note On with non-zero velocity. The D-pad buttons are not
    # velocity-sensitive in a musical sense — any keypress should trigger.
    # (velocity 0 is the MIDI convention for a Note Off and must be ignored.)
    if [[ "$line" == *"Note on"* && "$line" != *"velocity 0"* ]]; then
        note=$(echo "$line" | awk '{gsub(",",""); print $6}')
        case "$note" in
            # Changing soundfont also resets to preset 0 — different SFs have
            # different usable preset counts, and "next sound" feels more
            # natural starting from the base.
            98)  sf_idx=$(( (sf_idx - 1 + NUM_SOUNDFONTS) % NUM_SOUNDFONTS )); preset_idx=0; apply; beep "$note" ;;
            99)  sf_idx=$(( (sf_idx + 1) % NUM_SOUNDFONTS )); preset_idx=0; apply; beep "$note" ;;
            # ↑/↓ cycle within the current SF's actual usable preset count.
            96)  cnt=${SF_COUNT[$((sf_idx+1))]:-1}; preset_idx=$(( (preset_idx - 1 + cnt) % cnt )); apply; beep "$note" ;;
            97)  cnt=${SF_COUNT[$((sf_idx+1))]:-1}; preset_idx=$(( (preset_idx + 1) % cnt )); apply; beep "$note" ;;
            100) sf_idx=0; preset_idx=0; apply; beep "$note" ;;
        esac
    fi
done
