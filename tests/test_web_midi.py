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


def test_simulator_script_is_balanced_and_valid():
    from web.midi_source import SimSource
    steps = SimSource(lambda *a: None, seed=1).steps()
    events = [(s, d1, d2) for _, s, d1, d2 in steps if s is not None]
    ons = [d1 for s, d1, d2 in events if s == 0x90]
    offs = [d1 for s, d1, _ in events if s == 0x80]
    assert sorted(ons) == sorted(offs) and ons                         # every note released
    assert all(60 <= d2 <= 110 for s, _, d2 in events if s == 0x90)
    assert (0xB0, 64, 127) in events and (0xB0, 64, 0) in events       # sustain pedal down/up


def test_simulator_feeds_frames_until_stopped():
    import time as _t
    from web.midi_source import FRAME, SimSource
    got = []
    src = SimSource(lambda frame, t: got.append(FRAME.unpack(frame)), speed=20, seed=2)
    src.start()
    _t.sleep(0.4)
    src.stop()
    assert got and got[0][:2] == (0x90, 60)


def test_make_source_selects_by_env():
    from web.midi_source import AlsaSeqSource, CommandSource, SimSource, make_source, pi_bridge_argv
    assert isinstance(make_source(None, {}), AlsaSeqSource)
    assert isinstance(make_source(None, {"PISYNTH_WEB_MIDI_SOURCE": "sim"}), SimSource)
    src = make_source(None, {"PISYNTH_WEB_MIDI_SOURCE": "pi", "PISYNTH_HOST": "david@pi"})
    assert isinstance(src, CommandSource) and src.argv[:1] == ["ssh"] and "david@pi" in src.argv
    assert "aseqdump" in pi_bridge_argv("h")[-1]
