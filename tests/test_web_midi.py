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


# `aconnect -l` on the Pi right after the keyboard was unplugged and plugged back (#2410): the
# companion's aseqdump (pid 28607) lost its subscription, midi-bridge's (29252) was restarted.
ACONNECT_AFTER_REPLUG = """client 24: 'Keystation 61 MK3' [type=kernel,card=2]
    0 'Keystation 61 MK3(USB MIDI)'
	Connecting To: 130:0
    1 'Keystation 61 MK3(Transport)'
	Connecting To: 128:0
client 128: 'aseqdump' [type=user,pid=29252]
    0 'aseqdump        '
	Connected From: 24:1
client 129: 'aseqdump' [type=user,pid=28607]
    0 'aseqdump        '
client 130: 'FLUID Synth (29085)' [type=user,pid=29085]
    0 'Synth input port (29085:0)'
	Connected From: 0:1, 14:0, 24:0
"""


def test_subscription_check_spots_an_aseqdump_left_behind_by_a_replug():
    from web.midi_source import subscribed
    assert subscribed(ACONNECT_AFTER_REPLUG, 29252) is True
    assert subscribed(ACONNECT_AFTER_REPLUG, 28607) is False        # → restarted by the watchdog
    assert subscribed(ACONNECT_AFTER_REPLUG, 12345) is None         # not listed (yet): leave it
    assert subscribed("", 1) is None


def test_performance_model_follows_skill():
    import random
    from web.midi_source import performance
    notes = [(i * 250.0, i * 250.0 + 200, 60 + i % 12) for i in range(400)]
    pro = performance(notes, skill=1.0, rng=random.Random(1))
    ons = [e for e in pro if e[1] == 0x90]
    assert len(ons) >= 390                                        # hardly any misses
    errs = sorted(abs(e[0] - n[0]) for e, n in zip(ons, notes) if e[2] == n[2])
    assert errs[len(errs) // 2] < 36                              # mostly perfect timing
    novice = performance(notes, skill=0.0, rng=random.Random(1))
    assert len([e for e in novice if e[1] == 0x90]) < 380          # misses
    assert pro == sorted(pro, key=lambda e: (e[0], e[1] != 0x80))  # time-ordered, offs first
    assert all(e[0] >= 0 for e in novice)


def test_simulator_plays_a_song_then_resumes_its_patterns():
    import time as _t
    from web.midi_source import FRAME, SimSource
    got = []
    src = SimSource(lambda frame, t: got.append((_t.monotonic(), FRAME.unpack(frame))), speed=1, seed=3, skill=1.0)
    src.start()
    _t.sleep(0.05)
    t0 = _t.monotonic()
    src.play_song([(0, 80, 72), (150, 230, 74), (300, 380, 76)], in_ms=100)
    _t.sleep(0.8)
    src.stop()
    song_ons = [m for when, m in got if when >= t0 and m[0] == 0x90 and m[1] in (72, 74, 76)]
    assert [m[1] for m in song_ons] == [72, 74, 76]
    first_on = next(when for when, m in got if when >= t0 and m[0] == 0x90 and m[1] == 72)
    assert 0.06 < first_on - t0 < 0.2                             # ~100 ms later, within the skill-1 error
