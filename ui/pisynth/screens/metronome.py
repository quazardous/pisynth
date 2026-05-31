"""Metronome screens (#287), split out of the controller (#308).

Mixin for app.App: BPM/beats steppers + the output picker (ALSA cards or a BT sink,
routed through the injected `metro.play_fn`). Cross-feature helpers (toast,
_update_settings) resolve via the MRO.
"""
from ..core.soundfonts import list_soundfont_files, sf_key
from ..ui.menu import Item, MenuScreen
from .devices import output_label, output_picker_items

# Classic Italian tempo markings → a representative BPM (#668, david). The BPM stepper
# stays for fine control; this is a quick "set a musical tempo" picker.
TEMPO_PRESETS = [("Largo", 50), ("Adagio", 66), ("Andante", 92), ("Moderato", 114),
                 ("Allegro", 138), ("Vivace", 166), ("Presto", 184)]


class MetronomeMixin:
    # ---- metronome (#287) ----
    def _metronome_menu(self):
        items = [
            Item("Start / Stop", on_select=self._metro_toggle,    # first — the primary action (david)
                 value=(lambda: "running" if self.metro.running else "stopped")),
            Item("Tempo", on_select=self._open_metro_tempo, submenu=True,    # 2nd, after Start/Stop (david)
                 value=self._metro_tempo_label),     # classic tempo presets → BPM
            Item("BPM", on_adjust=self._metro_bpm, value=(lambda: str(self.metro.bpm))),
            Item("Beats/bar", on_adjust=self._metro_beats, value=(lambda: str(self.metro.beats))),
            Item("Volume", on_adjust=self._metro_vol, value=(lambda: f"{self.metro.vol}%")),
            Item("Mode", on_adjust=self._metro_mode, value=self._metro_mode_label),
        ]
        if self.metro.mode == "fluid":               # click via the synth (#655) → pick its soundfont
            items.append(Item("Click sound", on_select=self._open_metro_click_sf, submenu=True,
                              value=(lambda: self.metro.click_sf or "default")))
        else:                                        # separate output (#648/#287) → pick its card/sink
            items.append(Item("Output", on_select=self._open_metro_audio, submenu=True,
                              value=self._metro_card_label))
        return MenuScreen("Metronome", items)

    def _save_metro(self):
        """Persist all metronome prefs together so writing one never drops another (#287)."""
        self._update_settings(metro={"bpm": self.metro.bpm, "beats": self.metro.beats,
                                     "vol": self.metro.vol, "mode": self.metro.mode,
                                     "click_sf": self.metro.click_sf, "card": self.metro.card,
                                     "bt_sink": self.metro.bt_sink})

    def _metro_bpm(self, delta):
        self.metro.bpm = max(40, min(240, self.metro.bpm + 5 * delta))
        self._save_metro()
        self.metro.reload()                          # fluid mode: regenerate the SMF at the new tempo (#655)

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
        self.metro.reload()                          # fluid mode picks up the new tempo (#655)
        self.toast(f"{self._metro_tempo_label()} = {bpm} BPM")

    def _metro_beats(self, delta):
        self.metro.beats = max(1, min(8, self.metro.beats + delta))
        self._save_metro()
        self.metro.reload()                          # fluid mode: regenerate the SMF (#655)

    def _metro_vol(self, delta):
        self.metro.set_volume(self.metro.vol + 5 * delta)   # live: rebuilt for the next bar (#648)
        self._save_metro()

    # ---- output mode: separate card (#648) vs via the synth (#655) ----
    def _metro_mode_label(self):
        return "Piano" if self.metro.mode == "fluid" else "Separate"

    def _metro_mode(self, delta):
        self.metro.stop()                            # mode change → stop; restart in the new mode
        self.metro.mode = "fluid" if self.metro.mode == "separate" else "separate"
        self._save_metro()
        if self.stack and self.stack[-1].title == "Metronome":   # rebuild: Output ↔ Click sound swaps
            m = self._metronome_menu()
            m.idx = 5                                # keep the cursor on the Mode row (Start/Stop, BPM, Tempo before it)
            self.stack[-1] = m

    def _open_metro_click_sf(self):
        """Pick the soundfont that provides the click in fluid mode (#655)."""
        items = [Item("Default", on_select=(lambda: self._choose_metro_click_sf("")),
                      marker=(lambda: not self.metro.click_sf))]
        for path in list_soundfont_files():
            name = sf_key(path)
            items.append(Item(name, on_select=(lambda n=name: self._choose_metro_click_sf(n)),
                              marker=(lambda n=name: self.metro.click_sf == n)))
        self.stack.append(MenuScreen("Click sound", items))

    def _choose_metro_click_sf(self, name):
        self.metro.click_sf = name
        self._save_metro()
        if self.metro.running and self.metro.mode == "fluid":
            self.metro.stop()                        # font changed → restart to reload it
        self.toast("Click sound: " + (name or "default"))

    def _metro_toggle(self):
        if self.metro.running:
            self.metro.stop()
        else:
            self.metro.start()
            if not self.metro.running and self.metro.err:    # output failed to open (#648)
                self.toast(self.metro.err, secs=4)

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
        if name and name == self.soundcard:          # the synth holds its card exclusively (direct
            self.toast("⚠ synth's card — no sound, pick another output", secs=4)  # ALSA) → busy (#648)
            return
        self.metro.test_click()                     # immediate feedback so the device is testable
        self.toast("Test click played")

    def _choose_metro_bt(self, mac, label=""):
        self.metro.bt_sink = mac
        self.metro.card = ""                         # BT sink → drop any ALSA card (#287)
        self._remember_bt_name(mac, label)
        self._save_metro()
        self.metro.test_click()
        self.toast("Test click played")
