#!/usr/bin/env python3
"""Generate the two easiest starter levels as MIDI files (#2421 follow-up).

Well-known public domain tunes (children's songs), arranged here as simply as possible:
- 0-homer: the very first notes — right hand only, a handful of notes, very slow;
- 1-first-steps: the right hand plays the melody (mostly in the C–G five-finger position), the left
  hand holds one note per bar (C or G), slow — two tracks, so each hand can be practised.
The arrangements are ours and released as CC0 (see library/midi/SOURCES.md).

    python3 tools/make_first_steps.py            # writes library/midi/0-homer/ and 1-first-steps/
"""
import os
import struct

MIDI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "library", "midi")

# 0-homer: (file, title, bpm, beats per bar, right hand) — no left hand, few notes, slow
HOMER = [
    ("1-Do-Re-Mi.mid", "Do Ré Mi (three fingers)", 60, 4,
     [("C4", 2), ("D4", 2), ("E4", 4), ("E4", 2), ("D4", 2), ("C4", 4),
      ("C4", 2), ("D4", 2), ("E4", 2), ("D4", 2), ("C4", 4), ("r", 4)]),
    ("2-Hot-cross-buns.mid", "Hot cross buns", 66, 4,
     [("E4", 2), ("D4", 2), ("C4", 4), ("E4", 2), ("D4", 2), ("C4", 4),
      ("C4", 1), ("C4", 1), ("C4", 1), ("C4", 1), ("D4", 1), ("D4", 1), ("D4", 1), ("D4", 1),
      ("E4", 2), ("D4", 2), ("C4", 4)]),
    ("3-Au-clair-de-la-lune.mid", "Au clair de la lune (3 notes)", 66, 4,
     [("C4", 1), ("C4", 1), ("C4", 1), ("D4", 1), ("E4", 2), ("D4", 2),
      ("C4", 1), ("E4", 1), ("D4", 1), ("D4", 1), ("C4", 4)]),
    ("4-Mary-had-a-little-lamb.mid", "Mary had a little lamb (4 notes)", 66, 4,
     [("E4", 1), ("D4", 1), ("C4", 1), ("D4", 1), ("E4", 1), ("E4", 1), ("E4", 2),
      ("D4", 1), ("D4", 1), ("D4", 2), ("E4", 1), ("G4", 1), ("G4", 2),
      ("E4", 1), ("D4", 1), ("C4", 1), ("D4", 1), ("E4", 1), ("E4", 1), ("E4", 2),
      ("D4", 1), ("D4", 1), ("E4", 1), ("D4", 1), ("C4", 4)]),
    ("5-Frere-Jacques.mid", "Frère Jacques (the beginning)", 70, 4,
     [("C4", 1), ("D4", 1), ("E4", 1), ("C4", 1), ("C4", 1), ("D4", 1), ("E4", 1), ("C4", 1),
      ("E4", 1), ("F4", 1), ("G4", 2), ("E4", 1), ("F4", 1), ("G4", 2)]),
    ("6-Jingle-bells.mid", "Jingle bells (the beginning)", 72, 4,
     [("E4", 1), ("E4", 1), ("E4", 2), ("E4", 1), ("E4", 1), ("E4", 2),
      ("E4", 1), ("G4", 1), ("C4", 1), ("D4", 1), ("E4", 4)]),
    ("7-Ode-to-joy.mid", "Ode to Joy (the beginning)", 66, 4,
     [("E4", 1), ("E4", 1), ("F4", 1), ("G4", 1), ("G4", 1), ("F4", 1), ("E4", 1), ("D4", 1),
      ("C4", 1), ("C4", 1), ("D4", 1), ("E4", 1), ("E4", 2), ("D4", 2)]),
]
TPQ = 480                                              # ticks per quarter note
NAMES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# (file, title, bpm, beats per bar, right hand [(note|"r", beats)…], left hand per bar)
SONGS = [
    ("Five-fingers-up-and-down.mid", "Five fingers up and down", 80, 4,
     [("C4", 1), ("D4", 1), ("E4", 1), ("F4", 1), ("G4", 2), ("F4", 1), ("E4", 1),
      ("D4", 1), ("C4", 1), ("D4", 1), ("E4", 1), ("C4", 4)],
     ["C3", "G2", "G2", "C3"]),
    ("Au-clair-de-la-lune.mid", "Au clair de la lune", 90, 4,
     [("C4", 1), ("C4", 1), ("C4", 1), ("D4", 1), ("E4", 2), ("D4", 2),
      ("C4", 1), ("E4", 1), ("D4", 1), ("D4", 1), ("C4", 4)],
     ["C3", "G2", "G2", "C3"]),
    ("Mary-had-a-little-lamb.mid", "Mary had a little lamb", 90, 4,
     [("E4", 1), ("D4", 1), ("C4", 1), ("D4", 1), ("E4", 1), ("E4", 1), ("E4", 2),
      ("D4", 1), ("D4", 1), ("D4", 2), ("E4", 1), ("G4", 1), ("G4", 2),
      ("E4", 1), ("D4", 1), ("C4", 1), ("D4", 1), ("E4", 1), ("E4", 1), ("E4", 1), ("E4", 1),
      ("D4", 1), ("D4", 1), ("E4", 1), ("D4", 1), ("C4", 4)],
     ["C3", "C3", "G2", "C3", "C3", "C3", "G2", "C3"]),
    ("Ode-to-joy.mid", "Ode to Joy (Beethoven)", 84, 4,
     [("E4", 1), ("E4", 1), ("F4", 1), ("G4", 1), ("G4", 1), ("F4", 1), ("E4", 1), ("D4", 1),
      ("C4", 1), ("C4", 1), ("D4", 1), ("E4", 1), ("E4", 1.5), ("D4", 0.5), ("D4", 2),
      ("E4", 1), ("E4", 1), ("F4", 1), ("G4", 1), ("G4", 1), ("F4", 1), ("E4", 1), ("D4", 1),
      ("C4", 1), ("C4", 1), ("D4", 1), ("E4", 1), ("D4", 1.5), ("C4", 0.5), ("C4", 2)],
     ["C3", "G2", "C3", "G2", "C3", "G2", "C3", "C3"]),
    ("Frere-Jacques.mid", "Frère Jacques", 96, 4,
     [("C4", 1), ("D4", 1), ("E4", 1), ("C4", 1), ("C4", 1), ("D4", 1), ("E4", 1), ("C4", 1),
      ("E4", 1), ("F4", 1), ("G4", 2), ("E4", 1), ("F4", 1), ("G4", 2),
      ("G4", 0.5), ("A4", 0.5), ("G4", 0.5), ("F4", 0.5), ("E4", 1), ("C4", 1),
      ("G4", 0.5), ("A4", 0.5), ("G4", 0.5), ("F4", 0.5), ("E4", 1), ("C4", 1),
      ("C4", 1), ("G3", 1), ("C4", 2), ("C4", 1), ("G3", 1), ("C4", 2)],
     ["C3", "C3", "C3", "C3", "C3", "C3", "C3", "C3"]),
    ("Twinkle-twinkle-little-star.mid", "Twinkle twinkle little star (Ah vous dirai-je maman)", 90, 4,
     [("C4", 1), ("C4", 1), ("G4", 1), ("G4", 1), ("A4", 1), ("A4", 1), ("G4", 2),
      ("F4", 1), ("F4", 1), ("E4", 1), ("E4", 1), ("D4", 1), ("D4", 1), ("C4", 2),
      ("G4", 1), ("G4", 1), ("F4", 1), ("F4", 1), ("E4", 1), ("E4", 1), ("D4", 2),
      ("G4", 1), ("G4", 1), ("F4", 1), ("F4", 1), ("E4", 1), ("E4", 1), ("D4", 2),
      ("C4", 1), ("C4", 1), ("G4", 1), ("G4", 1), ("A4", 1), ("A4", 1), ("G4", 2),
      ("F4", 1), ("F4", 1), ("E4", 1), ("E4", 1), ("D4", 1), ("D4", 1), ("C4", 2)],
     ["C3", "C3", "G2", "C3", "C3", "G2", "C3", "G2", "C3", "C3", "G2", "C3"]),
    ("Jingle-bells.mid", "Jingle bells (chorus)", 100, 4,
     [("E4", 1), ("E4", 1), ("E4", 2), ("E4", 1), ("E4", 1), ("E4", 2),
      ("E4", 1), ("G4", 1), ("C4", 1.5), ("D4", 0.5), ("E4", 4),
      ("F4", 1), ("F4", 1), ("F4", 1.5), ("F4", 0.5), ("F4", 1), ("E4", 1), ("E4", 1), ("E4", 1),
      ("E4", 1), ("D4", 1), ("D4", 1), ("E4", 1), ("D4", 2), ("G4", 2)],
     ["C3", "C3", "C3", "C3", "F2", "C3", "G2", "G2"]),
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


def song_bytes(title, bpm, beats_per_bar, right, left):
    t0 = track([(0, meta_text(0x03, title)),
                (0, b"\xff\x51\x03" + (60_000_000 // bpm).to_bytes(3, "big")),
                (0, bytes((0xFF, 0x58, 4, beats_per_bar, 2, 24, 8)))])
    rh, tick = [(0, meta_text(0x03, "Right hand"))], 0
    for note, beats in right:
        dur = int(beats * TPQ)
        if note != "r":
            n = midi_note(note)
            rh += [(tick, bytes((0x90, n, 84))), (tick + dur - TPQ // 16, bytes((0x80, n, 0)))]
        tick += dur
    if left is None:                                  # 0-homer: the right hand alone
        return b"MThd" + struct.pack(">IHHH", 6, 1, 2, TPQ) + t0 + track(rh)
    lh = [(0, meta_text(0x03, "Left hand"))]
    bar = beats_per_bar * TPQ
    for i, note in enumerate(left):
        n = midi_note(note)
        lh += [(i * bar, bytes((0x91, n, 64))), ((i + 1) * bar - TPQ // 8, bytes((0x81, n, 0)))]
    return b"MThd" + struct.pack(">IHHH", 6, 1, 3, TPQ) + t0 + track(rh) + track(lh)


def main():
    levels = [("0-homer", [(*s, None) for s in HOMER]), ("1-first-steps", SONGS)]
    for folder, songs in levels:
        out = os.path.join(MIDI_DIR, folder)
        os.makedirs(out, exist_ok=True)
        for name, title, bpm, bpb, right, left in songs:
            bars = sum(b for _, b in right) / bpb
            assert bars == int(bars), f"{name}: the melody isn't whole bars ({bars})"
            assert left is None or len(left) == bars, f"{name}: {bars} melody bars, {len(left)} left-hand bars"
            with open(os.path.join(out, name), "wb") as f:
                f.write(song_bytes(title, bpm, bpb, right, left))
            print(f"{folder}/{name}: {int(bars)} bars @ {bpm} bpm")


if __name__ == "__main__":
    main()
