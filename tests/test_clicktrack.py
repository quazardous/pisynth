import struct

from pisynth.io.clicktrack import CH, DIVISION, click_midi


def _events(smf):
    """(delta, status, data1, data2) for channel events; meta events skipped."""
    assert smf[:4] == b"MThd"
    fmt, ntrk, div = struct.unpack(">HHH", smf[8:14])
    assert (fmt, ntrk, div) == (0, 1, DIVISION)
    assert smf[14:18] == b"MTrk"
    trk = smf[22:22 + struct.unpack(">I", smf[18:22])[0]]
    i, out = 0, []
    while i < len(trk):
        delta = 0
        while True:
            b = trk[i]; i += 1
            delta = (delta << 7) | (b & 0x7F)
            if not b & 0x80:
                break
        st = trk[i]
        if st == 0xFF:                               # meta: type, len, data
            ln = trk[i + 2]
            i += 3 + ln
            out.append((delta, "meta", None, None))
        else:
            out.append((delta, st, trk[i + 1], trk[i + 2]))
            i += 3
    return out


def test_bar_structure_accent_and_timing():
    ev = [e for e in _events(click_midi(120, 3, bars=2, vol=100)) if e[1] != "meta"]
    ons = [e for e in ev if e[1] == 0x90 | CH]
    offs = [e for e in ev if e[1] == 0x80 | CH]
    assert len(ons) == len(offs) == 6                # 2 bars × 3 beats
    vel = [e[3] for e in ons]
    assert vel == [120, 80, 80, 120, 80, 80]         # accent on beat 1 of each bar
    # every beat is exactly one quarter: note-off delta + next note-on delta = DIVISION
    assert all(off[0] + on[0] == DIVISION for off, on in zip(offs, ons[1:]))


def test_volume_scales_and_clamps():
    vel = [e[3] for e in _events(click_midi(100, 4, vol=50)) if e[1] == 0x90 | CH]
    assert vel == [60, 40, 40, 40]
    vel0 = [e[3] for e in _events(click_midi(100, 4, vol=0)) if e[1] == 0x90 | CH]
    assert min(vel0) >= 1                            # velocity 0 would be a note-off
