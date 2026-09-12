"""Synth settings API (#2417): everything the web companion may read or change, as JSON.

Mixin for app.App. The touch UI stays the single owner of the synth state: the phone's
changes (relayed by pisynth-web over the local control socket, JSON lines) run the SAME code
paths as the touch screen — the one-soundfont loader, persistence in settings.yaml, the
audio-restart for an output change — so the box screen, the saved settings and the sound
never drift apart. A `watch` connection streams the state whenever it changes, whoever
changed it.

Also makes the effects real settings: reverb and chorus (hardcoded on/off in start-piano.sh
before) are persisted and re-applied whenever the synth comes up, and gain is persisted.
"""
import os
import time

from ..core.audio import GAIN_MAX, GAIN_MIN, audio_active, list_audio_cards, list_bt_sinks, list_midi_inputs
from ..core.soundfonts import font_label, list_soundfont_files, read_sf_presets, sf_key

# fluidsynth defaults (synth.reverb.* / synth.chorus.*); on/off as start-piano.sh used to hardcode.
FX_DEFAULTS = {
    "reverb": {"on": True, "room": 0.2, "damp": 0.0, "width": 0.5, "level": 0.9},
    "chorus": {"on": False, "nr": 3, "level": 2.0, "speed": 0.3, "depth": 8.0},
}
# key → (min, max, type)
FX_RANGES = {
    "reverb": {"room": (0.0, 1.0, float), "damp": (0.0, 1.0, float), "width": (0.0, 100.0, float),
               "level": (0.0, 1.0, float)},
    "chorus": {"nr": (0, 99, int), "level": (0.0, 10.0, float), "speed": (0.1, 5.0, float),
               "depth": (0.0, 256.0, float)},
}
_FX_CMDS = {
    "reverb": {"room": "rev_setroomsize", "damp": "rev_setdamp", "width": "rev_setwidth", "level": "rev_setlevel"},
    "chorus": {"nr": "cho_set_nr", "level": "cho_set_level", "speed": "cho_set_speed", "depth": "cho_set_depth"},
}


def fx_from_settings(saved):
    """Merge persisted fx over the defaults, clamped — a hand-edited or old settings.yaml
    can never push an out-of-range value to the synth."""
    fx = {}
    for unit, defaults in FX_DEFAULTS.items():
        cur = dict(defaults)
        for k, v in ((saved or {}).get(unit) or {}).items():
            ok, val = _coerce_fx(unit, k, v)
            if ok:
                cur[k] = val
        fx[unit] = cur
    return fx


def _coerce_fx(unit, key, value):
    if key == "on":
        return isinstance(value, bool), bool(value)
    rng = FX_RANGES.get(unit, {}).get(key)
    if rng is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return False, None
    lo, hi, typ = rng
    return True, typ(min(hi, max(lo, value)))


def fx_commands(fx, units=("reverb", "chorus")):
    """fluidsynth shell commands that put the synth in the given fx state."""
    cmds = []
    for unit in units:
        cfg = fx[unit]
        for key, cmd in _FX_CMDS[unit].items():
            cmds.append(f"{cmd} {cfg[key]}")
        cmds.append(f"{unit} {'on' if cfg['on'] else 'off'}")
    return cmds


class SynthApiMixin:
    def _synthapi_init(self, settings):
        self.fx = fx_from_settings(settings.get("fx"))
        self._watchers = []                           # sockets streaming state (`watch`)
        self._last_pushed = None
        self._catalog_cache = (None, None)            # (files signature, catalog)
        self._gain_save_at = 0.0

    # ---- applying to the synth ----
    def _apply_fx(self, units=("reverb", "chorus")):
        if self.fs.online or self.fs.connect():
            self.fs.send(*fx_commands(self.fx, units))

    def _synth_came_online(self):
        """Called on every (re)connection to the synth: it lost our live settings."""
        self._apply_fx()
        self.fs.set_gain(self.gain)

    # ---- state + catalog ----
    def synth_state(self):
        return {
            "online": bool(self._online), "loading": bool(self._loading),
            "font": sf_key(self.cur_font_path), "bank": self.cur_bp[0] if self.cur_bp else None,
            "prog": self.cur_bp[1] if self.cur_bp else None, "preset_name": self.cur_preset_name,
            "gain": self.gain, "volume": self.volume,
            "output": {"soundcard": self.soundcard, "bt_sink": self.bt_sink, "label": self._audio_label()},
            "fx": {unit: dict(cfg) for unit, cfg in self.fx.items()},   # a copy: fx is mutated in place
            "metronome": {"running": self.metro.running, "bpm": self.metro.bpm, "beats": self.metro.beats,
                          "vol": self.metro.vol},
            "midi_keyboard": self.midi_keyboard,
        }

    def synth_catalog(self):
        files = list_soundfont_files()
        sig = tuple((f, os.path.getmtime(f)) for f in files if os.path.exists(f))
        if self._catalog_cache[0] != sig:
            fonts = [{"file": sf_key(f), "label": font_label(f),
                      "presets": [[b, p, n] for b, p, n in read_sf_presets(f)]} for f in files]
            self._catalog_cache = (sig, fonts)
        return {
            "fonts": self._catalog_cache[1],
            "outputs": [{"kind": "card", "id": n, "label": lb} for n, lb in list_audio_cards()]
                       + [{"kind": "bt", "id": mac, "label": lb} for mac, lb in list_bt_sinks()],
            "midi_inputs": [n for n, _ in list_midi_inputs()],
            "ranges": {"gain": [GAIN_MIN, GAIN_MAX], "volume": [0, 100], "bpm": [40, 240], "beats": [1, 8],
                       "metro_vol": [0, 100], "fx": {u: {k: [lo, hi] for k, (lo, hi, _) in r.items()}
                                                      for u, r in FX_RANGES.items()}},
        }

    # ---- JSON API ----
    def dispatch_json(self, msg):
        if not isinstance(msg, dict):
            return {"ok": False, "error": "bad request"}
        op = msg.get("op")
        if op == "get":
            self.volume = self._read_volume()         # the live output level, only when asked
            return {"ok": True, "state": self.synth_state(), "catalog": self.synth_catalog()}
        if op == "set":
            try:
                err = self.api_set(msg.get("key"), msg.get("value"))
            except (TypeError, ValueError, KeyError) as e:
                err = f"bad value: {e}"
            self.render()
            return {"ok": err is None, **({"error": err} if err else {}), "state": self.synth_state()}
        return {"ok": False, "error": f"unknown op: {op}"}

    def api_set(self, key, value):
        """Apply one change like the touch screen would. Returns None, or an error string."""
        if key == "preset":
            return self._api_preset(value["font"], int(value["bank"]), int(value["prog"]))
        if key == "font":
            path = self._font_path(value)
            if not path:
                return "unknown soundfont"
            d = self._default_preset(None, path)
            if not d:
                return "soundfont has no presets"
            self._choose_preset(path, d[0], d[1], d[2])
            return None
        if key == "gain":
            self._set_gain(float(value))
            self._update_settings(gain=self.gain)
            return None
        if key == "volume":
            return self._api_volume(int(value))
        if key in ("fx.reverb", "fx.chorus"):
            unit = key.split(".", 1)[1]
            if not isinstance(value, dict):
                return "expected an object"
            for k, v in value.items():
                ok, val = _coerce_fx(unit, k, v)
                if not ok:
                    return f"bad {unit} {k}"
                self.fx[unit][k] = val
            self._update_settings(fx=self.fx)
            self._apply_fx((unit,))
            return None
        if key == "metronome":
            return self._api_metronome(value)
        if key == "midi_keyboard":
            names = [n for n, _ in list_midi_inputs()]
            if value not in ("", *names):
                return "unknown MIDI keyboard"
            self.midi_keyboard = value
            self._update_settings(midi_keyboard=value)
            return self._api_restart_if_running()
        if key == "output":
            return self._api_output(value)
        return f"unknown setting: {key}"

    def _font_path(self, basename):
        for _, path in self.fonts:
            if sf_key(path) == basename:
                return path
        return None

    def _api_preset(self, font, bank, prog):
        path = self._font_path(font)
        if not path:
            return "unknown soundfont"
        match = [n for b, p, n in read_sf_presets(path) if (b, p) == (bank, prog)]
        if not match:
            return "unknown preset"
        self._choose_preset(path, bank, prog, match[0])
        return None

    def _api_volume(self, pct):
        from ..core.audio import set_alsa_volume, set_bt_volume
        pct = max(0, min(100, pct))
        if self.bt_sink:
            ok = set_bt_volume(self.bt_sink, pct)
        else:
            card = self._active_card()
            ok = set_alsa_volume(card, pct) if card else False
        if not ok:
            return "this output has no volume control"
        self.volume = pct
        return None

    def _api_metronome(self, value):
        if not isinstance(value, dict):
            return "expected an object"
        m, reload = self.metro, False
        if "bpm" in value:
            m.bpm, reload = max(40, min(240, int(value["bpm"]))), True
        if "beats" in value:
            m.beats, reload = max(1, min(8, int(value["beats"]))), True
        if "vol" in value:
            m.set_volume(int(value["vol"]))
        self._save_metro()
        if reload:
            m.reload()
        if "running" in value and bool(value["running"]) != m.running:
            self._metro_toggle()
        return None

    def _api_output(self, value):
        """The phone already asked the user to confirm (it restarts the audio)."""
        if not isinstance(value, dict):
            return "expected an object"
        if value.get("kind") == "bt":
            if value.get("id") not in [mac for mac, _ in list_bt_sinks()]:
                return "Bluetooth device not connected"
            self.bt_sink, self.soundcard = value["id"], ""
            self._update_bt_pref(audio_sink=self.bt_sink)
            self._update_settings(soundcard="")
        else:
            card = value.get("id", "") if value.get("kind") == "card" else ""
            if card and card not in [n for n, _ in list_audio_cards()]:
                return "unknown sound card"
            self.soundcard, self.bt_sink = card, ""
            self._update_settings(soundcard=card)
            self._update_bt_pref(audio_sink="")
        return self._api_restart_if_running()

    def _api_restart_if_running(self):
        if audio_active() and self._restart_audio():
            self._restart_pending = time.monotonic()
            self.toast("Restarting audio…", secs=30)
        return None

    # ---- watch stream ----
    def add_watcher(self, conn):
        conn.setblocking(False)
        self._watchers.append(conn)
        self._send_state(conn, self.synth_state())

    def push_state_if_changed(self):
        if not self._watchers:
            return
        state = self.synth_state()
        if state == self._last_pushed:
            return
        self._last_pushed = state
        for conn in list(self._watchers):
            self._send_state(conn, state)

    def _send_state(self, conn, state):
        import json
        try:
            conn.sendall((json.dumps({"state": state}) + "\n").encode())
        except OSError:                               # watcher gone (pisynth-web restarted)
            self._watchers.remove(conn)
            try:
                conn.close()
            except OSError:
                pass
