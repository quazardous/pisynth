#!/usr/bin/env bash
# install-soundfonts.sh — bring ~/soundfonts/ to its full curated state.
#
# Layout produced:
#   01-MuseScore_General.sf3       → symlink to apt package (musescore-general-soundfont)
#   02-FluidR3_GM.sf2              → symlink to apt package (fluid-soundfont-gm)
#   03-Yamaha-Grand-v2.1.sf2       → downloaded from Hugging Face mirror
#   04-Nice-Steinway-Lite-v3.0.sf2 → downloaded from Hugging Face mirror
#   05-Abbey-Steinway-D-v1.9.sf2   → downloaded from Hugging Face mirror
#   06-TimGM6mb.sf2                → symlink to apt package (timgm6mb-soundfont, small GM)
#
# Idempotent: skips anything already present and valid.
# Run as the `pi` user; sudo is invoked only for apt.
#
# Usage:
#   bash ~/pisynth/install-soundfonts.sh
# After:
#   sudo systemctl restart piano.service

set -uo pipefail

DEST="${HOME}/soundfonts"
HF_BASE="https://huggingface.co/datasets/projectlosangeles/soundfonts4u/resolve/main"

mkdir -p "$DEST"

# ---- 1) apt packages (provide 01 + 02) ----
APT_PACKAGES=(musescore-general-soundfont fluid-soundfont-gm timgm6mb-soundfont)
missing=()
for pkg in "${APT_PACKAGES[@]}"; do
    dpkg -s "$pkg" &>/dev/null || missing+=("$pkg")
done
if (( ${#missing[@]} > 0 )); then
    echo "[*] Installing apt packages: ${missing[*]}"
    sudo apt update -qq
    sudo apt install -y "${missing[@]}"
else
    echo "[=] apt packages already installed"
fi

# ---- 2) symlinks for the GM soundfonts (01 + 02) ----
# Symlink targets (real on-disk paths from the Debian packages).
SYMLINKS=(
    "01-MuseScore_General.sf3|/usr/share/sounds/sf3/MuseScore_General.sf3"
    "02-FluidR3_GM.sf2|/usr/share/sounds/sf2/FluidR3_GM.sf2"
    "06-TimGM6mb.sf2|/usr/share/sounds/sf2/TimGM6mb.sf2"
)
for entry in "${SYMLINKS[@]}"; do
    local_name=$(echo "$entry" | cut -d'|' -f1)
    target=$(echo "$entry" | cut -d'|' -f2)
    link="$DEST/$local_name"
    if [[ ! -e "$target" ]]; then
        echo "[!] $local_name: target $target missing — apt install may have failed"
        continue
    fi
    if [[ -L "$link" && "$(readlink -f "$link")" == "$(readlink -f "$target")" ]]; then
        echo "[=] $local_name → already symlinked"
    else
        ln -sf "$target" "$link"
        echo "[OK] $local_name → $target"
    fi
done

# ---- 3) Downloaded piano soundfonts (03 + 04 + 05) ----
# local-name | remote-name (URL-encoded) | approx-size-MB
DOWNLOADS=(
    "03-Yamaha-Grand-v2.1.sf2|Yamaha%20Grand-v2.1.sf2|243"
    "04-Nice-Steinway-Lite-v3.0.sf2|Nice-Steinway-Lite-v3.0.sf2|74"
    "05-Abbey-Steinway-D-v1.9.sf2|Abbey-Steinway-D-v1.9.sf2|40"
)

# Disk space precheck (sum of downloads + 50 MB safety).
total_mb=50
for entry in "${DOWNLOADS[@]}"; do
    name=$(echo "$entry" | cut -d'|' -f1)
    [[ -s "$DEST/$name" ]] && continue
    total_mb=$(( total_mb + $(echo "$entry" | cut -d'|' -f3) ))
done
if (( total_mb > 50 )); then
    avail_mb=$(df -BM --output=avail "$DEST" | tail -1 | tr -d 'M ')
    if (( avail_mb < total_mb )); then
        echo "[!] Not enough free space: need ~${total_mb} MB, have ${avail_mb} MB"
        exit 1
    fi
    echo "[*] Will download ~${total_mb} MB (free: ${avail_mb} MB)"
fi

ok=0; ko=0; skipped=0
for entry in "${DOWNLOADS[@]}"; do
    local_name=$(echo "$entry" | cut -d'|' -f1)
    remote_name=$(echo "$entry" | cut -d'|' -f2)
    size_mb=$(echo "$entry" | cut -d'|' -f3)
    target="$DEST/$local_name"

    if [[ -s "$target" ]]; then
        if head -c 4 "$target" | grep -q "RIFF"; then
            echo "[=] $local_name (~${size_mb} MB) — already present, skipping"
            skipped=$((skipped + 1))
            continue
        else
            echo "[!] $local_name exists but is not a valid SF2 — re-downloading"
            rm -f "$target"
        fi
    fi

    echo "[>] downloading $local_name (~${size_mb} MB)..."
    if curl -fL --retry 3 --retry-delay 2 --progress-bar \
            -o "$target.part" "$HF_BASE/$remote_name"; then
        if head -c 4 "$target.part" | grep -q "RIFF"; then
            mv "$target.part" "$target"
            actual_mb=$(du -m "$target" | cut -f1)
            echo "[OK] $local_name → ${actual_mb} MB"
            ok=$((ok + 1))
        else
            echo "[X] $local_name — downloaded file is not a valid SF2 (no RIFF header)"
            rm -f "$target.part"
            ko=$((ko + 1))
        fi
    else
        echo "[X] $local_name — curl failed"
        rm -f "$target.part"
        ko=$((ko + 1))
    fi
done

echo ""
echo "=== Summary ==="
echo "  apt installed/checked : ${#APT_PACKAGES[@]}"
echo "  symlinks              : ${#SYMLINKS[@]}"
echo "  downloads ok          : $ok"
echo "  downloads skipped     : $skipped"
echo "  downloads failed      : $ko"
echo ""
echo "=== ~/soundfonts/ ==="
ls -lh "$DEST"

if (( ko == 0 )); then
    echo ""
    echo "Next: sudo systemctl restart piano.service"
fi
