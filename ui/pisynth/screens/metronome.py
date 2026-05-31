"""Metronome screens (#287/#655/#668), split out of the controller (#308).

Mixin for app.App: Start/Stop, classic tempo presets, BPM/beats/volume steppers and a
Home-pulse toggle. The click always plays through the piano fluidsynth (same speakers) —
there is no separate-output device (#668, david: dropped). Cross-feature helpers (toast,
_update_settings) resolve via the MRO.
"""
from ..ui.menu import Item, MenuScreen

# Classic Italian tempo markings → a representative BPM (#668, david). The BPM stepper
# stays for fine control; this is a quick "set a musical tempo" picker.
TEMPO_PRESETS = [("Largo", 50), ("Adagio", 66), ("Andante", 92), ("Moderato", 114),
                 ("Allegro", 138), ("Vivace", 166), ("Presto", 184)]


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
            Item("Home pulse", on_select=self._metro_toggle_home_pulse,   # beat indicator on Home (#668)
                 value=(lambda: "on" if self.metro.home_pulse else "off")),
        ])

    def _save_metro(self):
        """Persist all metronome prefs together so writing one never drops another (#287)."""
        self._update_settings(metro={"bpm": self.metro.bpm, "beats": self.metro.beats,
                                     "vol": self.metro.vol, "home_pulse": self.metro.home_pulse})

    def _metro_bpm(self, delta):
        self.metro.bpm = max(40, min(240, self.metro.bpm + 5 * delta))
        self._save_metro()
        self.metro.reload()                          # regenerate the SMF at the new tempo (#655)

    # ---- classic tempo presets (#668) ----
    def _metro_nearest_preset(self):
        """The (name, bpm) classic preset closest to the current BPM. Tempo markings are
        ranges, so a custom BPM (e.g. 80) still maps to a marking (Andante) (#668, david)."""
        return min(TEMPO_PRESETS, key=lambda nb: abs(nb[1] - self.metro.bpm))

    def _metro_tempo_label(self):
        """The tempo marking for the current BPM (nearest preset) — always a name, never a
        bare number (#668, david: the Tempo value showed '80' with no name)."""
        return self._metro_nearest_preset()[0]

    def _open_metro_tempo(self):
        # Mark the preset nearest the current BPM so there's always a "you are here" (#668).
        items = [Item(f"{name}  ({bpm})", on_select=(lambda b=bpm: self._choose_metro_tempo(b)),
                      marker=(lambda b=bpm: self._metro_nearest_preset()[1] == b)) for name, bpm in TEMPO_PRESETS]
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
            if not self.metro.running and self.metro.err:    # click failed to start (#655)
                self.toast(self.metro.err, secs=4)
