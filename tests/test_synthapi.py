"""Synth settings API (#2417): state/catalog, set paths, fx persistence + shell commands, watch."""
import json
import socket

import pytest

from pisynth.screens import synthapi as S


def test_fx_defaults_merge_and_clamp():
    fx = S.fx_from_settings({"reverb": {"room": 5, "on": False, "bogus": 1}, "chorus": {"nr": "x", "depth": -3}})
    assert fx["reverb"] == {"on": False, "room": 1.0, "damp": 0.0, "width": 0.5, "level": 0.9}
    assert fx["chorus"]["nr"] == 3 and fx["chorus"]["depth"] == 0.0
    assert S.fx_from_settings(None) == S.FX_DEFAULTS


def test_fx_commands_use_fluidsynth_shell_names():
    cmds = S.fx_commands(S.FX_DEFAULTS)
    assert cmds[:4] == ["rev_setroomsize 0.2", "rev_setdamp 0.0", "rev_setwidth 0.5", "rev_setlevel 0.9"]
    assert "reverb on" in cmds and "chorus off" in cmds and "cho_set_nr 3" in cmds


class FS:
    online = True

    def __init__(self):
        self.sent, self.gains = [], []

    def connect(self):
        return True

    def send(self, *cmds):
        self.sent += cmds

    def set_gain(self, g):
        self.gains.append(g)


class Metro:
    running, bpm, beats, vol = False, 100, 4, 80

    def __init__(self):
        self.reloads = 0

    def set_volume(self, v):
        self.vol = max(0, min(100, v))

    def reload(self):
        self.reloads += 1


class Host(S.SynthApiMixin):
    def __init__(self, tmp_path):
        self.fs, self.metro = FS(), Metro()
        a = tmp_path / "01-A.sf2"
        self.fonts = [(None, str(a))]
        self.cur_font_path, self.cur_bp, self.cur_preset_name = str(a), (0, 0), "Piano"
        self.gain, self.volume, self.soundcard, self.bt_sink, self.midi_keyboard = 2.5, 70, "", "", ""
        self._online, self._loading, self._restart_pending = True, False, 0.0
        self.saved, self.chosen, self.toggles, self.renders, self.restarts = {}, [], 0, 0, 0
        self._synthapi_init({"fx": {"chorus": {"on": True}}})

    def _audio_label(self):
        return "Auto"

    def _update_settings(self, **kw):
        self.saved.update(kw)

    def _update_bt_pref(self, **kw):
        self.saved.setdefault("bluetooth", {}).update(kw)

    def _choose_preset(self, path, bank, prog, name=""):
        self.chosen.append((path.rsplit("/", 1)[-1], bank, prog, name))

    def _default_preset(self, sfid, path):
        return (0, 4, "Rhodes")

    def _set_gain(self, g):
        self.gain = round(min(4.0, max(0.0, g)), 2)

    def _save_metro(self):
        self.saved["metro"] = (self.metro.bpm, self.metro.beats, self.metro.vol)

    def _metro_toggle(self):
        self.toggles += 1
        self.metro.running = not self.metro.running

    def _read_volume(self):
        return self.volume

    def _active_card(self):
        return "Hub"

    def _restart_audio(self):
        self.restarts += 1
        return True

    def toast(self, *a, **k):
        pass

    def render(self):
        self.renders += 1


@pytest.fixture
def host(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "read_sf_presets", lambda p: [(0, 0, "Piano"), (0, 4, "Rhodes")])
    monkeypatch.setattr(S, "list_soundfont_files", lambda: [str(tmp_path / "01-A.sf2")])
    (tmp_path / "01-A.sf2").write_bytes(b"x")
    monkeypatch.setattr(S, "list_audio_cards", lambda: [("Hub", "M-Track Hub")])
    monkeypatch.setattr(S, "list_bt_sinks", lambda: [("AA:BB", "XM4")])
    monkeypatch.setattr(S, "list_midi_inputs", lambda: [("Keystation 61 MK3", "Keystation 61 MK3")])
    monkeypatch.setattr(S, "audio_active", lambda: True)
    return Host(tmp_path)


def test_get_returns_state_and_catalog(host):
    r = host.dispatch_json({"op": "get"})
    assert r["ok"] and r["state"]["font"] == "01-A.sf2" and r["state"]["fx"]["chorus"]["on"] is True
    cat = r["catalog"]
    assert cat["fonts"] == [{"file": "01-A.sf2", "label": "A", "presets": [[0, 0, "Piano"], [0, 4, "Rhodes"]]}]
    assert {"kind": "bt", "id": "AA:BB", "label": "XM4"} in cat["outputs"]
    assert cat["ranges"]["fx"]["reverb"]["width"] == [0.0, 100.0]


def test_set_preset_font_gain(host):
    assert host.dispatch_json({"op": "set", "key": "preset", "value": {"font": "01-A.sf2", "bank": 0, "prog": 4}})["ok"]
    assert host.chosen[-1] == ("01-A.sf2", 0, 4, "Rhodes")
    assert host.dispatch_json({"op": "set", "key": "preset", "value": {"font": "01-A.sf2", "bank": 9, "prog": 9}})["error"] == "unknown preset"
    assert host.dispatch_json({"op": "set", "key": "font", "value": "nope.sf2"})["error"] == "unknown soundfont"
    assert host.dispatch_json({"op": "set", "key": "font", "value": "01-A.sf2"})["ok"] and host.chosen[-1][2] == 4
    r = host.dispatch_json({"op": "set", "key": "gain", "value": 9})
    assert r["ok"] and host.gain == 4.0 and host.saved["gain"] == 4.0 and host.renders


def test_set_fx_persists_clamps_and_applies_only_that_unit(host):
    r = host.dispatch_json({"op": "set", "key": "fx.reverb", "value": {"room": 0.8, "on": False}})
    assert r["ok"] and host.saved["fx"]["reverb"]["room"] == 0.8
    assert "rev_setroomsize 0.8" in host.fs.sent and "reverb off" in host.fs.sent
    assert not any(c.startswith("cho_") for c in host.fs.sent)
    assert host.dispatch_json({"op": "set", "key": "fx.chorus", "value": {"nr": "lots"}})["error"] == "bad chorus nr"


def test_set_metronome_output_and_keyboard(host):
    assert host.dispatch_json({"op": "set", "key": "metronome", "value": {"bpm": 300, "running": True}})["ok"]
    assert host.metro.bpm == 240 and host.metro.reloads == 1 and host.toggles == 1
    assert host.dispatch_json({"op": "set", "key": "output", "value": {"kind": "bt", "id": "AA:BB"}})["ok"]
    assert host.bt_sink == "AA:BB" and host.soundcard == "" and host.restarts == 1
    assert host.dispatch_json({"op": "set", "key": "output", "value": {"kind": "card", "id": "Nope"}})["error"]
    assert host.dispatch_json({"op": "set", "key": "midi_keyboard", "value": "Ghost"})["error"] == "unknown MIDI keyboard"
    assert host.dispatch_json({"op": "set", "key": "midi_keyboard", "value": "Keystation 61 MK3"})["ok"]
    assert host.dispatch_json({"op": "set", "key": "wat", "value": 1})["error"] == "unknown setting: wat"
    assert host.dispatch_json({"op": "set", "key": "preset", "value": "notadict"})["ok"] is False


def test_came_online_reapplies_gain_and_fx(host):
    host._synth_came_online()
    assert host.fs.gains == [2.5] and "chorus on" in host.fs.sent


def test_watch_pushes_only_on_change_and_drops_dead_watchers(host):
    a, b = socket.socketpair()
    host.add_watcher(a)
    first = json.loads(b.recv(65536).decode().splitlines()[0])
    assert first["state"]["gain"] == 2.5
    host.push_state_if_changed()                      # records baseline (same as sent) → pushes once
    b.setblocking(False)
    try:
        b.recv(65536)
    except BlockingIOError:
        pass
    host.push_state_if_changed()
    with pytest.raises(BlockingIOError):
        b.recv(65536)                                 # unchanged: nothing sent
    host.gain = 3.0
    host.push_state_if_changed()
    assert json.loads(b.recv(65536).decode().splitlines()[0])["state"]["gain"] == 3.0
    b.close()
    host.gain = 1.0
    for _ in range(3):                                # the send to a closed peer eventually fails
        host.push_state_if_changed()
        host.gain += 0.1
    assert host._watchers == []


def test_an_fx_change_is_seen_as_a_state_change(host):
    before = host.synth_state()
    host.api_set("fx.reverb", {"room": 0.6})
    assert host.synth_state() != before                 # fx is mutated in place: state must copy it
