"""Metronome click track as a Standard MIDI File (#655).

For the 'fused' metronome — the click played BY the existing fluidsynth (so it comes
out the same card as the piano, which holds it exclusively, see #648) — we feed it MIDI
rather than a separate audio stream. `click_midi()` renders ONE bar of clicks as a
format-0 SMF on a dedicated channel: an accent note on beat 1, a normal note on the
others, spaced one quarter apart, the bar exactly `beats` quarters long so it loops
seamlessly. The bytes are mechanism-independent — they can be played by fluidsynth's
own MIDI player or by `aplaymidi` through the ALSA sequencer (the timing then comes
from that clock, not a Python loop → steady tempo, like the PCM stream of #648).
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


def click_midi(bpm, beats, *, accent_note=ACCENT_NOTE, normal_note=NORMAL_NOTE,
               vel_accent=120, vel_normal=80, gate=0.25):
    """One bar of metronome clicks as a format-0 SMF (bytes), channel 9 (#655).
    accent on beat 1, normal on the rest; the bar is exactly `beats` quarters so it loops.
    `gate` = note length as a fraction of the beat (percussive, so it barely matters)."""
    bpm = max(1, min(300, int(bpm)))
    beats = max(1, min(8, int(beats)))
    beat_ticks = DIVISION
    dur = max(1, int(beat_ticks * gate))
    tempo = 60_000_000 // bpm                         # microseconds per quarter

    trk = bytearray()
    trk += _varlen(0) + bytes([0xFF, 0x51, 0x03]) + struct.pack(">I", tempo)[1:]  # set tempo
    pending = 0                                       # delta ticks owed before the next event
    for i in range(beats):
        note = accent_note if i == 0 else normal_note
        vel = vel_accent if i == 0 else vel_normal
        trk += _varlen(pending) + bytes([0x90 | CH, note, vel])    # note on
        trk += _varlen(dur) + bytes([0x80 | CH, note, 0])          # note off
        pending = beat_ticks - dur                    # rest until the next beat
    trk += _varlen(pending) + bytes([0xFF, 0x2F, 0x00])            # end of track (pads to bar end)

    head = b"MThd" + struct.pack(">IHHH", 6, 0, 1, DIVISION)
    return head + b"MTrk" + struct.pack(">I", len(trk)) + bytes(trk)
