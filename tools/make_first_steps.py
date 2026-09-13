#!/usr/bin/env python3
"""Generate the two easiest starter levels as MIDI files (#2421 follow-up).

Well-known public domain tunes (children's songs), whole songs, arranged here as simply as possible:
- 0-homer: the very first notes — right hand only, a handful of notes, very slow;
- 1-first-steps: the right hand plays the melody, the left hand holds one note per bar (C, F or G),
  slow — two tracks, so each hand can be practised.
Each song is cut into parts (its phrases or verses), written as MIDI markers ("Part 2 · …"): the
companion's step-by-step mode unlocks them one after the other.
The arrangements are ours and released as CC0 (see library/midi/SOURCES.md).

    python3 tools/make_first_steps.py            # writes library/midi/0-homer/ and 1-first-steps/
"""
import os
import struct

MIDI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "library", "midi")
TPQ = 480                                              # ticks per quarter note
NAMES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def notes(text):
    """'C4 D4 E4:2 r:4 E4:1.5' → [("C4", 1), ("D4", 1), ("E4", 2), ("r", 4), ("E4", 1.5)] (beats, default 1)."""
    out = []
    for tok in text.split():
        name, _, beats = tok.partition(":")
        out.append((name, float(beats) if beats else 1))
    return out


# ---- the tunes, by phrase: (part name, melody) ----
AU_CLAIR = [
    ("Au clair de la lune", notes("C4 C4 C4 D4 E4:2 D4:2 C4 E4 D4 D4 C4:4")),
    ("Mon ami Pierrot", notes("C4 C4 C4 D4 E4:2 D4:2 C4 E4 D4 D4 C4:4")),
    ("Ma chandelle est morte", notes("D4 D4 D4 D4 A3:2 A3:2 D4 C4 B3 A3 G3:4")),
    ("Ouvre-moi ta porte", notes("C4 C4 C4 D4 E4:2 D4:2 C4 E4 D4 D4 C4:4")),
]
FRERE_JACQUES = [
    ("Frère Jacques", notes("C4 D4 E4 C4 C4 D4 E4 C4")),
    ("Dormez-vous ?", notes("E4 F4 G4:2 E4 F4 G4:2")),
    ("Sonnez les matines", notes("G4:.5 A4:.5 G4:.5 F4:.5 E4 C4 G4:.5 A4:.5 G4:.5 F4:.5 E4 C4")),
    ("Ding, dang, dong", notes("C4 G3 C4:2 C4 G3 C4:2")),
]
MARY = [
    ("Mary had a little lamb", notes("E4 D4 C4 D4 E4 E4 E4:2 D4 D4 D4:2 E4 G4 G4:2")),
    ("Its fleece was white as snow", notes("E4 D4 C4 D4 E4 E4 E4 E4 D4 D4 E4 D4 C4:4")),
]
ODE = [
    ("Theme", notes("E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 E4:1.5 D4:.5 D4:2")),
    ("Theme again", notes("E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 D4:1.5 C4:.5 C4:2")),
    ("Middle", notes("D4 D4 E4 C4 D4 E4:.5 F4:.5 E4 C4 D4 E4:.5 F4:.5 E4 D4 C4 D4 G3:2")),
    ("Theme, the end", notes("E4 E4 F4 G4 G4 F4 E4 D4 C4 C4 D4 E4 D4:1.5 C4:.5 C4:2")),
]
JINGLE = [
    ("Jingle bells", notes("E4 E4 E4:2 E4 E4 E4:2 E4 G4 C4:1.5 D4:.5 E4:4")),
    ("Oh what fun", notes("F4 F4 F4:1.5 F4:.5 F4 E4 E4 E4:.5 E4:.5 E4 D4 D4 E4 D4:2 G4:2")),
    ("Jingle bells again", notes("E4 E4 E4:2 E4 E4 E4:2 E4 G4 C4:1.5 D4:.5 E4:4")),
    ("In a one-horse open sleigh", notes("F4 F4 F4 F4 F4 E4 E4 E4:.5 E4:.5 G4 G4 F4 D4 C4:4")),
]
TWINKLE = [
    ("Twinkle twinkle little star", notes("C4 C4 G4 G4 A4 A4 G4:2 F4 F4 E4 E4 D4 D4 C4:2")),
    ("Up above the world so high", notes("G4 G4 F4 F4 E4 E4 D4:2 G4 G4 F4 F4 E4 E4 D4:2")),
    ("Twinkle twinkle, the end", notes("C4 C4 G4 G4 A4 A4 G4:2 F4 F4 E4 E4 D4 D4 C4:2")),
]

# 0-homer: (file, title, bpm, beats per bar, parts) — the right hand alone
HOMER = [
    ("1-Do-Re-Mi.mid", "Do Ré Mi (three fingers)", 60, 4, [
        ("Up and down", notes("C4:2 D4:2 E4:4 E4:2 D4:2 C4:4")),
        ("Again", notes("C4:2 D4:2 E4:2 D4:2 C4:4 r:4")),
    ]),
    ("2-Hot-cross-buns.mid", "Hot cross buns", 66, 4, [
        ("Hot cross buns", notes("E4:2 D4:2 C4:4 E4:2 D4:2 C4:4")),
        ("One a penny", notes("C4 C4 C4 C4 D4 D4 D4 D4 E4:2 D4:2 C4:4")),
    ]),
    ("3-Au-clair-de-la-lune.mid", "Au clair de la lune", 66, 4, AU_CLAIR),
    ("4-Mary-had-a-little-lamb.mid", "Mary had a little lamb", 66, 4, MARY),
    ("5-Frere-Jacques.mid", "Frère Jacques", 70, 4, FRERE_JACQUES),
    ("6-Jingle-bells.mid", "Jingle bells", 72, 4, JINGLE),
    ("7-Ode-to-joy.mid", "Ode to Joy", 66, 4, ODE),
]

# 1-first-steps: (file, title, bpm, beats per bar, parts, left hand per bar)
SONGS = [
    ("Five-fingers-up-and-down.mid", "Five fingers up and down", 80, 4, [
        ("Up", notes("C4 D4 E4 F4 G4:2 F4 E4")),
        ("And down", notes("D4 C4 D4 E4 C4:4")),
    ], "C3 G2 G2 C3"),
    ("Au-clair-de-la-lune.mid", "Au clair de la lune", 90, 4, AU_CLAIR,
     "C3 G2 G2 C3  C3 G2 G2 C3  G2 F2 G2 G2  C3 G2 G2 C3"),
    ("Mary-had-a-little-lamb.mid", "Mary had a little lamb", 90, 4, MARY, "C3 C3 G2 C3 C3 C3 G2 C3"),
    ("Ode-to-joy.mid", "Ode to Joy (Beethoven)", 84, 4, ODE,
     "C3 G2 C3 G2  C3 G2 C3 C3  G2 G2 G2 C3  C3 G2 C3 C3"),
    ("Frere-Jacques.mid", "Frère Jacques", 96, 4, FRERE_JACQUES, "C3 C3 C3 C3 C3 C3 C3 C3"),
    ("Twinkle-twinkle-little-star.mid", "Twinkle twinkle little star (Ah vous dirai-je maman)", 90, 4, TWINKLE,
     "C3 C3 G2 C3  C3 C3 G2 G2  C3 C3 G2 C3"),
    ("Jingle-bells.mid", "Jingle bells (chorus)", 100, 4, JINGLE,
     "C3 C3 C3 C3 F2 C3 G2 G2  C3 C3 C3 C3 F2 C3 G2 C3"),
]


def midi_note(name):
    return 12 * (int(name[-1]) + 1) + NAMES[name[0]] + (1 if "#" in name else 0)


def vlq(n):
    out = [n & 0x7F]
    while n >> 7:
        n >>= 7
        out.insert(0, (n & 0x7F) | 0x80)
    return bytes(out)


def track(events):
    """events: [(tick, bytes)] → an MTrk chunk (sorted, note-offs before note-ons at the same tick)."""
    body, last = b"", 0
    for tick, data in sorted(events, key=lambda e: (e[0], e[1][0] & 0xF0 != 0x80)):
        body += vlq(tick - last) + data
        last = tick
    body += b"\x00\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(body)) + body


def meta_text(kind, text):
    raw = text.encode("utf-8")
    return bytes((0xFF, kind)) + vlq(len(raw)) + raw


def song_bytes(title, bpm, beats_per_bar, parts, left):
    """parts: [(name, [(note|"r", beats)…])]; left: one note per bar (str) or None for the right hand alone."""
    head = [(0, meta_text(0x03, title)),
            (0, b"\xff\x51\x03" + (60_000_000 // bpm).to_bytes(3, "big")),
            (0, bytes((0xFF, 0x58, 4, beats_per_bar, 2, 24, 8)))]
    rh, tick = [(0, meta_text(0x03, "Right hand"))], 0
    for k, (name, melody) in enumerate(parts):
        head.append((tick, meta_text(0x06, f"Part {k + 1} · {name}")))     # marker: where each part starts
        for note, beats in melody:
            dur = int(beats * TPQ)
            if note != "r":
                n = midi_note(note)
                rh += [(tick, bytes((0x90, n, 84))), (tick + dur - TPQ // 16, bytes((0x80, n, 0)))]
            tick += dur
    if left is None:                                  # 0-homer: the right hand alone
        return b"MThd" + struct.pack(">IHHH", 6, 1, 2, TPQ) + track(head) + track(rh)
    lh = [(0, meta_text(0x03, "Left hand"))]
    bar = beats_per_bar * TPQ
    for i, note in enumerate(left.split()):
        n = midi_note(note)
        lh += [(i * bar, bytes((0x91, n, 64))), ((i + 1) * bar - TPQ // 8, bytes((0x81, n, 0)))]
    return b"MThd" + struct.pack(">IHHH", 6, 1, 3, TPQ) + track(head) + track(rh) + track(lh)


def main():
    levels = [("0-homer", [(*s, None) for s in HOMER]), ("1-first-steps", SONGS)]
    for folder, songs in levels:
        out = os.path.join(MIDI_DIR, folder)
        os.makedirs(out, exist_ok=True)
        for name, title, bpm, bpb, parts, left in songs:
            for part, melody in parts:
                bars = sum(b for _, b in melody) / bpb
                assert bars == int(bars), f"{name} / {part}: not whole bars ({bars})"
            bars = int(sum(b for _, melody in parts for _, b in melody) / bpb)
            assert left is None or len(left.split()) == bars, f"{name}: {bars} melody bars, {len(left.split())} left-hand bars"
            with open(os.path.join(out, name), "wb") as f:
                f.write(song_bytes(title, bpm, bpb, parts, left))
            print(f"{folder}/{name}: {bars} bars in {len(parts)} parts @ {bpm} bpm")


if __name__ == "__main__":
    main()
