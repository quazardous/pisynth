"""Soundfont catalog + preset model — offline-capable, no synth needed (#276/#308)."""
import glob
import os
import re
import struct

# Where soundfonts live on disk — same default as start-piano.sh's SOUNDFONT_DIR.
# Used to build the font/preset catalog OFFLINE (no synth/hardware), ticket #276.
SOUNDFONT_DIR = os.path.expanduser(os.environ.get("PISYNTH_SOUNDFONT_DIR", "~/soundfonts"))


def font_label(path):
    """Pretty display name from a soundfont path: 01-MuseScore_General.sf3 → 'MuseScore General'."""
    base = os.path.basename(path)
    base = re.sub(r"\.(sf2|sf3)$", "", base, flags=re.I)
    base = re.sub(r"^\d+\s*[-_]\s*", "", base)        # strip "01-" load-order prefix
    return (base.replace("_", " ").replace("-", " ").strip()) or base


def sf_key(path):
    """Stable identity of a soundfont across synth reloads = its basename. Used to
    match a persisted/offline choice to a live fluidsynth font id (#276)."""
    return os.path.basename(path or "")


def list_soundfont_files():
    """[path, ...] of *.sf2/*.sf3 in SOUNDFONT_DIR, sorted by name — same set and
    order start-piano.sh loads into fluidsynth, so the catalog matches offline (#276)."""
    files = []
    try:
        for name in os.listdir(SOUNDFONT_DIR):
            if name.lower().endswith((".sf2", ".sf3")):
                files.append(os.path.join(SOUNDFONT_DIR, name))
    except OSError:
        return []
    return sorted(files)


def read_sf_presets(path):
    """[(bank, prog, name), ...] read straight from a SoundFont's `phdr` chunk —
    no synth, no audio decode, no hardware (#276). Works for SF2 AND SF3 (only the
    sample data differs in SF3; pdta/phdr is identical). Same shape as Fluid.presets."""
    try:
        with open(path, "rb") as f:
            riff = f.read(12)
            if riff[:4] != b"RIFF" or riff[8:12] != b"sfbk":
                return []
            end, pos, phdr = struct.unpack("<I", riff[4:8])[0] + 8, 12, None
            while pos < end:
                f.seek(pos)
                hdr = f.read(8)
                if len(hdr) < 8:
                    break
                cid, csz = hdr[:4], struct.unpack("<I", hdr[4:8])[0]
                if cid == b"LIST" and f.read(4) == b"pdta":
                    spos, send = pos + 12, pos + 8 + csz
                    while spos < send:
                        f.seek(spos)
                        sh = f.read(8)
                        if len(sh) < 8:
                            break
                        sid, ssz = sh[:4], struct.unpack("<I", sh[4:8])[0]
                        if sid == b"phdr":
                            f.seek(spos + 8)
                            phdr = f.read(ssz)
                            break
                        spos += 8 + ssz + (ssz & 1)
                    break
                pos += 8 + csz + (csz & 1)
    except OSError:
        return []
    if not phdr:
        return []
    out = []
    for i in range(0, len(phdr) - 38, 38):             # drop the terminal EOP record
        rec = phdr[i:i + 38]
        name = rec[:20].split(b"\x00", 1)[0].decode("latin-1", "replace").strip()
        prog, bank = struct.unpack("<HH", rec[20:24])
        out.append((bank, prog, name))
    return sorted(out)
