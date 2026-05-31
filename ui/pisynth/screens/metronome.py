"""Metronome screens (#287/#655/#668), split out of the controller (#308).

Mixin for app.App: Start/Stop, classic tempo presets, BPM/beats/volume steppers, a
Home-pulse toggle, and a single Output picker (#668): "Piano (synth)" plays the click
through the piano fluidsynth (same speakers), or pick an audio device for a dedicated
metronome output. Cross-feature helpers (toast, _update_settings) resolve via the MRO.
"""
from ..ui.menu import Item, MenuScreen
from .devices import output_label, output_picker_items

# Classic Italian tempo markings → a representative BPM (#668, david). The BPM stepper
# stays for fine control; this is a quick "set a musical tempo" picker.
TEMPO_PRESETS = [("Largo", 50), ("Adagio", 66), ("Andante", 92), ("Moderato", 114),
                 ("Allegro", 138), ("Vivace", 166), ("Presto", 184)]

# Output device (#668) is one string: "" = via the piano synth; "card:<name>" / "bt:<mac>".
_PIANO_OUTPUT = "Piano (synth)"


def _dev_card(device):
    return device[5:] if device.startswith("card:") else ""


def _dev_bt(device):
    return device[3:] if device.startswith("bt:") else ""


class MetronomeMixin:
    # ---- metronome (#287/#655/#668) ----
    def _metronome_menu(self):
        return MenuScreen("Metronome", [
            Item("Start / Stop", on_select=self._metro_toggle,    # first — the primary action (david)
                 value=(lambda: "running" if self.metro.running else "stopped")),
            Item("Tempo", on_select=self._open_metro_tempo, submenu=True,    # 2nd, after Start/Stop (david)
                 value=self._metro_tempo_label),     # classic tempo presets → BPM
            Item("BPM", on_adjust=self._metro_bpm, value=(lambda: str(self.metro.bpm))),
            Item("Beats/bar", on_adjust=self._metro_beats, value=(lambda: str(self.metro.beats))),
            Item("Volume", on_adjust=self._metro_vol, value=(lambda: f"{self.metro.vol}%")),
            Item("Output", on_select=self._open_metro_output, submenu=True,   # device picker (#668)
                 value=self._metro_output_label),
            Item("Home pulse", on_select=self._metro_toggle_home_pulse,   # beat indicator on Home (#668)
                 value=(lambda: "on" if self.metro.home_pulse else "off")),
        ])

    def _save_metro(self):
        """Persist all metronome prefs together so writing one never drops another (#287)."""
        self._update_settings(metro={"bpm": self.metro.bpm, "beats": self.metro.beats,
                                     "vol": self.metro.vol, "device": self.metro.device,
                                     "home_pulse": self.metro.home_pulse})

    def _metro_bpm(self, delta):
        self.metro.bpm = max(40, min(240, self.metro.bpm + 5 * delta))
        self._save_metro()
        self.metro.reload()                          # regenerate the SMF at the new tempo (#655)

    # ---- classic tempo presets (#668) ----
    def _metro_tempo_label(self):
        """Tempo name if the current BPM matches a preset, else the BPM number."""
        return next((name for name, bpm in TEMPO_PRESETS if bpm == self.metro.bpm), str(self.metro.bpm))

    def _open_metro_tempo(self):
        items = [Item(f"{name}  ({bpm})", on_select=(lambda b=bpm: self._choose_metro_tempo(b)),
                      marker=(lambda b=bpm: self.metro.bpm == b)) for name, bpm in TEMPO_PRESETS]
        self.stack.append(MenuScreen("Tempo", items))

    def _choose_metro_tempo(self, bpm):
        self.metro.bpm = bpm
        self._save_metro()
        self.metro.reload()                          # picks up the new tempo (#655)
        self.toast(f"{self._metro_tempo_label()} = {bpm} BPM")

    def _metro_beats(self, delta):
        self.metro.beats = max(1, min(8, self.metro.beats + delta))
        self._save_metro()
        self.metro.reload()                          # regenerate the SMF (#655)

    def _metro_vol(self, delta):
        self.metro.set_volume(self.metro.vol + 5 * delta)   # live: regenerated at the new velocity (#655)
        self._save_metro()

    def _metro_toggle_home_pulse(self):
        self.metro.home_pulse = not self.metro.home_pulse
        self._save_metro()

    def _metro_toggle(self):
        if self.metro.running:
            self.metro.stop()
        else:
            self.metro.start()
            if not self.metro.running and self.metro.err:    # output failed to open (#655/#668)
                self.toast(self.metro.err, secs=4)

    # ---- metronome output (#668): the piano synth, or a dedicated device ----
    def _metro_output_label(self):
        """Friendly name of the metronome output: 'Piano (synth)' (device ""), an ALSA card,
        or a BT sink."""
        dev = self.metro.device
        if not dev:
            return _PIANO_OUTPUT
        return output_label(_dev_card(dev), _dev_bt(dev), self.bt_names, _PIANO_OUTPUT)

    def _open_metro_output(self):
        # "Piano (synth)" + ALSA cards + connected BT sinks (#668). Exactly one active.
        self.stack.append(MenuScreen("Metronome output", output_picker_items(
            _PIANO_OUTPUT,
            lambda: _dev_card(self.metro.device), lambda: _dev_bt(self.metro.device),
            lambda: self._choose_metro_output(""),
            lambda n: self._choose_metro_output(f"card:{n}"),
            self._choose_metro_bt)))

    def _choose_metro_output(self, device):
        was_running = self.metro.running
        self.metro.stop()                            # device change → stop; restart in the new path
        self.metro.device = device
        self._save_metro()
        if was_running:
            self.metro.start()
            if not self.metro.running and self.metro.err:
                self.toast(self.metro.err, secs=4)
                return
        self.toast("Output: " + self._metro_output_label())

    def _choose_metro_bt(self, mac, label=""):
        self._remember_bt_name(mac, label)
        self._choose_metro_output(f"bt:{mac}")
