"""Metronome screens (#287), split out of the controller (#308).

Mixin for app.App: BPM/beats steppers + the output picker (ALSA cards or a BT sink,
routed through the injected `metro.play_fn`). Cross-feature helpers (toast,
_update_settings) resolve via the MRO.
"""
from ..ui.menu import Item, MenuScreen
from .devices import output_label, output_picker_items


class MetronomeMixin:
    # ---- metronome (#287) ----
    def _metronome_menu(self):
        return MenuScreen("Metronome", [
            Item("BPM", on_adjust=self._metro_bpm, value=(lambda: str(self.metro.bpm))),
            Item("Beats/bar", on_adjust=self._metro_beats, value=(lambda: str(self.metro.beats))),
            Item("Output", on_select=self._open_metro_audio, submenu=True,
                 value=self._metro_card_label),
            Item("Start / Stop", on_select=self._metro_toggle,
                 value=(lambda: "running" if self.metro.running else "stopped")),
        ])

    def _save_metro(self):
        """Persist all metronome prefs together so writing one never drops another (#287)."""
        self._update_settings(metro={"bpm": self.metro.bpm, "beats": self.metro.beats,
                                     "card": self.metro.card, "bt_sink": self.metro.bt_sink})

    def _metro_bpm(self, delta):
        self.metro.bpm = max(40, min(240, self.metro.bpm + 5 * delta))
        self._save_metro()

    def _metro_beats(self, delta):
        self.metro.beats = max(1, min(8, self.metro.beats + delta))
        self._save_metro()

    def _metro_toggle(self):
        self.metro.stop() if self.metro.running else self.metro.start()

    # ---- metronome output device (#287) ----
    def _metro_card_label(self):
        """Friendly name of the metronome's output (BT sink, ALSA card, or 'Default')."""
        return output_label(self.metro.card, self.metro.bt_sink, self.bt_names, "Default")

    def _open_metro_audio(self):
        # ALSA cards (incl. onboard jack) + connected BT sinks (#287). Exactly one active.
        self.stack.append(MenuScreen("Metronome output", output_picker_items(
            "Default (system)", lambda: self.metro.card, lambda: self.metro.bt_sink,
            lambda: self._choose_metro_card(""), self._choose_metro_card, self._choose_metro_bt)))

    def _choose_metro_card(self, name):
        self.metro.card = name
        self.metro.bt_sink = ""                      # ALSA card → drop any BT sink (#287)
        self._save_metro()
        self.metro.test_click()                     # immediate feedback so the device is testable
        self.toast("Test click played")

    def _choose_metro_bt(self, mac, label=""):
        self.metro.bt_sink = mac
        self.metro.card = ""                         # BT sink → drop any ALSA card (#287)
        self._remember_bt_name(mac, label)
        self._save_metro()
        self.metro.test_click()
        self.toast("Test click played")
