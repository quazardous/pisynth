"""web/midi_source.py — aseqdump lines → raw MIDI bytes → 7-byte frames (#659)."""
from web.midi_source import FRAME, pack, parse_line


def test_parses_real_aseqdump_lines():
    assert parse_line(" 24:0   Note on                 0, note 60, velocity 100") == (0x90, 60, 100)
    assert parse_line(" 24:0   Note off                2, note 61, velocity 0") == (0x82, 61, 0)
    assert parse_line(" 24:0   Note on                 0, note 62, velocity 0") == (0x90, 62, 0)
    assert parse_line(" 24:0   Control change          0, controller 64, value 127") == (0xB0, 64, 127)


def test_ignores_everything_else():
    for line in ("Waiting for data. Press Ctrl+C to end.", "Source  Event                  Ch  Data",
                 " 24:0   Pitch bend              0, value 12", " 24:0   Active Sensing", ""):
        assert parse_line(line) is None


def test_frame_layout_is_7_bytes_big_endian_and_wraps_time():
    f = pack(0x90, 60, 100, 0x1_0000_0005)
    assert len(f) == 7 and FRAME.unpack(f) == (0x90, 60, 100, 5)
    assert f[:3] == bytes((0x90, 60, 100))
