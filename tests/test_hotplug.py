"""#2410 hot-plug: the presence edge detector, the /proc parsers, and the recovery actions."""
import pytest

from pisynth.core import audio as A
from pisynth.core.hotplug import PresenceWatch
from pisynth.screens import hotplug as H


# ---- PresenceWatch ----
def feed(w, *polls):
    return [w.update(p) for p in polls]


def test_initial_state_never_fires():
    assert feed(PresenceWatch(), {"Hub"}, {"Hub"}, {"Hub"}) == [set(), set(), set()]


def test_replug_fires_once_after_settling():
    w = PresenceWatch(settle=2)
    assert feed(w, {"Hub"}, set(), {"Hub"}, {"Hub"}, {"Hub"}) == [set(), set(), set(), {"Hub"}, set()]


def test_flapping_does_not_fire_until_stable():
    w = PresenceWatch(settle=2)
    assert feed(w, {"Hub"}, set(), {"Hub"}, set(), {"Hub"}, {"Hub"}) == [set(), set(), set(), set(), set(), {"Hub"}]


def test_require_seen_ignores_a_new_card_but_not_a_new_keyboard():
    cards = PresenceWatch(settle=1, require_seen=True)
    assert feed(cards, set(), {"Hub"}) == [set(), set()]           # appeared after boot, never seen
    kbds = PresenceWatch(settle=1, require_seen=False)
    assert feed(kbds, set(), {"Keystation"}) == [set(), {"Keystation"}]


def test_each_key_is_tracked_independently():
    w = PresenceWatch(settle=1, require_seen=False)
    assert feed(w, {"A"}, {"A", "B"}, {"B"}, {"A", "B"}) == [set(), {"B"}, set(), {"A"}]


# ---- /proc parsers ----
CARDS = """ 0 [Headphones     ]: bcm2835_headpho - bcm2835 Headphones
                      bcm2835 Headphones
 1 [Hub            ]: USB-Audio - M-Track Hub
                      M-AUDIO M-Track Hub at usb-3f980000.usb-1.1.2.4, full speed
 2 [MK3            ]: USB-Audio - Keystation 61 MK3
                      M-Audio Keystation 61 MK3 at usb-3f980000.usb-1.1.3, full speed
 3 [vc4hdmi        ]: vc4-hdmi - vc4-hdmi
"""

SEQ = '''Client   0 : "System" [Kernel]
  Port   0 : "Timer" (Rwe-) [In/Out]
Client  14 : "Midi Through" [Kernel Legacy]
Client  24 : "Keystation 61 MK3" [Kernel Legacy]
  Port   0 : "Keystation 61 MK3(USB MIDI)" (RWeX) [In/Out]
Client 128 : "aseqdump" [User Legacy]
Client 129 : "FLUID Synth (6967)" [User Legacy]
'''


@pytest.fixture
def fake_proc(monkeypatch):
    files = {"/proc/asound/cards": CARDS, "/proc/asound/seq/clients": SEQ}
    real_open = open

    def fake_open(path, *a, **k):
        if path in files:
            import io
            return io.StringIO(files[path])
        return real_open(path, *a, **k)

    monkeypatch.setattr(A, "open", fake_open, raising=False)
    playback = {"/proc/asound/card0/pcm*p", "/proc/asound/card1/pcm*p", "/proc/asound/card3/pcm*p"}
    monkeypatch.setattr(A.glob, "glob", lambda pat: [pat] if pat in playback else [])
    return files


def test_synth_card_candidates_auto_picks_usb_playback_only(fake_proc):
    assert A.synth_card_candidates("") == {"Hub"}              # not Headphones, not MIDI-only MK3, not HDMI
    assert A.synth_card_candidates("Headphones") == {"Headphones"}
    assert A.synth_card_candidates("Gone") == set()


def test_midi_hw_clients_keeps_kernel_keyboards(fake_proc):
    assert A.midi_hw_clients() == {"Keystation 61 MK3"}


# ---- recovery actions (HotplugMixin on a fake host) ----
class Host(H.HotplugMixin):
    def __init__(self, soundcard="", bt_sink="", midi_keyboard=""):
        self.soundcard, self.bt_sink, self.midi_keyboard = soundcard, bt_sink, midi_keyboard
        self.calls, self._restart_pending = [], 0.0
        self._hotplug_init()

    def _restart_audio(self):
        self.calls.append("restart-piano")
        return True

    def toast(self, msg, secs=3.0):
        self.calls.append("toast")

    def _nav_on_keyboard_back(self):
        self.calls.append("nav-rebind")


@pytest.fixture
def world(monkeypatch):
    state = {"cards": {"Hub"}, "midi": {"Keystation 61 MK3"}, "active": True, "routes": [], "bridge": []}
    monkeypatch.setattr(H, "synth_card_candidates", lambda sc: set(state["cards"]))
    monkeypatch.setattr(H, "midi_hw_clients", lambda: set(state["midi"]))
    monkeypatch.setattr(H, "audio_active", lambda: state["active"])
    monkeypatch.setattr(H, "midi_route_to_fluid", lambda p, connect: state["routes"].append((p, connect)))

    class R:
        def __init__(self, rc):
            self.returncode = rc

    def fake_run(argv, **k):
        state["bridge"].append(argv[1])
        return R(0)
    monkeypatch.setattr(H.subprocess, "run", fake_run)
    return state


def poll(host, n=1):
    for _ in range(n):
        host._hotplug_poll()


def test_card_replug_restarts_the_synth_once(world):
    h = Host()
    poll(h)
    world["cards"] = set(); poll(h)
    world["cards"] = {"Hub"}; poll(h, 3)
    assert h.calls.count("restart-piano") == 1 and h._restart_pending > 0


def test_card_back_while_synth_not_running_does_nothing(world):
    h = Host()
    poll(h)
    world["cards"], world["active"] = set(), False; poll(h)
    world["cards"] = {"Hub"}; poll(h, 2)
    assert "restart-piano" not in h.calls


def test_bluetooth_output_skips_card_watch(world):
    h = Host(bt_sink="AA:BB")
    poll(h)
    world["cards"] = set(); poll(h)
    world["cards"] = {"Hub"}; poll(h, 2)
    assert "restart-piano" not in h.calls


def test_keyboard_replug_rewires_nav_chosen_keyboard_and_bridge(world):
    h = Host(midi_keyboard="Keystation 61 MK3")
    poll(h)
    world["midi"] = set(); poll(h)
    world["midi"] = {"Keystation 61 MK3"}; poll(h, 2)
    assert h.calls.count("nav-rebind") == 1
    assert world["routes"] == [("Keystation 61 MK3", True)]
    assert world["bridge"] == ["is-active", "restart"]


def test_auto_mode_does_not_force_a_route(world):
    h = Host()
    poll(h)
    world["midi"] = set(); poll(h)
    world["midi"] = {"Keystation 61 MK3"}; poll(h, 2)
    assert world["routes"] == [] and h.calls.count("nav-rebind") == 1
