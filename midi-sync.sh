#!/usr/bin/env bash
# midi-sync.sh REPO LIBRARY — (re)build the MIDI library's links: MIDI files and MusicXML scores
# (#2421, #2657). Run by sync.sh on every deploy (and by the dev stack), as the owner of LIBRARY.
#
#   REPO/library/midi/…  → LIBRARY/starter/…   the shipped Public Domain set
#   REPO/midi/…          → LIBRARY/…           your own files (gitignored), subfolders kept
#
# Folders are real, files are symlinks, so nothing big is copied. A file uploaded from the web
# companion is a real file: it is never replaced, even by a PC file of the same name. Then the
# links whose file left the repo are removed, and the folders left empty with them; a folder made
# from the phone holds a marker file, so it survives.
set -euo pipefail

[[ $# -eq 2 ]] || { echo "usage: midi-sync.sh REPO LIBRARY" >&2; exit 2; }
repo="$(cd "$1" && pwd)"
lib="$2"
mkdir -p "$lib"
lib="$(cd "$lib" && pwd)"

link_tree() {   # SRC DEST: link every MIDI file under SRC to the same relative path under DEST
    local src="$1" dst="$2" n=0 f rel target
    [[ -d "$src" ]] || { echo 0; return; }
    while IFS= read -r -d '' f; do
        rel="${f#"$src"/}"
        target="$dst/$rel"
        mkdir -p "$(dirname "$target")"
        if [[ -L "$target" || ! -e "$target" ]]; then
            ln -sfn "$f" "$target"
            n=$((n + 1))
        fi
    done < <(find "$src" -type f \( -iname '*.mid' -o -iname '*.midi' -o -iname '*.musicxml' -o -iname '*.xml' -o -iname '*.mxl' \) -not -path '*/.*' -print0)
    echo "$n"
}

starter="$(link_tree "$repo/library/midi" "$lib/starter")"
pc="$(link_tree "$repo/midi" "$lib")"

removed=0
while IFS= read -r -d '' l; do
    case "$(readlink "$l")" in
        "$repo"/*) [[ -e "$l" ]] || { rm -f "$l"; removed=$((removed + 1)); } ;;
    esac
done < <(find "$lib" -type l -print0)
find "$lib" -mindepth 1 -type d -empty -delete

echo "[midi] $lib: $starter starter + $pc of yours linked, $removed stale link(s) removed"
