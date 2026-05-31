"""Metronome click track as a Standard MIDI File (#655).

For the 'fused' metronome — the click played BY the existing fluidsynth (so it comes
out the same card as the piano, which holds it exclusively, see #648) — we feed it MIDI
rather than a separate audio stream. `click_midi()` renders N bars of clicks as a
format-0 SMF on channel 9: an accent note on beat 1 of each bar, a normal note on the
others, spaced one quarter apart, each bar exactly `beats` quarters. The chosen player
is `aplaymidi` (in alsa-utils, confirmed on the Pi) sending to FLUID Synth's ALSA-seq
port — the timing then comes from the ALSA-seq queue, not a Python loop → steady tempo,
like the PCM stream of #648. (FluidSynth 2.4's internal player can't load a file at
runtime, so it can't follow a beats/pattern change — hence aplaymidi.) aplaymidi doesn't
loop, so `click_midi_file()` renders many bars and a watcher relaunches if it ends.
"""
import struct

DIVISION = 480                  # ticks per quarter note
CH = 9                          # GM drum channel (0-indexed) — out of the keyboard's way (#655)
ACCENT_NOTE = 76                # GM High Wood Block
NORMAL_NOTE = 77                # GM Low Wood Block


def _varlen(n):
    """MIDI variable-length quantity."""
    out = bytearray([n & 0x7F])
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def click_midi(bpm, beats, *, bars=1, vol=80, accent_note=ACCENT_NOTE,
               normal_note=NORMAL_NOTE, gate=0.25):
    """`bars` bars of metronome clicks as a format-0 SMF (bytes), channel 9 (#655).
    accent on beat 1 of each bar, normal on the rest; one beat = one quarter, so a bar is
    exactly `beats` quarters (loops seamlessly). `vol` (0-100) scales the note velocity.
    `gate` = note length as a fraction of the beat (percussive, so it barely matters).
    For `aplaymidi` (which doesn't loop), pass a large `bars` so one run lasts a long time."""
    bpm = max(1, min(300, int(bpm)))
    beats = max(1, min(8, int(beats)))
    bars = max(1, int(bars))
    vol = max(0, min(100, int(vol)))
    vel_accent = max(1, int(120 * vol / 100))
    vel_normal = max(1, int(80 * vol / 100))
    beat_ticks = DIVISION
    dur = max(1, int(beat_ticks * gate))
    tempo = 60_000_000 // bpm                         # microseconds per quarter

    trk = bytearray()
    trk += _varlen(0) + bytes([0xFF, 0x51, 0x03]) + struct.pack(">I", tempo)[1:]  # set tempo
    pending = 0                                       # delta ticks owed before the next event
    for _b in range(bars):
        for i in range(beats):
            accent = (i == 0)
            note = accent_note if accent else normal_note
            vel = vel_accent if accent else vel_normal
            trk += _varlen(pending) + bytes([0x90 | CH, note, vel])    # note on
            trk += _varlen(dur) + bytes([0x80 | CH, note, 0])          # note off
            pending = beat_ticks - dur                # rest until the next beat
    trk += _varlen(pending) + bytes([0xFF, 0x2F, 0x00])               # end of track (pads to last bar end)

    head = b"MThd" + struct.pack(">IHHH", 6, 0, 1, DIVISION)
    return head + b"MTrk" + struct.pack(">I", len(trk)) + bytes(trk)


def click_midi_file(path, bpm, beats, *, vol=80, minutes=60):
    """Write a click SMF to `path` long enough to run ~`minutes` at `bpm` (#655). aplaymidi
    doesn't loop, so we render many bars; a watcher relaunches if it ever ends."""
    bars = max(1, int(minutes * bpm / max(1, min(8, int(beats)))))   # bpm beats/min ÷ beats/bar
    with open(path, "wb") as f:
        f.write(click_midi(bpm, beats, bars=bars, vol=vol))
    return path
